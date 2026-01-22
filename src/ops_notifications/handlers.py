"""Custom Django logging handler for Slack error notifications with intelligent grouping."""

import hashlib
import logging
import traceback
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache

from ops_notifications.client import slack_client

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_TRACEBACK_MAX_LENGTH = 2000
DEFAULT_MESSAGE_MAX_LENGTH = 500


class SlackErrorHandler(logging.Handler):
    """
    Custom logging handler that sends errors to Slack with intelligent grouping.

    Groups errors by error signature (hash of error type + traceback) and uses
    threads to avoid spam. First occurrence creates a new message, subsequent
    occurrences reply in thread with updated count.

    Configuration options (Django settings):
        SLACK_FULL_TRACEBACK_ENABLED: Enable full stack trace feature (default: False)
        SLACK_FULL_TRACEBACK_IN_THREAD: Send full traceback as a thread reply (default: True)
        SLACK_FULL_TRACEBACK_AS_FILE: Upload traceback as a file attachment (default: False)
    """

    def __init__(self, level=logging.ERROR):
        """Initialize the handler."""
        super().__init__(level)
        self.cache_timeout = 3600  # 1 hour

    def _get_full_traceback_config(self) -> dict:
        """Get full traceback configuration from Django settings."""
        return {
            "enabled": getattr(settings, "SLACK_FULL_TRACEBACK_ENABLED", False),
            "in_thread": getattr(settings, "SLACK_FULL_TRACEBACK_IN_THREAD", True),
            "as_file": getattr(settings, "SLACK_FULL_TRACEBACK_AS_FILE", False),
        }

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and send to Slack if appropriate."""
        if not slack_client.enabled:
            return

        try:
            # Create error signature for grouping
            error_signature = self._create_error_signature(record)
            cache_key = f"slack_error:{error_signature}"

            # Get existing error data from cache
            error_data = cache.get(cache_key)

            if error_data is None:
                # First occurrence - create new message
                self._send_new_error(record, error_signature, cache_key)
            else:
                # Subsequent occurrence - update thread
                self._update_error_thread(record, error_data, cache_key)

        except Exception:
            # Don't let logging errors break the application
            logger.exception("Failed to send error to Slack")

    def _create_error_signature(self, record: logging.LogRecord) -> str:
        """Create a unique signature for this error type."""
        # Use error type and traceback to create signature
        error_type = record.exc_info[0].__name__ if record.exc_info else record.levelname
        tb_lines = traceback.format_exception(*record.exc_info) if record.exc_info else [record.getMessage()]

        # Get just the code locations (ignore line numbers for grouping)
        signature_parts = [error_type]
        for line in tb_lines:
            if "File" in line:
                # Extract file path without line number
                parts = line.split(",")
                if parts:
                    signature_parts.append(parts[0])

        signature_str = "|".join(signature_parts)
        return hashlib.sha256(signature_str.encode()).hexdigest()[:16]

    def _send_new_error(self, record: logging.LogRecord, error_signature: str, cache_key: str) -> None:  # noqa: ARG002
        """Send a new error message to Slack."""
        config = self._get_full_traceback_config()
        include_traceback_in_main = not (config["enabled"] and config["in_thread"])

        blocks = self._format_error_blocks(record, count=1, include_traceback=include_traceback_in_main)

        response = slack_client.send_alert(
            text=f"Error: {record.getMessage()[:100]}",
            blocks=blocks,
        )

        if response and "ts" in response:
            thread_ts = response["ts"]

            # Store thread timestamp and count in cache
            error_data = {
                "thread_ts": thread_ts,
                "count": 1,
                "first_seen": datetime.now(UTC).isoformat(),
                "last_seen": datetime.now(UTC).isoformat(),
            }
            cache.set(cache_key, error_data, self.cache_timeout)

            # Send full traceback in thread if configured
            if config["enabled"] and record.exc_info:
                self._send_full_traceback(record, thread_ts, config)

    def _update_error_thread(self, record: logging.LogRecord, error_data: dict, cache_key: str) -> None:  # noqa: ARG002
        """Update existing error thread with new occurrence."""
        # Create new dictionary to avoid race conditions with cache mutations
        count = error_data["count"] + 1
        last_seen = datetime.now(UTC).isoformat()

        updated_error_data = {
            "thread_ts": error_data["thread_ts"],
            "count": count,
            "first_seen": error_data["first_seen"],
            "last_seen": last_seen,
        }

        # Send update to thread every 1, 5, 10, 25, 50, 100, etc.
        should_update = (
            count in {1, 5, 10, 25, 50, 100, 250, 500, 1000} or count % 1000 == 0  # Every 1000 after that
        )

        if should_update:
            blocks = [
                slack_client.format_section(
                    f"*Error occurred {count} times*\n"
                    f"Last seen: {datetime.fromisoformat(last_seen).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                ),
            ]

            slack_client.send_alert(
                text=f"Error count: {count}",
                blocks=blocks,
                thread_ts=updated_error_data["thread_ts"],
            )

        # Update cache with new dictionary
        cache.set(cache_key, updated_error_data, self.cache_timeout)

    def _send_full_traceback(self, record: logging.LogRecord, thread_ts: str, config: dict) -> None:
        """Send full traceback to thread, optionally as a file attachment.

        Args:
            record: The log record containing exception info.
            thread_ts: The thread timestamp to reply to.
            config: Configuration dict with 'as_file' and other options.
        """
        if not record.exc_info:
            return

        full_traceback = "".join(traceback.format_exception(*record.exc_info))

        if config["as_file"]:
            # Upload as file attachment
            error_type = record.exc_info[0].__name__ if record.exc_info[0] else "Error"
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"traceback_{error_type}_{timestamp}.txt"

            slack_client.upload_file(
                content=full_traceback,
                filename=filename,
                title=f"Full Traceback - {error_type}",
                thread_ts=thread_ts,
                initial_comment="Full stack trace attached below:",
            )
        else:
            # Send as threaded message (may be split if very long)
            self._send_traceback_as_message(full_traceback, thread_ts)

    def _send_traceback_as_message(self, traceback_text: str, thread_ts: str) -> None:
        """Send traceback as a threaded message, splitting if necessary.

        Slack has a 3000 character limit per text block. We split into chunks
        if needed to ensure the full traceback is posted.
        """
        max_chunk_size = 2900  # Leave room for formatting

        if len(traceback_text) <= max_chunk_size:
            blocks = [
                slack_client.format_section("*Full Stack Trace:*"),
                slack_client.format_section(f"```{traceback_text}```"),
            ]
            slack_client.send_alert(
                text="Full stack trace",
                blocks=blocks,
                thread_ts=thread_ts,
            )
        else:
            # Split into multiple messages
            chunks = []
            remaining = traceback_text
            while remaining:
                if len(remaining) <= max_chunk_size:
                    chunks.append(remaining)
                    break
                # Find a good break point (newline)
                break_point = remaining.rfind("\n", 0, max_chunk_size)
                if break_point == -1:
                    break_point = max_chunk_size
                chunks.append(remaining[:break_point])
                remaining = remaining[break_point:].lstrip("\n")

            for i, chunk in enumerate(chunks):
                part_label = f" (part {i + 1}/{len(chunks)})" if len(chunks) > 1 else ""
                header = "*Full Stack Trace:*" if i == 0 else f"*Continued{part_label}:*"
                blocks = [
                    slack_client.format_section(header),
                    slack_client.format_section(f"```{chunk}```"),
                ]
                slack_client.send_alert(
                    text=f"Full stack trace{part_label}",
                    blocks=blocks,
                    thread_ts=thread_ts,
                )

    def _format_error_blocks(self, record: logging.LogRecord, count: int, include_traceback: bool = True) -> list:  # noqa: FBT001, FBT002
        """Format error information as Slack blocks.

        Args:
            record: The log record to format.
            count: The occurrence count.
            include_traceback: Whether to include the traceback in the blocks.
                              When False, traceback is omitted (sent separately in thread).
        """
        blocks = [
            slack_client.format_header("Application Error"),
        ]

        # Error details
        error_text = f"*Level:* {record.levelname}\n*Logger:* {record.name}\n*Count:* {count}\n"

        if record.pathname:
            error_text += f"*Location:* `{record.pathname}:{record.lineno}`\n"

        if record.funcName:
            error_text += f"*Function:* `{record.funcName}`\n"

        blocks.append(slack_client.format_section(error_text))

        # Message
        message = record.getMessage()
        if message:
            truncated_msg = message[:DEFAULT_MESSAGE_MAX_LENGTH]
            if len(message) > DEFAULT_MESSAGE_MAX_LENGTH:
                truncated_msg += "..."
            blocks.append(slack_client.format_section(f"*Message:*\n```{truncated_msg}```"))

        # Traceback (if available and requested)
        if include_traceback and record.exc_info:
            tb_text = "".join(traceback.format_exception(*record.exc_info))
            # Truncate if too long
            if len(tb_text) > DEFAULT_TRACEBACK_MAX_LENGTH:
                tb_text = tb_text[:DEFAULT_TRACEBACK_MAX_LENGTH] + "\n... (truncated, see thread for full trace)"
            blocks.append(slack_client.format_section(f"*Traceback:*\n```{tb_text}```"))
        elif not include_traceback and record.exc_info:
            # Add note that full traceback is in thread
            blocks.append(slack_client.format_context(["Full stack trace posted in thread below"]))

        return blocks

"""Custom Django logging handler for Slack error notifications with intelligent grouping."""

import hashlib
import logging
import traceback
from datetime import UTC, datetime

from django.core.cache import cache

from ops_notifications.client import slack_client

logger = logging.getLogger(__name__)


class SlackErrorHandler(logging.Handler):
    """
    Custom logging handler that sends errors to Slack with intelligent grouping.

    Groups errors by error signature (hash of error type + traceback) and uses
    threads to avoid spam. First occurrence creates a new message, subsequent
    occurrences reply in thread with updated count.
    """

    def __init__(self, level=logging.ERROR):
        """Initialize the handler."""
        super().__init__(level)
        self.cache_timeout = 3600  # 1 hour

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

    def _send_new_error(self, record: logging.LogRecord, error_signature: str, cache_key: str) -> None:
        """Send a new error message to Slack."""
        blocks = self._format_error_blocks(record, count=1)

        response = slack_client.send_alert(
            text=f"Error: {record.getMessage()[:100]}",
            blocks=blocks,
        )

        if response and "ts" in response:
            # Store thread timestamp and count in cache
            error_data = {
                "thread_ts": response["ts"],
                "count": 1,
                "first_seen": datetime.now(UTC).isoformat(),
                "last_seen": datetime.now(UTC).isoformat(),
            }
            cache.set(cache_key, error_data, self.cache_timeout)

    def _update_error_thread(self, record: logging.LogRecord, error_data: dict, cache_key: str) -> None:
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

    def _format_error_blocks(self, record: logging.LogRecord, count: int) -> list:
        """Format error information as Slack blocks."""
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
            blocks.append(slack_client.format_section(f"*Message:*\n```{message[:500]}```"))

        # Traceback (if available)
        if record.exc_info:
            tb_text = "".join(traceback.format_exception(*record.exc_info))
            # Truncate if too long
            if len(tb_text) > 2000:  # noqa: PLR2004
                tb_text = tb_text[:2000] + "\n... (truncated)"
            blocks.append(slack_client.format_section(f"*Traceback:*\n```{tb_text}```"))

        return blocks

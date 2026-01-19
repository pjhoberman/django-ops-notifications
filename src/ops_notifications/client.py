"""Slack client wrapper for sending notifications."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SlackClient:
    """Wrapper for Slack SDK with error handling and formatting helpers.

    Note: This uses lazy initialization to avoid accessing Django settings at import time.
    The client is only initialized when first accessed.
    """

    def __init__(self):
        """Initialize Slack client with lazy loading."""
        self._initialized = False
        self._enabled = False
        self._alerts_channel = ""
        self._reports_channel = ""
        self._client = None

    def _ensure_initialized(self) -> None:
        """Initialize the client if not already done."""
        if self._initialized:
            return

        from django.conf import settings  # noqa: PLC0415

        self._enabled = getattr(settings, "SLACK_ENABLED", False)
        self._alerts_channel = getattr(settings, "SLACK_ALERTS_CHANNEL", "")
        self._reports_channel = getattr(settings, "SLACK_REPORTS_CHANNEL", "")

        if self._enabled:
            try:
                from slack_sdk import WebClient  # noqa: PLC0415

                self._client = WebClient(token=settings.SLACK_BOT_TOKEN)
            except ImportError:
                logger.exception("slack-sdk not installed, disabling Slack notifications")
                self._enabled = False
            except Exception:
                logger.exception("Failed to initialize Slack client")
                self._enabled = False

        self._initialized = True

    @property
    def enabled(self) -> bool:
        """Return whether Slack is enabled."""
        self._ensure_initialized()
        return self._enabled

    @property
    def alerts_channel(self) -> str:
        """Return the alerts channel."""
        self._ensure_initialized()
        return self._alerts_channel

    @property
    def reports_channel(self) -> str:
        """Return the reports channel."""
        self._ensure_initialized()
        return self._reports_channel

    @property
    def client(self):
        """Return the Slack WebClient."""
        self._ensure_initialized()
        return self._client

    def _send_message(
        self,
        channel: str,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a message to Slack."""
        # Check SLACK_ENABLED dynamically at runtime via property
        # This ensures test settings are respected
        from django.conf import settings  # noqa: PLC0415

        slack_enabled = getattr(settings, "SLACK_ENABLED", False)
        if not slack_enabled or not self.client:
            logger.debug("Slack disabled, skipping message: %s", text or "blocks message")
            return None

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts,
            )
            return response.data if response else None
        except Exception:
            logger.exception("Failed to send Slack message to channel %s", channel)
            return None

    def send_alert(
        self,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any] | None:
        """Send an alert to the alerts channel."""
        return self._send_message(self.alerts_channel, text=text, blocks=blocks, thread_ts=thread_ts)

    def send_report(
        self,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Send a report to the reports channel."""
        return self._send_message(self.reports_channel, text=text, blocks=blocks)

    @staticmethod
    def format_header(text: str) -> dict[str, Any]:
        """Format a header block."""
        return {"type": "header", "text": {"type": "plain_text", "text": text}}

    @staticmethod
    def format_section(text: str, markdown: bool = True) -> dict[str, Any]:  # noqa: FBT001, FBT002
        """Format a section block."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn" if markdown else "plain_text",
                "text": text,
            },
        }

    @staticmethod
    def format_divider() -> dict[str, Any]:
        """Format a divider block."""
        return {"type": "divider"}

    @staticmethod
    def format_context(elements: list[str]) -> dict[str, Any]:
        """Format a context block with mrkdwn elements."""
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": element} for element in elements],
        }


# Singleton instance
slack_client = SlackClient()

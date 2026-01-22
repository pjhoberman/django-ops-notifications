"""Tests for SlackClient."""

from unittest.mock import MagicMock, patch

import pytest

from ops_notifications.client import SlackClient


class TestSlackClient:
    """Tests for SlackClient class."""

    def test_client_disabled_by_default(self, settings):
        """Client should be disabled when SLACK_ENABLED is False."""
        settings.SLACK_ENABLED = False
        client = SlackClient()
        assert not client.enabled
        assert client.client is None

    def test_client_reads_channel_settings(self, settings):
        """Client should read channel settings from Django settings."""
        settings.SLACK_ALERTS_CHANNEL = "my-alerts"
        settings.SLACK_REPORTS_CHANNEL = "my-reports"
        client = SlackClient()
        assert client.alerts_channel == "my-alerts"
        assert client.reports_channel == "my-reports"

    def test_send_alert_returns_none_when_disabled(self, settings):
        """send_alert should return None when Slack is disabled."""
        settings.SLACK_ENABLED = False
        client = SlackClient()
        result = client.send_alert(text="Test message")
        assert result is None

    def test_send_report_returns_none_when_disabled(self, settings):
        """send_report should return None when Slack is disabled."""
        settings.SLACK_ENABLED = False
        client = SlackClient()
        result = client.send_report(text="Test report")
        assert result is None

    @patch("ops_notifications.client.SlackClient._send_message")
    def test_send_alert_calls_send_message(self, mock_send, settings):
        """send_alert should call _send_message with alerts channel."""
        settings.SLACK_ALERTS_CHANNEL = "alerts"
        client = SlackClient()
        client.send_alert(text="Test", blocks=[{"type": "section"}])
        mock_send.assert_called_once_with(
            "alerts",
            text="Test",
            blocks=[{"type": "section"}],
            thread_ts=None,
        )

    @patch("ops_notifications.client.SlackClient._send_message")
    def test_send_report_calls_send_message(self, mock_send, settings):
        """send_report should call _send_message with reports channel."""
        settings.SLACK_REPORTS_CHANNEL = "reports"
        client = SlackClient()
        client.send_report(text="Test report")
        mock_send.assert_called_once_with("reports", text="Test report", blocks=None)


class TestSlackClientFormatters:
    """Tests for SlackClient formatting methods."""

    def test_format_header(self):
        """format_header should create proper header block."""
        result = SlackClient.format_header("Test Header")
        assert result == {
            "type": "header",
            "text": {"type": "plain_text", "text": "Test Header"},
        }

    def test_format_section_markdown(self):
        """format_section should create mrkdwn section by default."""
        result = SlackClient.format_section("*Bold* text")
        assert result == {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Bold* text"},
        }

    def test_format_section_plain_text(self):
        """format_section should support plain text."""
        result = SlackClient.format_section("Plain text", markdown=False)
        assert result == {
            "type": "section",
            "text": {"type": "plain_text", "text": "Plain text"},
        }

    def test_format_divider(self):
        """format_divider should create divider block."""
        result = SlackClient.format_divider()
        assert result == {"type": "divider"}

    def test_format_context(self):
        """format_context should create context block with mrkdwn elements."""
        result = SlackClient.format_context(["Element 1", "Element 2"])
        assert result == {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Element 1"},
                {"type": "mrkdwn", "text": "Element 2"},
            ],
        }


class TestSlackClientFileUpload:
    """Tests for SlackClient file upload functionality."""

    def test_upload_file_returns_none_when_disabled(self, settings):
        """upload_file should return None when Slack is disabled."""
        settings.SLACK_ENABLED = False
        client = SlackClient()
        result = client.upload_file(content="test content", filename="test.txt")
        assert result is None

    def test_upload_file_calls_slack_api(self, settings):
        """upload_file should call Slack files_upload_v2 API."""
        settings.SLACK_ENABLED = True
        settings.SLACK_BOT_TOKEN = "test-token"
        settings.SLACK_ALERTS_CHANNEL = "alerts"

        client = SlackClient()
        mock_slack_client = MagicMock()
        mock_slack_client.files_upload_v2.return_value = MagicMock(data={"ok": True, "file": {"id": "F123"}})

        with patch.object(client, "_client", mock_slack_client):
            with patch.object(client, "_initialized", True):
                with patch.object(client, "_enabled", True):
                    with patch.object(client, "_alerts_channel", "alerts"):
                        client.upload_file(
                            content="traceback content",
                            filename="traceback.txt",
                            title="Error Traceback",
                            thread_ts="1234.5678",
                            initial_comment="Full trace attached",
                        )

        mock_slack_client.files_upload_v2.assert_called_once_with(
            channel="alerts",
            content="traceback content",
            filename="traceback.txt",
            title="Error Traceback",
            thread_ts="1234.5678",
            initial_comment="Full trace attached",
        )

    def test_upload_file_uses_alerts_channel_by_default(self, settings):
        """upload_file should use alerts channel when no channel specified."""
        settings.SLACK_ENABLED = True
        settings.SLACK_BOT_TOKEN = "test-token"
        settings.SLACK_ALERTS_CHANNEL = "default-alerts"

        client = SlackClient()
        mock_slack_client = MagicMock()
        mock_slack_client.files_upload_v2.return_value = MagicMock(data={"ok": True})

        with patch.object(client, "_client", mock_slack_client):
            with patch.object(client, "_initialized", True):
                with patch.object(client, "_enabled", True):
                    with patch.object(client, "_alerts_channel", "default-alerts"):
                        client.upload_file(content="test", filename="test.txt")

        call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
        assert call_kwargs["channel"] == "default-alerts"

    def test_upload_file_uses_custom_channel(self, settings):
        """upload_file should use specified channel when provided."""
        settings.SLACK_ENABLED = True
        settings.SLACK_BOT_TOKEN = "test-token"
        settings.SLACK_ALERTS_CHANNEL = "default-alerts"

        client = SlackClient()
        mock_slack_client = MagicMock()
        mock_slack_client.files_upload_v2.return_value = MagicMock(data={"ok": True})

        with patch.object(client, "_client", mock_slack_client):
            with patch.object(client, "_initialized", True):
                with patch.object(client, "_enabled", True):
                    client.upload_file(content="test", filename="test.txt", channel="custom-channel")

        call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
        assert call_kwargs["channel"] == "custom-channel"

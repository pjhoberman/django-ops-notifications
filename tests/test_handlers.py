"""Tests for SlackErrorHandler."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from ops_notifications.handlers import SlackErrorHandler


class TestSlackErrorHandler:
    """Tests for SlackErrorHandler."""

    def test_handler_does_nothing_when_disabled(self, settings):
        """Handler should not send anything when Slack is disabled."""
        settings.SLACK_ENABLED = False

        with patch("ops_notifications.handlers.slack_client") as mock_client:
            mock_client.enabled = False
            handler = SlackErrorHandler()

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/test.py",
                lineno=1,
                msg="Test error",
                args=(),
                exc_info=None,
            )

            handler.emit(record)
            mock_client.send_alert.assert_not_called()

    @patch("ops_notifications.handlers.cache")
    @patch("ops_notifications.handlers.slack_client")
    def test_handler_sends_new_error(self, mock_client, mock_cache, settings):
        """Handler should send new error to Slack."""
        mock_client.enabled = True
        mock_cache.get.return_value = None  # No existing error
        mock_client.send_alert.return_value = {"ts": "1234.5678"}

        handler = SlackErrorHandler()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Something went wrong",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        mock_client.send_alert.assert_called_once()
        mock_cache.set.assert_called_once()

    @patch("ops_notifications.handlers.cache")
    @patch("ops_notifications.handlers.slack_client")
    def test_handler_updates_existing_error_thread(self, mock_client, mock_cache, settings):
        """Handler should update thread for repeated errors."""
        mock_client.enabled = True
        mock_cache.get.return_value = {
            "thread_ts": "1234.5678",
            "count": 4,  # Will become 5, which triggers update
            "first_seen": "2024-01-01T00:00:00+00:00",
            "last_seen": "2024-01-01T00:01:00+00:00",
        }

        handler = SlackErrorHandler()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/test.py",
            lineno=1,
            msg="Repeated error",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        # Should send thread reply at count 5
        mock_client.send_alert.assert_called_once()
        call_kwargs = mock_client.send_alert.call_args.kwargs
        assert call_kwargs["thread_ts"] == "1234.5678"

    def test_error_signature_consistency(self):
        """Same error should produce same signature."""
        handler = SlackErrorHandler()

        record1 = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        record2 = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        sig1 = handler._create_error_signature(record1)
        sig2 = handler._create_error_signature(record2)

        assert sig1 == sig2

    def test_different_errors_have_different_signatures(self):
        """Different errors should produce different signatures."""
        handler = SlackErrorHandler()

        record1 = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Error one",
            args=(),
            exc_info=None,
        )

        record2 = logging.LogRecord(
            name="test",
            level=logging.WARNING,  # Different level
            pathname="/app/other.py",  # Different file
            lineno=100,
            msg="Error two",
            args=(),
            exc_info=None,
        )

        sig1 = handler._create_error_signature(record1)
        sig2 = handler._create_error_signature(record2)

        assert sig1 != sig2


class TestSlackErrorHandlerFullTraceback:
    """Tests for full traceback configuration."""

    def test_get_full_traceback_config_defaults(self, settings):
        """Config should return defaults when settings are not defined."""
        # Ensure settings don't have the full traceback options
        if hasattr(settings, "SLACK_FULL_TRACEBACK_ENABLED"):
            delattr(settings, "SLACK_FULL_TRACEBACK_ENABLED")
        if hasattr(settings, "SLACK_FULL_TRACEBACK_IN_THREAD"):
            delattr(settings, "SLACK_FULL_TRACEBACK_IN_THREAD")
        if hasattr(settings, "SLACK_FULL_TRACEBACK_AS_FILE"):
            delattr(settings, "SLACK_FULL_TRACEBACK_AS_FILE")

        handler = SlackErrorHandler()
        config = handler._get_full_traceback_config()

        assert config["enabled"] is False
        assert config["in_thread"] is True
        assert config["as_file"] is False

    def test_get_full_traceback_config_from_settings(self, settings):
        """Config should read from Django settings."""
        settings.SLACK_FULL_TRACEBACK_ENABLED = True
        settings.SLACK_FULL_TRACEBACK_IN_THREAD = True
        settings.SLACK_FULL_TRACEBACK_AS_FILE = True

        handler = SlackErrorHandler()
        config = handler._get_full_traceback_config()

        assert config["enabled"] is True
        assert config["in_thread"] is True
        assert config["as_file"] is True

    @patch("ops_notifications.handlers.cache")
    @patch("ops_notifications.handlers.slack_client")
    def test_full_traceback_in_thread_as_message(self, mock_client, mock_cache, settings):
        """Full traceback should be sent as thread message when enabled."""
        settings.SLACK_FULL_TRACEBACK_ENABLED = True
        settings.SLACK_FULL_TRACEBACK_IN_THREAD = True
        settings.SLACK_FULL_TRACEBACK_AS_FILE = False

        mock_client.enabled = True
        mock_cache.get.return_value = None
        mock_client.send_alert.return_value = {"ts": "1234.5678"}

        handler = SlackErrorHandler()

        # Create a record with exception info
        try:
            raise ValueError("Test error for traceback")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )

        handler.emit(record)

        # Should be called twice: main message + thread with full traceback
        assert mock_client.send_alert.call_count == 2

        # Second call should be to thread
        second_call = mock_client.send_alert.call_args_list[1]
        assert second_call.kwargs["thread_ts"] == "1234.5678"

    @patch("ops_notifications.handlers.cache")
    @patch("ops_notifications.handlers.slack_client")
    def test_full_traceback_as_file(self, mock_client, mock_cache, settings):
        """Full traceback should be uploaded as file when configured."""
        settings.SLACK_FULL_TRACEBACK_ENABLED = True
        settings.SLACK_FULL_TRACEBACK_IN_THREAD = True
        settings.SLACK_FULL_TRACEBACK_AS_FILE = True

        mock_client.enabled = True
        mock_cache.get.return_value = None
        mock_client.send_alert.return_value = {"ts": "1234.5678"}
        mock_client.upload_file.return_value = {"ok": True}

        handler = SlackErrorHandler()

        # Create a record with exception info
        try:
            raise ValueError("Test error for file upload")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )

        handler.emit(record)

        # Main message should be sent
        mock_client.send_alert.assert_called_once()

        # File should be uploaded to thread
        mock_client.upload_file.assert_called_once()
        upload_call = mock_client.upload_file.call_args
        assert upload_call.kwargs["thread_ts"] == "1234.5678"
        assert "ValueError" in upload_call.kwargs["filename"]
        assert "traceback" in upload_call.kwargs["filename"].lower()

    @patch("ops_notifications.handlers.cache")
    @patch("ops_notifications.handlers.slack_client")
    def test_disabled_full_traceback_uses_truncated(self, mock_client, mock_cache, settings):
        """When disabled, should use traditional truncated traceback in main message."""
        settings.SLACK_FULL_TRACEBACK_ENABLED = False

        mock_client.enabled = True
        mock_cache.get.return_value = None
        mock_client.send_alert.return_value = {"ts": "1234.5678"}

        handler = SlackErrorHandler()

        # Create a record with exception info
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )

        handler.emit(record)

        # Should only be called once (main message with truncated traceback)
        mock_client.send_alert.assert_called_once()
        mock_client.upload_file.assert_not_called()

    def test_format_error_blocks_without_traceback(self, settings):
        """Blocks should exclude traceback when include_traceback=False."""
        handler = SlackErrorHandler()

        # Create a record with exception info
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )

        blocks = handler._format_error_blocks(record, count=1, include_traceback=False)

        # Should have context block about thread instead of traceback
        block_types = [b.get("type") for b in blocks]
        assert "context" in block_types

        # Should not contain "Traceback:" in any section
        for block in blocks:
            if block.get("type") == "section":
                text = block.get("text", {}).get("text", "")
                assert "*Traceback:*" not in text

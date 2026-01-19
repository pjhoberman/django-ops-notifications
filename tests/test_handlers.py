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

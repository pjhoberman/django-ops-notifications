"""Tests for alert functions."""

from unittest.mock import patch

import pytest


class TestDeployAlert:
    """Tests for send_deploy_alert function."""

    @patch("ops_notifications.alerts.slack_client")
    def test_deploy_success_alert(self, mock_client, settings):
        """Successful deploy should send appropriate message."""
        from ops_notifications.alerts import send_deploy_alert

        settings.GITHUB_REPO_URL = "https://github.com/test/repo"

        send_deploy_alert(
            success=True,
            environment="production",
            git_sha="abc123def456",
        )

        mock_client.send_alert.assert_called_once()
        call_args = mock_client.send_alert.call_args
        assert "Deploy Successful" in call_args.kwargs["text"]
        assert "production" in call_args.kwargs["text"]

    @patch("ops_notifications.alerts.slack_client")
    def test_deploy_failure_alert(self, mock_client, settings):
        """Failed deploy should include error message."""
        from ops_notifications.alerts import send_deploy_alert
        from ops_notifications.client import SlackClient

        settings.GITHUB_REPO_URL = "https://github.com/test/repo"

        # Use real formatting methods
        mock_client.format_header = SlackClient.format_header
        mock_client.format_section = SlackClient.format_section
        mock_client.format_context = SlackClient.format_context

        send_deploy_alert(
            success=False,
            environment="staging",
            git_sha="abc123def456",
            error_message="Container failed to start",
        )

        mock_client.send_alert.assert_called_once()
        call_args = mock_client.send_alert.call_args
        assert "Deploy Failed" in call_args.kwargs["text"]

        # Check blocks include error message by looking at block structure
        blocks = call_args.kwargs["blocks"]
        section_texts = [
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        ]
        assert any("Container failed to start" in text for text in section_texts)

    @patch("ops_notifications.alerts.slack_client")
    def test_deploy_without_github_url(self, mock_client, settings):
        """Deploy alert should work without GITHUB_REPO_URL."""
        from ops_notifications.alerts import send_deploy_alert

        settings.GITHUB_REPO_URL = ""

        send_deploy_alert(
            success=True,
            environment="production",
            git_sha="abc123",
        )

        mock_client.send_alert.assert_called_once()


class TestBackupAlert:
    """Tests for send_backup_alert function."""

    @patch("ops_notifications.alerts.slack_client")
    def test_backup_success_alert(self, mock_client):
        """Successful backup should send appropriate message."""
        from ops_notifications.alerts import send_backup_alert

        send_backup_alert(success=True, backup_type="daily")

        mock_client.send_alert.assert_called_once()
        call_args = mock_client.send_alert.call_args
        assert "Successful" in call_args.kwargs["text"]
        assert "daily" in call_args.kwargs["text"]

    @patch("ops_notifications.alerts.slack_client")
    def test_backup_failure_alert(self, mock_client):
        """Failed backup should include error message."""
        from ops_notifications.alerts import send_backup_alert
        from ops_notifications.client import SlackClient

        # Use real formatting methods
        mock_client.format_header = SlackClient.format_header
        mock_client.format_section = SlackClient.format_section

        send_backup_alert(
            success=False,
            backup_type="weekly",
            error_message="Storage unavailable",
        )

        mock_client.send_alert.assert_called_once()
        call_args = mock_client.send_alert.call_args
        assert "Failed" in call_args.kwargs["text"]

        # Check blocks include error message by looking at block structure
        blocks = call_args.kwargs["blocks"]
        section_texts = [
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        ]
        assert any("Storage unavailable" in text for text in section_texts)

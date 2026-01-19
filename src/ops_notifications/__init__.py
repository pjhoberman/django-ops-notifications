"""Django Ops Notifications - Reusable Slack notifications for Django projects.

This package provides:
- SlackClient for sending messages to Slack
- SlackErrorHandler for logging errors to Slack with intelligent grouping
- Generic alerts for deployments and backups
- Webhook views for receiving deployment notifications
- Block formatting utilities

Example usage:
    from ops_notifications import slack_client, send_deploy_alert, send_backup_alert

    # Send custom alert
    slack_client.send_alert(
        blocks=[
            slack_client.format_header("Something happened"),
            slack_client.format_section("Details here"),
        ]
    )

    # Built-in alerts
    send_deploy_alert(success=True, environment="production", git_sha="abc123")
    send_backup_alert(success=True, backup_type="daily")
"""

from ops_notifications.alerts import send_backup_alert, send_deploy_alert
from ops_notifications.client import SlackClient, slack_client
from ops_notifications.handlers import SlackErrorHandler
from ops_notifications.utils import (
    context_block,
    divider_block,
    fields_block,
    header_block,
    section_block,
)

__all__ = [
    # Client
    "SlackClient",
    "slack_client",
    # Handler
    "SlackErrorHandler",
    # Alerts
    "send_deploy_alert",
    "send_backup_alert",
    # Block utilities
    "header_block",
    "section_block",
    "divider_block",
    "context_block",
    "fields_block",
]

__version__ = "0.1.0"

# Django app configuration
default_app_config = "ops_notifications.apps.OpsNotificationsConfig"

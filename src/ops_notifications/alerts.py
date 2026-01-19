"""Generic alert functions for Slack notifications."""

import logging
from typing import Any

from django.conf import settings

from ops_notifications.client import slack_client

logger = logging.getLogger(__name__)


def send_deploy_alert(
    success: bool,  # noqa: FBT001
    environment: str,
    git_sha: str,
    error_message: str | None = None,
) -> None:
    """Send alert for deployment success or failure.

    Args:
        success: Whether the deployment was successful.
        environment: The deployment environment (e.g., "production", "staging").
        git_sha: The git commit SHA being deployed.
        error_message: Optional error message if deployment failed.
    """
    try:
        emoji = "+" if success else "x"
        status = "Successful" if success else "Failed"

        blocks: list[dict[str, Any]] = [
            slack_client.format_header(f"{emoji} Deploy {status}"),
            slack_client.format_section(
                f"*Environment:* {environment}\n*Git SHA:* `{git_sha[:8]}`\n*Status:* {status}",
            ),
        ]

        if error_message:
            blocks.append(slack_client.format_section(f"*Error:*\n```{error_message[:500]}```"))

        # Add GitHub commit link if configured
        github_url = getattr(settings, "GITHUB_REPO_URL", "")
        if github_url:
            full_url = f"{github_url}/commit/{git_sha}"
            blocks.append(slack_client.format_context([f"<{full_url}|View Commit>"]))

        slack_client.send_alert(
            text=f"Deploy {status}: {environment} ({git_sha[:8]})",
            blocks=blocks,
        )
    except Exception:
        logger.exception("Failed to send deploy alert")


def send_backup_alert(
    success: bool,  # noqa: FBT001
    backup_type: str,
    error_message: str | None = None,
) -> None:
    """Send alert for database backup success or failure.

    Args:
        success: Whether the backup was successful.
        backup_type: The type of backup (e.g., "daily", "weekly").
        error_message: Optional error message if backup failed.
    """
    try:
        emoji = "+" if success else "x"
        status = "Successful" if success else "Failed"

        blocks: list[dict[str, Any]] = [
            slack_client.format_header(f"{emoji} Database Backup {status}"),
            slack_client.format_section(f"*Type:* {backup_type}\n*Status:* {status}"),
        ]

        if error_message:
            blocks.append(slack_client.format_section(f"*Error:*\n```{error_message[:500]}```"))

        slack_client.send_alert(
            text=f"Database backup {status}: {backup_type}",
            blocks=blocks,
        )
    except Exception:
        logger.exception("Failed to send backup alert")

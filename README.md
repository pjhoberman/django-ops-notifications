# Django Ops Notifications

Reusable Slack notifications for Django projects - deployments, backups, and error logging.

## Features

- **Slack Client**: Simple wrapper for sending messages with block formatting
- **Error Handler**: Logging handler that sends errors to Slack with intelligent grouping
- **Generic Alerts**: Pre-built alerts for deployments and database backups
- **Webhook Views**: Receive deployment notifications from CI/CD pipelines
- **Block Utilities**: Helper functions for building Slack message blocks

## Installation

```bash
# Via git (private repo)
uv add git+https://github.com/pjhoberman/django-ops-notifications.git

# Or via local path
uv add ../django-ops-notifications
```

## Configuration

Add to your Django settings:

```python
# settings.py
INSTALLED_APPS = [
    ...
    "ops_notifications",
]

# Required settings
SLACK_ENABLED = True  # Set to False to disable all Slack notifications
SLACK_BOT_TOKEN = env("SLACK_BOT_TOKEN")
SLACK_ALERTS_CHANNEL = env("SLACK_ALERTS_CHANNEL", default="alerts")
SLACK_REPORTS_CHANNEL = env("SLACK_REPORTS_CHANNEL", default="reports")
WEBHOOK_SECRET = env("WEBHOOK_SECRET")

# Optional - for commit links in deploy alerts
GITHUB_REPO_URL = env("GITHUB_REPO_URL", default="")
```

### Error Logging Handler

Add the Slack error handler to your logging configuration:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
        "slack": {
            "level": "ERROR",
            "class": "ops_notifications.SlackErrorHandler",
        },
    },
    "root": {
        "handlers": ["console", "slack"],
        "level": "INFO",
    },
}
```

### Webhook URL

Add the webhook URL to receive deployment notifications:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("ops/", include("ops_notifications.urls")),
]
```

The deploy webhook will be available at `/ops/webhooks/deploy/`.

## Usage

### Custom Alerts

```python
from ops_notifications import slack_client

slack_client.send_alert(
    blocks=[
        slack_client.format_header("Something happened"),
        slack_client.format_section("*Details:*\n• Item 1\n• Item 2"),
        slack_client.format_divider(),
        slack_client.format_context(["<https://example.com|View details>"]),
    ]
)
```

### Deploy Alerts

```python
from ops_notifications import send_deploy_alert

# Successful deployment
send_deploy_alert(
    success=True,
    environment="production",
    git_sha="abc123def456",
)

# Failed deployment
send_deploy_alert(
    success=False,
    environment="staging",
    git_sha="abc123def456",
    error_message="Container failed to start",
)
```

### Backup Alerts

```python
from ops_notifications import send_backup_alert

# Successful backup
send_backup_alert(success=True, backup_type="daily")

# Failed backup
send_backup_alert(
    success=False,
    backup_type="weekly",
    error_message="Storage unavailable",
)
```

### Block Utilities

Use the standalone block utilities without the client:

```python
from ops_notifications import header_block, section_block, divider_block, context_block

blocks = [
    header_block("Report Title"),
    section_block("*Metric 1:* 100\n*Metric 2:* 200"),
    divider_block(),
    context_block(["Generated at 2024-01-15 10:00 UTC"]),
]
```

## Webhook Integration

Send POST requests to `/ops/webhooks/deploy/` with the `X-Webhook-Secret` header:

```bash
curl -X POST https://your-site.com/ops/webhooks/deploy/ \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-secret" \
  -d '{
    "success": true,
    "environment": "production",
    "git_sha": "abc123def456"
  }'
```

## Project-Specific Extensions

This package provides generic functionality. For project-specific needs, create your own alerts in your project:

```python
# your_project/notifications/alerts.py
from ops_notifications import slack_client

def send_user_signup_alert(user):
    """Send alert when a new user signs up."""
    from django.conf import settings
    from django.urls import reverse

    admin_url = f"{settings.SITE_URL}{reverse('admin:users_user_change', args=[user.pk])}"

    blocks = [
        slack_client.format_header("New User Signup"),
        slack_client.format_section(
            f"*Email:* {user.email}\n"
            f"*Joined:* {user.date_joined.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ),
        slack_client.format_context([f"<{admin_url}|View in Admin>"]),
    ]

    slack_client.send_alert(
        text=f"New user signup: {user.email}",
        blocks=blocks,
    )
```

## License

MIT

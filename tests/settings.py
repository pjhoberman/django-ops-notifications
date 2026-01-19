"""Minimal Django settings for testing."""

SECRET_KEY = "test-secret-key-for-testing-only"  # noqa: S105

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "ops_notifications",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Slack settings for testing (disabled by default)
SLACK_ENABLED = False
SLACK_BOT_TOKEN = "test-token"
SLACK_ALERTS_CHANNEL = "test-alerts"
SLACK_REPORTS_CHANNEL = "test-reports"
WEBHOOK_SECRET = "test-webhook-secret"
GITHUB_REPO_URL = "https://github.com/test/repo"
SITE_URL = "https://test.example.com"

# Cache settings
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

USE_TZ = True

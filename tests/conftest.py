"""Pytest configuration for django-ops-notifications tests."""

import pytest


@pytest.fixture(autouse=True)
def disable_slack(settings):
    """Ensure Slack is disabled for all tests by default."""
    settings.SLACK_ENABLED = False

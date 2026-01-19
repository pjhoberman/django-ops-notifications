"""Django app configuration for ops_notifications."""

from django.apps import AppConfig


class OpsNotificationsConfig(AppConfig):
    """App configuration for ops_notifications."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ops_notifications"
    verbose_name = "Ops Notifications"

"""URL configuration for ops_notifications app."""

from django.urls import path

from ops_notifications.views import DeployWebhookView

app_name = "ops_notifications"

urlpatterns = [
    path("webhooks/deploy/", DeployWebhookView.as_view(), name="deploy_webhook"),
]

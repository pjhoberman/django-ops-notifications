"""Tests for webhook views."""

import json
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from ops_notifications.views import DeployWebhookView


class TestDeployWebhookView:
    """Tests for DeployWebhookView."""

    @pytest.fixture
    def factory(self):
        """Return a request factory."""
        return RequestFactory()

    def test_missing_webhook_secret(self, factory, settings):
        """Request without secret should return 401."""
        settings.WEBHOOK_SECRET = "correct-secret"
        request = factory.post(
            "/webhooks/deploy/",
            data=json.dumps({"success": True}),
            content_type="application/json",
        )

        view = DeployWebhookView.as_view()
        response = view(request)

        assert response.status_code == 401
        assert json.loads(response.content)["status"] == "error"

    def test_wrong_webhook_secret(self, factory, settings):
        """Request with wrong secret should return 401."""
        settings.WEBHOOK_SECRET = "correct-secret"
        request = factory.post(
            "/webhooks/deploy/",
            data=json.dumps({"success": True}),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="wrong-secret",
        )

        view = DeployWebhookView.as_view()
        response = view(request)

        assert response.status_code == 401

    @patch("ops_notifications.views.send_deploy_alert")
    def test_valid_request(self, mock_alert, factory, settings):
        """Valid request should call send_deploy_alert and return 200."""
        settings.WEBHOOK_SECRET = "correct-secret"
        request = factory.post(
            "/webhooks/deploy/",
            data=json.dumps({
                "success": True,
                "environment": "production",
                "git_sha": "abc123",
            }),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="correct-secret",
        )

        view = DeployWebhookView.as_view()
        response = view(request)

        assert response.status_code == 200
        assert json.loads(response.content)["status"] == "ok"
        mock_alert.assert_called_once_with(
            success=True,
            environment="production",
            git_sha="abc123",
            error_message=None,
        )

    @patch("ops_notifications.views.send_deploy_alert")
    def test_failed_deploy_request(self, mock_alert, factory, settings):
        """Failed deploy should pass error message."""
        settings.WEBHOOK_SECRET = "secret"
        request = factory.post(
            "/webhooks/deploy/",
            data=json.dumps({
                "success": False,
                "environment": "staging",
                "git_sha": "def456",
                "error_message": "Build failed",
            }),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="secret",
        )

        view = DeployWebhookView.as_view()
        response = view(request)

        assert response.status_code == 200
        mock_alert.assert_called_once_with(
            success=False,
            environment="staging",
            git_sha="def456",
            error_message="Build failed",
        )

    def test_invalid_json(self, factory, settings):
        """Invalid JSON should return 400."""
        settings.WEBHOOK_SECRET = "secret"
        request = factory.post(
            "/webhooks/deploy/",
            data="not valid json",
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="secret",
        )

        view = DeployWebhookView.as_view()
        response = view(request)

        assert response.status_code == 400
        assert "Invalid JSON" in json.loads(response.content)["message"]

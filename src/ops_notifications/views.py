"""Views for notification webhooks."""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ops_notifications.alerts import send_deploy_alert

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class DeployWebhookView(View):
    """
    Webhook endpoint for deployment notifications.

    Requires X-Webhook-Secret header for authentication.

    Expected POST data:
    {
        "success": true,
        "environment": "production",
        "git_sha": "abc123...",
        "error_message": "..." (optional)
    }
    """

    def post(self, request):
        """Handle deploy webhook."""
        # Verify webhook secret
        webhook_secret = request.headers.get("X-Webhook-Secret", "")
        expected_secret = getattr(settings, "WEBHOOK_SECRET", "")

        if not webhook_secret or webhook_secret != expected_secret:
            logger.warning("Unauthorized webhook attempt from %s", request.META.get("REMOTE_ADDR"))
            return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

        try:
            data = json.loads(request.body)
            success = data.get("success", False)
            environment = data.get("environment", "unknown")
            git_sha = data.get("git_sha", "unknown")
            error_message = data.get("error_message")

            send_deploy_alert(
                success=success,
                environment=environment,
                git_sha=git_sha,
                error_message=error_message,
            )

            return JsonResponse({"status": "ok"})

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received in deploy webhook")
            return JsonResponse({"status": "error", "message": "Invalid JSON payload"}, status=400)
        except Exception:
            logger.exception("Failed to process deploy webhook")
            return JsonResponse({"status": "error", "message": "Failed to process webhook"}, status=500)

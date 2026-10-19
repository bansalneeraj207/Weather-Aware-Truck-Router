"""Process-level endpoints that do not depend on application services."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Report process liveness without touching the database or providers."""
    return JsonResponse({"status": "ok"})

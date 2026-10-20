"""Process-level endpoints that do not depend on application services."""

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Report process liveness without touching the database or providers."""
    return JsonResponse({"status": "ok"})


@require_GET
def readiness(request):
    """Report readiness after completing a database round trip."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_ready = cursor.fetchone() == (1,)
    except DatabaseError:
        database_ready = False

    status = 200 if database_ready else 503
    return JsonResponse(
        {"status": "ok" if database_ready else "unavailable", "database": database_ready},
        status=status,
    )

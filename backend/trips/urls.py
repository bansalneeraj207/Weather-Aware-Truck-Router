"""URL routes for the trips API."""

from django.urls import path

from trips import views

app_name = "trips"

urlpatterns = [
    path("", views.root, name="root"),
]

from django.urls import path

from sprintmanagement.health_checks.views import liveness, readiness

urlpatterns = [
    path("live/", liveness),
    path("ready/", readiness),
]

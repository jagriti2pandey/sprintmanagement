from django.apps import AppConfig
from django.db.models.signals import post_save


class WorkspacesConfig(AppConfig):
    name = "sprintmanagement.workspaces"

    def ready(self):
        from sprintmanagement.workspaces import signals
        from sprintmanagement.users.models import User

        post_save.connect(signals.create_default_workspace, sender=User)

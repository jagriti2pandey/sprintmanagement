from django.forms import Select, Form, ChoiceField, ModelChoiceField, ModelForm

from sprintmanagement.users.models import User

from .models import EpicState, StoryState, Epic, Story
from sprintmanagement.sprints.models import Sprint


custom_select = Select(
    attrs={
        "form": "object-list",
        "hx-trigger": "change",
        "hx-post": ".",
        "hx-target": "body",
    }
)


class EpicFilterForm(Form):
    state = ModelChoiceField(
        empty_label="--Set State--", queryset=EpicState.objects.all(), required=False, widget=custom_select
    )

    owner = ModelChoiceField(
        empty_label="--Set Owner--", queryset=User.objects.all(), required=False, widget=custom_select
    )


class StoryFilterForm(Form):
    state = ModelChoiceField(
        empty_label="--Set State--", queryset=StoryState.objects.all(), required=False, widget=custom_select
    )

    assignee = ModelChoiceField(
        empty_label="--Set Assignee--", queryset=User.objects.all(), required=False, widget=custom_select
    )


class EpicGroupByForm(Form):
    CHOICES = [
        ("", "None"),
        ("requester", "Requester"),
        ("assignee", "Assignee"),
        ("state", "State"),
        ("sprint", "Sprint"),
    ]

    group_by = ChoiceField(
        choices=CHOICES,
        required=False,
        widget=Select(
            attrs={
                "hx-trigger": "change",
                "hx-get": ".",
                "hx-target": "body",
                "hx-replace-url": "true",
            }
        ),
    )


class BaseWorkspaceModelForm(ModelForm):
    """
    Base form for models that belong to a workspace. See EpicForm and StoryForm below for usage.
    """

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.workspace = self.workspace
        if commit:
            instance.save()
        return instance


class EpicForm(BaseWorkspaceModelForm):
    class Meta:
        model = Epic
        fields = ["title", "description", "owner", "state", "priority", "tags"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True, workspace=self.workspace).order_by(
            "username"
        )


class StoryForm(BaseWorkspaceModelForm):
    class Meta:
        model = Story
        fields = [
            "title",
            "description",
            "epic",
            "sprint",
            "requester",
            "assignee",
            "state",
            "priority",
            "points",
            "tags",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requester"].queryset = self.workspace.members.filter(is_active=True).order_by("username")
        self.fields["assignee"].queryset = self.workspace.members.filter(is_active=True).order_by("username")
        self.fields["epic"].queryset = Epic.objects.filter(workspace=self.workspace).order_by("title")
        self.fields["sprint"].queryset = Sprint.objects.filter(workspace=self.workspace).order_by("ends_at")

from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.db.models import Max, F
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView

from sprintmanagement.views import BaseListView
from sprintmanagement.sprints.models import Sprint
from sprintmanagement.stories.forms import EpicFilterForm, EpicGroupByForm, StoryFilterForm, EpicForm, StoryForm
from sprintmanagement.stories.models import Epic, Story
from sprintmanagement.stories.tasks import (
    duplicate_epics,
    duplicate_stories,
    epic_set_owner,
    epic_set_state,
    remove_epics,
    remove_stories,
    reset_epic,
    story_set_assignee,
    story_set_state,
    story_set_sprint,
    story_set_epic,
)
from sprintmanagement.utils import get_clean_next_url, get_referer_url


@method_decorator(login_required, name="dispatch")
class EpicDetailView(DetailView):
    """ """

    model = Epic

    def get_children(self):
        queryset = self.get_object().story_set.select_related("requester", "assignee", "sprint", "state")

        config = dict(
            sprint=("sprint__starts_at", lambda story: story.sprint and story.sprint.title or "No sprint"),
            state=("state__slug", lambda story: story.state.name),
            requester=("requester__id", lambda story: story.requester and story.requester.username or "Unset"),
            assignee=("assignee__id", lambda story: story.assignee and story.assignee.username or "Unassigned"),
        )

        group_by = self.request.GET.get("group_by")

        try:
            order_by, fx = config[group_by]
        except KeyError:
            return [(None, queryset)]
        else:
            queryset = queryset.order_by(F(order_by).asc(nulls_last=True), "priority")
            foo = [(t[0], list(t[1])) for t in groupby(queryset, key=fx)]
            return foo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["objects_by_group"] = self.get_children()
        context["group_by_form"] = EpicGroupByForm(self.request.GET)
        context["group_by"] = self.request.GET.get("group_by")
        context["filters_form"] = StoryFilterForm(self.request.POST)
        context["current_workspace"] = self.kwargs["workspace"]
        return context

    def post(self, *args, **kwargs):
        params = self.request.POST

        if params.get("remove") == "yes":
            remove_epics.delay([self.get_object().id])
            url = reverse_lazy("stories:epic-list", args=[self.kwargs["workspace"]])
            return HttpResponseRedirect(url)

        if params.get("epic-reset") == "yes":
            story_ids = [t[6:] for t in params.keys() if "story-" in t]
            reset_epic.delay(story_ids)

        state = params.get("state")
        if isinstance(state, list):
            state = state[0]
        if state:
            story_ids = [t[6:] for t in params.keys() if "story-" in t]
            story_set_state.delay(story_ids, state)

        assignee = params.get("assignee")
        if isinstance(assignee, list):
            assignee = assignee[0]
        if assignee:
            story_ids = [t[6:] for t in params.keys() if "story-" in t]
            story_set_assignee.delay(story_ids, assignee)

        url = get_referer_url(self.request)
        return HttpResponseRedirect(url)


class StoryBaseView:
    model = Story
    fields = [
        "title",
        "description",
        "epic",
        "sprint",
        "requester",
        "assignee",
        "priority",
        "points",
        "state",
        "tags",
    ]

    @property
    def success_url(self):
        return get_clean_next_url(self.request, reverse_lazy("stories:story-list", args=[self.kwargs["workspace"]]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        story_add_url = reverse_lazy("stories:story-add", args=[self.kwargs["workspace"]])

        epic_id = self.request.GET.get("epic")
        sprint_id = self.request.GET.get("sprint")
        if epic_id or sprint_id:
            story_add_url += "?"
            if epic_id:
                story_add_url += "epic=" + epic_id
            if sprint_id:
                story_add_url += "sprint=" + sprint_id

        context["story_add_url"] = story_add_url
        context["current_workspace"] = self.kwargs["workspace"]

        return context


@method_decorator(login_required, name="dispatch")
class StoryCreateView(StoryBaseView, CreateView):

    def get_initial(self):
        initial_dict = dict(requester=self.request.user.id, state="pl")

        epic_id = self.request.GET.get("epic")
        if epic_id is not None:
            initial_dict["epic"] = epic_id

            max_priority = Story.objects.filter(epic=epic_id).aggregate(Max("priority"))["priority__max"] or 0
            initial_dict["priority"] = max_priority + 1

        sprint_id = self.request.GET.get("sprint")
        if sprint_id is not None:
            initial_dict["sprint"] = sprint_id

        return initial_dict

    def post(self, *args, **kwargs):
        kwargs = self.get_form_kwargs()
        kwargs["data"] = self.request.POST
        form = self.get_form_class()(**kwargs)
        return self.form_valid(form)

    def get_form_class(self):
        return StoryForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["workspace"] = self.request.workspace
        return kwargs


@method_decorator(login_required, name="dispatch")
class StoryUpdateView(StoryBaseView, UpdateView):

    def post(self, *args, **kwargs):
        kwargs = self.get_form_kwargs()
        kwargs["data"] = self.request.POST

        if not kwargs.get("save-as-new"):
            kwargs["instance"] = self.get_object()

        form = self.get_form_class()(**kwargs)
        return self.form_valid(form)

    def get_form_class(self):
        return StoryForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["workspace"] = self.request.workspace
        return kwargs


class EpicBaseView:
    model = Epic
    fields = [
        "title",
        "description",
        "owner",
        "priority",
        "state",
        "tags",
    ]

    @property
    def success_url(self):
        return get_clean_next_url(self.request, reverse_lazy("stories:epic-list", args=[self.kwargs["workspace"]]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        epic_add_url = reverse_lazy("stories:epic-add", args=[self.kwargs["workspace"]])
        context["epic_add_url"] = epic_add_url
        context["current_workspace"] = self.kwargs["workspace"]
        return context


@method_decorator(login_required, name="dispatch")
class EpicCreateView(EpicBaseView, CreateView):

    def get_initial(self):
        return dict(owner=self.request.user.id, state="pl")

    def get_form_class(self):
        return EpicForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["workspace"] = self.request.workspace
        return kwargs

    def post(self, *args, **kwargs):
        kwargs = self.get_form_kwargs()
        kwargs["data"] = self.request.POST
        form = self.get_form_class()(**kwargs)
        return self.form_valid(form)


@method_decorator(login_required, name="dispatch")
class EpicUpdateView(EpicBaseView, UpdateView):

    def post(self, *args, **kwargs):
        kwargs = self.get_form_kwargs()
        kwargs["data"] = self.request.POST

        if not kwargs.get("save-as-new"):
            kwargs["instance"] = self.get_object()

        form = self.get_form_class()(**kwargs)
        return self.form_valid(form)

    def get_form_class(self):
        return EpicForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["workspace"] = self.request.workspace
        return kwargs


@method_decorator(login_required, name="dispatch")
class EpicList(BaseListView):
    model = Epic
    filter_fields = dict(owner="owner__username", state="state__name__iexact", label="tags__name__iexact")
    select_related = ["owner", "state"]
    prefetch_related = ["tags"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters_form"] = EpicFilterForm(self.request.POST)
        context["current_workspace"] = self.kwargs["workspace"]
        return context

    def post(self, *args, **kwargs):
        params = self.request.POST
        epic_ids = [t[5:] for t in params.keys() if "epic-" in t]

        if len(epic_ids) > 0:
            if params.get("remove") == "yes":
                remove_epics.delay(epic_ids)

            if params.get("duplicate") == "yes":
                duplicate_epics.delay(epic_ids)

            state = params.get("state")
            if isinstance(state, list):
                state = state[0]
            if state:
                epic_set_state.delay(epic_ids, state)

            owner = params.get("owner")
            if isinstance(owner, list):
                owner = owner[0]
            if owner:
                epic_set_owner.delay(epic_ids, owner)

        url = self.request.get_full_path()
        return HttpResponseRedirect(url)


@method_decorator(login_required, name="dispatch")
class StoryList(BaseListView):
    model = Story
    filter_fields = dict(
        requester="requester__username",
        assignee="assignee__username",
        state="state__name__iexact",
        label="tags__name__iexact",
        sprint="sprint__title__iexact",
    )
    select_related = ["requester", "assignee", "state", "sprint"]
    prefetch_related = ["tags"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters_form"] = StoryFilterForm(self.request.POST)

        to_sprint = self.request.GET.get("to-sprint")
        to_epic = self.request.GET.get("to-epic")

        if to_sprint:
            try:
                sprint = Sprint.objects.get(pk=to_sprint)
            except Sprint.DoesNotExist:
                pass
            else:
                context["add_to"] = "sprint"
                context["add_to_object"] = sprint

        elif to_epic:
            try:
                epic = Epic.objects.get(pk=to_epic)
            except Epic.DoesNotExist:
                pass
            else:
                context["add_to"] = "epic"
                context["add_to_object"] = epic

        context["current_workspace"] = self.kwargs["workspace"]

        return context

    def post(self, *args, **kwargs):
        params = self.request.POST

        story_ids = [t[6:] for t in params.keys() if "story-" in t]

        if len(story_ids) > 0:
            if params.get("remove") == "yes":
                remove_stories.delay(story_ids)

            elif params.get("duplicate") == "yes":
                duplicate_stories.delay(story_ids)

            else:
                add_to_sprint = params.get("add-to-sprint")
                if add_to_sprint:
                    story_set_sprint.delay(story_ids, add_to_sprint)

                add_to_epic = params.get("add-to-epic")
                if add_to_epic:
                    story_set_epic.delay(story_ids, add_to_epic)

            state = params.get("state")
            if isinstance(state, list):
                state = state[0]
            if state:
                story_set_state.delay(story_ids, state)

            assignee = params.get("assignee")
            if isinstance(assignee, list):
                assignee = assignee[0]
            if assignee:
                story_set_assignee.delay(story_ids, assignee)

        url = self.request.get_full_path()
        return HttpResponseRedirect(url)


@method_decorator(login_required, name="dispatch")
class StoryDetailView(DetailView):
    """ """

    model = Story

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_workspace"] = self.kwargs["workspace"]
        return context

    def post(self, *args, **kwargs):
        params = self.request.POST

        if params.get("remove") == "yes":
            remove_stories.delay([self.get_object().id])
            url = reverse_lazy("stories:story-list", args=[self.kwargs["workspace"]])
            return HttpResponseRedirect(url)

        url = self.request.get_full_path()
        return HttpResponseRedirect(url)

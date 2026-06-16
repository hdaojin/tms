from django import forms

from competition_standards.models import StandardModule
from core.utils.forms import StyledFormMixin

from .models import SkillNode, SkillTree


def build_parent_node_choices(nodes):
    children_by_parent = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    rows = []
    visited = set()

    def append_node(node, depth):
        if node.pk in visited:
            return
        visited.add(node.pk)
        rows.append((node, depth))
        for child in children_by_parent.get(node.pk, []):
            append_node(child, depth + 1)

    for root in children_by_parent.get(None, []):
        append_node(root, 0)

    for node in nodes:
        if node.pk not in visited:
            append_node(node, 0)

    return [(node.pk, f"{'- ' * depth}{node.code} - {node.name}") for node, depth in rows]


class SkillTreeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillTree
        fields = ["module", "name", "version", "description", "is_current"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["module"].queryset = StandardModule.objects.select_related(
            "project",
            "module_set",
        ).order_by("project__name", "module_set__sort_order", "sort_order", "code")
        self.fields["module"].label_from_instance = lambda obj: f"{obj.project.name} / {obj.code} - {obj.name}"


class SkillNodeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillNode
        fields = ["parent", "code", "name", "node_type", "description", "difficulty", "sort_order", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, tree, **kwargs):
        self.tree = tree
        super().__init__(*args, **kwargs)
        queryset = tree.nodes.order_by("sort_order", "code", "name")
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = queryset
        self.fields["parent"].choices = [("", "---------"), *build_parent_node_choices(list(queryset))]
        self.fields["parent"].required = False
        self.fields["parent"].label_from_instance = lambda obj: f"{obj.code} - {obj.name}"

    def clean(self):
        self.instance.tree = self.tree
        return super().clean()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tree = self.tree
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SkillNodeInlineCreateForm(SkillNodeForm):
    class Meta(SkillNodeForm.Meta):
        fields = ["parent", "code", "name", "node_type", "difficulty", "sort_order", "is_active"]

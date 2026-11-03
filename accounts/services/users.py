from __future__ import annotations


ROLE_STAFF = "工作人员"
ROLE_SUPERUSER = "超级用户"
ROLE_UNASSIGNED = "未分配"

ROLE_BADGE_CLASSES = {
    ROLE_STAFF: "badge badge-soft badge-secondary",
    ROLE_SUPERUSER: "badge badge-soft badge-error",
}
DEFAULT_ROLE_BADGE_CLASS = "badge badge-soft badge-accent"
NO_ROLE_BADGE_CLASS = "badge badge-soft"


def get_user_display_name(user) -> str:
    if label := getattr(user, "identity_label", ""):
        return label
    full_name = f"{user.last_name}{user.first_name}".strip()
    return full_name or "未填写姓名"


def get_user_full_info(user) -> str:
    return getattr(user, "identity_label", "") or get_user_display_name(user)


def require_distinguishable_users(queryset, ids):
    """不允许选择在授权候选范围内无法用姓名和区分备注辨认的用户。"""
    from collections import Counter
    from django.core.exceptions import ValidationError

    chosen = set(ids)
    if not chosen:
        return
    rows = list(queryset.values_list("pk", "last_name", "first_name", "profile__name_disambiguation"))
    names = Counter((last + first).strip() for _, last, first, _ in rows)
    labels = Counter(((last + first).strip(), (note or "").strip()) for _, last, first, note in rows)
    for pk, last, first, note in rows:
        name, note = (last + first).strip(), (note or "").strip()
        if pk in chosen and names[name] > 1 and (not note or labels[(name, note)] > 1):
            raise ValidationError("同名人员的区分备注未填写或重复，请先完善资料。")


def annotate_identity_labels(queryset):
    """按当前可见查询集批量标注同名备注和无法区分的对象。"""
    from collections import Counter
    from django.db.models import BooleanField, Case, CharField, Value, When

    rows = list(queryset.values_list("pk", "last_name", "first_name", "profile__name_disambiguation").distinct())
    names = Counter((last + first).strip() for _, last, first, _ in rows)
    notes = Counter(((last + first).strip(), (note or "").strip()) for _, last, first, note in rows)
    labels, invalid = [], []
    for pk, last, first, note in rows:
        name, note = (last + first).strip(), (note or "").strip()
        if names[name] > 1:
            if not note or notes[(name, note)] > 1:
                invalid.append(pk)
            if note:
                labels.append(When(pk=pk, then=Value(f"{name or '未填写姓名'}（{note}）")))
    return queryset.annotate(
        identity_label=Case(*labels, default=Value(""), output_field=CharField()),
        identity_invalid=Case(When(pk__in=invalid, then=Value(True)), default=Value(False), output_field=BooleanField()),
    )


def user_name_search_terms(name, pronunciation=""):
    from pypinyin import Style, lazy_pinyin, pinyin

    def initials_for(name, manual):
        parts = manual.strip().split()
        if len(parts) > 1:
            return "".join(part[0] for part in parts if part)
        target = "".join(parts).casefold()
        alternatives = pinyin(name, style=Style.NORMAL, heteronym=True)
        states = {"": ""}
        for syllables in alternatives:
            next_states = {}
            for prefix, initial in states.items():
                for syllable in syllables:
                    combined = prefix + syllable.casefold()
                    if target.startswith(combined):
                        next_states[combined] = initial + syllable[0]
            states = next_states
        return states.get(target) or "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))

    parts = (pronunciation or "").strip().split()
    return name, "".join(parts) if parts else "".join(lazy_pinyin(name)), initials_for(name, pronunciation or "")


def user_name_search_ids(queryset, query):
    """按姓名、全拼或首字母筛选已授权的用户集合。"""
    needle = "".join(query.casefold().split())
    if not needle:
        return []
    matches = []
    for pk, last, first, pronunciation in queryset.values_list(
        "pk", "last_name", "first_name", "profile__name_pronunciation"
    ).iterator(chunk_size=1000):
        name = f"{last}{first}".strip()
        if any(needle in "".join(value.casefold().split())
               for value in user_name_search_terms(name, pronunciation or "")):
            matches.append(pk)
    return matches


def get_user_role_badges(user, *, size: str = "") -> list[dict[str, str]]:
    role_names = []
    seen_role_names = set()

    for group in user.groups.all():
        if group.name in seen_role_names:
            continue
        role_names.append(group.name)
        seen_role_names.add(group.name)

    if user.is_staff and not user.is_superuser and ROLE_STAFF not in seen_role_names:
        role_names.append(ROLE_STAFF)
        seen_role_names.add(ROLE_STAFF)

    if user.is_superuser and ROLE_SUPERUSER not in seen_role_names:
        role_names.append(ROLE_SUPERUSER)
        seen_role_names.add(ROLE_SUPERUSER)

    if not role_names:
        role_names = [ROLE_UNASSIGNED]

    return [
        {
            "label": role_name,
            "css_class": _get_role_badge_class(role_name, size=size),
        }
        for role_name in role_names
    ]


def _get_role_badge_class(role_name: str, *, size: str = "") -> str:
    css_class = (
        NO_ROLE_BADGE_CLASS
        if role_name == ROLE_UNASSIGNED
        else ROLE_BADGE_CLASSES.get(role_name, DEFAULT_ROLE_BADGE_CLASS)
    )
    return f"{css_class} {size}".strip()

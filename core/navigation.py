from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse


CACHE_NS = "tms:navigation:v1"


@dataclass
class NavigationItem:
    key: str
    label: str
    icon_class: str = ""
    url_name: str | None = None
    url: str | None = None
    section: str | None = None
    permissions: list[str] = field(default_factory=list)
    children: list["NavigationItem"] = field(default_factory=list)
    external: bool = False
    debug_only: bool = False
    login_required: bool = True
    staff_required: bool = False
    superuser_required: bool = False
    resolved_url: str = "#"
    active: bool = False
    expanded: bool = False
    has_own_url: bool = False

    @property
    def has_children(self) -> bool:
        return bool(self.children)


def _config_path() -> Path:
    core_app = apps.get_app_config("core")
    return Path(core_app.path) / "config" / "navigation.yml"


def _load_config() -> dict:
    cache_key = f"{CACHE_NS}:config"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    path = _config_path()
    data: dict = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    cache.set(cache_key, data, timeout=settings.CACHE_TIMEOUT)
    return data


def get_theme_choices() -> list[str]:
    return list(_load_config().get("themes") or ["light", "dark", "corporate", "business", "night"])


def get_sections() -> list[dict]:
    return list(_load_config().get("sections") or [])


def get_layout_sections(key: str) -> list[str]:
    layouts = _load_config().get("layouts") or {}
    value = layouts.get(key) or []
    if isinstance(value, str):
        return [value]
    return [entry for entry in value if isinstance(entry, str)]


def _reverse_url(url_name: str | None) -> str:
    if not url_name:
        return "#"
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def _build_item(raw: dict, section_slug: str | None = None) -> NavigationItem:
    children = [_build_item(child, section_slug) for child in raw.get("children", []) or []]
    item = NavigationItem(
        key=raw["key"],
        label=raw["label"],
        icon_class=raw.get("icon_class", ""),
        url_name=raw.get("url_name"),
        url=raw.get("url"),
        section=raw.get("section") or section_slug,
        permissions=list(raw.get("permissions") or []),
        children=children,
        external=bool(raw.get("external", False)),
        debug_only=bool(raw.get("debug_only", False)),
        login_required=bool(raw.get("login_required", True)),
        staff_required=bool(raw.get("staff_required", False)),
        superuser_required=bool(raw.get("superuser_required", False)),
        has_own_url=bool(raw.get("url") or raw.get("url_name")),
    )
    item.resolved_url = item.url or _reverse_url(item.url_name)
    return item


def _filter_item(item: NavigationItem, user) -> NavigationItem | None:
    if item.debug_only and not settings.DEBUG:
        return None
    if item.login_required and isinstance(user, AnonymousUser):
        return None
    if item.staff_required and not getattr(user, "is_staff", False):
        return None
    if item.superuser_required and not getattr(user, "is_superuser", False):
        return None
    if item.permissions and (isinstance(user, AnonymousUser) or not user.has_perms(item.permissions)):
        return None

    filtered_children: list[NavigationItem] = []
    for child in item.children:
        filtered = _filter_item(child, user)
        if filtered is not None:
            filtered_children.append(filtered)
    item.children = filtered_children
    if not item.children and item.resolved_url == "#" and not item.url and not item.url_name:
        return None
    if item.children and item.resolved_url == "#":
        item.resolved_url = _first_item_url(item.children) or "#"
    return item


def _first_item_url(items: Iterable[NavigationItem]) -> str | None:
    for item in items:
        if item.resolved_url and item.resolved_url != "#":
            return item.resolved_url
        child_url = _first_item_url(item.children)
        if child_url:
            return child_url
    return None


def _mark_active(items: list[NavigationItem], request) -> None:
    path = getattr(request, "path", "") or ""
    view_name = getattr(getattr(request, "resolver_match", None), "view_name", None)
    app_name = getattr(getattr(request, "resolver_match", None), "app_name", None)
    best_item: NavigationItem | None = None
    best_score = 0

    def path_match_score(url: str) -> int:
        if not url or url == "#":
            return 0
        if path == url:
            return 500_000 + len(url)
        if url == "/":
            return 500_000 if path == "/" else 0
        normalized = url.rstrip("/") + "/"
        if path.startswith(normalized):
            return len(normalized)
        return 0

    def item_score(item: NavigationItem) -> int:
        score = path_match_score(item.resolved_url) if item.has_own_url else 0
        if item.url_name and view_name == item.url_name:
            score = max(score, 1_000_000 + len(item.resolved_url or ""))
        if item.key == app_name:
            score = max(score, 10)
        return score

    def collect(item: NavigationItem) -> None:
        nonlocal best_item, best_score
        score = item_score(item)
        if score > best_score:
            best_score = score
            best_item = item
        for child in item.children:
            collect(child)

    def mark_branch(item: NavigationItem) -> bool:
        child_contains_target = any(mark_branch(child) for child in item.children)
        item.active = item is best_item
        item.expanded = child_contains_target
        return item.active or child_contains_target

    for item in items:
        collect(item)
    for item in items:
        mark_branch(item)


def _section_for_slug(section_slug: str) -> dict | None:
    for section in get_sections():
        if section.get("key") == section_slug:
            return section
    return None


def get_section_items(section_slug: str, user, request=None) -> list[NavigationItem]:
    section = _section_for_slug(section_slug)
    if not section:
        return []
    items: list[NavigationItem] = []
    for raw_item in section.get("items", []) or []:
        item = _filter_item(_build_item(raw_item, section_slug), user)
        if item is not None:
            items.append(item)
    if request is not None:
        _mark_active(items, request)
    return items


def get_visible_sections(user, request=None, *, layout_key: str | None = None, include_items: bool = False) -> list[dict]:
    desired = get_layout_sections(layout_key) if layout_key else [section.get("key") for section in get_sections()]
    visible_sections: list[dict] = []
    for section_slug in desired:
        section = _section_for_slug(section_slug)
        if not section:
            continue
        login_required = bool(section.get("login_required", True))
        if login_required and isinstance(user, AnonymousUser):
            continue
        items = get_section_items(section_slug, user, request=request)
        if not items:
            continue
        section_data = {
            "key": section_slug,
            "slug": section_slug,
            "label": section.get("label", section_slug),
            "description": section.get("description", ""),
            "icon_class": section.get("icon_class", ""),
            "url": _first_item_url(items) or "#",
            "active": any(item.active or item.expanded for item in items),
            "count": len(items),
        }
        if include_items:
            section_data["items"] = items
        visible_sections.append(section_data)
    return visible_sections


def resolve_current_section(request) -> str | None:
    app_name = getattr(getattr(request, "resolver_match", None), "app_name", None)
    if app_name:
        for section in get_sections():
            if section.get("key") == app_name:
                return section.get("key")
            for item in _iter_raw_items(section.get("items", []) or []):
                if item.get("key") == app_name:
                    return section.get("key")
    path = getattr(request, "path", "") or ""
    best_section: str | None = None
    best_score = 0

    def raw_path_match_score(url: str) -> int:
        if not url or url == "#":
            return 0
        if path == url:
            return 500_000 + len(url)
        if url == "/":
            return 0
        normalized = url.rstrip("/") + "/"
        return len(normalized) if path.startswith(normalized) else 0

    for section in get_sections():
        for raw_item in _iter_raw_items(section.get("items", []) or []):
            item = _build_item(raw_item, section.get("key"))
            score = raw_path_match_score(item.resolved_url)
            if score > best_score:
                best_score = score
                best_section = section.get("key")
    return best_section


def _iter_raw_items(items: Iterable[dict]) -> Iterable[dict]:
    for item in items:
        yield item
        yield from _iter_raw_items(item.get("children", []) or [])

# common/utils/menus.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse


@dataclass
class MenuItem:
    """内存中的菜单节点对象，对应 YAML 中的单个菜单项。"""

    name: str
    icon: Optional[str] = None
    named_url: Optional[str] = None
    is_group_header: bool = False
    is_visible: bool = True
    login_required: bool = False
    perm_match_all: bool = True
    required_perms: List[str] = field(default_factory=list)
    visible_for_groups: List[str] = field(default_factory=list)
    children: List["MenuItem"] = field(default_factory=list)
    menu_slug: Optional[str] = None  # 所属菜单片段（如 accounts/traininglogs）
    resolved_url: str = "#"
    active: bool = False
    expanded: bool = False

    @property
    def has_children(self) -> bool:
        return bool(self.children)


# ---------- YAML 加载部分（从 config/menus/ 目录读取） ----------

def _get_menus_dir() -> Path:
    """
    返回 config app 中 menus 目录的路径：config/menus/
    """
    config_app = apps.get_app_config("config")  # 确保 app_label 就叫 'config'
    return Path(config_app.path) / "menus"


def _load_layout_config() -> dict:
    """从 config/menus/layout.yml 读取布局配置。"""
    cache_key = "tms:menus:layout"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    menus_dir = _get_menus_dir()
    layout_path = menus_dir / "layout.yml"
    layout: dict = {}
    if layout_path.exists():
        with layout_path.open("r", encoding="utf-8") as f:
            layout = yaml.safe_load(f) or {}

    cache.set(cache_key, layout, timeout=settings.CACHE_TIMEOUT)
    return layout


def _load_app_menus() -> dict[str, dict]:
    """
    从 config/menus 目录加载所有 *.yml（不含 sections.yml），
    合并成 {menu_slug: menu_def}。
    """
    cache_key = "tms:menus:by_slug"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    menus_dir = _get_menus_dir()
    result: dict[str, dict] = {}

    if not menus_dir.exists():
        cache.set(cache_key, result, settings.CACHE_TIMEOUT)
        return result

    for path in menus_dir.glob("*.yml"):
        if path.name == "sections.yml":
            continue  # sections.yml 另行处理
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        menu_slug = data.get("menu_slug") or path.stem
        result[menu_slug] = data

    cache.set(cache_key, result, timeout=settings.CACHE_TIMEOUT)
    return result


def _load_sections() -> List[dict]:
    """从 sections.yml 读取主菜单区域配置，保持 YAML 顺序。"""
    cache_key = "tms:menus:sections:list"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    menus_dir = _get_menus_dir()
    sections_path = menus_dir / "sections.yml"
    sections: List[dict] = []

    if sections_path.exists():
        with sections_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        for entry in data:
            sections.append(entry)

    cache.set(cache_key, sections, timeout=settings.CACHE_TIMEOUT)
    return sections


# ---------- 构建 MenuItem 树结构 ----------

def _build_items(raw_items: Iterable[dict], menu_slug: Optional[str]) -> List[MenuItem]:
    items: List[MenuItem] = []
    for raw in raw_items:
        children_raw = raw.get("children", []) or []
        children = _build_items(children_raw, menu_slug) if children_raw else []

        resolved_url = "#"
        named_url = raw.get("named_url")
        external_url = raw.get("external_url")
        if named_url:
            try:
                resolved_url = reverse(named_url)
            except NoReverseMatch:
                resolved_url = "#"
        elif external_url:
            resolved_url = external_url

        item = MenuItem(
            name=raw["name"],
            icon=raw.get("icon"),
            named_url=named_url,
            is_group_header=raw.get("is_group_header", False),
            is_visible=raw.get("is_visible", True),
            login_required=raw.get("login_required", False),
            perm_match_all=raw.get("perm_match_all", True),
            required_perms=raw.get("required_perms", []) or [],
            visible_for_groups=raw.get("visible_for_groups", []) or [],
            children=children,
            menu_slug=menu_slug,
            resolved_url=resolved_url,
        )
        items.append(item)
    return items


# ---------- 用户过滤（登录 / 组 / 权限） ----------

def _user_in_groups(user, group_names: list[str]) -> bool:
    if not group_names:
        return True
    if isinstance(user, AnonymousUser):
        return False
    user_groups = set(user.groups.values_list("name", flat=True))
    return bool(user_groups.intersection(group_names))


def _check_perms(user, perms: list[str], match_all: bool) -> bool:
    # 允许 YAML 中配置为字符串或列表，统一转 list 后判断
    if isinstance(perms, str):
        perms = [perms]
    perms = list(perms or [])
    if not perms:
        return True
    if isinstance(user, AnonymousUser):
        return False
    if match_all:
        return user.has_perms(perms)
    return any(user.has_perm(p) for p in perms)


def _filter_item(item: MenuItem, user) -> Optional[MenuItem]:
    """
    按用户登录状态 / 组 / 权限过滤单个菜单节点，并递归过滤其 children。
    """
    # 显示标记
    if not item.is_visible:
        return None

    # 登录要求
    if item.login_required and isinstance(user, AnonymousUser):
        return None

    # 组过滤
    if item.visible_for_groups and not _user_in_groups(user, item.visible_for_groups):
        return None

    # 权限过滤
    if not _check_perms(user, item.required_perms, item.perm_match_all):
        return None

    # 递归处理子节点
    filtered_children: list[MenuItem] = []
    for child in item.children:
        fc = _filter_item(child, user)
        if fc is not None:
            filtered_children.append(fc)
    item.children = filtered_children

    return item


def _mark_active(items: List[MenuItem], request) -> None:
    """根据当前请求标记 active/expanded，用于侧边栏展开。"""
    path = getattr(request, "path", "")
    view_name = getattr(getattr(request, "resolver_match", None), "view_name", None)

    def recurse(node: MenuItem) -> bool:
        matched = False
        if node.named_url and view_name and node.named_url == view_name:
            matched = True
        if node.resolved_url and node.resolved_url != "#" and path.startswith(node.resolved_url):
            matched = True
        child_active = False
        for child in node.children:
            if recurse(child):
                child_active = True
        node.active = matched or child_active
        node.expanded = child_active or matched
        return node.active

    for item in items:
        recurse(item)


# ---------- 对外主接口：按 section 聚合菜单 ----------

def get_sections() -> List[dict]:
    """返回所有 section 定义的列表，保持 YAML 顺序。"""
    return _load_sections()


def get_layout_sections(key: str) -> List[str]:
    """从 layout.yml 获取指定布局下的 section 顺序列表。"""
    layout = _load_layout_config()
    value = layout.get(key) or []
    if isinstance(value, str):
        return [value]
    return list(value)


def get_section_menu(section_slug: str, user, request=None) -> list[MenuItem]:
    """根据 section 获取菜单项列表，并可选根据 request 标记 active/expanded。"""
    app_menus = _load_app_menus()
    sections = _load_sections()
    section = next((s for s in sections if s.get("section") == section_slug), None)
    if not section:
        return []

    include_menus: list[str] = section.get("include_menus", []) or []

    items: list[MenuItem] = []

    for menu_ref in include_menus:
        menu_def = app_menus.get(menu_ref)
        if not menu_def:
            # 兼容按 app_name 引用菜单（需菜单 yml 设置 app_name）
            for slug, md in app_menus.items():
                if md.get("app_name") == menu_ref:
                    menu_def = md
                    menu_ref = slug
                    break
        if not menu_def:
            continue
        raw_items = menu_def.get("items", []) or []
        menu_items = _build_items(raw_items, menu_ref)

        for mi in menu_items:
            fi = _filter_item(mi, user)
            if fi is not None:
                items.append(fi)

    if request is not None:
        _mark_active(items, request)

    return items


# 可选：如果你有需要直接按 menu_slug 渲染（不经过 section），也可以暴露一个函数：
def get_menu_by_slug(menu_slug: str, user) -> list[MenuItem]:
    """
    不通过 section，直接按 menu_slug 获取一个菜单片段。
    """
    app_menus = _load_app_menus()
    menu_def = app_menus.get(menu_slug)
    if not menu_def:
        return []
    raw_items = menu_def.get("items", []) or []
    menu_items = _build_items(raw_items, menu_slug)

    items: list[MenuItem] = []
    for mi in menu_items:
        fi = _filter_item(mi, user)
        if fi is not None:
            items.append(fi)
    return items

# core/utils/menus.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse

# 缓存命名空间（版本化以便更新配置后强制刷新）
CACHE_NS = "tms:menus:v5"

logger = logging.getLogger(__name__)


@dataclass
class MenuItem:
    """内存中的菜单节点对象，对应 YAML 中的单个菜单项。"""

    name: str
    icon: Optional[object] = None  # 兼容：字符串或 {pic, size, color}
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
    target_blank: bool = False
    superuser_required: bool = False
    staff_required: bool = False

    @property
    def has_children(self) -> bool:
        return bool(self.children)


# ---------- YAML 加载部分（从 config/menus/ 目录读取） ----------

def _get_core_config_dir() -> Path:
    """core 应用配置目录 core/config。"""
    core_app = apps.get_app_config("core")
    return Path(core_app.path) / "config"


def _get_menus_dir() -> Path:
    """core/config/menus/ 目录。"""
    return _get_core_config_dir() / "menus"


def _get_root_config_path() -> Path:
    """根菜单配置文件 core/config/menus.yml。"""
    return _get_core_config_dir() / "menus.yml"


def _load_root_config() -> dict:
    """一次读取根菜单配置（layouts/sections）。"""
    cache_key = f"{CACHE_NS}:root"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    root_cfg: dict = {}
    root_path = _get_root_config_path()
    if root_path.exists():
        with root_path.open("r", encoding="utf-8") as f:
            root_cfg = yaml.safe_load(f) or {}

    cache.set(cache_key, root_cfg, timeout=settings.CACHE_TIMEOUT)
    return root_cfg


def _load_layout_config() -> dict:
    """读取 layouts 配置，默认空字典。"""
    return _load_root_config().get("layouts", {}) or {}


def _load_app_menus() -> dict[str, dict]:
    """加载 core/config/menus/*.yml（每个应用/片段一个）。"""
    cache_key = f"{CACHE_NS}:by_slug"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    menus_dir = _get_menus_dir()
    result: dict[str, dict] = {}

    if menus_dir.exists():
        for path in sorted(menus_dir.glob("*.yml")):
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            menu_slug = data.get("menu_slug") or path.stem
            result[menu_slug] = data

    cache.set(cache_key, result, timeout=settings.CACHE_TIMEOUT)
    return result


def _load_sections() -> List[dict]:
    """从根配置加载 sections，保持顺序。"""
    cache_key = f"{CACHE_NS}:sections:list"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    sections: List[dict] = []
    raw_sections = _load_root_config().get("sections") or []
    for entry in raw_sections:
        sections.append(entry)

    cache.set(cache_key, sections, timeout=settings.CACHE_TIMEOUT)
    return sections


# ---------- 构建 MenuItem 树结构 ----------

def _reverse_named_url(named_url: str) -> str:
    try:
        return reverse(named_url)
    except NoReverseMatch:
        logger.warning("菜单链接反解失败，named_url=%s", named_url)
        return "#"


def _resolve_url(raw: dict) -> str:
    named_url = raw.get("named_url")
    external_url = raw.get("external_url")
    if named_url:
        return _reverse_named_url(named_url)
    if external_url:
        return external_url
    return "#"


def _build_items(raw_items: Iterable[dict], menu_slug: Optional[str]) -> List[MenuItem]:
    items: List[MenuItem] = []
    for raw in raw_items:
        children_raw = raw.get("children", []) or []
        children = _build_items(children_raw, menu_slug) if children_raw else []

        item = MenuItem(
            name=raw["name"],
            icon=raw.get("icon"),
            named_url=raw.get("named_url"),
            is_group_header=raw.get("is_group_header", False),
            is_visible=raw.get("is_visible", True),
            login_required=raw.get("login_required", False),
            perm_match_all=raw.get("perm_match_all", True),
            required_perms=raw.get("required_perms", []) or [],
            visible_for_groups=raw.get("visible_for_groups", []) or [],
            children=children,
            menu_slug=menu_slug,
            resolved_url=_resolve_url(raw),
            target_blank=raw.get("target_blank", False),
            superuser_required=raw.get("superuser_required", False),
            staff_required=raw.get("staff_required", False),
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
        return True  # 未配置权限，不做限制
    if isinstance(user, AnonymousUser):
        return False
    if match_all:
        return user.has_perms(perms)
    return any(user.has_perm(p) for p in perms)


def _login_required_effective(item: MenuItem) -> bool:
    """login_required 或配置了 required_perms/superuser/staff 均视为需要登录。"""
    return bool(item.login_required or item.required_perms or item.superuser_required or item.staff_required)


def _filter_item(item: MenuItem, user) -> Optional[MenuItem]:
    """按可见性 / 登录 / 权限过滤节点，并递归过滤子节点。"""
    # （1）显式可见性
    if not item.is_visible:
        return None

    # （2）登录要求（自动推导 required_perms -> 必须登录）
    if _login_required_effective(item) and isinstance(user, AnonymousUser):
        return None

    # superuser / staff 限制
    if item.superuser_required and not getattr(user, "is_superuser", False):
        return None
    if item.staff_required and not getattr(user, "is_staff", False):
        return None

    # 组过滤（保留旧字段兼容）
    if item.visible_for_groups and not _user_in_groups(user, item.visible_for_groups):
        return None

    # （3）权限检查
    if not _check_perms(user, item.required_perms, item.perm_match_all):
        return None

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
    has_exact_view_match = False

    def _has_named_url_match(nodes: List[MenuItem]) -> bool:
        for node in nodes:
            if node.named_url and view_name and node.named_url == view_name:
                return True
            if node.children and _has_named_url_match(node.children):
                return True
        return False

    if view_name:
        has_exact_view_match = _has_named_url_match(items)

    def _path_matches(node_url: str) -> bool:
        if not node_url or node_url == "#":
            return False
        # 精确匹配或以节点路径为前缀（但避免根"/"匹配所有）。
        if path == node_url:
            return True
        if node_url == "/":
            return False
        normalized = node_url.rstrip("/") + "/"
        return path.startswith(normalized)

    def recurse(node: MenuItem) -> bool:
        matched = False
        if node.named_url and view_name and node.named_url == view_name:
            matched = True
        if not has_exact_view_match and _path_matches(node.resolved_url):
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
    """从根配置 layouts 读取指定布局下的 section 顺序。"""
    layout = _load_layout_config()
    value = layout.get(key) or []
    if isinstance(value, str):
        return [value]
    sections: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            sections.append(entry)
        elif isinstance(entry, dict) and "section" in entry:
            sections.append(entry.get("section"))  # type: ignore
    return sections


def _pick_section(section_slug: str) -> Optional[dict]:
    for s in _load_sections():
        if s.get("section") == section_slug:
            return s
    return None


def _iter_menu_refs(section: dict) -> list[str]:
    # 兼容 include / include_menus 字段
    include = section.get("include") or section.get("include_menus") or []
    if isinstance(include, str):
        return [include]
    return list(include)


def _prune_empty_headers(items: list[MenuItem]) -> list[MenuItem]:
    """移除没有可见子项的分组头，递归保持顺序。"""
    pruned: list[MenuItem] = []
    for item in items:
        if item.children:
            item.children = _prune_empty_headers(item.children)
        if item.is_group_header and not item.children:
            continue
        pruned.append(item)
    return pruned


def get_section_menu(section_slug: str, user, request=None) -> list[MenuItem]:
    """根据 section 获取菜单项列表，并可选根据 request 标记 active/expanded。"""
    app_menus = _load_app_menus()
    section = _pick_section(section_slug)
    if not section:
        return []

    items: list[MenuItem] = []
    for menu_ref in _iter_menu_refs(section):
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
    items = _prune_empty_headers(items)

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


def get_all_menus() -> dict[str, dict]:
    """公开的菜单字典（便于模板标签推断）。"""
    return _load_app_menus()

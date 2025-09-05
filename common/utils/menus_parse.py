# common/utils/menus_parse.py

from django.urls import reverse, NoReverseMatch

import yaml
from importlib import resources
from urllib.parse import urlencode


def _load_menus_from_app_yaml(app_name: str) -> list[dict]:
    """
    从指定应用的 menus.yaml 文件中加载菜单配置并解析成字典列表，不存在则返回空列表。
    Args:
        app_name (str): 应用名称
    Returns:
        list(dict): 菜单配置字典列表
    """
    try:
        with (
            resources.files(app_name)
            .joinpath("menus.yml")
            .open("r", encoding="utf-8") as f
        ):
            data = yaml.safe_load(f.read()) or []
            return data if isinstance(data, list) else []
    except (FileNotFoundError, ModuleNotFoundError):
        return []
    except Exception as e:
        print(f"加载 {app_name} 的 menus.yaml 时出错: {e}")
        return []


def _resolve_menu_item_url(item: dict) -> str:
    """
    解析菜单项的最终URL
    Args:
        item (dict): 菜单项字典
    Returns:
        str: 解析后的URL
    """
    if item.get("is_group_header"):
        return "#"
    if item.get("external_url"):
        return item["external_url"]
    if item.get("named_url"):
        try:
            url = reverse(item["named_url"], kwargs=item.get("url_kwargs", {}))
        except NoReverseMatch:
            return "#"
        if item.get("url_query") or {}:
            url += "?" + urlencode(item["url_query"])
        return url
    return "#"


def _perm_match(user, item: dict) -> bool:
    """
    检查用户是否满足显示菜单项的权限和登录要求: 默认登录可见
    Args:
        user (User): 用户实例
        item (dict): 菜单项字典
    Returns:
        bool: 用户是否满足要求
    """
    if item.get("login_required", True) and not user.is_authenticated:
        return False
    # 兼容旧字段 required_perms（YAML 中用户当前使用），优先使用新字段 permissions
    perms = item.get("permissions") or item.get("required_perms") or []
    if not perms:
        return True
    if item.get("perm_match_all", True):
        return all(user.has_perm(p) for p in perms)
    else:
        return any(user.has_perm(p) for p in perms)


def _map_menu_items(item: dict, request) -> dict | None:
    """
    将菜单项字典映射为前端需要的格式，并过滤不可见项
    Args:
        items (dict): 菜单项字典
        request (HttpRequest): 当前请求对象
    Returns:
        dict | None: 映射后的菜单项字典，若不可见则返回 None
    """
    if item.get("is_visible") is False:
        return None

    user = request.user
    if not _perm_match(user, item):
        return None

    mapped = {
        "name": item.get("name"),
        "icon": item.get("icon", None),
        "url": _resolve_menu_item_url(item),
        "css_classes": item.get("css_classes", ""),
        "target_blank": item.get("target_blank", False),
        "htmx_attrs": item.get("htmx_attrs", {}) or {},
        "is_group_header": item.get("is_group_header", False),
        # 传递计算后的权限列表（仅用于调试或前端需要显示，可选）
        "_perms": item.get("permissions") or item.get("required_perms") or [],
        "children": [],
    }
    for child in item.get("children", []):
        mapped_child = _map_menu_items(child, request)
        if mapped_child:
            mapped["children"].append(mapped_child)

    if mapped["is_group_header"] and not mapped["children"]:
        return None
    return mapped


def build_menu_tree_for_app(request, app_name: str) -> list[dict]:
    """
    构建指定应用的菜单树，包含权限和可见性过滤
    Args:
        request (HttpRequest): 当前请求对象
        app_name (str): 应用名称
    Returns:
        list(dict): 菜单树列表
    """
    raw_items = _load_menus_from_app_yaml(app_name)
    tree = []
    for item in raw_items:
        mapped_item = _map_menu_items(item, request)
        if mapped_item:
            tree.append(mapped_item)

    return tree


def _build_menu_tree_for_specified_menus_file(request, file) -> list[dict]:
    """
    构建指定菜单列表的菜单树，包含权限和可见性过滤
    Args:
        request (HttpRequest): 当前请求对象
        specified_menu (list(dict)): 菜单项字典列表
    Returns:
        list(dict): 菜单树列表
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            menus_list = yaml.safe_load(f.read()) or []
            if not isinstance(menus_list, list):
                return []
    except Exception as e:
        print(f"加载指定菜单文件 {file} 时出错: {e}")
        return []
    
    tree = []
    for item in menus_list:
        mapped_item = _map_menu_items(item, request)
        if mapped_item:
            tree.append(mapped_item)
    return tree



def build_menu_tree_for_flatpages(request) -> list[dict]:
    """
    构建简单页面菜单树
    Args:
        request (HttpRequest): 当前请求对象
    Returns:
        list(dict): 菜单树列表
    """
    flatpage_menus = resources.files("common").joinpath("menus/menus_flatpage.yml")
    return _build_menu_tree_for_specified_menus_file(request, flatpage_menus)


def build_menu_tree_for_header(request) -> list[dict]:
    """
    构建顶部菜单树
    """
    header_menus = resources.files("common").joinpath("menus/menus_header.yml")
    return _build_menu_tree_for_specified_menus_file(request, header_menus)

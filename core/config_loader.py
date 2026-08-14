from pathlib import Path

import yaml


class ConfigurationError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigurationError(
                f"{loader.name}:{key_node.start_mark.line + 1}: YAML 键 {key!r} 重复。"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml_mapping(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as stream:
            loader = UniqueKeyLoader(stream)
            loader.name = str(path)
            try:
                data = loader.get_single_data()
            finally:
                loader.dispose()
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"无法读取配置 {path}：{exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"配置 {path} 顶层必须是 mapping。")
    return data

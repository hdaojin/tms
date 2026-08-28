from .registry import PARSER_DEFINITIONS, default_parser_key


def parser_config_records(*, force, database_is_empty):
    registry_default = default_parser_key()
    records = []
    for order, definition in enumerate(PARSER_DEFINITIONS.values()):
        record = {
            "parser_key": definition.key,
            "display_name": definition.display_name,
            "alias": definition.alias,
            "description": definition.description,
            "is_enabled": True,
            "is_default": definition.key == registry_default,
            "order": order,
        }
        if not force and not database_is_empty:
            record["__create_defaults__"] = {"is_enabled": False, "is_default": False}
        records.append(record)
    return records


def registry_default_key():
    return default_parser_key()


BOOTSTRAP_DATA = [
    {
        "label": "评分表解析器运行配置",
        "model": "scoring.ScoringParserConfig",
        "key_fields": ("parser_key",),
        "records_factory": parser_config_records,
        "required_default_key_factory": registry_default_key,
        "require_managed_database_keys": True,
        "unmanaged_key_error": "数据库解析器配置 {key} 已不在 Registry 中，请通过明确的数据迁移或人工处理恢复不变量。",
        "default_switch_field": "is_default",
        "default_switch_scope_fields": (),
    },
]

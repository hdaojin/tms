from django.core.exceptions import ValidationError

from .models import ScoringParserConfig
from .registry import PARSER_DEFINITIONS, default_parser_key


def bootstrap_defaults():
    registry_default = default_parser_key()
    if registry_default not in PARSER_DEFINITIONS:
        raise ValidationError('评分解析器注册表的默认 key 不存在，请先修正代码配置。')

    database_was_empty = not ScoringParserConfig.objects.exists()
    created_count = 0
    existing_count = 0
    for order, definition in enumerate(PARSER_DEFINITIONS.values()):
        _config, created = ScoringParserConfig.objects.get_or_create(
            parser_key=definition.key,
            defaults={
                'display_name': definition.display_name,
                'alias': definition.alias,
                'description': definition.description,
                'is_enabled': database_was_empty,
                'is_default': database_was_empty and definition.key == registry_default,
                'order': order,
            },
        )
        created_count += int(created)
        existing_count += int(not created)
    return {'created': created_count, 'existing': existing_count}

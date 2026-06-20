from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class ParserDefinition:
    key: str
    display_name: str
    alias: str
    description: str
    template_filename: str
    parse_function_path: str

    @property
    def template_path(self) -> Path:
        return settings.BASE_DIR / "scoring" / "resources" / "templates" / self.template_filename

    def parse(self, file_or_path: Any, **kwargs):
        parse_function = import_string(self.parse_function_path)
        return parse_function(file_or_path, **kwargs)


CMP_SINGLE_MODULE_V1 = "cmp_single_module_v1"

PARSER_DEFINITIONS = {
    CMP_SINGLE_MODULE_V1: ParserDefinition(
        key=CMP_SINGLE_MODULE_V1,
        display_name="CMP 单模块评分表",
        alias="CMP v1",
        description="严格解析 CMP 官方单模块评分表模板，支持 M 测量评分点和 J 评价四档分档。",
        template_filename="cpm_48th_wsc_marking_scheme_template_v5.0.xlsx",
        parse_function_path="scoring.parser.parse_marking_workbook",
    ),
}


def get_parser_definition(parser_key: str) -> ParserDefinition:
    return PARSER_DEFINITIONS[parser_key]


def default_parser_key() -> str:
    return CMP_SINGLE_MODULE_V1


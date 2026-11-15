from math import isfinite

from django.core.exceptions import ValidationError

from .providers import provider_definition

SAMPLING_PARAMETERS = {
    "temperature": (
        "采样温度（temperature）",
        "数值越低，回答通常越稳定。数值越高，回答通常越多样。范围为 0–2，留空使用接口默认值。",
        2,
    ),
    "top_p": (
        "核采样范围（top_p）",
        "控制模型从多大的候选概率范围内选择词语。数值越低，回答通常越集中。范围为 0–1，留空使用接口默认值。",
        1,
    ),
}
THINKING_HELP = "开启后，模型会在回答前进行更多推理，可能增加等待时间和费用。"
EFFORT_HELP = "强度越高，模型通常投入更多推理，适合复杂任务，也可能更慢。"


def sampling_value(name, value):
    label, _, maximum = SAMPLING_PARAMETERS[name]
    if type(value) not in (float, int) or not 0 <= value <= maximum or not isfinite(value):
        raise ValidationError({name: f"{label}应在 0–{maximum} 之间。"})
    return value


def supported_sampling_parameters(provider, model_id):
    from litellm import get_supported_openai_params

    adapter = provider_definition(provider)
    return set(get_supported_openai_params(
        model=f"{adapter.route}/{model_id}", custom_llm_provider=adapter.route,
    ) or ())


def sampling_arguments(model, thinking, *, adapter=None):
    suppress_temperature = thinking == "enabled" and (adapter or provider_definition(model.provider)).thinking
    return {
        name: value for name, value in getattr(model, "request_parameters", {}).items()
        if name in SAMPLING_PARAMETERS
        and (name != "temperature" or not suppress_temperature)
    }

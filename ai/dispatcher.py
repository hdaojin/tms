from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

from .llm.client import GenerationRequest, invoke
from .models import AIModelPreference
from .providers import ProviderError, supports_images, supports_thinking
from .services import model_key, usable_models

__all__ = ["GenerationRequest", "ProviderError", "generate", "generate_text", "supports_images", "supports_thinking"]


@sensitive_variables()
def generate(user, request, *, model_id=None, revision=None):
    if model_id is None:
        model_id = AIModelPreference.objects.filter(user=user).values_list("model_id", flat=True).first()
    models = usable_models(user).filter(pk=model_id)
    if revision is not None:
        models = models.filter(revision=revision)
    model = models.first()
    if model is None:
        raise ValidationError("所选模型已变更或已不可用，请重新选择。")
    return invoke(model, request, model_key(model))


def generate_text(user, model_id, revision, payload):
    if isinstance(payload, GenerationRequest):
        request = payload
    else:
        request = GenerationRequest(
            messages=payload.get("messages", []),
            max_output_tokens=payload.get("max_tokens", 16000),
            response_mode="json" if payload.get("response_format") else "text",
            thinking=payload.get("thinking", {}).get("type", ""),
            reasoning_effort=payload.get("reasoning_effort", ""),
        )
    return generate(user, request, model_id=model_id, revision=revision)

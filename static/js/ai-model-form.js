(() => {
  for (const options of document.querySelectorAll("[data-ai-thinking-options]")) {
    const thinking = options.querySelector('[name="thinking"]');
    const effort = options.querySelector("[data-ai-reasoning-effort]");
    const update = () => { effort.hidden = thinking.value !== "enabled"; };
    thinking.addEventListener("change", update);
    update();
  }

  const form = document.getElementById("ai-model-form");
  if (!form) return;

  const catalog = JSON.parse(document.getElementById("ai-provider-catalog").textContent);
  const provider = form.elements.namedItem("provider");
  const address = form.elements.namedItem("base_url");
  const shownDefault = form.elements.namedItem("shown_default_base_url");
  const hint = document.getElementById("ai-api-default");
  const model = form.elements.namedItem("model_choice");
  const manual = document.getElementById("ai-manual-model");

  function showManualField() {
    manual.hidden = Boolean(model.value);
  }

  function updateChoices() {
    const entry = catalog[provider.value];
    const defaultAddress = entry?.default ?? "";
    shownDefault.value = defaultAddress;
    hint.textContent = defaultAddress ? `留空将使用 ${defaultAddress}` : "";
    const options = entry?.models ?? [];
    model.replaceChildren(
      new Option("手动输入模型 ID", ""),
      ...options.map(({id, label}) => new Option(label, id)),
    );
    model.value = entry?.default_model ?? "";
    showManualField();
  }

  provider.addEventListener("change", () => {
    address.value = "";
    const entry = catalog[provider.value];
    const thinking = form.elements.namedItem("thinking");
    thinking.value = entry?.thinking ?? "disabled";
    form.elements.namedItem("reasoning_effort").value = entry?.reasoning_effort || "high";
    thinking.dispatchEvent(new Event("change"));
    updateChoices();
  });
  model.addEventListener("change", showManualField);
  showManualField();
})();

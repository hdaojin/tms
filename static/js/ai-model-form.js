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
  const key = form.elements.namedItem("api_key");
  const id = form.elements.namedItem("model_id");
  const shownDefault = form.elements.namedItem("shown_default_base_url");
  const hint = document.getElementById("ai-api-default");
  const model = form.elements.namedItem("model_choice");
  const manual = document.getElementById("ai-manual-model");
  const advanced = document.getElementById("ai-advanced");
  const thinking = form.elements.namedItem("thinking");
  const effort = form.elements.namedItem("reasoning_effort");
  const drafts = new Map();
  let activeProvider = provider.value;
  const discovery = document.getElementById("ai-discovery");
  const discoverButton = discovery.querySelector("button");
  const discoverStatus = discovery.querySelector('[role="status"]');
  const discoveredModels = discovery.querySelector("select");
  const discoveredLabel = discoveredModels.closest("label");
  let lookup;

  function clearDiscovery() {
    lookup?.abort();
    lookup = null;
    discoverButton.disabled = false;
    discoverStatus.textContent = "";
    discoveredLabel.hidden = true;
    discoveredModels.replaceChildren();
    const entry = catalog[provider.value];
    discovery.hidden = !(entry?.enabled && entry.discovery);
  }

  discoverButton.addEventListener("click", async () => {
    clearDiscovery();
    const request = new AbortController();
    lookup = request;
    discoverButton.disabled = true;
    discoverStatus.textContent = "正在获取模型列表…";
    const data = new FormData();
    for (const name of ["csrfmiddlewaretoken", "provider", "base_url", "shown_default_base_url", "api_key"]) {
      data.set(name, form.elements.namedItem(name).value);
    }
    const timeout = setTimeout(() => request.abort(), 15000);
    try {
      const response = await fetch(discoverButton.dataset.url, {
        method: "POST",
        body: data,
        signal: request.signal,
        redirect: "error",
      });
      const result = await response.json();
      if (lookup !== request) return;
      if (!response.ok) {
        discoverStatus.textContent = result.error || "获取模型列表失败，可手动输入模型 ID。";
      } else if (result.models.length) {
        discoveredModels.replaceChildren(
          new Option("请选择模型", ""),
          ...result.models.map(value => new Option(value, value)),
        );
        discoveredLabel.hidden = false;
        discoverStatus.textContent = "选择后将填入模型 ID。保存后仍需发起连接测试。";
      } else {
        discoverStatus.textContent = "未获取到可选的模型 ID，可手动输入。";
      }
    } catch {
      if (lookup === request) discoverStatus.textContent = "获取模型列表失败，可手动输入模型 ID。";
    } finally {
      clearTimeout(timeout);
      if (lookup === request) {
        lookup = null;
        discoverButton.disabled = false;
      }
    }
  });
  discoveredModels.addEventListener("change", () => {
    if (!discoveredModels.value) return;
    model.value = "";
    id.value = discoveredModels.value;
    showFields();
  });
  address.addEventListener("input", clearDiscovery);
  key.addEventListener("input", clearDiscovery);

  function showFields() {
    manual.hidden = Boolean(model.value) && !id.value;
    advanced.hidden = provider.value !== "deepseek";
    thinking.disabled = advanced.hidden;
    effort.disabled = advanced.hidden;
  }

  provider.addEventListener("change", () => {
    if (key.value && !window.confirm("切换提供商会清空已输入的 API 密钥，是否继续？")) {
      provider.value = activeProvider;
      return;
    }
    drafts.set(activeProvider, {
      address: address.value, id: id.value, model: model.value, thinking: thinking.value, effort: effort.value,
    });
    activeProvider = provider.value;
    const entry = catalog[activeProvider];
    const draft = drafts.get(activeProvider);
    key.value = "";
    address.value = draft?.address ?? "";
    id.value = draft?.id ?? "";
    shownDefault.value = entry?.default ?? "";
    hint.textContent = shownDefault.value ? `留空将使用 ${shownDefault.value}` : "请输入 API 地址。";
    model.replaceChildren(
      new Option("手动输入模型 ID", ""),
      ...(entry?.models ?? []).map(({id, label}) => new Option(label, id)),
    );
    model.value = draft?.model ?? entry?.default_model ?? "";
    thinking.value = draft?.thinking ?? entry?.thinking ?? "disabled";
    effort.value = draft?.effort ?? (entry?.reasoning_effort || "high");
    thinking.dispatchEvent(new Event("change"));
    clearDiscovery();
    showFields();
  });
  model.addEventListener("change", () => {
    if (id.value && model.value && id.value !== model.value) {
      if (window.confirm("使用推荐模型将清空已填写的手动模型 ID，是否继续？")) id.value = "";
      else model.value = "";
    }
    showFields();
  });
  clearDiscovery();
  showFields();
})();

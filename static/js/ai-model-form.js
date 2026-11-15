(() => {
  document.addEventListener("change", event => {
    if (!event.target.matches('[name="mode"]')) return;
    const recipients = event.target.form?.querySelector("[data-ai-share-recipients]");
    if (recipients) recipients.hidden = recipients.disabled = event.target.value !== "selected";
  });

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
  const input = name => form.elements.namedItem(name);
  const provider = input("provider");
  const address = input("base_url");
  const key = input("api_key");
  const modelId = input("model_id");
  const shownDefault = input("shown_default_base_url");
  const customName = input("custom_provider_name");
  const discovery = document.getElementById("ai-discovery");
  const discoverButton = discovery.querySelector("button");
  const discoverStatus = discovery.querySelector('[role="status"]');
  const modelPicker = document.getElementById("ai-model-picker");
  const modelResults = document.getElementById("ai-model-results");
  const modelNoResults = document.getElementById("ai-model-no-results");
  const modelSource = document.getElementById("ai-model-source");
  const capabilities = document.getElementById("ai-model-capabilities");
  const advanced = document.getElementById("ai-advanced");
  const parameters = [...advanced.querySelectorAll("[data-ai-parameter]")].map(block => ({
    block,
    name: block.dataset.aiParameter,
    recommendation: block.querySelector("[data-ai-recommendation]"),
    field: input(block.dataset.aiParameter),
  }));
  const providerDrafts = new Map();
  const parameterDrafts = new Map();
  const savedProvider = form.dataset.savedProvider;
  const savedAddress = form.dataset.savedAddress;
  let activeProvider = provider.value;
  let parameterContext;
  let discovered = new Set();
  let candidates = new Map();
  let verified = new Set();
  let verificationRequest;
  let verificationTimer;
  let candidateQuery = "";
  let lookup;

  function currentEntry() {
    return catalog[provider.value] ?? {};
  }

  function currentAddress() {
    return (address.value.trim() || shownDefault.value).replace(/\/+$/, "");
  }

  function recommendedModels() {
    return provider.value === "custom" ? [] : (currentEntry().models ?? []);
  }

  function refreshCandidates() {
    candidates = new Map(recommendedModels().map(({id, label}) => [id, `${label} · 系统预设`]));
    for (const id of discovered) {
      candidates.set(id, candidates.has(id) ? `${candidates.get(id)} / 在线获取` : "在线获取");
    }
    modelPicker.hidden = !candidates.size;
    refreshVerification();
  }

  function refreshVerification() {
    verificationRequest?.abort();
    clearTimeout(verificationTimer);
    verified = new Set();
    renderCandidates();
    if (!candidates.size || !currentAddress()) return;
    verificationTimer = setTimeout(async () => {
      const request = new AbortController();
      verificationRequest = request;
      const data = new FormData();
      data.set("csrfmiddlewaretoken", input("csrfmiddlewaretoken").value);
      data.set("provider", provider.value);
      data.set("base_url", currentAddress());
      for (const id of [...candidates.keys()].slice(0, 400)) data.append("model_ids", id);
      try {
        const response = await fetch(modelPicker.dataset.verificationUrl, {
          method: "POST", body: data, signal: request.signal, redirect: "error",
        });
        if (!response.ok) return;
        const result = await response.json();
        if (request.signal.aborted) return;
        verified = new Set(result.models);
        for (const button of modelResults.querySelectorAll("[data-model-id]")) {
          if (verified.has(button.dataset.modelId)) button.append(verificationBadge());
        }
      } catch {
        // The candidate list remains usable if verification status is unavailable.
      }
    }, 250);
  }

  function verificationBadge() {
    const badge = document.createElement("span");
    badge.className = "badge badge-success badge-sm shrink-0";
    badge.textContent = "已有配置通过验证";
    return badge;
  }

  function renderCandidates() {
    const matches = [...candidates].filter(([id, label]) =>
      `${id} ${label}`.toLowerCase().includes(candidateQuery.trim().toLowerCase()));
    modelNoResults.hidden = Boolean(matches.length);
    modelResults.hidden = !matches.length;
    modelResults.replaceChildren(...matches.map(([id, label]) => {
      const row = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.modelId = id;
      button.className = "btn btn-ghost h-auto w-full flex-wrap justify-start whitespace-normal py-2 text-left";
      const name = document.createElement("span");
      name.className = "min-w-0 break-all";
      name.textContent = `${id} · ${label}`;
      button.append(name);
      if (verified.has(id)) button.append(verificationBadge());
      button.addEventListener("click", () => {
        modelId.value = id;
        candidateQuery = "";
        renderCandidates();
        modelId.focus();
        updateModel();
      });
      row.append(button);
      return row;
    }));
  }

  function clearDiscovery() {
    lookup?.abort();
    lookup = null;
    discovered = new Set();
    discoverButton.disabled = false;
    discoverStatus.textContent = "";
    const entry = currentEntry();
    discovery.hidden = !(entry.enabled && entry.discovery);
    refreshCandidates();
  }

  function updateConnection() {
    const entry = currentEntry();
    const sameEndpoint = provider.value === savedProvider && currentAddress() === savedAddress;
    document.getElementById("ai-provider-selection").textContent =
      provider.value === "custom" ? "自定义 API" : entry.label || "选择提供商";
    document.getElementById("ai-protocol").textContent = entry.protocol || "—";
    document.getElementById("ai-custom-provider").hidden = provider.value !== "custom";
    document.getElementById("ai-api-default").textContent = shownDefault.value
      ? `留空将使用 ${shownDefault.value}` : "请输入完整的 API 地址。";
    document.getElementById("ai-address-source").textContent = currentAddress()
      ? currentAddress() === entry.official ? "提供商内置地址"
        : currentAddress() === entry.default?.replace(/\/+$/, "") && provider.value !== "custom"
          ? "管理员配置的默认地址" : "自定义地址"
      : "";
    address.required = !shownDefault.value;
    key.required = Boolean(entry.key_required && !sameEndpoint);
    document.getElementById("ai-key-required").textContent = key.required && savedProvider
      ? "更换提供商或 API 地址后，请输入当前地址的密钥。"
      : entry.key_required ? "" : "此接入可在服务未启用认证时留空密钥。";
  }

  function updateModel() {
    const id = modelId.value.trim();
    const recommended = recommendedModels().find(option => option.id === id);
    const entry = currentEntry();
    const option = entry.trusted?.includes(currentAddress())
      ? (entry.models ?? []).find(item => item.id === id) : undefined;
    modelSource.hidden = !id;
    modelSource.textContent = !id ? ""
      : discovered.has(id) ? "在线获取" : recommended ? "系统预设" : "手动输入";

    const badges = [];
    if (option) {
      badges.push("文本生成");
      if (option.images && (!option.builtin || currentAddress() === entry.official)) badges.push("图片输入");
      if (option.json) badges.push("JSON 输出");
      if (Object.hasOwn(option.presets, "thinking")) badges.push("思考模式");
    }
    capabilities.replaceChildren(...(badges.length ? badges : ["待确认"]).map(label => {
      const badge = document.createElement("span");
      badge.className = "badge badge-ghost";
      badge.textContent = label;
      return badge;
    }));
    if (badges.length) {
      const source = document.createElement("span");
      source.className = "text-xs text-base-content/60";
      source.textContent = option.builtin ? "内置能力" : "提供商目录";
      capabilities.append(source);
    }

    const presets = option && !option.builtin ? option.presets : {};
    const context = JSON.stringify([provider.value, currentAddress(), id]);
    if (parameterContext !== undefined && parameterContext !== context) {
      advanced.open = false;
      parameterDrafts.set(parameterContext, Object.fromEntries(parameters.map(({name, field}) => [name, field.value])));
      const previous = parameterDrafts.get(context);
      for (const {name, field} of parameters) {
        field.value = previous?.[name] ?? (savedProvider ? "" : presets[name] ?? "");
      }
    }
    parameterContext = context;

    const thinkingEnabled = Object.hasOwn(presets, "thinking") && input("thinking").value === "enabled";
    advanced.hidden = !Object.keys(presets).length;
    for (const {block, name, recommendation, field} of parameters) {
      const configured = Object.hasOwn(presets, name);
      const available = configured && (name !== "reasoning_effort" || thinkingEnabled);
      const hasError = Boolean(block.querySelector(".alert-error"));
      block.hidden = !available && !hasError;
      field.disabled = !available;
      const value = presets[name];
      const label = field instanceof HTMLSelectElement
        ? [...field.options].find(option => option.value === String(value))?.textContent : value;
      recommendation.textContent = configured && value !== null && value !== "" && label != null
        ? `建议值：${label}` : "";
      if (name === "temperature" && currentEntry().provider_key === "deepseek" && thinkingEnabled) {
        recommendation.textContent = "DeepSeek 开启思考模式时，采样温度不生效。";
      }
    }
  }

  discoverButton.addEventListener("click", async () => {
    clearDiscovery();
    const request = new AbortController();
    lookup = request;
    discoverButton.disabled = true;
    discoverStatus.textContent = "正在获取模型列表…";
    const data = new FormData();
    for (const name of ["csrfmiddlewaretoken", "provider", "base_url", "shown_default_base_url", "api_key"]) {
      data.set(name, input(name).value);
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
      } else {
        discovered = new Set(result.models);
        candidateQuery = "";
        refreshCandidates();
        updateModel();
        discoverStatus.textContent = discovered.size
          ? `已获取 ${discovered.size} 个模型。可在候选模型中选择。`
          : "未获取到可选的模型 ID，可手动输入。";
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

  address.addEventListener("input", () => {
    clearDiscovery();
    updateConnection();
    updateModel();
  });
  key.addEventListener("input", () => {
    clearDiscovery();
    updateModel();
  });
  modelId.removeAttribute("list");
  modelId.addEventListener("input", () => {
    candidateQuery = modelId.value;
    renderCandidates();
    updateModel();
  });
  input("thinking").addEventListener("change", updateModel);
  advanced.addEventListener("invalid", () => { advanced.open = true; }, true);

  provider.addEventListener("change", () => {
    if (provider.value === activeProvider) return;
    if (key.value && !window.confirm("切换提供商会清空已输入的 API Key，是否继续？")) {
      provider.value = activeProvider;
      return;
    }
    providerDrafts.set(activeProvider, {address: address.value, id: modelId.value, name: customName.value});
    activeProvider = provider.value;
    const draft = providerDrafts.get(activeProvider);
    const entry = currentEntry();
    key.value = "";
    shownDefault.value = activeProvider === savedProvider ? savedAddress : entry.default ?? "";
    address.value = draft?.address ?? shownDefault.value;
    modelId.value = draft?.id ?? (activeProvider === "custom" ? "" : entry.default_model ?? "");
    customName.value = draft?.name ?? "";
    candidateQuery = "";
    clearDiscovery();
    updateConnection();
    updateModel();
  });

  const picker = document.getElementById("ai-provider-picker");
  const dialog = document.getElementById("ai-provider-dialog");
  const search = dialog.querySelector('input[type="search"]');
  const groups = [...dialog.querySelectorAll("[data-ai-provider-group]")];
  function filterProviders() {
    const query = search.value.trim().toLowerCase();
    for (const group of groups) {
      const buttons = [...group.querySelectorAll("[data-ai-provider]")];
      for (const button of buttons) {
        button.hidden = !`${button.textContent} ${button.dataset.aiProvider}`.toLowerCase().includes(query);
      }
      group.hidden = !buttons.some(button => !button.hidden);
    }
    dialog.querySelector("[data-ai-provider-empty]").hidden = groups.some(group => !group.hidden);
  }
  if (typeof dialog.showModal === "function") {
    document.getElementById("ai-provider-fallback").hidden = true;
    picker.hidden = false;
    picker.querySelector("button").addEventListener("click", () => {
      search.value = "";
      filterProviders();
      dialog.showModal();
    });
    search.addEventListener("input", filterProviders);
    dialog.querySelector("[data-ai-close]").addEventListener("click", () => dialog.close());
    for (const button of dialog.querySelectorAll("[data-ai-provider]")) {
      button.addEventListener("click", () => {
        provider.value = button.dataset.aiProvider;
        provider.dispatchEvent(new Event("change"));
        dialog.close();
      });
    }
  }

  clearDiscovery();
  updateConnection();
  updateModel();
})();

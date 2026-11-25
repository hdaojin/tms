const editor = document.querySelector("[data-log-editor]");

function initReasoningSettings(form) {
  const section = form.querySelector("[data-log-reasoning]");
  if (!section) return;

  const settings = JSON.parse(document.getElementById("training-log-reasoning-settings").textContent);
  const thinkingGroup = section.querySelector("[data-log-thinking]");
  const effortGroup = section.querySelector("[data-log-effort]");
  const { model, thinking, effort } = form.elements;

  function updateSettings() {
    const current = settings[model.value];
    const showEffort = current?.effort && (thinking.value || current.default_thinking) === "enabled";
    section.hidden = !current;
    thinkingGroup.hidden = !current;
    thinkingGroup.disabled = !current;
    effortGroup.hidden = !showEffort;
    effortGroup.disabled = !showEffort;
    if (!showEffort) effort.value = "";
  }

  model.addEventListener("change", () => {
    thinking.value = "";
    effort.value = "";
    updateSettings();
  });
  thinking.addEventListener("change", updateSettings);
  updateSettings();
}

if (editor) {
  initReasoningSettings(editor);
  const preview = document.createElement("form");
  preview.method = "post";
  preview.enctype = "multipart/form-data";
  preview.action = editor.action;
  preview.target = "training-log-preview";
  preview.hidden = true;
  document.body.append(preview);

  function refreshPreview() {
    preview.replaceChildren();
    const values = [
      ["action", "preview"],
      ["csrfmiddlewaretoken", editor.elements.csrfmiddlewaretoken.value],
      ["revision", editor.elements.revision.value],
      ...Array.from(editor.querySelectorAll("[data-log-section]"), (field) => [field.name, field.value]),
    ];
    for (const [name, value] of values) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      preview.append(input);
    }
    preview.submit();
  }

  let refreshTimer;
  editor.addEventListener("input", (event) => {
    if (!event.target.matches("[data-log-section]")) return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshPreview, 450);
  });
  editor.querySelector("[data-log-section][aria-invalid=true]")?.focus();
  if (!document.querySelector('iframe[name="training-log-preview"]').hasAttribute("src")) refreshPreview();
}

document.addEventListener("click", (event) => {
  const remove = event.target.closest("[data-remove-issue]");
  if (remove) {
    const row = remove.closest("[data-skill-domain-row]");
    row.querySelector('[name$="-DELETE"]').checked = true;
    row.hidden = true;
    row.closest("[data-completion-issues]").querySelector("[data-add-issue]").focus();
    return;
  }
  const button = event.target.closest("[data-add-issue]");
  if (!button) return;
  const fieldset = button.closest("[data-completion-issues]");
  const total = fieldset.querySelector('[name="issues-TOTAL_FORMS"]');
  const maximum = fieldset.querySelector('[name="issues-MAX_NUM_FORMS"]');
  const index = Number(total.value);
  if (index >= Number(maximum.value)) return;

  const template = fieldset.querySelector("[data-issue-template]");
  const rows = fieldset.querySelector("[data-issue-rows]");
  rows.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", String(index)));
  total.value = String(index + 1);
  button.disabled = Number(total.value) >= Number(maximum.value);
  document.dispatchEvent(new Event("tms:search-picker-added"));
  rows.lastElementChild.querySelector('select[name$="-domain"]').focus();
});

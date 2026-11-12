(() => {
  if (window.tmsChecklistEditorLoaded) return;
  window.tmsChecklistEditorLoaded = true;

  function updateAssignment(form) {
    const control = form.querySelector('[name="assign_all"]');
    const section = form.querySelector('[data-individual-assignment]');
    if (control && section) section.hidden = control.checked;
  }

  document.addEventListener("change", (event) => {
    if (event.target.matches('[data-task-editor] [name="assign_all"]')) updateAssignment(event.target.form);
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-subtask-add], [data-subtask-remove]");
    if (!button) return;
    if (button.hasAttribute("data-subtask-remove")) {
      button.closest("[data-subtask-row]").remove();
      return;
    }
    const editor = button.closest("[data-subtask-editor]");
    const rows = editor.querySelector("[data-subtask-rows]");
    if (rows.childElementCount >= 100) return;
    rows.append(editor.querySelector("template").content.cloneNode(true));
    rows.lastElementChild.querySelector("input").focus();
  });
})();

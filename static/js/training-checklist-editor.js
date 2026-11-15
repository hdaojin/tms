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
    const button = event.target.closest("[data-subtask-add], [data-subtask-remove], [data-subtask-move]");
    if (!button) return;
    const row = button.closest("[data-subtask-row]");
    if (button.dataset.subtaskMove) {
      const up = button.dataset.subtaskMove === "up";
      const neighbor = up ? row.previousElementSibling : row.nextElementSibling;
      if (!neighbor) return;
      if (up) neighbor.before(row);
      else neighbor.after(row);
      if (up ? row.previousElementSibling : row.nextElementSibling) button.focus();
      else row.querySelector("input").focus();
      return;
    }
    if (button.hasAttribute("data-subtask-remove")) {
      row.remove();
      return;
    }
    const editor = button.closest("[data-subtask-editor]");
    const rows = editor.querySelector("[data-subtask-rows]");
    if (rows.childElementCount >= 100) return;
    rows.append(editor.querySelector("template").content.cloneNode(true));
    rows.lastElementChild.querySelector("input").focus();
  });
})();

document.getElementById("log-generation-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "prepare") return;

  const form = event.currentTarget;
  const data = new FormData(form);
  const pending = data.getAll("images").some((file) => file.name) || data.has("progress_images");
  const warning = document.getElementById("unsaved-log-images");
  warning.hidden = !pending;
  if (pending) {
    event.preventDefault();
    warning.closest("details").open = true;
    form.querySelector('button[value="image"]').focus();
  }
});

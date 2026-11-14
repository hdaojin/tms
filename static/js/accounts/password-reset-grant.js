const resetForm = document.getElementById("password-reset-grant");
const fragmentToken = window.location.hash.slice(1);

if (fragmentToken) {
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

if (resetForm) {
  const tokenField = resetForm.elements.namedItem("token");
  const token = fragmentToken || tokenField.value;
  if (/^[A-Za-z0-9_-]{43}$/.test(token)) {
    tokenField.value = token;
    resetForm.querySelector('button[type="submit"]').disabled = false;
    document.getElementById("reset-link-missing").hidden = true;
  }
}

document.getElementById('role-search')?.addEventListener('input', (event) => {
  const query = event.target.value.trim().toLocaleLowerCase();
  document.querySelectorAll('[data-user-role-option]').forEach((option) => {
    option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
  });
});

document.querySelectorAll('[data-role-form]').forEach((form) => {
  form.querySelector('[data-bundle-search]').addEventListener('input', (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    form.querySelectorAll('[data-bundle-group]').forEach((group) => {
      group.querySelectorAll('[data-bundle-option]').forEach((option) => {
        option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
      });
      group.hidden = !Array.from(group.querySelectorAll('[data-bundle-option]')).some((option) => !option.hidden);
    });
  });
  form.querySelector('[data-member-search]').addEventListener('input', (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    form.querySelectorAll('[data-member-option]').forEach((option) => {
      option.hidden = !option.querySelector('input').checked && !option.textContent.toLocaleLowerCase().includes(query);
    });
  });
});

function filterStaff(event) {
  if (!event.target.matches('[data-staff-search], [data-staff-role]')) return;
  const section = event.target.closest('[data-staff-section]');
  const query = section.querySelector('[data-staff-search]').value.toLocaleLowerCase().replace(/\s+/g, '');
  const role = section.querySelector('[data-staff-role]').value;
  section.querySelectorAll('[data-staff-search-text]').forEach(item => {
    item.hidden = !item.dataset.staffSearchText.toLocaleLowerCase().replace(/\s+/g, '').includes(query)
      || (role && !item.dataset.staffRoles.split(' ').includes(role));
    if (item.hidden) item.querySelector('input[type=checkbox]').checked = false;
  });
}
document.addEventListener('input', filterStaff);
document.addEventListener('change', filterStaff);

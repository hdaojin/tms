// 日程交互只保留本计划的折叠偏好；权限和版本由服务器校验。
(() => {
  const dialogFor = id => document.getElementById(id === 'task-editor' ? 'task-dialog' : 'schedule-dialog');
  function mayDiscard(dialog) {
    return !dialog?.open || !dialog.dataset.dirty || window.confirm('当前内容尚未保存，确定放弃修改？');
  }
  const dayMs = 24 * 60 * 60 * 1000;
  const shanghaiOffsetMs = 8 * 60 * 60 * 1000;
  function shanghaiWeekStart(now) {
    const date = new Date(now + shanghaiOffsetMs);
    date.setUTCHours(0, 0, 0, 0);
    date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
    return date;
  }
  function weekState(root) {
    const result = root.closest?.('[data-plan-id]') || root.querySelector?.('[data-plan-id]');
    if (!result) return;
    const now = Date.now();
    const currentWeek = shanghaiWeekStart(now).toISOString().slice(0, 10);
    for (const button of result.querySelectorAll('[data-week-toggle]')) {
      let collapsed = button.dataset.weekToggle !== currentWeek;
      const key = `training-week:${result.dataset.planId}:${button.dataset.weekToggle}`;
      try {
        const preference = JSON.parse(localStorage.getItem(key));
        if (typeof preference?.collapsed === 'boolean' && preference.expiresAt > now) {
          collapsed = preference.collapsed;
        } else if (preference !== null) {
          localStorage.removeItem(key);
        }
      } catch {}
      button.setAttribute('aria-expanded', String(!collapsed));
      for (const row of result.querySelectorAll('[data-week]')) if (row.dataset.week === button.dataset.weekToggle) row.hidden = collapsed;
    }
  }
  function operationFields() {
    for (const form of document.querySelectorAll('[data-entry-operation]')) {
      const operation = form.elements.operation.value;
      const groups = { source: ['copy'], copy_mode: ['copy'], include_duty: ['copy', 'swap'], include_note: ['copy', 'swap'], first: ['swap'], second: ['swap'], days: ['schedule', 'copy', 'tasks', 'clear', 'unused'], date_from: ['schedule', 'copy', 'tasks', 'clear', 'unused'], date_to: ['schedule', 'copy', 'tasks', 'clear', 'unused'], weekdays: ['schedule', 'copy', 'tasks', 'clear', 'unused'], overwrite: ['copy', 'schedule'], state: ['schedule'], domain: ['schedule'], coaches: ['schedule'], primary_coach: ['schedule'], titles: ['tasks'], description: ['tasks'] };
      for (const [field, operations] of Object.entries(groups)) {
        const wrapper = form.querySelector(`[data-operation-field="${field}"]`);
        if (wrapper) wrapper.hidden = !operations.includes(operation);
      }
    }
  }
  function wholeCoachLists(root = document) {
    for (const checkbox of root.querySelectorAll('input[name$="-duty_all"], input[name$="-coaches_all"]')) {
      const name = checkbox.name.replace(/duty_all$/, 'duty_coaches').replace(/coaches_all$/, 'coaches');
      const field = checkbox.form?.elements.namedItem(name);
      if (field) {
        field.disabled = checkbox.checked;
        const duty = checkbox.name.endsWith('-duty_all');
        const domain = duty ? null : checkbox.form.elements.namedItem(checkbox.name.replace(/coaches_all$/, 'domain_choice'));
        if (duty || domain) {
          const slots = duty ? Array.from(checkbox.form.querySelectorAll?.('select[name^="slot-"][name$="-domain_choice"]') || []) : [];
          const optional = duty ? slots.length > 0 && slots.every(slot => ['rest', 'unused'].includes(slot.value)) : ['rest', 'unused'].includes(domain.value);
          field.required = !checkbox.name.startsWith('unified-') && !checkbox.checked && !optional;
          const legend = field.closest('fieldset')?.querySelector('legend');
          let star = legend?.querySelector('.text-error');
          if (legend && !star && field.required) { star = document.createElement('span'); star.className = 'text-error'; star.textContent = '*'; legend.append(star); }
          if (star) star.hidden = !field.required;
        }
      }
    }
  }
  document.addEventListener('change', () => { operationFields(); wholeCoachLists(); });
  document.addEventListener('input', event => {
    const dialog = event.target.closest('dialog');
    if (dialog) dialog.dataset.dirty = '1';
  });
  document.addEventListener('change', event => {
    const dialog = event.target.closest('dialog');
    if (dialog) dialog.dataset.dirty = '1';
  });
  document.addEventListener('click', event => {
    const applyDay = event.target.closest('[data-apply-day]');
    if (applyDay) {
      const form = applyDay.closest('form');
      const domain = form.elements.namedItem('unified-domain_choice');
      const coaches = form.elements.namedItem('unified-coaches');
      const all = form.elements.namedItem('unified-coaches_all');
      if (!domain.value) { domain.focus(); return; }
      const selected = new Set(Array.from(coaches.selectedOptions, option => option.value));
      if (!all.checked && !['rest', 'unused'].includes(domain.value) && !selected.size) { coaches.focus(); return; }
      for (const field of form.querySelectorAll('select[name$="-domain_choice"]')) {
        if (!field.name.startsWith('slot-')) continue;
        field.value = domain.value;
        const prefix = field.name.replace(/domain_choice$/, '');
        form.elements.namedItem(`${prefix}coaches_all`).checked = all.checked;
        for (const option of form.elements.namedItem(`${prefix}coaches`).options) option.selected = selected.has(option.value);
      }
      wholeCoachLists(form);
      const dialog = form.closest('dialog');
      if (dialog) dialog.dataset.dirty = '1';
      return;
    }
    const week = event.target.closest('[data-week-toggle]');
    if (week) {
      const result = week.closest('[data-plan-id]');
      const collapsed = week.getAttribute('aria-expanded') === 'true';
      week.setAttribute('aria-expanded', String(!collapsed));
      for (const row of result.querySelectorAll('[data-week]')) if (row.dataset.week === week.dataset.weekToggle) row.hidden = collapsed;
      const now = Date.now();
      const nextMonday = shanghaiWeekStart(now).getTime() + 7 * dayMs - shanghaiOffsetMs;
      const expiresAt = Math.min(now + dayMs, nextMonday);
      try {
        localStorage.setItem(`training-week:${result.dataset.planId}:${week.dataset.weekToggle}`, JSON.stringify({ collapsed, expiresAt }));
      } catch {}
      return;
    }
    const close = event.target.closest('form[method="dialog"]');
    if (close && !mayDiscard(close.closest('dialog'))) { event.preventDefault(); return; }
    const card = event.target.closest('[data-slot-edit]');
    if (card && !event.target.closest('a, button, input, summary, details')) {
      window.htmx.ajax('GET', card.dataset.slotEdit, { target: '#schedule-editor', swap: 'innerHTML' });
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-slot-edit]')) {
      event.preventDefault();
      window.htmx.ajax('GET', event.target.dataset.slotEdit, { target: '#schedule-editor', swap: 'innerHTML' });
    }
  });
  for (const dialog of document.querySelectorAll('#schedule-dialog, #task-dialog')) {
    dialog.addEventListener('cancel', event => { if (!mayDiscard(dialog)) event.preventDefault(); });
  }
  document.addEventListener('htmx:beforeRequest', event => {
    const target = event.detail.target;
    if (!['schedule-editor', 'task-editor'].includes(target?.id)) return;
    if (event.detail.elt?.closest?.('[data-schedule-reset]')) return;
    if (event.detail.requestConfig?.verb?.toLowerCase() === 'get' && !mayDiscard(dialogFor(target.id))) event.preventDefault();
  });
  document.addEventListener('htmx:afterSwap', event => {
    const target = event.detail.target;
    if (['schedule-editor', 'task-editor'].includes(target.id)) {
      const dialog = dialogFor(target.id);
      if (dialog) {
        dialog.dataset.dirty = target.querySelector('.errorlist, .alert-error') ? '1' : '';
        if (!dialog.open) dialog.showModal();
      }
    }
    weekState(target);
    wholeCoachLists(target);
  });
  weekState(document);
  wholeCoachLists();
  operationFields();
})();
  document.addEventListener('htmx:historyRestore', () => weekState(document));
  window.addEventListener('pageshow', event => { if (event.persisted) weekState(document); });

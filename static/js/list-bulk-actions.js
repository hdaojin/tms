// 委托事件兼容 HTMX 替换结果；选择状态仅存于当前结果表单。
(() => {
  function update(form) {
    const selectAll = form.querySelector('[data-select-all]');
    const all = Boolean(selectAll) && form.querySelector('[data-selection-mode]').value === 'all';
    const boxes = [...form.querySelectorAll('[data-row-selection]')];
    const count = boxes.filter(box => box.checked).length;
    const total = Number(form.dataset.matchingCount);
    for (const box of boxes) box.disabled = all;
    const page = form.querySelector('[data-select-page]');
    if (page) {
      page.disabled = all || boxes.length === 0;
      page.checked = all || (boxes.length > 0 && count === boxes.length);
      page.indeterminate = !all && count > 0 && count < boxes.length;
    }
    if (selectAll) selectAll.hidden = all || count === 0 || count !== boxes.length || total <= count;
    form.querySelector('[data-clear-selection]').hidden = !all;
    form.querySelector('[data-selection-error]').hidden = true;
    form.querySelector('[data-selection-status]').textContent = all
      ? `已选择全部 ${total} ${form.dataset.selectionLabel || '条记录'}（含全部分页）`
      : `已选择 ${count} ${form.dataset.selectionLabel || '条记录'}`;
  }
  document.addEventListener('click', event => {
    const form = event.target.closest('[data-bulk-list]');
    if (!form) return;
    if (event.target.closest('[data-select-all]')) {
      form.querySelector('[data-selection-mode]').value = 'all';
      update(form);
    }
    if (event.target.closest('[data-clear-selection]')) {
      form.querySelector('[data-selection-mode]').value = 'selected';
      for (const box of form.querySelectorAll('[data-row-selection]')) box.checked = false;
      update(form);
    }
  });
  document.addEventListener('change', event => {
    const form = event.target.closest('[data-bulk-list]');
    if (!form) return;
    if (event.target.matches('[data-select-page]')) {
      for (const box of form.querySelectorAll('[data-row-selection]')) box.checked = event.target.checked;
    }
    if (event.target.matches('[data-select-page], [data-row-selection]')) update(form);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-bulk-list]');
    if (!form) return;
    let message = '';
    if (!form.querySelector('[data-bulk-operation]').value) {
      message = '请选择要执行的操作。';
    } else if (form.querySelector('[data-selection-mode]').value === 'all' && !form.querySelector('[data-select-all]')) {
      message = '当前列表不支持选择全部匹配结果。';
    } else if (!(form.querySelector('[data-select-all]') && form.querySelector('[data-selection-mode]').value === 'all')
      && ![...form.querySelectorAll('[data-row-selection]')].some(box => box.checked)) {
      message = `请至少选择一${form.dataset.selectionLabel || '条记录'}。`;
    }
    if (message) {
      event.preventDefault();
      const error = form.querySelector('[data-selection-error]');
      error.textContent = message;
      error.hidden = false;
    }
  });
  function resetSelections(root = document) {
    const owner = root.closest?.('[data-bulk-list]');
    const forms = owner ? [owner] : root.querySelectorAll('[data-bulk-list]');
    for (const form of forms) {
      form.querySelector('[data-selection-mode]').value = 'selected';
      for (const box of form.querySelectorAll('[data-row-selection]')) box.checked = false;
      update(form);
    }
  }
  window.addEventListener('pageshow', () => resetSelections());
  document.addEventListener('htmx:afterSwap', event => resetSelections(event?.detail?.target || document));
  document.addEventListener('htmx:historyRestore', () => resetSelections());
})();

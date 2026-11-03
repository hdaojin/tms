(() => {
  function init(root) {
    if (root.dataset.bound) return;
    root.dataset.bound = 'true';
    const selected = root.querySelector('[data-plan-selected]');
    const dialog = root.querySelector('[data-plan-dialog]');
    const query = root.querySelector('[data-plan-query]');
    const results = root.querySelector('[data-plan-results]');
    const staged = root.querySelector('[data-plan-staged]');
    const status = root.querySelector('[data-plan-status]');
    const more = root.querySelector('[data-plan-more]');
    const initialPeople = [...selected.querySelectorAll('[data-person-id]')].map(node => ({
      id: node.dataset.personId, label: node.dataset.personLabel, unavailable: node.dataset.unavailable === 'true'
    }));
    let people = new Map(), page = 0, version = 0, timer;

    function badge(person, removable) {
      const span = document.createElement('span');
      span.className = 'badge badge-outline h-auto';
      span.dataset.personId = person.id;
      span.dataset.personLabel = person.label;
      span.dataset.unavailable = person.unavailable ? 'true' : 'false';
      span.append(document.createTextNode(person.label + (person.unavailable ? '（账号停用或缺少权限）' : '')));
      if (removable) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = ' ×';
        button.setAttribute('aria-label', '移除 ' + person.label);
        button.addEventListener('click', () => { people.delete(person.id); renderStaged(); });
        span.append(button);
      } else {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = root.dataset.fieldName;
        input.value = person.id;
        span.prepend(input);
      }
      return span;
    }
    function renderStaged() {
      staged.replaceChildren(...[...people.values()].map(person => badge(person, true)));
      for (const button of results.querySelectorAll('[data-result-id]')) {
        button.disabled = button.dataset.invalid === 'true' || people.has(button.dataset.resultId);
      }
    }
    async function search(next = false) {
      const term = query.value.trim();
      const current = ++version;
      if (!next) { page = 0; results.replaceChildren(); }
      if (!term) { status.textContent = '输入姓名或拼音开始搜索。'; more.hidden = true; return; }
      const url = new URL(root.dataset.searchUrl, window.location.origin);
      url.searchParams.set('q', term);
      url.searchParams.set('page', String(page + 1));
      status.textContent = '正在搜索…';
      try {
        const response = await fetch(url, { credentials: 'same-origin' });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (current !== version) return;
        page += 1;
        for (const item of data.results) {
          const person = { id: String(item.id), label: item.label, unavailable: false };
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn btn-outline btn-sm';
          button.dataset.resultId = person.id;
          button.dataset.invalid = item.invalid ? 'true' : 'false';
          button.textContent = person.label + (item.invalid ? '（同名备注未填写或重复）' : '');
          button.addEventListener('click', () => { people.set(person.id, person); renderStaged(); });
          results.append(button);
        }
        more.hidden = !data.has_more;
        status.textContent = data.results.length ? '' : '没有找到符合条件的人员。';
        renderStaged();
      } catch (_) {
        if (current === version) status.textContent = '搜索失败，请重试。';
      }
    }
    root.querySelector('[data-plan-open]').addEventListener('click', () => {
      ++version;
      people = new Map([...selected.querySelectorAll('[data-person-id]')].map(node => [
        node.dataset.personId,
        { id: node.dataset.personId, label: node.dataset.personLabel, unavailable: node.dataset.unavailable === 'true' }
      ]));
      query.value = '';
      results.replaceChildren();
      more.hidden = true;
      status.textContent = '输入姓名或拼音开始搜索。';
      renderStaged();
      dialog.showModal();
      query.focus();
    });
    query.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => search(), 250); });
    query.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        clearTimeout(timer);
        search();
      }
    });
    more.addEventListener('click', () => search(true));
    dialog.addEventListener('close', () => { ++version; clearTimeout(timer); });
    root.querySelector('[data-plan-cancel]').addEventListener('click', () => { ++version; dialog.close(); });
    root.querySelector('[data-plan-confirm]').addEventListener('click', () => {
      selected.replaceChildren(...[...people.values()].map(person => badge(person, false)));
      ++version;
      dialog.close();
    });
    root.closest('form')?.addEventListener('reset', () => {
      ++version;
      clearTimeout(timer);
      selected.replaceChildren(...initialPeople.map(person => badge(person, false)));
      if (dialog.open) dialog.close();
    });
  }
  function refresh() {
    document.querySelectorAll('[data-plan-people]').forEach(init);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refresh, { once: true });
  } else {
    refresh();
  }
  document.addEventListener('htmx:afterSwap', refresh);
})();

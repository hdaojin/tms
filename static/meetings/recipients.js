(function () {
  "use strict";

  class SelectionState {
    constructor(initial) {
      this.initial = initial.map((person) => ({ ...person, id: String(person.id) }));
      this.reset();
    }
    reset() {
      this.people = new Map(this.initial.map((person) => [person.id, { ...person }]));
    }
    add(person) {
      this.people.set(String(person.id), { ...person, id: String(person.id) });
    }
    remove(id) {
      this.people.delete(String(id));
    }
    has(id) {
      return this.people.has(String(id));
    }
  }

  function searchURL(base, origin, meetingId, query, page) {
    const url = new URL(base, origin);
    url.searchParams.set("q", query.trim());
    url.searchParams.set("page", String(page));
    if (meetingId) url.searchParams.set("meeting_id", meetingId);
    return url;
  }

  function initPicker(root) {
    if (root.dataset.bound === "true") return;
    root.dataset.bound = "true";
    const selected = root.querySelector("[data-recipient-selected]");
    const results = root.querySelector("[data-recipient-results]");
    const query = root.querySelector("[data-recipient-query]");
    const status = root.querySelector("[data-recipient-status]");
    const more = root.querySelector("[data-recipient-more]");
    const form = root.closest("form");
    const state = new SelectionState([...selected.querySelectorAll("[data-recipient-id]")].map((tag) => ({
      id: tag.dataset.recipientId,
      label: tag.dataset.recipientLabel,
      unavailable: tag.dataset.unavailable === "true",
    })));
    let timer;
    let controller;
    let version = 0;
    let page = 0;
    let activeQuery = "";
    let hasMore = false;
    let loading = false;

    function syncCandidates() {
      results.querySelectorAll("button[data-person-id]").forEach((button) => {
        button.disabled = state.has(button.dataset.personId);
        button.textContent = button.dataset.label + (button.disabled ? "（已选）" : "");
      });
    }

    function renderSelected() {
      selected.replaceChildren();
      state.people.forEach((person) => {
        const tag = document.createElement("span");
        tag.className = "badge badge-outline h-auto max-w-full gap-2 py-2";
        tag.dataset.recipientId = person.id;
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = root.dataset.fieldName;
        input.value = person.id;
        const label = document.createElement("span");
        label.className = "min-w-0 break-all whitespace-normal";
        label.textContent = person.label + (person.unavailable ? "（当前不可阅读）" : "");
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "shrink-0";
        remove.textContent = "×";
        remove.setAttribute("aria-label", "移除 " + person.label);
        remove.addEventListener("click", () => {
          state.remove(person.id);
          renderSelected();
          query.focus();
        });
        tag.append(input, label, remove);
        selected.append(tag);
      });
      syncCandidates();
    }

    function cancelSearch() {
      clearTimeout(timer);
      if (controller) controller.abort();
      version += 1;
      loading = false;
      root.removeAttribute("aria-busy");
      more.disabled = false;
    }

    function clearResults() {
      results.replaceChildren();
      more.hidden = true;
      hasMore = false;
      page = 0;
    }

    async function load(nextPage) {
      const text = query.value.trim();
      cancelSearch();
      if (!text) {
        clearResults();
        status.textContent = "请输入姓名或账号搜索人员。";
        return;
      }
      const requestVersion = version;
      controller = new AbortController();
      loading = true;
      more.disabled = true;
      root.setAttribute("aria-busy", "true");
      status.textContent = "正在搜索…";
      if (nextPage === 1) clearResults();
      try {
        const response = await fetch(searchURL(root.dataset.searchUrl, window.location.origin, root.dataset.meetingId, text, nextPage), {
          signal: controller.signal,
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!response.ok || response.redirected) throw new Error("search");
        const data = await response.json();
        if (requestVersion !== version) return;
        if (!Array.isArray(data.results)) throw new Error("search");
        data.results.forEach((person) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "btn btn-outline btn-sm h-auto max-w-full break-all whitespace-normal py-2";
          button.dataset.personId = String(person.id);
          button.dataset.label = person.label;
          button.addEventListener("click", () => {
            state.add(person);
            renderSelected();
            query.focus();
            status.textContent = "已选择 " + person.label;
          });
          results.append(button);
        });
        page = nextPage;
        activeQuery = text;
        hasMore = data.has_more === true;
        more.hidden = !hasMore;
        syncCandidates();
        status.textContent = results.childElementCount ? "选择结果可添加人员；已选人员会保留。" : "未找到符合条件的人员。";
      } catch (error) {
        if (requestVersion === version && error.name !== "AbortError") {
          status.textContent = "搜索失败，请检查登录状态后重新搜索。";
        }
      } finally {
        if (requestVersion === version) {
          loading = false;
          more.disabled = false;
          root.removeAttribute("aria-busy");
        }
      }
    }

    query.addEventListener("input", () => {
      cancelSearch();
      clearResults();
      if (!query.value.trim()) {
        status.textContent = "请输入姓名或账号搜索人员。";
        return;
      }
      timer = setTimeout(() => load(1), 300);
    });
    query.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        load(1);
      } else if (event.key === "Escape") {
        cancelSearch();
        query.value = "";
        clearResults();
        status.textContent = "请输入姓名或账号搜索人员。";
      }
    });
    more.addEventListener("click", () => {
      if (!loading && hasMore && query.value.trim() === activeQuery) load(page + 1);
    });

    const all = form.querySelector('input[name="is_public"]');
    function syncMode() {
      const areas = form.querySelectorAll("[data-audience-limited], .field-visible_groups, .field-visible_users");
      areas.forEach((area) => { area.hidden = Boolean(all && all.checked); });
      if (all && all.checked) cancelSearch();
    }
    if (all) all.addEventListener("change", syncMode);
    form.addEventListener("reset", () => {
      cancelSearch();
      setTimeout(() => {
        state.reset();
        renderSelected();
        query.value = "";
        clearResults();
        status.textContent = "";
        syncMode();
      }, 0);
    });
    renderSelected();
    syncMode();
  }

  if (typeof module !== "undefined") module.exports = { SelectionState, searchURL };
  if (typeof document !== "undefined") {
    const init = () => document.querySelectorAll("[data-recipient-picker]").forEach(initPicker);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
  }
})();

(function () {
  const themes = ["light", "dark", "corporate", "business", "night"];
  const preferences = ["system"].concat(themes);
  const labels = {
    system: "跟随系统",
    light: "浅色",
    dark: "深色",
    corporate: "企业",
    business: "商务",
    night: "夜间",
  };
  const storageKey = "tms-theme";
  const root = document.documentElement;
  const colorSchemeQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function storedPreference() {
    const stored = window.localStorage.getItem(storageKey);
    return preferences.includes(stored) ? stored : "system";
  }

  function resolveTheme(preference) {
    if (themes.includes(preference)) return preference;
    if (colorSchemeQuery && colorSchemeQuery.matches) return "dark";
    return "light";
  }

  function stateFor(preference) {
    const nextPreference = preferences.includes(preference) ? preference : "system";
    const resolvedTheme = resolveTheme(nextPreference);
    return {
      preference: nextPreference,
      theme: resolvedTheme,
      label: labels[nextPreference] || nextPreference,
      resolvedLabel: labels[resolvedTheme] || resolvedTheme,
    };
  }

  function applyTheme(preference, persist) {
    const state = stateFor(preference);
    root.dataset.theme = state.theme;
    if (persist !== false) window.localStorage.setItem(storageKey, state.preference);
    window.dispatchEvent(new CustomEvent("tms:theme-changed", { detail: state }));
    return state;
  }

  if (colorSchemeQuery) {
    colorSchemeQuery.addEventListener("change", function () {
      if (storedPreference() === "system") applyTheme("system", false);
    });
  }

  const initialState = applyTheme(storedPreference(), false);
  window.localStorage.setItem(storageKey, initialState.preference);
  window.tmsTheme = {
    themes,
    preferences,
    labels,
    setTheme: function (preference) {
      return applyTheme(preference, true);
    },
    currentState: function () {
      return stateFor(storedPreference());
    },
    labelFor: function (preference) {
      return labels[preference] || preference;
    },
  };
})();

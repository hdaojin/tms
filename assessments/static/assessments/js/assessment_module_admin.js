(function () {
  function findRankingCheckbox(moduleSelect) {
    if (!moduleSelect.form) {
      return null;
    }

    var checkboxName = moduleSelect.name === 'module'
      ? 'counts_towards_ranking'
      : moduleSelect.name.replace(/module$/, 'counts_towards_ranking');

    return moduleSelect.form.elements[checkboxName] || null;
  }

  function findHintContainer(checkbox) {
    return checkbox.closest('.field-counts_towards_ranking')
      || checkbox.closest('td')
      || checkbox.parentElement;
  }

  function ensureHintElement(checkbox) {
    var container = findHintContainer(checkbox);
    if (!container) {
      return null;
    }

    var hint = container.querySelector('.assessment-ranking-default-hint');
    if (!hint) {
      hint = document.createElement('div');
      hint.className = 'help assessment-ranking-default-hint';
      container.appendChild(hint);
    }
    return hint;
  }

  function renderHint(checkbox, moduleLabel, defaultValue) {
    var hint = ensureHintElement(checkbox);
    if (!hint) {
      return;
    }

    var baseHelp = checkbox.dataset.rankingDefaultHelp || '';
    if (!moduleLabel) {
      hint.textContent = baseHelp;
      return;
    }

    var defaultLabel = defaultValue ? '计入排名分' : '不计入排名分';
    if (checkbox.dataset.followModuleDefault === 'true') {
      hint.textContent = '当前标准模块默认：' + moduleLabel + '，' + defaultLabel + '。未手动修改时会自动同步。';
      return;
    }

    hint.textContent = '当前标准模块默认：' + moduleLabel + '，' + defaultLabel + '。你已手动改写当前考核模块设置。';
  }

  function syncRankingRule(moduleSelect) {
    var url = moduleSelect.dataset.rankingDefaultUrl;
    var checkbox = findRankingCheckbox(moduleSelect);
    if (!url || !checkbox) {
      return;
    }

    var moduleId = moduleSelect.value;
    if (!moduleId) {
      renderHint(checkbox, '', false);
      return;
    }

    var requestUrl = url + '?module_id=' + encodeURIComponent(moduleId);
    window.fetch(requestUrl, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).then(function (response) {
      if (!response.ok) {
        throw new Error('Failed to load ranking default.');
      }

      return response.json();
    }).then(function (payload) {
      if (!payload || !payload.found || !payload.module) {
        renderHint(checkbox, '', false);
        return;
      }

      var defaultValue = !!payload.module.default_counts_towards_ranking;
      if (checkbox.dataset.followModuleDefault === 'true') {
        checkbox.checked = defaultValue;
      }
      renderHint(checkbox, payload.module.label, defaultValue);
    }).catch(function () {
      renderHint(checkbox, '', false);
    });
  }

  function initializeModuleSelect(moduleSelect) {
    if (!moduleSelect || moduleSelect.dataset.rankingDefaultInitialized === 'true') {
      return;
    }

    var checkbox = findRankingCheckbox(moduleSelect);
    if (!checkbox) {
      return;
    }

    moduleSelect.dataset.rankingDefaultInitialized = 'true';
    renderHint(checkbox, '', false);
    syncRankingRule(moduleSelect);
  }

  function initializeAll(scope) {
    var root = scope || document;
    var moduleSelects = root.querySelectorAll('select[data-ranking-default-url]');
    moduleSelects.forEach(initializeModuleSelect);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initializeAll(document);
  });

  document.addEventListener('change', function (event) {
    var target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.matches('select[data-ranking-default-url]')) {
      syncRankingRule(target);
      return;
    }

    if (target.matches('input[type="checkbox"][name="counts_towards_ranking"], input[type="checkbox"][name$="counts_towards_ranking"]')) {
      target.dataset.followModuleDefault = 'false';

      var moduleName = target.name === 'counts_towards_ranking'
        ? 'module'
        : target.name.replace(/counts_towards_ranking$/, 'module');
      var moduleSelect = target.form ? target.form.elements[moduleName] : null;
      if (moduleSelect && moduleSelect.matches('select[data-ranking-default-url]')) {
        syncRankingRule(moduleSelect);
      } else {
        renderHint(target, '', false);
      }
    }
  });

  document.addEventListener('formset:added', function (event) {
    initializeAll(event.target);
  });
})();
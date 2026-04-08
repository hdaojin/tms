(function () {
  function renderOptions(selectElement, choices, selectedValue) {
    selectElement.innerHTML = '';

    choices.forEach(function (choice) {
      var option = new Option(choice.label, choice.value);
      option.selected = choice.value === selectedValue;
      selectElement.add(option);
    });
  }

  function pickSelectedValue(choices, preferredValue, defaultValue) {
    var availableValues = choices.map(function (choice) {
      return choice.value;
    });

    if (availableValues.includes(preferredValue)) {
      return preferredValue;
    }

    if (availableValues.includes(defaultValue)) {
      return defaultValue;
    }

    return availableValues[0] || '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    var itemSelect = document.getElementById('id_item');
    var severitySelect = document.getElementById('id_severity');

    if (!itemSelect || !severitySelect) {
      return;
    }

    var url = itemSelect.dataset.severityChoicesUrl;
    var defaultSeverity = severitySelect.dataset.defaultSeverity || '';
    var placeholderLabel = severitySelect.dataset.placeholderLabel || '请先选择奖惩事项';

    function resetPlaceholder() {
      renderOptions(severitySelect, [{ value: '', label: placeholderLabel }], '');
    }

    function refreshSeverityChoices() {
      var itemId = itemSelect.value;

      if (!url || !itemId) {
        resetPlaceholder();
        return;
      }

      var currentValue = severitySelect.value;
      var requestUrl = url + '?item_id=' + encodeURIComponent(itemId);

      window.fetch(requestUrl, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      }).then(function (response) {
        if (!response.ok) {
          throw new Error('Failed to load severity choices.');
        }

        return response.json();
      }).then(function (payload) {
        var choices = Array.isArray(payload.choices) ? payload.choices : [];
        var nextValue = pickSelectedValue(choices, currentValue, payload.default || defaultSeverity);
        renderOptions(severitySelect, choices, nextValue);
      }).catch(function () {
        resetPlaceholder();
      });
    }

    itemSelect.addEventListener('change', refreshSeverityChoices);
    refreshSeverityChoices();
  });
})();
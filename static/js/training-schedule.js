(function () {
  "use strict";
  document.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail.target.id === "schedule-editor") {
      const dialog = document.getElementById("schedule-dialog");
      if (dialog && !dialog.open) dialog.showModal();
    }
  });
  document.addEventListener("scheduleChanged", function (event) {
    const rowsUpdated = Boolean(event.detail && event.detail.rowsUpdated);
    const target = document.getElementById(rowsUpdated ? "schedule-activity" : "schedule-results");
    if (target && window.htmx) {
      window.htmx.trigger(target, rowsUpdated ? "refreshActivity" : "refreshSchedule");
    }
  });
})();

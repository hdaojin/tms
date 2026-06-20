(function () {
  const DEFAULT_METRICS = {
    cpu: 36,
    mem: 62,
    net: 78,
  };

  function pad(value, length) {
    return String(value).padStart(length, "0");
  }

  function formatTime(date) {
    return [
      date.getFullYear(),
      pad(date.getMonth() + 1, 2),
      pad(date.getDate(), 2),
    ].join("-") + " " + [
      pad(date.getHours(), 2),
      pad(date.getMinutes(), 2),
      pad(date.getSeconds(), 2),
    ].join(":");
  }

  function setText(element, value) {
    if (!element) return;
    const nextValue = String(value);
    element.textContent = nextValue;
    element.setAttribute("aria-label", nextValue);
  }

  function setMetric(stage, key, value) {
    const label = stage.querySelector(`[data-countdown-metric="${key}"]`);
    const bar = stage.querySelector(`[data-countdown-metric-bar="${key}"]`);
    if (label) label.textContent = `${value}%`;
    if (bar) bar.value = value;
  }

  function updateMetrics(stage, metrics) {
    metrics.cpu = Math.min(96, Math.max(8, metrics.cpu + Math.floor(Math.random() * 7) - 3));
    metrics.mem = Math.min(96, Math.max(8, metrics.mem + Math.floor(Math.random() * 5) - 2));
    metrics.net = Math.min(96, Math.max(8, metrics.net + Math.floor(Math.random() * 9) - 4));
    setMetric(stage, "cpu", metrics.cpu);
    setMetric(stage, "mem", metrics.mem);
    setMetric(stage, "net", metrics.net);
  }

  function setFinishedState(stage, isFinished) {
    const live = stage.querySelector("[data-countdown-live]");
    const finished = stage.querySelector("[data-countdown-finished]");
    if (live) live.classList.toggle("hidden", isFinished);
    if (finished) finished.classList.toggle("hidden", !isFinished);
  }

  function initCountdownStage(stage) {
    if (stage.dataset.countdownBound === "true") return;
    stage.dataset.countdownBound = "true";

    const target = stage.dataset.targetAt ? new Date(stage.dataset.targetAt) : null;
    const serverNow = stage.dataset.serverNow ? new Date(stage.dataset.serverNow) : null;
    const clockOffset = serverNow && !Number.isNaN(serverNow.getTime()) ? serverNow.getTime() - Date.now() : 0;
    const metrics = { ...DEFAULT_METRICS };

    const nodes = {
      currentTime: stage.querySelector("[data-countdown-current-time]"),
      days: stage.querySelector("[data-countdown-days]"),
      hours: stage.querySelector("[data-countdown-hours]"),
      minutes: stage.querySelector("[data-countdown-minutes]"),
      seconds: stage.querySelector("[data-countdown-seconds]"),
    };

    function setZero() {
      setText(nodes.days, "000");
      setText(nodes.hours, "00");
      setText(nodes.minutes, "00");
      setText(nodes.seconds, "00");
    }

    function tick() {
      const now = new Date(Date.now() + clockOffset);
      setText(nodes.currentTime, formatTime(now));

      if (!target || Number.isNaN(target.getTime())) {
        setFinishedState(stage, true);
        setZero();
        return;
      }

      const distance = target.getTime() - now.getTime();
      if (distance <= 0) {
        setFinishedState(stage, true);
        setZero();
        return;
      }

      setFinishedState(stage, false);
      const days = Math.floor(distance / 86400000);
      const hours = Math.floor((distance % 86400000) / 3600000);
      const minutes = Math.floor((distance % 3600000) / 60000);
      const seconds = Math.floor((distance % 60000) / 1000);

      setText(nodes.days, pad(days, 3));
      setText(nodes.hours, pad(hours, 2));
      setText(nodes.minutes, pad(minutes, 2));
      setText(nodes.seconds, pad(seconds, 2));
    }

    tick();
    setMetric(stage, "cpu", metrics.cpu);
    setMetric(stage, "mem", metrics.mem);
    setMetric(stage, "net", metrics.net);

    const countdownTimer = window.setInterval(tick, 1000);
    const metricsTimer = window.setInterval(function () {
      updateMetrics(stage, metrics);
    }, 1600);

    window.addEventListener(
      "beforeunload",
      function () {
        window.clearInterval(countdownTimer);
        window.clearInterval(metricsTimer);
      },
      { once: true },
    );
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-countdown-stage]").forEach(initCountdownStage);
  });
})();

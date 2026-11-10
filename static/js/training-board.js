function fitTaskBox(box) {
  const tasks = Array.from(box.querySelector("[data-screen-tasks]").children);
  const candidates = tasks.slice(0, 3);
  const more = box.querySelector("[data-screen-more]");
  for (const [index, task] of tasks.entries()) {
    task.hidden = index >= candidates.length;
  }
  more.hidden = true;

  const bottom =
    box.getBoundingClientRect().bottom -
    parseFloat(getComputedStyle(box).borderBottomWidth) -
    parseFloat(getComputedStyle(box).paddingBottom);
  if (
    tasks.length === candidates.length &&
    candidates.at(-1).getBoundingClientRect().bottom <= bottom
  )
    return;

  more.textContent = `… 还有 ${tasks.length} 项任务`;
  more.hidden = false;
  const hintHeight =
    more.getBoundingClientRect().height +
    parseFloat(getComputedStyle(more).marginTop);
  const firstHidden = candidates.findIndex(
    (task) => task.getBoundingClientRect().bottom > bottom - hintHeight,
  );
  const visible = firstHidden === -1 ? candidates.length : firstHidden;
  for (const task of candidates.slice(visible)) task.hidden = true;
  more.textContent = `… 还有 ${tasks.length - visible} 项任务`;
}

const screen = document.querySelector("[data-training-screen]");
const content = screen.querySelector("[data-screen-content]");
const error = screen.querySelector("[data-screen-error]");
const screenDate = screen.querySelector("[data-screen-date-text]");
const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
const fragmentUrl = new URL(window.location.pathname, window.location.origin);
fragmentUrl.searchParams.set("fragment", "1");

let source = content.innerHTML;
let plans = [];
let page = 0;
let selectedId;
let paused = motion.matches;
let refreshing = false;
let rotation;
let layoutFrame;
let boxes = [];

function fitTasks() {
  window.cancelAnimationFrame(layoutFrame);
  layoutFrame = window.requestAnimationFrame(() => boxes.forEach(fitTaskBox));
}

const observer = new ResizeObserver(fitTasks);

function showPlan(index, focusAction) {
  window.clearTimeout(rotation);
  observer.disconnect();
  boxes = [];
  if (!plans.length) return;

  page = (index + plans.length) % plans.length;
  const active = plans[page];
  selectedId = active.dataset.planId;
  for (const plan of plans) plan.hidden = plan !== active;

  const controls = active.querySelector("[data-screen-controls]");
  controls.hidden = plans.length < 2;
  if (!controls.hidden) {
    controls.querySelector("[data-screen-page]").textContent =
      `${page + 1} / ${plans.length}`;
    controls.querySelector("[data-screen-pause-label]").textContent = paused
      ? "继续轮播"
      : "15s 自动切换";
    const pause = controls.querySelector('[data-screen-action="pause"]');
    pause.setAttribute(
      "aria-label",
      paused ? "继续轮播" : "暂停轮播，当前每 15 秒自动切换",
    );
    const dots = controls.querySelector("[data-screen-dots]");
    if (dots.children.length !== plans.length) {
      dots.replaceChildren(
        ...plans.map((plan, position) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "btn btn-ghost btn-sm btn-circle";
          button.dataset.screenAction = String(position);
          button.setAttribute("aria-label", `显示第 ${position + 1} 份计划`);
          return button;
        }),
      );
    }
    for (const [position, button] of Array.from(dots.children).entries()) {
      button.setAttribute("aria-current", String(position === page));
    }
    if (focusAction)
      controls.querySelector(`[data-screen-action="${focusAction}"]`)?.focus();
  }

  boxes = Array.from(active.querySelectorAll("[data-screen-task-box]"));
  for (const box of boxes) observer.observe(box);
  fitTasks();
  if (!paused && !document.hidden && plans.length > 1) {
    rotation = window.setTimeout(() => {
      showPlan(
        page + 1,
        active.contains(document.activeElement)
          ? document.activeElement.dataset.screenAction
          : null,
      );
    }, 15000);
  }
}

function readPlans(focusAction) {
  screenDate.textContent =
    content
      .querySelector("[data-screen-date-value]")
      ?.content.textContent.trim() ?? "";
  plans = Array.from(content.querySelectorAll("[data-plan-id]"));
  for (const plan of plans) {
    const progress = plan.querySelector("[data-completion]");
    progress.style.setProperty(
      "--completion",
      `${progress.dataset.completion}%`,
    );
    const ring = plan.querySelector("[data-domain-ring]");
    if (ring) {
      const segments = Array.from(
        plan.querySelectorAll("[data-domain-hue]"),
        (item) => {
          const { domainHue, domainStart, domainEnd } = item.dataset;
          item.style.setProperty("--domain-hue", domainHue);
          return `hsl(${domainHue} 90% 65%) ${domainStart / 100}% ${domainEnd / 100}%`;
        },
      );
      ring.style.setProperty(
        "--domain-chart",
        `conic-gradient(${segments.join(", ")})`,
      );
    }
  }
  showPlan(
    Math.max(
      0,
      plans.findIndex((plan) => plan.dataset.planId === selectedId),
    ),
    focusAction,
  );
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const response = await fetch(fragmentUrl, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error("刷新失败");
    const next = await response.text();
    if (!next.includes("data-screen-date-value"))
      throw new Error("刷新响应无效");
    if (next.trim() !== source.trim() || !error.hidden) {
      const focusAction = content.contains(document.activeElement)
        ? document.activeElement.dataset.screenAction
        : null;
      source = next;
      content.innerHTML = source;
      error.hidden = true;
      readPlans(focusAction);
    }
  } catch {
    source = "";
    content.replaceChildren();
    error.hidden = false;
    readPlans();
  } finally {
    refreshing = false;
  }
}

content.addEventListener("click", (event) => {
  const action = event.target.closest("[data-screen-action]")?.dataset
    .screenAction;
  if (!action) return;
  if (action === "pause") {
    paused = !paused;
    showPlan(page, action);
  } else if (action === "previous" || action === "next") {
    showPlan(page + (action === "next" ? 1 : -1), action);
  } else {
    showPlan(Number(action), action);
  }
});

motion.addEventListener("change", () => {
  paused = motion.matches;
  showPlan(page);
});
document.addEventListener("visibilitychange", () => showPlan(page));
window.addEventListener("resize", fitTasks);
document.fonts.ready.then(fitTasks);

readPlans();
window.setInterval(refresh, 60000);

const screen = document.querySelector("[data-training-screen]");
const viewport = screen.querySelector("[data-screen-viewport]");
const grid = screen.querySelector("[data-screen-grid]");
const controls = screen.querySelector("[data-screen-controls]");
const pauseButton = screen.querySelector("[data-screen-pause]");
const error = screen.querySelector("[data-screen-error]");
const screenDate = screen.querySelector("[data-screen-date]");
const fragmentUrl = new URL(window.location.pathname, window.location.origin);
fragmentUrl.searchParams.set("fragment", "1");

let source = grid.innerHTML.trim();
let pages = [];
let page = 0;
let paused = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let refreshing = false;
let rotation;

function showPage(index) {
    window.clearTimeout(rotation);
    if (!pages.length) return;

    page = (index + pages.length) % pages.length;
    grid.replaceChildren(...pages[page]);
    viewport.scrollTop = 0;
    screen.querySelector("[data-screen-page]").textContent = `${page + 1} / ${pages.length}`;
    pauseButton.textContent = paused ? "继续轮播" : "暂停轮播";
    if (!paused && pages.length > 1) {
        rotation = window.setTimeout(() => showPage(page + 1), 15000);
    }
}

function paginate(reset = false) {
    window.clearTimeout(rotation);
    pages = [];
    grid.innerHTML = source;
    const dateValue = grid.querySelector("[data-screen-date-value]");
    if (dateValue) screenDate.textContent = dateValue.content.textContent.trim();
    const plans = Array.from(grid.querySelectorAll("[data-screen-plan]"));
    controls.hidden = !plans.length;
    if (!plans.length) return;

    grid.replaceChildren();
    const fits = () => grid.offsetHeight <= viewport.clientHeight;
    const finishPage = () => {
        if (!grid.children.length) return;
        pages.push(Array.from(grid.children));
        grid.replaceChildren();
    };

    for (const plan of plans) {
        grid.append(plan);
        if (fits()) continue;
        plan.remove();
        finishPage();
        grid.append(plan);
        if (fits()) continue;
        plan.remove();

        let currentPlan;
        let currentSlot;
        const startPlan = () => {
            currentPlan = plan.cloneNode(true);
            currentPlan.querySelectorAll("[data-screen-slot]").forEach((slot) => slot.remove());
            grid.append(currentPlan);
        };
        const startSlot = (slot) => {
            currentSlot = slot.cloneNode(true);
            currentSlot.querySelector("[data-screen-tasks]").replaceChildren();
            currentPlan.querySelector("[data-screen-plan-body]").append(currentSlot);
        };

        startPlan();
        for (const slot of plan.querySelectorAll("[data-screen-slot]")) {
            startSlot(slot);
            for (const task of slot.querySelector("[data-screen-tasks]").children) {
                const row = task.cloneNode(true);
                currentSlot.querySelector("[data-screen-tasks]").append(row);
                if (fits() || currentPlan.querySelectorAll("[data-screen-tasks] li").length === 1) continue;

                row.remove();
                if (!currentSlot.querySelector("li")) currentSlot.remove();
                finishPage();
                startPlan();
                startSlot(slot);
                currentSlot.querySelector("[data-screen-tasks]").append(row);
            }
        }
    }
    finishPage();
    controls.hidden = pages.length < 2;
    showPage(reset ? 0 : Math.min(page, pages.length - 1));
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
        const content = (await response.text()).trim();
        if (content !== source || !error.hidden) {
            source = content;
            error.hidden = true;
            paginate(true);
        }
    } catch {
        source = "";
        screenDate.textContent = "";
        error.hidden = false;
        paginate(true);
    } finally {
        refreshing = false;
    }
}

function refreshAtMidnight() {
    const dayLength = 86400000;
    const shanghaiOffset = 8 * 60 * 60 * 1000;
    const untilMidnight = dayLength - (Date.now() + shanghaiOffset) % dayLength;
    window.setTimeout(() => {
        refresh();
        refreshAtMidnight();
    }, untilMidnight + 250);
}

screen.querySelector("[data-screen-previous]").addEventListener("click", () => showPage(page - 1));
screen.querySelector("[data-screen-next]").addEventListener("click", () => showPage(page + 1));
pauseButton.addEventListener("click", () => {
    paused = !paused;
    showPage(page);
});
let resize;
window.addEventListener("resize", () => {
    window.clearTimeout(resize);
    resize = window.setTimeout(() => paginate(), 150);
});
paginate();
window.setInterval(refresh, 60000);
refreshAtMidnight();

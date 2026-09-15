(function () {
  const appPathPrefix = "/who-let-the-agents-act";
  const configuredBasePath = document.querySelector('meta[name="wlaa-base-path"]')?.content || "";
  const APP_BASE_PATH = configuredBasePath || (window.location.pathname === appPathPrefix || window.location.pathname.startsWith(`${appPathPrefix}/`) ? appPathPrefix : "");
  function updateCount(selector, value) {
    const count = Number(value);
    const available = Number.isFinite(count) && count >= 0;
    document.querySelectorAll(selector).forEach((el) => {
      const current = Number(String(el.textContent || "").replace(/,/g, ""));
      if (!available || (count === 0 && Number.isFinite(current) && current > 0)) return;
      el.textContent = count.toLocaleString();
      el.title = "Live count from GitHub";
    });
  }

  function setStatsVisibility(visible) {
    document.querySelectorAll(".github-repo-facts, .github-community-star-pill").forEach((el) => {
      el.hidden = !visible;
    });
  }

  function initCallout() {
    const banner = document.getElementById("github-callout");
    if (!banner) return;
  }

  async function loadGithubStats() {
    setStatsVisibility(false);
    try {
      const res = await fetch(`${APP_BASE_PATH}/api/github-stats`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const statsAvailable = Number.isFinite(Number(data.stars)) && Number.isFinite(Number(data.forks));
      if (!statsAvailable) return;
      setStatsVisibility(true);
      updateCount("[data-github-stars]", data.stars);
      updateCount("[data-github-forks]", data.forks);
      if (data.repo) {
        document.querySelectorAll(".github-repo-title").forEach((el) => {
          el.textContent = data.repo;
        });
      }

      if (data.url) {
        document.querySelectorAll('a[href*="github.com/rewanthtammana/"]').forEach((el) => {
          el.href = data.url;
        });
      }
    } catch (_) {
      setStatsVisibility(false);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initCallout();
      loadGithubStats();
    });
  } else {
    initCallout();
    loadGithubStats();
  }
})();

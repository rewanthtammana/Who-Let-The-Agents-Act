(function () {
  const appPathPrefix = "/who-let-the-agents-act";
  const configuredBasePath = document.querySelector('meta[name="wlaa-base-path"]')?.content || "";
  const APP_BASE_PATH = configuredBasePath || (window.location.pathname === appPathPrefix || window.location.pathname.startsWith(`${appPathPrefix}/`) ? appPathPrefix : "");
  const fallbackRepoUrl = "https://github.com/rewanthtammana/who-let-the-agents-act";
  let repoRoot = fallbackRepoUrl;

  function routeScenarioId() {
    const path = window.location.pathname.slice(APP_BASE_PATH.length).replace(/\/+$/, "");
    const match = path.match(/^\/(?:lab|labs|blog)\/([a-z0-9-]+)$/);
    return match ? match[1] : "";
  }

  function validScenarioId(value) {
    return /^[a-z0-9-]+$/.test(value || "") ? value : "";
  }

  function normalizedRepoUrl(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== "https:" || url.hostname !== "github.com") return "";
      return url.href.replace(/\/$/, "");
    } catch (_) {
      return "";
    }
  }

  function githubUrl(location, scenarioId) {
    const scenarioDirectory = scenarioId.replace(/-/g, "_");
    if (location === "scenario_footer_contribute") return `${repoRoot}/blob/main/CONTRIBUTING.md`;
    if (location === "scenario_footer_source" && scenarioDirectory) return `${repoRoot}/tree/main/scenarios/${scenarioDirectory}`;
    if (location === "hardened_result" && scenarioDirectory) return `${repoRoot}/blob/main/scenarios/${scenarioDirectory}/modes/hardened.py`;
    return repoRoot;
  }

  function applyGithubLinks(scenarioId = routeScenarioId()) {
    const validRouteScenario = validScenarioId(scenarioId);
    document.querySelectorAll("a[data-github-location]").forEach((link) => {
      const linkScenario = validScenarioId(link.dataset.scenarioId) || validRouteScenario;
      if (linkScenario) link.dataset.scenarioId = linkScenario;
      link.href = githubUrl(link.dataset.githubLocation, linkScenario);
    });
  }
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

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-github-location]");
    if (!link || typeof window.gtag !== "function") return;
    if (!normalizedRepoUrl(link.href)) return;
    const location = link.dataset.githubLocation;
    if (!/^[a-z_]+$/.test(location || "")) return;
    const params = { link_location: location };
    const scenarioId = validScenarioId(link.dataset.scenarioId) || validScenarioId(routeScenarioId());
    if (scenarioId) params.scenario_id = scenarioId;
    if (["vulnerable", "prompt_only", "hardened"].includes(link.dataset.mode)) params.mode = link.dataset.mode;
    if (["exposed", "refused", "contained", "allowed"].includes(link.dataset.verdict)) params.verdict = link.dataset.verdict;
    if (["single", "compare"].includes(link.dataset.runType)) params.run_type = link.dataset.runType;
    window.gtag("event", "github_click", params);
  });

  async function loadGithubStats() {
    setStatsVisibility(false);
    try {
      const res = await fetch(`${APP_BASE_PATH}/api/github-stats`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const apiRepoUrl = normalizedRepoUrl(data.url);
      if (apiRepoUrl) repoRoot = apiRepoUrl;
      applyGithubLinks();
      if (data.repo) {
        document.querySelectorAll(".github-repo-title").forEach((el) => {
          el.textContent = data.repo;
        });
      }
      const statsAvailable = Number.isFinite(Number(data.stars)) && Number.isFinite(Number(data.forks));
      if (!statsAvailable) return;
      setStatsVisibility(true);
      updateCount("[data-github-stars]", data.stars);
      updateCount("[data-github-forks]", data.forks);
    } catch (_) {
      setStatsVisibility(false);
    }
  }

  document.addEventListener("wlaa:scenario-change", (event) => {
    const scenarioId = validScenarioId(event.detail?.scenarioId);
    document.querySelectorAll("a[data-github-location]").forEach((link) => {
      if (scenarioId) link.dataset.scenarioId = scenarioId;
      else delete link.dataset.scenarioId;
    });
    applyGithubLinks(scenarioId);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initCallout();
      applyGithubLinks();
      loadGithubStats();
    });
  } else {
    initCallout();
    applyGithubLinks();
    loadGithubStats();
  }
})();

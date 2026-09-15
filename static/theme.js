(function () {
  const root = document.documentElement;
  const storageKey = "who_let_the_agents_act-theme";
  const saved = localStorage.getItem(storageKey);
  if (saved === "dark" || saved === "light") root.dataset.theme = saved;

  function updateButton() {
    const dark = root.dataset.theme === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
      button.textContent = dark ? "LIGHT MODE" : "DARK MODE";
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    });
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem(storageKey, next);
    updateButton();
  });

  updateButton();
})();

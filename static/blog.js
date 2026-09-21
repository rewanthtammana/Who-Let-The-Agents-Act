const root = document.querySelector("#blog-root");
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[char]);
const APP_PATH_PREFIX = "/who-let-the-agents-act";
const configuredBasePath = document.querySelector('meta[name="wlaa-base-path"]')?.content || "";
const APP_BASE_PATH = configuredBasePath || (window.location.pathname === APP_PATH_PREFIX || window.location.pathname.startsWith(`${APP_PATH_PREFIX}/`) ? APP_PATH_PREFIX : "");
const appUrl = (path) => {
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) return path;
  if (path.startsWith("#")) return `${APP_BASE_PATH}${path}`;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!APP_BASE_PATH || normalizedPath === APP_BASE_PATH || normalizedPath.startsWith(`${APP_BASE_PATH}/`)) return normalizedPath;
  return `${APP_BASE_PATH}${normalizedPath}`;
};
const appLink = (path) => path.startsWith("/") ? appUrl(path) : path;
const articleSlug = decodeURIComponent(window.location.pathname.replace(new RegExp(`^${APP_BASE_PATH}\/blog\/?`), "").replace(/\/$/, ""));
document.querySelectorAll("[data-app-path]").forEach((link) => {
  link.href = appUrl(link.dataset.appPath);
});

function severityClass(severity) {
  return String(severity).toLowerCase() === "critical" ? "critical" : "high";
}

function canonicalPageUrl(fallbackPath) {
  const canonical = document.querySelector('link[rel="canonical"]')?.href;
  if (canonical) return canonical;
  return new URL(appLink(fallbackPath), window.location.origin).href;
}

function renderShareMenu({ title, description, path, compact = false }) {
  const url = canonicalPageUrl(path);
  const xText = `Worth reading: ${title}\n\n${description}\n`;
  const linkedinUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&summary=${encodeURIComponent(description)}`;
  const xUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(xText)}&url=${encodeURIComponent(url)}`;
  return `<details class="share-menu ${compact ? "compact" : ""}">
    <summary class="share-trigger"><span>Share</span></summary>
    <div class="share-panel">
      <button type="button" aria-label="Copy page link" data-share-copy="${encodeURIComponent(url)}">Copy link</button>
      <a href="${escapeHtml(linkedinUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Share on LinkedIn">Share on LinkedIn</a>
      <a href="${escapeHtml(xUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Share on X">Share on X</a>
      <span class="share-status" aria-live="polite"></span>
    </div>
  </details>`;
}

function setupShareMenus() {
  document.querySelectorAll("[data-share-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = decodeURIComponent(button.dataset.shareCopy || "");
      const status = button.closest(".share-panel")?.querySelector(".share-status");
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(value);
        } else {
          const textarea = document.createElement("textarea");
          textarea.value = value;
          textarea.setAttribute("readonly", "");
          textarea.style.position = "fixed";
          textarea.style.opacity = "0";
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand("copy");
          textarea.remove();
        }
        if (status) status.textContent = "Copied";
      } catch {
        if (status) status.textContent = "Copy failed";
      }
    });
  });
}

function renderIndex(posts) {
  document.title = "Who Let the Agents Act - Field Guide";
  root.innerHTML = `
    <section class="guide-hero">
      <div>
        <p class="eyebrow">FIELD GUIDE · AGENTIC AI SECURITY</p>
        <h1>Where should an agent's authority end?</h1>
      </div>
      <div class="guide-intro">
        <p>Who Let the Agents Act is a hands-on guide to security failures that appear when models can choose data, tools, targets, and follow-up actions.</p>
        <p>Each chapter begins with the vulnerable path, tests a prompt-only defense, then moves the boundary into application code where it can be enforced and evidenced.</p>
        <div class="guide-share">${renderShareMenu({
          title: "Who Let the Agents Act",
          description: "An interactive field guide on agentic AI security, with realistic failure modes and vulnerable vs hardened controls.",
          path: "/blog",
          compact: true,
        })}</div>
      </div>
    </section>

    <section class="principles" aria-label="Core principles">
      <article><span>01</span><strong>Let the model plan</strong><p>Natural language becomes structured intent and tool arguments.</p></article>
      <article><span>02</span><strong>Keep authority outside it</strong><p>Identity, policy, data scope, and side effects remain deterministic.</p></article>
      <article><span>03</span><strong>Preserve the evidence</strong><p>Every meaningful decision is visible in the trace and run artifacts.</p></article>
    </section>

    <section class="catalog-heading">
      <div><p class="eyebrow">NINE PRACTICAL CHAPTERS</p><h2>Start with a security boundary</h2></div>
      <p>Read the attack, inspect the control, then open the exact scenario in the live lab.</p>
    </section>
    <div class="post-grid">
      ${posts.map((post) => {
        const thumbnailSrc = post.article_thumbnail
          ? appUrl(`/api/scenario-assets/${encodeURIComponent(post.id)}/${encodeURIComponent(post.article_thumbnail)}?v=20260915-field-guide-thumbnails1`)
          : "";
        return `
        <a class="post-card" href="${escapeHtml(appLink(post.url))}">
          ${thumbnailSrc ? `<figure class="post-thumbnail"><img src="${escapeHtml(thumbnailSrc)}" alt="" width="480" height="252" loading="lazy" decoding="async"></figure>` : ""}
          <div class="post-card-top"><span>LAB ${String(post.number).padStart(2, "0")}</span><span class="severity ${severityClass(post.severity)}">${escapeHtml(post.severity)}</span></div>
          <p class="post-domain">${escapeHtml(post.domain)} · ${escapeHtml(post.category)}</p>
          <h3>${escapeHtml(post.title)}</h3>
          <p>${escapeHtml(post.dek)}</p>
          <div class="post-boundary"><span>SECURITY BOUNDARY</span><strong>${escapeHtml(post.security_boundary)}</strong></div>
          <span class="read-link">Read chapter →</span>
        </a>`;
      }).join("")}
    </div>
    <aside class="safety-note"><strong>Educational use only.</strong> Vulnerable and prompt-only modes intentionally expose synthetic data or execute simulated side effects. Never connect them to production systems.</aside>`;
  setupShareMenus();
}

function renderList(items, ordered = false) {
  const tag = ordered ? "ol" : "ul";
  return `<${tag}>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>`;
}

function modeCard(label, title, body, tone) {
  return `<article class="mode-card ${tone}"><span>${label}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></article>`;
}

function sectionNumber(post, base) {
  if (!post.story_heading) return base;
  const primerSections = { "01": "05", "02": "06", "03": "07", "04": "03", "05": "08", "06": "09" };
  return primerSections[base] || base;
}

function renderArchitecture(architecture) {
  if (!architecture?.length) return "";
  return `<div class="architecture-flow">
    ${architecture.map((node) => `<article class="architecture-node tone-${escapeHtml(node.tone || "neutral")}">
      <span>${escapeHtml(node.label)}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.detail)}</p>
    </article>`).join("")}
  </div>`;
}

function renderWalkthroughSteps(steps) {
  if (!steps?.length) return "";
  return `<div class="walkthrough-steps">
    ${steps.map((step, index) => `<article class="walkthrough-step"><span>${String(index + 1).padStart(2, "0")}</span><div><h3>${escapeHtml(step.title)}</h3><p>${escapeHtml(step.detail)}</p><strong>LOOK FOR</strong><p>${escapeHtml(step.expect)}</p></div></article>`).join("")}
  </div>`;
}

function renderEvidenceBoard(panels) {
  if (!panels?.length) return "";
  return `<div class="evidence-board">
    ${panels.map((panel) => `<figure class="evidence-panel tone-${escapeHtml(panel.tone || "neutral")}"><figcaption><span>${escapeHtml(panel.label)}</span><strong>${escapeHtml(panel.title)}</strong></figcaption><pre>${escapeHtml(panel.code)}</pre><p>${escapeHtml(panel.note)}</p></figure>`).join("")}
  </div>`;
}

function renderReaderMap(post) {
  const question = post.reader_question || `Can the agent cross the ${String(post.security_boundary || "security").toLowerCase()} boundary?`;
  const success = post.success_check || (post.observe?.[0] || "You can point to the enforced boundary in the trace.");
  return `<section class="reader-map" aria-label="How to use this chapter">
    <div class="reader-map-heading"><span>YOUR FIRST FIVE MINUTES</span><strong>${escapeHtml(post.time_to_complete || "5 minutes")}</strong></div>
    <div class="reader-map-grid">
      <article><span>QUESTION</span><p>${escapeHtml(question)}</p></article>
      <article><span>DO THIS</span><p>${escapeHtml(post.reader_do || "Run the scenario, compare all three postures, and inspect the enforcement trace.")}</p></article>
      <article><span>DONE WHEN</span><p>${escapeHtml(success)}</p></article>
    </div>
  </section>`;
}

function renderModeTable(post) {
  const modes = [
    ["vulnerable", "VULNERABLE"],
    ["prompt_only", "PROMPT-ONLY"],
    ["hardened", "HARDENED"],
  ];
  const technical = post.mode_technical || {
    vulnerable: { authority: "Model-selected plan + scenario tool", scope: "The model's requested data or action", enforcement: "No reliable application boundary", mechanism: post.mode_copy.vulnerable, proof: post.attack_path?.[1] || "Inspect the tool result or side effect." },
    prompt_only: { authority: "Model-controlled guard", scope: "The model-approved plan", enforcement: "Another model judgment before the tool", mechanism: post.prompt_only_failure, proof: "Run the bypass pretext and inspect whether it reaches the unsafe path." },
    hardened: { authority: "Application policy", scope: post.security_boundary, enforcement: "Before protected data access or side effects", mechanism: (post.hardened_controls || []).slice(0, 3).map((control) => control.detail).join(" "), proof: (post.observe || ["Inspect the hardened trace and run artifacts."])[0] }
  };
  const rows = [["AUTHORITY", "authority"], ["DATA / ACTION SCOPE", "scope"], ["ENFORCEMENT POINT", "enforcement"], ["TECHNICAL MECHANISM", "mechanism"], ["PROOF TO CHECK", "proof"]];
  return `<div class="mode-table-wrap"><table class="mode-table"><thead><tr><th>COMPARE</th>${modes.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows.map(([label, key]) => `<tr><th scope="row">${label}</th>${modes.map(([mode]) => `<td>${escapeHtml(technical[mode][key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function renderScreenshots(screenshots, scenarioId) {
  if (!screenshots?.length) return "";
  return `<div class="live-screenshot-grid">
    ${screenshots.map((shot) => {
      const source = appUrl(`/api/scenario-assets/${encodeURIComponent(scenarioId)}/${encodeURIComponent(shot.src)}?v=20260913-live-captures1`);
      return `<figure class="live-screenshot"><button class="screenshot-trigger" type="button" data-image-src="${source}" data-image-alt="${escapeHtml(shot.alt)}" data-image-caption="${escapeHtml(shot.caption)}" aria-label="Open ${escapeHtml(shot.caption)} full size"><img src="${source}" alt="${escapeHtml(shot.alt)}" loading="lazy"><span class="zoom-hint" aria-hidden="true">CLICK TO ZOOM</span></button><figcaption><strong>${escapeHtml(shot.caption)}</strong><span>${escapeHtml(shot.note)}</span></figcaption></figure>`;
    }).join("")}
  </div>`;
}

function renderTocLinks(post, hasPrimer) {
  return `
    ${hasPrimer ? `<a href="#scenario-brief">Scenario brief</a><a href="#architecture">Architecture</a>` : ""}
    <a href="#walkthrough">Try the lab</a>
    ${hasPrimer && post.screenshots?.length ? `<a href="#live-captures">Live captures</a>` : ""}
    <a href="#threat-model">Threat model</a>
    <a href="#attack-path">Attack path</a>
    <a href="#three-modes">Compare the modes</a>
    ${hasPrimer && post.walkthrough_steps?.length ? `<a href="#guided-walkthrough">Guided walkthrough</a>` : ""}
    ${hasPrimer && post.annotated_evidence?.length ? `<a href="#annotated-evidence">Annotated evidence</a>` : ""}
    <a href="#controls">Hardened design</a>
    <a href="#evidence">Evidence</a>`;
}

function setupArticleNavigation() {
  const centerActiveChapter = () => {
    const chapterNav = document.querySelector(".chapter-nav");
    const activeChapter = chapterNav?.querySelector(".chapter-link.active");
    if (!chapterNav || !activeChapter || !window.matchMedia("(max-width: 920px)").matches) return;
    const left = activeChapter.offsetLeft - (chapterNav.clientWidth - activeChapter.offsetWidth) / 2;
    chapterNav.scrollTo({ left: Math.max(0, left), behavior: "auto" });
  };

  window.requestAnimationFrame(centerActiveChapter);
  window.addEventListener("resize", centerActiveChapter, { passive: true });
  document.querySelectorAll(".mobile-toc a").forEach((link) => link.addEventListener("click", () => {
    link.closest("details")?.removeAttribute("open");
  }));
}

function setupScreenshotLightbox() {
  if (document.querySelector("#screenshot-lightbox")) return;
  document.body.insertAdjacentHTML("beforeend", `
    <div id="screenshot-lightbox" class="screenshot-lightbox" hidden role="dialog" aria-modal="true" aria-label="Expanded live capture">
      <div class="lightbox-backdrop" data-lightbox-close></div>
      <div class="lightbox-panel">
        <div class="lightbox-toolbar">
          <p class="lightbox-title" data-lightbox-caption></p>
          <div class="lightbox-actions">
            <button type="button" data-lightbox-zoom-out aria-label="Zoom out">−</button>
            <span data-lightbox-zoom-level>100%</span>
            <button type="button" data-lightbox-zoom-in aria-label="Zoom in">+</button>
            <button type="button" data-lightbox-reset>RESET</button>
            <button type="button" class="lightbox-close" data-lightbox-close aria-label="Close expanded image">×</button>
          </div>
        </div>
        <div class="lightbox-viewport"><img data-lightbox-image alt=""></div>
      </div>
    </div>`);

  const lightbox = document.querySelector("#screenshot-lightbox");
  const image = lightbox.querySelector("[data-lightbox-image]");
  const caption = lightbox.querySelector("[data-lightbox-caption]");
  const level = lightbox.querySelector("[data-lightbox-zoom-level]");
  let zoom = 1;
  let lastTrigger = null;

  const updateZoom = (nextZoom) => {
    zoom = Math.min(3, Math.max(1, nextZoom));
    image.style.transform = `scale(${zoom})`;
    level.textContent = `${Math.round(zoom * 100)}%`;
  };
  const close = () => {
    lightbox.hidden = true;
    image.removeAttribute("src");
    document.body.classList.remove("lightbox-open");
    lastTrigger?.focus();
  };

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest(".screenshot-trigger");
    if (trigger) {
      lastTrigger = trigger;
      image.src = trigger.dataset.imageSrc;
      image.alt = trigger.dataset.imageAlt || "Expanded live capture";
      caption.textContent = trigger.dataset.imageCaption || "Live capture";
      updateZoom(1);
      lightbox.hidden = false;
      document.body.classList.add("lightbox-open");
      lightbox.querySelector("[data-lightbox-zoom-in]").focus();
      return;
    }
    if (event.target.closest("[data-lightbox-close]")) close();
  });
  lightbox.querySelector("[data-lightbox-zoom-in]").addEventListener("click", () => updateZoom(zoom + 0.25));
  lightbox.querySelector("[data-lightbox-zoom-out]").addEventListener("click", () => updateZoom(zoom - 0.25));
  lightbox.querySelector("[data-lightbox-reset]").addEventListener("click", () => updateZoom(1));
  lightbox.querySelector(".lightbox-viewport").addEventListener("wheel", (event) => {
    if (!lightbox.hidden) {
      event.preventDefault();
      updateZoom(zoom + (event.deltaY < 0 ? 0.1 : -0.1));
    }
  }, { passive: false });
  document.addEventListener("keydown", (event) => {
    if (!lightbox.hidden && event.key === "Escape") close();
  });
}

function renderArticle(post, posts) {
  document.title = `${post.title} - Who Let the Agents Act Field Guide`;
  const description = document.querySelector('meta[name="description"]');
  description.setAttribute("content", post.dek);
  const current = posts.findIndex((item) => item.id === post.id);
  const previous = current > 0 ? posts[current - 1] : null;
  const next = current < posts.length - 1 ? posts[current + 1] : null;
  const hasPrimer = Boolean(post.story_heading || post.goal || post.architecture?.length);
  const articleHeroSrc = post.article_hero
    ? appUrl(`/api/scenario-assets/${encodeURIComponent(post.id)}/${encodeURIComponent(post.article_hero)}?v=20260915-article-hero2`)
    : "";
  const attackPresetLabel = "Vulnerable-mode attack";
  const bypassPresetLabel = "Prompt-only bypass";
  root.innerHTML = `
    <div class="article-shell">
      <aside class="chapter-nav" aria-label="Scenario chapters">
        <a class="chapter-nav-title" href="${appUrl("/blog")}">FIELD GUIDE</a>
        ${posts.map((item) => `<a class="chapter-link ${item.id === post.id ? "active" : ""}" href="${escapeHtml(appLink(item.url))}"><span>${String(item.number).padStart(2, "0")}</span>${escapeHtml(item.title)}</a>`).join("")}
      </aside>

      <article class="article ${articleHeroSrc ? "has-article-hero" : ""}">
        <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="${appUrl("/blog")}">Field guide</a><span>/</span><span>Lab ${String(post.number).padStart(2, "0")}</span></nav>
        <details class="mobile-toc">
          <summary><span>ON THIS PAGE</span><span class="mobile-toc-icon" aria-hidden="true">+</span></summary>
          <nav aria-label="On this page">${renderTocLinks(post, hasPrimer)}</nav>
        </details>
        <header class="article-header">
          <div class="article-header-top">
            <div class="article-meta"><span>${escapeHtml(post.domain)}</span><span>${escapeHtml(post.category)}</span><span class="severity ${severityClass(post.severity)}">${escapeHtml(post.severity)}</span></div>
            ${renderShareMenu({
              title: post.title,
              description: post.dek,
              path: post.url,
              compact: true,
            })}
          </div>
          <h1>${escapeHtml(post.title)}</h1>
          <p class="dek">${escapeHtml(post.dek)}</p>
          <a class="primary-action" href="${escapeHtml(appLink(post.lab_url))}">Open this scenario in the lab <span>→</span></a>
        </header>

        ${renderReaderMap(post)}

        ${articleHeroSrc ? `<figure class="article-hero"><img src="${escapeHtml(articleHeroSrc)}" alt="Security flow illustration for ${escapeHtml(post.title)}" width="1200" height="630" decoding="async"></figure>` : ""}

        <section class="quick-summary" aria-labelledby="quick-summary-title">
          <div class="quick-summary-heading"><span>30-SECOND SUMMARY</span><h2 id="quick-summary-title">The boundary at a glance</h2></div>
          <div class="quick-summary-grid">
            <article class="failure"><span>FAILURE</span><p>${escapeHtml(post.vulnerability_type)}</p></article>
            <article class="warning"><span>WHY PROMPT-ONLY FAILS</span><p>${escapeHtml(post.prompt_only_failure)}</p></article>
            <article class="safe"><span>ENFORCED BOUNDARY</span><p>${escapeHtml(post.security_boundary)}</p></article>
          </div>
        </section>

        ${hasPrimer ? `<section id="scenario-brief" class="article-section scenario-primer">
          <div class="primer-story"><p class="section-number">01 / SCENARIO BRIEF</p><h2>${escapeHtml(post.story_heading || "The scenario")}</h2><p>${escapeHtml(post.story || "")}</p></div>
          <aside class="primer-goal" aria-label="Scenario objective">
            <div class="primer-goal-header">
              <span class="goal-label">Objective</span>
            </div>
            <p class="goal-statement">${escapeHtml(post.goal || "")}</p>
            ${post.tip ? `<div class="tip-callout">
              <div class="tip-head"><span class="tip-tag">Field note</span></div>
              <p class="tip-text">${escapeHtml(post.tip)}</p>
            </div>` : ""}
          </aside>
        </section>

        <section id="architecture" class="article-section architecture-section">
          <p class="section-number">02 / SCENARIO ARCHITECTURE</p><h2>Follow the request to the boundary</h2>
          <p class="architecture-intro">${escapeHtml(post.architecture_intro || "Follow the request through the model, tool, policy, and final data or action boundary.")}</p>
          ${renderArchitecture(post.architecture)}
        </section>` : ""}

        <section id="walkthrough" class="article-section walkthrough">
          <div>
            <p class="section-number">${sectionNumber(post, "04")} / TRY THE LAB</p>
            <h2>Start with the attack</h2>
            <p>${escapeHtml(post.walkthrough_intro || `Open the scenario, choose the ${attackPresetLabel}, and use Compare 3 modes. Inspect the trace and artifacts to see where the application boundary changes the result.`)}</p>
            <a class="text-action" href="${escapeHtml(appLink(post.lab_url))}">Launch Lab ${String(post.number).padStart(2, "0")} →</a>
          </div>
          <div class="prompt-set">
            <div><span>NORMAL REQUEST</span><code>${escapeHtml(post.prompts.normal)}</code></div>
            <div><span>${escapeHtml(attackPresetLabel.toUpperCase())}</span><code>${escapeHtml(post.prompts.attack)}</code></div>
            <div><span>${escapeHtml(bypassPresetLabel.toUpperCase())}</span><code>${escapeHtml(post.prompts.bypass)}</code></div>
          </div>
        </section>

        ${hasPrimer && post.screenshots?.length ? `<section id="live-captures" class="article-section live-captures">
          <p class="section-number">04 / LIVE LAB CAPTURES</p><h2>See the difference immediately</h2>
          <p>These captures come from real local runs with synthetic lab data. Compare what the vulnerable tool returned with what application policy allowed through.</p>
          ${renderScreenshots(post.screenshots, post.id)}
        </section>` : ""}

        <section id="threat-model" class="article-section">
          <p class="section-number">${sectionNumber(post, "01")} / THREAT MODEL</p>
          <h2>The risk is authority, not intelligence</h2>
          <p>${escapeHtml(post.threat_model)}</p>
        </section>

        <section id="attack-path" class="article-section">
          <p class="section-number">${sectionNumber(post, "02")} / ATTACK PATH</p>
          <h2>How the vulnerable path fails</h2>
          <div class="attack-steps">${renderList(post.attack_path, true)}</div>
        </section>

        <section id="three-modes" class="article-section">
          <p class="section-number">${sectionNumber(post, "03")} / THREE DEFENSE POSTURES</p>
          <h2>The same goal, three different boundaries</h2>
          <p class="technical-intro">${escapeHtml(post.technical_intro || "Compare who supplies authority, what scope is permitted, where the request is enforced, and which artifact proves the result.")}</p>
          ${renderModeTable(post)}
        </section>

        ${hasPrimer && post.walkthrough_steps?.length ? `<section id="guided-walkthrough" class="article-section guided-steps">
          <p class="section-number">GUIDED WALKTHROUGH</p><h2>Move from observation to proof</h2>
          ${renderWalkthroughSteps(post.walkthrough_steps)}
        </section>` : ""}

        ${hasPrimer && post.annotated_evidence?.length ? `<section id="annotated-evidence" class="article-section annotated-evidence">
          <p class="section-number">ANNOTATED EVIDENCE</p><h2>Read the boundary in the artifacts</h2>
          <p>These are the two moments worth comparing after a run: what the unsafe path allowed through, and the application decision that contained it.</p>
          ${renderEvidenceBoard(post.annotated_evidence)}
        </section>` : ""}

        <section id="controls" class="article-section">
          <p class="section-number">${sectionNumber(post, "05")} / HARDENED DESIGN</p><h2>The controls that make the difference</h2>
          <div class="control-list">${post.hardened_controls.map((control, index) => `<article><span>${String(index + 1).padStart(2, "0")}</span><div><h3>${escapeHtml(control.name)}</h3><p>${escapeHtml(control.detail)}</p></div></article>`).join("")}</div>
          <blockquote>${escapeHtml(post.lesson)}</blockquote>
        </section>

        <section id="evidence" class="article-section evidence-grid">
          <div><p class="section-number">${sectionNumber(post, "06")} / WHAT TO OBSERVE</p><h2>Evidence, not reassurance</h2>${renderList(post.observe)}</div>
          <div class="engineering"><p class="section-number">IMPLEMENTATION NOTES</p>${renderList(post.engineering_notes)}</div>
        </section>

        <nav class="article-pagination" aria-label="Chapter pagination">
          ${previous ? `<a href="${escapeHtml(appLink(previous.url))}"><span>← Previous</span><strong>${escapeHtml(previous.title)}</strong></a>` : "<span></span>"}
          ${next ? `<a class="next" href="${escapeHtml(appLink(next.url))}"><span>Next →</span><strong>${escapeHtml(next.title)}</strong></a>` : `<a class="next" href="${appUrl("/blog")}"><span>Complete</span><strong>Return to the field guide</strong></a>`}
        </nav>
      </article>

      <aside class="toc" aria-label="On this page">
        <span>ON THIS PAGE</span>
        ${renderTocLinks(post, hasPrimer)}
      </aside>
    </div>`;
  setupScreenshotLightbox();
  setupArticleNavigation();
  setupShareMenus();
}

async function initialize() {
  const catalogResponse = await fetch(appUrl("/api/blog"), { cache: "no-store" });
  if (!catalogResponse.ok) throw new Error("The field guide could not be loaded.");
  const posts = await catalogResponse.json();
  if (!articleSlug) {
    renderIndex(posts);
    return;
  }
  const articleResponse = await fetch(appUrl(`/api/blog/${encodeURIComponent(articleSlug)}`), { cache: "no-store" });
  if (!articleResponse.ok) throw new Error("This scenario chapter does not exist.");
  renderArticle(await articleResponse.json(), posts);
}

initialize().catch((error) => {
  root.innerHTML = `<section class="error-state"><p class="eyebrow">FIELD GUIDE</p><h1>Chapter unavailable</h1><p>${escapeHtml(error.message)}</p><a href="${appUrl("/blog")}">Return to all chapters →</a></section>`;
});

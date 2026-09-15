from __future__ import annotations

import json
import html
import re
import io
import os
import secrets
import shutil
import threading
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from core.langchain_agent import GROQ, ModelServiceError, model_call_budget
from scenarios.overpowered_data_tool.database import CustomerNotFound
from scenarios.cross_customer_access.database import CustomerNotFound as CrossCustomerNotFound
from scenarios.business_rule.database import RefundPolicyViolation, TransactionNotFound
from scenarios.indirect_injection.database import InvoiceNotFound
from scenarios.signed_handoff.database import TransferNotFound
from scenarios.rag_tenant_isolation.database import DocumentNotFound
from scenarios.approval_service_outage.database import PaymentRequestNotFound
from scenarios.multi_agent_confused_deputy.database import AccountNotFound, FraudCaseNotFound
from scenarios.registry import DATABASE, INJECTION_ROOT, SCENARIOS

ROOT = Path(__file__).resolve().parent
PUBLIC_SITE_ROOT = "https://rewanthtammana.com/who-let-the-agents-act"
PUBLIC_ASSET_ORIGIN = "https://who-let-the-agents-act.rewanthtammana.com"
PUBLIC_APP_BASE_PATH = os.getenv("PUBLIC_APP_BASE_PATH", "/who-let-the-agents-act")
APP_STYLESHEET_VERSION = "20260915-mobile-console2"
APP_SCRIPT_VERSION = "20260915-basepath1"
BLOG_ASSET_VERSION = "20260915-share4"
SITE_HEADER_ASSET_VERSION = "20260915-unified1"
GITHUB_CALLOUT_ASSET_VERSION = "20260915-callout6"
GITHUB_CALLOUT_SCRIPT_VERSION = "20260915-basepath1"
SESSION_ROOT = ROOT / ".sessions"
SESSION_COOKIE = "who_let_the_agents_act_session"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(30 * 60)))
SESSION_LOCK = threading.RLock()
RUN_LIMIT_PER_MINUTE = int(os.getenv("RUN_RATE_LIMIT_PER_MINUTE", "100"))
RUN_MAX_CONCURRENT_PER_IP = int(os.getenv("RUN_MAX_CONCURRENT_PER_IP", "5"))
RUN_SUSTAINED_MINUTES = int(os.getenv("RUN_SUSTAINED_RATE_MINUTES", "5"))
RUN_ABUSE_BLOCK_MINUTES = int(os.getenv("RUN_ABUSE_BLOCK_MINUTES", "15"))
MODEL_MAX_ATTEMPTS_PER_RUN = int(os.getenv("MODEL_MAX_ATTEMPTS_PER_RUN", "12"))
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0").lower() in {"1", "true", "yes", "on"}

app = FastAPI(title="Who Let the Agents Act - Agentic AI Security Labs", version="1.0.0")


def _valid_session_id(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[a-f0-9]{32}", value))


def _session_id(request: Request) -> str:
    return request.state.session_id


def _cleanup_expired_sessions() -> None:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - SESSION_TTL_SECONDS
    for directory in SESSION_ROOT.iterdir():
        if not directory.is_dir():
            continue
        try:
            if directory.stat().st_mtime < cutoff:
                shutil.rmtree(directory)
        except FileNotFoundError:
            continue


def session_database(scenario_id: str, session_id: str):
    """Return a lazily seeded database private to one browser session."""
    config, shared_database, _, _ = SCENARIOS[scenario_id]
    del config
    with SESSION_LOCK:
        _cleanup_expired_sessions()
        session_dir = SESSION_ROOT / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        os.utime(session_dir, None)
        database_path = session_dir / f"{scenario_id}.sqlite3"
        database = type(shared_database)(database_path)
        if not database_path.exists():
            database.initialize()
        return database


def session_agent(scenario_id: str, session_id: str):
    database = session_database(scenario_id, session_id)
    shared_agent = SCENARIOS[scenario_id][2]
    return type(shared_agent)(database, GROQ), database


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = request.cookies.get(SESSION_COOKIE)
    is_new = not _valid_session_id(session_id)
    if is_new:
        session_id = secrets.token_hex(16)
    request.state.session_id = session_id
    response = await call_next(request)
    if is_new:
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="lax",
            secure=os.getenv("COOKIE_SECURE", "0") == "1",
            max_age=SESSION_TTL_SECONDS,
        )
    return response


def client_ip(request: Request) -> str:
    """Use the edge-provided address only when the origin trusts its proxy."""
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("CF-Connecting-IP", "").strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


class AnonymousRunLimiter:
    """Process-local fallback for the edge limiter and local development.

    Production deployments should also enforce the same policy at Cloudflare's
    edge with shared state. This guard protects a single app process and makes
    the behavior testable without requiring Cloudflare during development.
    """

    def __init__(self, limit: int, concurrency: int, sustained_minutes: int, block_minutes: int):
        self.limit = limit
        self.concurrency = concurrency
        self.sustained_minutes = sustained_minutes
        self.block_seconds = block_minutes * 60
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.buckets: dict[str, dict[int, int]] = defaultdict(dict)
        self.active: dict[str, int] = defaultdict(int)
        self.blocked_until: dict[str, float] = {}
        self.lock = threading.Lock()

    def _record_attempt(self, ip: str, now: float) -> bool:
        bucket = int(now // 60)
        counts = self.buckets[ip]
        counts[bucket] = counts.get(bucket, 0) + 1
        for old_bucket in list(counts):
            if old_bucket < bucket - self.sustained_minutes - 1:
                del counts[old_bucket]
        return all(counts.get(bucket - offset, 0) > self.limit for offset in range(self.sustained_minutes))

    def admit(self, ip: str, now: float | None = None) -> tuple[bool, int, str]:
        now = time.monotonic() if now is None else now
        with self.lock:
            blocked_until = self.blocked_until.get(ip, 0)
            if blocked_until > now:
                return False, max(1, int(blocked_until - now)), "abuse_block"
            if blocked_until:
                self.blocked_until.pop(ip, None)

            over_limit = self._record_attempt(ip, now)
            recent = self.requests[ip]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= self.limit:
                if over_limit:
                    self.blocked_until[ip] = now + self.block_seconds
                    return False, int(self.block_seconds), "abuse_block"
                return False, max(1, int(60 - (now - recent[0]))), "rate_limit"
            recent.append(now)
            if over_limit:
                self.blocked_until[ip] = now + self.block_seconds
                return False, int(self.block_seconds), "abuse_block"
            return True, max(1, int(60 - (now - recent[0]))), "accepted"

    def acquire(self, ip: str) -> bool:
        with self.lock:
            if self.active[ip] >= self.concurrency:
                return False
            self.active[ip] += 1
            return True

    def release(self, ip: str) -> None:
        with self.lock:
            self.active[ip] = max(0, self.active[ip] - 1)
            if not self.active[ip]:
                self.active.pop(ip, None)

    def snapshot(self, ip: str) -> dict[str, int | bool]:
        now = time.monotonic()
        with self.lock:
            recent = self.requests[ip]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            blocked_until = self.blocked_until.get(ip, 0)
            return {
                "available": blocked_until <= now,
                "remaining_submissions": max(0, self.limit - len(recent)),
                "concurrency_remaining": max(0, self.concurrency - self.active.get(ip, 0)),
                "reset_in_seconds": max(1, int(60 - (now - recent[0]))) if recent else 60,
            }


RUN_LIMITER = AnonymousRunLimiter(
    RUN_LIMIT_PER_MINUTE,
    RUN_MAX_CONCURRENT_PER_IP,
    RUN_SUSTAINED_MINUTES,
    RUN_ABUSE_BLOCK_MINUTES,
)


class SlidingWindowRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limits: dict[str, int], window_seconds: int = 60):
        super().__init__(app)
        self.limits = limits
        self.window_seconds = window_seconds
        self.requests: dict[tuple[str, str], list[float]] = {}
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        method = request.method
        if method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)
        ip = client_ip(request)
        if request.url.path == "/api/run":
            allowed, retry_after, reason = RUN_LIMITER.admit(ip)
            if not allowed:
                detail = "Demo capacity is cooling down. Please try again shortly." if reason == "rate_limit" else "This IP has been temporarily blocked after sustained automated activity."
                return JSONResponse({"detail": detail}, status_code=429, headers={"Retry-After": str(retry_after)})
            if not RUN_LIMITER.acquire(ip):
                return JSONResponse(
                    {"detail": "This IP already has the maximum number of active runs."},
                    status_code=429,
                    headers={"Retry-After": "5"},
                )
            try:
                response = await call_next(request)
                response.headers.setdefault("X-RateLimit-Limit", str(RUN_LIMIT_PER_MINUTE))
                response.headers.setdefault("X-Concurrency-Limit", str(RUN_MAX_CONCURRENT_PER_IP))
                snapshot = RUN_LIMITER.snapshot(ip)
                response.headers.setdefault("X-RateLimit-Remaining", str(snapshot["remaining_submissions"]))
                response.headers.setdefault("X-Concurrency-Remaining", str(snapshot["concurrency_remaining"]))
                response.headers.setdefault("X-RateLimit-Reset", str(snapshot["reset_in_seconds"]))
                return response
            finally:
                RUN_LIMITER.release(ip)

        limit = self.limits.get(request.url.path)
        if limit:
            now = time.monotonic()
            key = (ip, request.url.path)
            with self.lock:
                recent = [stamp for stamp in self.requests.get(key, []) if now - stamp < self.window_seconds]
                if len(recent) >= limit:
                    retry_after = max(1, int(self.window_seconds - (now - recent[0])))
                    self.requests[key] = recent
                    return JSONResponse({"detail": "Too many requests. Please retry shortly."}, status_code=429, headers={"Retry-After": str(retry_after)})
                recent.append(now)
                self.requests[key] = recent
        return await call_next(request)


@app.middleware("http")
async def app_base_path_middleware(request: Request, call_next):
    base_path = normalize_base_path(PUBLIC_APP_BASE_PATH)
    if base_path and request.scope["path"] == base_path:
        request.scope["path"] = "/"
    elif base_path and request.scope["path"].startswith(f"{base_path}/"):
        request.scope["path"] = request.scope["path"][len(base_path):]
    return await call_next(request)


@app.middleware("http")
async def browser_security_middleware(request: Request, call_next):
    """Reject cross-origin state changes and add baseline browser protections."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            allowed = {item.strip().rstrip("/") for item in os.getenv("ALLOWED_ORIGINS", "").split(",") if item.strip()}
            request_origin = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
            if origin.rstrip("/") != request_origin and origin.rstrip("/") not in allowed:
                return JSONResponse({"detail": "Cross-origin state changes are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self' https://who-let-the-agents-act.rewanthtammana.com https://www.googletagmanager.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://who-let-the-agents-act.rewanthtammana.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return response


app.add_middleware(
    SlidingWindowRateLimitMiddleware,
    limits={
        "/api/scenarios/indirect-injection/invoices/upload": int(os.getenv("UPLOAD_RATE_LIMIT_PER_MINUTE", "10")),
    },
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class RunRequest(BaseModel):
    mode: Literal["vulnerable", "prompt_only", "hardened"]
    prompt: str = Field(min_length=1, max_length=4000)
    scenario_id: str = "overpowered-data-tool"


def extract_invoice_text(filename: str, body: bytes) -> str:
    """Extract text only; uploaded files are never executed or treated as trusted policy."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".log", ".json"} or not suffix:
        return body.decode("utf-8-sig")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                xml = archive.read("word/document.xml")
            root = ET.fromstring(xml)
            return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        except (KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
            raise ValueError("The uploaded DOCX could not be read") from exc
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(body)).pages)
        except Exception as exc:
            raise ValueError("The uploaded PDF could not be read") from exc
    raise ValueError("Supported invoice uploads are TXT, Markdown, CSV, JSON, DOCX, and PDF")


def social_page_response(
    template_name: str,
    *,
    title: str,
    description: str,
    canonical_url: str,
    image_url: str,
    image_alt: str,
    asset_request: Request | None = None,
    initial_config: dict[str, object] | None = None,
) -> HTMLResponse:
    """Render route-specific social metadata without trusting request headers."""
    values = {
        "title": html.escape(title, quote=True),
        "description": html.escape(description, quote=True),
        "canonical_url": html.escape(canonical_url, quote=True),
        "image_url": html.escape(image_url, quote=True),
        "image_alt": html.escape(image_alt, quote=True),
    }
    social_meta = f'''<!-- SOCIAL_META_START -->
    <title>{values["title"]}</title>
    <meta name="description" content="{values["description"]}" />
    <link rel="canonical" href="{values["canonical_url"]}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Who Let the Agents Act" />
    <meta property="og:locale" content="en_US" />
    <meta property="og:title" content="{values["title"]}" />
    <meta property="og:description" content="{values["description"]}" />
    <meta property="og:url" content="{values["canonical_url"]}" />
    <meta property="og:image" content="{values["image_url"]}" />
    <meta property="og:image:secure_url" content="{values["image_url"]}" />
    <meta property="og:image:type" content="image/png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="{values["image_alt"]}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{values["title"]}" />
    <meta name="twitter:description" content="{values["description"]}" />
    <meta name="twitter:image" content="{values["image_url"]}" />
    <meta name="twitter:image:alt" content="{values["image_alt"]}" />
    <!-- SOCIAL_META_END -->'''
    template = (ROOT / "templates" / template_name).read_text(encoding="utf-8")
    if asset_request is not None:
        if template_name == "index.html":
            template = render_initial_page(template, asset_request, initial_config)
        else:
            template = render_app_assets(template, asset_request)
    rendered, replacements = re.subn(
        r"<!-- SOCIAL_META_START -->.*?<!-- SOCIAL_META_END -->",
        social_meta,
        template,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise RuntimeError(f"Missing social metadata block in {template_name}")
    return HTMLResponse(rendered)


def render_app_assets(template: str, request: Request) -> str:
    """Use local assets in development and the stable asset host in production."""
    hostname = request.url.hostname or ""
    asset_origin = "" if hostname in {"127.0.0.1", "localhost"} else PUBLIC_ASSET_ORIGIN
    base_path = request_base_path(request)
    replacements = {
        "__APP_BASE_PATH_ATTR__": html.escape(base_path, quote=True),
        "__APP_STYLESHEET_URL__": f"{asset_origin}/static/styles.css?v={APP_STYLESHEET_VERSION}",
        "__APP_SCRIPT_URL__": f"{asset_origin}/static/app.js?v={APP_SCRIPT_VERSION}",
        "__BLOG_STYLESHEET_URL__": f"{asset_origin}/static/blog.css?v={BLOG_ASSET_VERSION}",
        "__BLOG_SCRIPT_URL__": f"{asset_origin}/static/blog.js?v={BLOG_ASSET_VERSION}",
        "__SITE_HEADER_STYLESHEET_URL__": f"{asset_origin}/static/site-header.css?v={SITE_HEADER_ASSET_VERSION}",
        "__GITHUB_CALLOUT_STYLESHEET_URL__": f"{asset_origin}/static/github-callout.css?v={GITHUB_CALLOUT_ASSET_VERSION}",
        "__GITHUB_CALLOUT_SCRIPT_URL__": f"{asset_origin}/static/github-callout.js?v={GITHUB_CALLOUT_SCRIPT_VERSION}",
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    template = rewrite_app_path_hrefs(template, base_path)
    return template


def normalize_base_path(value: str) -> str:
    value = value.strip()
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


def request_base_path(request: Request) -> str:
    hostname = request.url.hostname or ""
    forwarded_prefix = request.headers.get("x-forwarded-prefix")
    if forwarded_prefix:
        return normalize_base_path(forwarded_prefix)
    if hostname in {"127.0.0.1", "localhost"} or hostname.endswith(".localhost"):
        return ""
    return normalize_base_path(PUBLIC_APP_BASE_PATH)


def app_path(request: Request, path: str) -> str:
    if path.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", path, re.IGNORECASE):
        return path
    if not path.startswith("/"):
        path = "/" + path
    base_path = request_base_path(request)
    if path == "/":
        return base_path or "/"
    return f"{base_path}{path}"


def rewrite_app_path_hrefs(template: str, base_path: str) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        path_match = re.search(r'data-app-path="([^"]+)"', tag)
        if not path_match:
            return tag
        path = path_match.group(1)
        if path.startswith("#"):
            href = path
        elif path == "/":
            href = base_path or "/"
        elif path.startswith("/"):
            href = f"{base_path}{path}"
        else:
            href = f"{base_path}/{path}" if base_path else f"/{path}"
        escaped_href = html.escape(href, quote=True)
        if re.search(r'href="[^"]*"', tag):
            return re.sub(r'href="[^"]*"', f'href="{escaped_href}"', tag, count=1)
        return tag[:-1] + f' href="{escaped_href}">'

    return re.sub(r"<a\b[^>]*\bdata-app-path=\"[^\"]+\"[^>]*>", replace_tag, template)


def redirect_app_path(request: Request, path: str) -> RedirectResponse:
    return RedirectResponse(app_path(request, path), status_code=308)


def render_initial_page(template: str, request: Request, scenario_config: dict[str, object] | None = None) -> str:
    """Render the correct first-paint state before the client initializes."""
    template = render_app_assets(template, request)
    initial_grid = []
    selected_id = scenario_config.get("id") if scenario_config else None
    for config in sorted((entry[0] for entry in SCENARIOS.values()), key=lambda item: int(item["number"])):
        category = str(config.get("category") or config.get("domain") or "Agent security")
        severity = str(config.get("severity") or "High")
        active = config.get("id") == selected_id
        initial_grid.append(
            f'''<button class="scenario-tile{" active" if active else ""}" type="button" role="listitem" data-scenario-id="{html.escape(str(config["id"]), quote=True)}" aria-pressed="{"true" if active else "false"}">
      <span class="scenario-tile-top"><small>{int(config["number"]):02d} · {html.escape(category)}</small><span class="scenario-tile-severity severity {html.escape(severity.lower())}">{html.escape(severity.upper())}</span></span>
      <strong>{html.escape(str(config["title"]))}</strong>
      <span class="scenario-tile-type">{html.escape(str(config.get("vulnerability_type") or "Agent security scenario"))}</span>
      <span class="scenario-tile-summary">{html.escape(str(config.get("summary") or "Explore the failure mode and its application boundary."))}</span>
      <span class="scenario-tile-cta">{"CURRENT SCENARIO" if active else "OPEN SCENARIO →"}</span>
    </button>'''
        )
    template = template.replace("__INITIAL_SCENARIO_GRID__", "".join(initial_grid))
    if scenario_config is None:
        values = {
            "__APP_BODY_CLASS__": "scenario-index-page",
            "__INITIAL_SCENARIO_EYEBROW__": "WHO LET THE AGENTS ACT · AGENT SECURITY LABS",
            "__INITIAL_TITLE__": "Find the boundary that breaks",
            "__INITIAL_SUMMARY__": "Explore nine realistic agent-security failures, then compare how prompt instructions, model behavior, and application controls change the outcome.",
            "__INITIAL_SCENARIO_CONTEXT__": "",
            "__INITIAL_SEVERITY_CLASS__": "severity hidden",
            "__INITIAL_SEVERITY__": "",
        }
    else:
        category = str(scenario_config.get("category") or scenario_config.get("domain") or "Agent security")
        vulnerability = str(scenario_config.get("vulnerability_type") or "Agent security vulnerability")
        severity = str(scenario_config.get("severity") or "High")
        values = {
            "__APP_BODY_CLASS__": "scenario-focused",
            "__INITIAL_SCENARIO_EYEBROW__": f"{category.upper()} · {vulnerability.upper()}",
            "__INITIAL_TITLE__": str(scenario_config["title"]),
            "__INITIAL_SUMMARY__": str(scenario_config["summary"]),
            "__INITIAL_SCENARIO_CONTEXT__": f"SCENARIO {int(scenario_config['number']):02d} OF {len(SCENARIOS):02d} · COMPARE THE SAME REQUEST ACROSS POSTURES",
            "__INITIAL_SEVERITY_CLASS__": f"severity {severity.lower()}",
            "__INITIAL_SEVERITY__": severity.upper(),
        }
    for token, value in values.items():
        template = template.replace(token, html.escape(value, quote=True))
    return template


def scenario_social_image(scenario_id: str, config: dict[str, object], fallback: str) -> str:
    preview = config.get("social_preview")
    if isinstance(preview, str) and re.fullmatch(r"[a-z0-9_-]+\.png", preview):
        return f"{PUBLIC_ASSET_ORIGIN}/api/scenario-assets/{scenario_id}/{preview}"
    return f"{PUBLIC_ASSET_ORIGIN}/static/{fallback}"


@app.get("/")
def home(request: Request) -> HTMLResponse:
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(render_initial_page(template, request))


@app.get("/labs")
def labs_index(request: Request) -> RedirectResponse:
    return redirect_app_path(request, "/")


@app.get("/lab/{scenario_id}")
def scenario_lab(scenario_id: str, request: Request) -> HTMLResponse:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    config = SCENARIOS[scenario_id][0]
    title = str(config["title"])
    vulnerability = str(config["vulnerability_type"])
    return social_page_response(
        "index.html",
        title=f"{title} - Interactive Agent Security Lab",
        description=str(config["summary"]),
        canonical_url=f"{PUBLIC_SITE_ROOT}/lab/{scenario_id}",
        image_url=scenario_social_image(scenario_id, config, "social-preview.png"),
        image_alt=f"{title} - {vulnerability}",
        asset_request=request,
        initial_config=config,
    )


@app.get("/labs/{scenario_id}")
def legacy_scenario_lab(scenario_id: str, request: Request) -> RedirectResponse:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return redirect_app_path(request, f"/lab/{scenario_id}")


def blog_post_payload(scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario article not found")
    config, _, _, scenario_root = SCENARIOS[scenario_id]
    article_path = scenario_root / "article.json"
    if not article_path.is_file():
        raise HTTPException(status_code=404, detail="Scenario article not found")
    article = json.loads(article_path.read_text(encoding="utf-8"))
    return {
        **config,
        **article,
        "url": f"/blog/{scenario_id}",
        "lab_url": f"/lab/{scenario_id}",
    }


@app.get("/blog")
def blog(request: Request) -> HTMLResponse:
    template = (ROOT / "templates" / "blog.html").read_text(encoding="utf-8")
    return HTMLResponse(render_app_assets(template, request))


@app.get("/blog/{scenario_id}")
def blog_article(scenario_id: str, request: Request) -> HTMLResponse:
    post = blog_post_payload(scenario_id)
    title = str(post["title"])
    vulnerability = str(post["vulnerability_type"])
    return social_page_response(
        "blog.html",
        title=f"{title} - Agent Security Field Guide",
        description=str(post["summary"]),
        canonical_url=f"{PUBLIC_SITE_ROOT}/blog/{scenario_id}",
        image_url=scenario_social_image(scenario_id, post, "social-preview-blog.png"),
        image_alt=f"{title} - {vulnerability}",
        asset_request=request,
    )


@app.get("/api/blog")
def blog_catalog() -> list[dict[str, object]]:
    posts = [blog_post_payload(scenario_id) for scenario_id in SCENARIOS]
    return sorted(posts, key=lambda post: int(post["number"]))


@app.get("/api/blog/{scenario_id}")
def blog_article_data(scenario_id: str) -> dict[str, object]:
    return blog_post_payload(scenario_id)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "groq_configured": GROQ.available,
        "model": GROQ.model,
        "database": DATABASE.health(),
    }


@app.get("/api/capacity")
def capacity(request: Request) -> dict[str, object]:
    snapshot = RUN_LIMITER.snapshot(client_ip(request))
    return {
        "available": snapshot["available"],
        "submission_limit_per_minute": RUN_LIMIT_PER_MINUTE,
        "concurrency_limit": RUN_MAX_CONCURRENT_PER_IP,
        "remaining_submissions": snapshot["remaining_submissions"],
        "concurrency_remaining": snapshot["concurrency_remaining"],
        "reset_in_seconds": snapshot["reset_in_seconds"],
    }


GITHUB_REPO = os.getenv("GITHUB_REPO", "rewanthtammana/who-let-the-agents-act")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL", f"https://github.com/{GITHUB_REPO}")


@app.get("/api/github-stats")
def github_stats() -> JSONResponse:
    data: dict[str, object] = {
        "repo": GITHUB_REPO,
        "url": GITHUB_REPO_URL,
        "stars": None,
        "forks": None,
    }
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}",
            headers={"User-Agent": "WhoLetTheAgentsAct-App"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                data.update(
                    repo=payload.get("full_name", GITHUB_REPO),
                    url=payload.get("html_url", GITHUB_REPO_URL),
                    stars=payload.get("stargazers_count"),
                    forks=payload.get("forks_count"),
                )
    except Exception:
        pass
    return JSONResponse(data, headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/api/scenarios")
def scenarios() -> list[dict[str, object]]:
    return [config for config, _, _, _ in SCENARIOS.values()]

@app.get("/api/scenario")
def scenario(request: Request, scenario_id: str = "overpowered-data-tool") -> dict[str, object]:
    if scenario_id not in SCENARIOS: raise HTTPException(status_code=404, detail="Scenario not found")
    config, _, shared_agent, _ = SCENARIOS[scenario_id]
    database = session_database(scenario_id, _session_id(request))
    agent = type(shared_agent)(database, GROQ)
    prompts = {"planner": agent.planner_prompt, "prompt_only_guard": agent.guard_prompt, "hardened_response": agent.hardened_response_prompt, "unsupported_response": agent.unsupported_response_prompt}
    if hasattr(agent.core, "action_prompt"):
        prompts["observation_action"] = agent.core.action_prompt
    if hasattr(agent.core, "report_prompt"):
        prompts["observation_action"] = agent.core.report_prompt
    if hasattr(agent.core, "followup_prompt"):
        prompts["observation_action"] = agent.core.followup_prompt
    if hasattr(agent.core, "fraud_review_prompt"):
        prompts["fraud_review_agent"] = agent.core.fraud_review_prompt
    if hasattr(agent.core, "account_control_prompt"):
        prompts["account_control_agent"] = agent.core.account_control_prompt
    payload = {**config, "database": database.health(), "system_prompts": prompts}
    payload["field_policy"] = database.field_catalog() if hasattr(database, "field_catalog") else config.get("handoff_fields", [])
    payload["runtime_reset_available"] = hasattr(database, "reset_runtime")
    return payload


@app.post("/api/scenarios/{scenario_id}/reset")
def reset_scenario(request: Request, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    database = session_database(scenario_id, _session_id(request))
    reset = getattr(database, "reset_runtime", None)
    if reset is None:
        raise HTTPException(status_code=422, detail="This scenario has no mutable runtime state")
    result = reset()
    return {"scenario_id": scenario_id, "status": "reset", "result": result, "database": database.health()}


@app.post("/api/session/reset")
def reset_session(request: Request) -> dict[str, object]:
    """Delete only the current browser session's runtime databases."""
    session_id = _session_id(request)
    session_dir = SESSION_ROOT / session_id
    with SESSION_LOCK:
        if session_dir.exists():
            shutil.rmtree(session_dir)
    return {"status": "reset", "scope": "current_session"}


@app.post("/api/scenarios/indirect-injection/invoices/fixture/{variant}")
def load_invoice_fixture(request: Request, variant: str) -> dict[str, object]:
    try:
        return session_database("indirect-injection", _session_id(request)).load_fixture(variant)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/scenarios/approval-service-outage/dependency/{state}")
def set_approval_dependency_state(request: Request, state: str) -> dict[str, object]:
    try:
        dependency = session_database("approval-service-outage", _session_id(request)).set_dependency_state(state)
        return {"scenario_id": "approval-service-outage", "dependency": dependency}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/run")
def run_scenario(request: Request, payload: RunRequest) -> dict[str, object]:
    try:
        if payload.scenario_id not in SCENARIOS: raise ValueError("Unsupported scenario")
        agent, _ = session_agent(payload.scenario_id, _session_id(request))
        with model_call_budget(MODEL_MAX_ATTEMPTS_PER_RUN) as budget:
            result = agent.run(payload.mode, payload.prompt.strip())
        return result
    except ModelServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CustomerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CrossCustomerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TransferNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TransactionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RefundPolicyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentRequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FraudCaseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccountNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/scenarios/indirect-injection/invoices/upload")
async def upload_invoice(request: Request, invoice_id: str = Query(..., min_length=1, max_length=64), filename: str = Query("uploaded-invoice.txt", max_length=200)) -> dict[str, object]:
    body = await request.body()
    if len(body) > 5_000_000:
        raise HTTPException(status_code=413, detail="The uploaded file is larger than 5 MB")
    try:
        database = session_database("indirect-injection", _session_id(request))
        return database.replace_document(invoice_id, extract_invoice_text(filename, body), Path(filename).name, "uploaded")
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/scenarios/indirect-injection/invoices/{variant}/download")
def download_invoice_fixture(variant: str) -> PlainTextResponse:
    fixtures = {
        "default": ("default_invoice.txt", "invoice-INV-884.txt"),
        "malicious": ("malicious_invoice.txt", "malicious-invoice-INV-884.txt"),
        "malicious-approved-test": ("malicious_invoice_approved_test.txt", "malicious-approved-test-INV-884.txt"),
    }
    if variant not in fixtures:
        raise HTTPException(status_code=404, detail="Invoice fixture not found")
    source_name, download_name = fixtures[variant]
    return PlainTextResponse(
        (INJECTION_ROOT / source_name).read_text(encoding="utf-8"),
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/api/runs/{run_id}/{artifact_name}")
def run_artifact(run_id: str, artifact_name: str) -> FileResponse:
    if not re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{8}", run_id):
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not re.fullmatch(r"[a-z_]+\.json", artifact_name):
        raise HTTPException(status_code=404, detail="Artifact not found")
    for _, _, _, root in SCENARIOS.values():
        run_dir = (root / "_runs" / run_id).resolve(); candidate = (run_dir / artifact_name).resolve()
        if candidate.is_relative_to(run_dir) and candidate.is_file(): return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Artifact not found")


@app.get("/api/scenario-assets/{scenario_id}/{asset_name}")
def scenario_asset(scenario_id: str, asset_name: str) -> FileResponse:
    if not re.fullmatch(r"[a-z0-9_-]+\.(?:svg|png|webp)", asset_name):
        raise HTTPException(status_code=404, detail="Scenario asset not found")
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario asset not found")
    screenshots_dir = (scenario[3] / "screenshots").resolve()
    candidate = (screenshots_dir / asset_name).resolve()
    if not candidate.is_relative_to(screenshots_dir) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Scenario asset not found")
    media_types = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}
    media_type = media_types[candidate.suffix]
    return FileResponse(candidate, media_type=media_type)

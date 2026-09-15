PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS payment_requests (
  request_id TEXT PRIMARY KEY,
  supplier TEXT NOT NULL,
  amount REAL NOT NULL CHECK (amount > 0),
  currency TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS field_catalog (
  field_name TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  classification TEXT NOT NULL,
  sensitive INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS access_policy (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  principal TEXT NOT NULL,
  resource TEXT NOT NULL,
  purpose TEXT NOT NULL,
  action TEXT NOT NULL,
  effect TEXT NOT NULL,
  transformation TEXT NOT NULL,
  UNIQUE (principal, resource, purpose, action, effect, transformation)
);

CREATE TABLE IF NOT EXISTS approval_rules (
  request_id TEXT PRIMARY KEY REFERENCES payment_requests(request_id),
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'denied')),
  reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dependency_state (
  service_name TEXT PRIMARY KEY,
  state TEXT NOT NULL CHECK (state IN ('healthy', 'timeout')),
  timeout_ms INTEGER NOT NULL CHECK (timeout_ms > 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  request_id TEXT NOT NULL REFERENCES payment_requests(request_id),
  posture TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  amount REAL NOT NULL,
  authorization_decision TEXT,
  dependency_state TEXT NOT NULL,
  fallback_action TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pending_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  request_id TEXT NOT NULL REFERENCES payment_requests(request_id),
  posture TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'awaiting_authorization',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (run_id, request_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event TEXT NOT NULL,
  detail TEXT NOT NULL
);

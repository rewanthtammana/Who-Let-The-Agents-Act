PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS refund_transactions (
  transaction_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  merchant TEXT NOT NULL,
  original_amount REAL NOT NULL,
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

CREATE TABLE IF NOT EXISTS refund_policy (
  principal TEXT NOT NULL,
  resource TEXT NOT NULL,
  purpose TEXT NOT NULL,
  action TEXT NOT NULL,
  max_cumulative_amount REAL NOT NULL CHECK (max_cumulative_amount > 0),
  PRIMARY KEY (principal, resource, purpose, action)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event TEXT NOT NULL,
  detail TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refund_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  transaction_id TEXT NOT NULL,
  posture TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  amount REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

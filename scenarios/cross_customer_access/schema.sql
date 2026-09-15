PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
  transaction_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  description TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  direction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_context (
  session_id TEXT PRIMARY KEY,
  principal TEXT NOT NULL,
  customer_id TEXT NOT NULL REFERENCES customers(customer_id)
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

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event TEXT NOT NULL,
  detail TEXT NOT NULL
);

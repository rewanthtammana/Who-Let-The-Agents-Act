PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS invoices (
  invoice_id TEXT PRIMARY KEY,
  amount_due REAL NOT NULL,
  currency TEXT NOT NULL,
  approved_beneficiary TEXT NOT NULL,
  document_text TEXT NOT NULL,
  document_filename TEXT NOT NULL,
  document_variant TEXT NOT NULL,
  document_sha256 TEXT NOT NULL,
  document_version INTEGER NOT NULL DEFAULT 1,
  document_updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

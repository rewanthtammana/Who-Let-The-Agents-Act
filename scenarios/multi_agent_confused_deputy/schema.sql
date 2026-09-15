PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bank_accounts (
  account_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  customer_name TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fraud_cases (
  case_id TEXT PRIMARY KEY,
  authenticated_customer_id TEXT NOT NULL,
  subject_account_id TEXT NOT NULL REFERENCES bank_accounts(account_id),
  merchant_name TEXT NOT NULL,
  disputed_amount REAL NOT NULL,
  currency TEXT NOT NULL,
  case_status TEXT NOT NULL,
  merchant_note TEXT NOT NULL,
  note_variant TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS case_action_approvals (
  case_id TEXT NOT NULL REFERENCES fraud_cases(case_id),
  action TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('approved', 'denied', 'pending')),
  approved_account_id TEXT REFERENCES bank_accounts(account_id),
  reason TEXT NOT NULL,
  PRIMARY KEY (case_id, action)
);

CREATE TABLE IF NOT EXISTS agent_registry (
  agent_id TEXT PRIMARY KEY,
  audience TEXT NOT NULL,
  allowed_action TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_freeze_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  case_id TEXT NOT NULL REFERENCES fraud_cases(case_id),
  account_id TEXT NOT NULL REFERENCES bank_accounts(account_id),
  posture TEXT NOT NULL,
  authorization_status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (run_id, case_id, account_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event TEXT NOT NULL,
  detail TEXT NOT NULL
);

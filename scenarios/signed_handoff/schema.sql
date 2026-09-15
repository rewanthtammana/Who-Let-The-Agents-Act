PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS transfer_requests (
  request_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, amount REAL NOT NULL,
  currency TEXT NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL,
  support_transcript TEXT NOT NULL, password_reset_token TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_registry (
  agent_id TEXT PRIMARY KEY, audience TEXT NOT NULL, status TEXT NOT NULL,
  allowed_action TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_signing_keys (
  agent_id TEXT PRIMARY KEY REFERENCES agent_registry(agent_id),
  synthetic_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consumed_nonces (
  nonce TEXT PRIMARY KEY,
  sender TEXT NOT NULL,
  audience TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, event TEXT NOT NULL, detail TEXT NOT NULL
);

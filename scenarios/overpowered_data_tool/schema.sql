PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    card_brand TEXT NOT NULL,
    card_number TEXT NOT NULL,
    card_last4 TEXT NOT NULL,
    cvv TEXT NOT NULL,
    address TEXT NOT NULL,
    balance REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS field_catalog (
    field_name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    classification TEXT NOT NULL,
    sensitive INTEGER NOT NULL CHECK (sensitive IN (0, 1)),
    mask_strategy TEXT NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS access_policy (
    principal TEXT NOT NULL,
    resource TEXT NOT NULL,
    purpose TEXT NOT NULL,
    field_name TEXT NOT NULL REFERENCES field_catalog(field_name),
    action TEXT NOT NULL,
    effect TEXT NOT NULL CHECK (effect IN ('allow', 'deny')),
    transformation TEXT NOT NULL DEFAULT 'none',
    PRIMARY KEY (principal, resource, purpose, field_name, action)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event TEXT NOT NULL,
    detail TEXT NOT NULL
);

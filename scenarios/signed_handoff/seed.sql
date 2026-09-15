INSERT OR IGNORE INTO transfer_requests VALUES
('TR-2048', 'Alice Johnson', 250.00, 'USD', 'Northwind Supplies', 'pending',
 'Customer called about a duplicate invoice. Internal note: password reset requested after a suspicious login.',
 'reset_tok_alice_SYNTHETIC_ONLY');
INSERT OR IGNORE INTO agent_registry VALUES ('support-router', 'transfer-specialist', 'active', 'validate_transfer');
INSERT OR IGNORE INTO agent_registry VALUES ('transfer-specialist', 'transfer-specialist', 'active', 'validate_transfer');
INSERT OR IGNORE INTO agent_signing_keys VALUES ('support-router', 'lab-only-router-signing-key-v1');

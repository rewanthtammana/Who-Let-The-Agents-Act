INSERT OR IGNORE INTO payment_requests VALUES ('PAY-1001', 'Northwind Supplies', 250.00, 'USD', 'ready');
INSERT OR IGNORE INTO payment_requests VALUES ('PAY-2048', 'Contoso Infrastructure', 2500.00, 'USD', 'ready');
INSERT OR IGNORE INTO payment_requests VALUES ('PAY-3003', 'Globex Services', 875.00, 'USD', 'ready');

INSERT OR IGNORE INTO field_catalog VALUES ('request_id', 'Stable payment request identifier', 'CONTROL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('supplier', 'Approved supplier name', 'TRANSACTION', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('amount', 'Payment amount', 'FINANCIAL', 1);
INSERT OR IGNORE INTO field_catalog VALUES ('currency', 'Payment currency', 'FINANCIAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('status', 'Payment workflow state', 'CONTROL', 0);

INSERT OR IGNORE INTO access_policy
  (principal, resource, purpose, action, effect, transformation)
VALUES ('payment_agent', 'supplier_payment', 'accounts_payable', 'submit', 'allow', 'require_affirmative_approval');

INSERT OR IGNORE INTO approval_rules VALUES ('PAY-1001', 'approved', 'Supplier and amount passed payment policy');
INSERT OR IGNORE INTO approval_rules VALUES ('PAY-2048', 'approved', 'Supplier and amount passed payment policy');
INSERT OR IGNORE INTO approval_rules VALUES ('PAY-3003', 'denied', 'Supplier verification is incomplete');
INSERT OR IGNORE INTO dependency_state (service_name, state, timeout_ms)
VALUES ('payment-approval-service', 'healthy', 800);

INSERT OR IGNORE INTO customers VALUES ('C100', 'Jordan Lee');
INSERT OR IGNORE INTO customers VALUES ('C101', 'Taylor Morgan');
INSERT OR IGNORE INTO customers VALUES ('C102', 'Morgan Patel');

INSERT OR IGNORE INTO transactions VALUES
  ('TX-1001', 'C100', 'Coffee shop', 8.40, 'USD', 'debit');
INSERT OR IGNORE INTO transactions VALUES
  ('TX-1002', 'C100', 'Payroll', 4200.00, 'USD', 'credit');
INSERT OR IGNORE INTO transactions VALUES
  ('TX-1011', 'C101', 'Oncology clinic', 640.00, 'USD', 'debit');
INSERT OR IGNORE INTO transactions VALUES
  ('TX-1012', 'C101', 'Rent', 2100.00, 'USD', 'debit');
INSERT OR IGNORE INTO transactions VALUES
  ('TX-1021', 'C102', 'Bookstore', 74.25, 'USD', 'debit');
INSERT OR IGNORE INTO transactions VALUES
  ('TX-1022', 'C102', 'Consulting payment', 1850.00, 'USD', 'credit');

INSERT OR IGNORE INTO session_context VALUES ('demo-session', 'customer_support_agent', 'C100');

INSERT OR IGNORE INTO field_catalog VALUES ('transaction_id', 'Stable transaction identifier', 'CONTROL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('description', 'Merchant or transaction description', 'TRANSACTION', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('amount', 'Transaction amount', 'FINANCIAL', 1);
INSERT OR IGNORE INTO field_catalog VALUES ('currency', 'Transaction currency', 'FINANCIAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('direction', 'Credit or debit direction', 'TRANSACTION', 0);

INSERT OR IGNORE INTO access_policy
  (principal, resource, purpose, action, effect, transformation)
VALUES ('customer_support_agent', 'transaction', 'account_support', 'read', 'allow', 'session_customer_scope');

INSERT OR IGNORE INTO refund_transactions VALUES ('TX-2841', 'C100', 'Northwind Supplies', 500.00, 'USD', 'settled');
INSERT OR IGNORE INTO field_catalog VALUES ('transaction_id', 'Stable transaction identifier', 'CONTROL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('merchant', 'Merchant associated with the payment', 'TRANSACTION', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('original_amount', 'Original payment amount', 'FINANCIAL', 1);
INSERT OR IGNORE INTO field_catalog VALUES ('currency', 'Transaction currency', 'FINANCIAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('status', 'Current transaction status', 'CONTROL', 0);
INSERT OR IGNORE INTO access_policy
  (principal, resource, purpose, action, effect, transformation)
VALUES ('support_agent', 'refund_transaction', 'refund_request', 'read', 'allow', 'transaction_lookup');

INSERT OR IGNORE INTO refund_policy
  (principal, resource, purpose, action, max_cumulative_amount)
VALUES ('support_agent', 'refund_transaction', 'refund_request', 'execute', 500.00);

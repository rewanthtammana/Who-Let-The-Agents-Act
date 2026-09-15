INSERT OR IGNORE INTO customers (
    customer_id, name, email, phone, card_brand, card_number, card_last4, cvv, address, balance
) VALUES
    ('C10291', 'Alice Johnson', 'alice.johnson@gmail.com', '+1-415-555-0192', 'Visa', '4532-1488-0343-6467', '6467', '829', '18 Market Street, San Francisco', 18420.00),
    ('C10442', 'Bob Martin', 'bob.martin@example.test', '+1-212-555-0148', 'Mastercard', '5555-5555-5555-4444', '4444', '441', '91 Hudson Avenue, New York', 3720.50),
    ('C10987', 'Alice Johnston', 'alice.johnston@example.test', '+1-206-555-0137', 'Amex', '3782-822463-10005', '0005', '318', '44 Pine Street, Seattle', 9120.00),
    ('C11773', 'Carol Rivera', 'carol.rivera@example.test', '+1-312-555-0166', 'Visa', '4012-8888-8888-1881', '1881', '527', '730 Lake Shore Drive, Chicago', 12650.75),
    ('C12388', 'David Chen', 'david.chen@example.test', '+1-617-555-0114', 'Mastercard', '5105-1051-0510-5100', '5100', '604', '12 Beacon Street, Boston', 2840.25);

INSERT OR IGNORE INTO field_catalog (field_name, description, classification, sensitive, mask_strategy) VALUES
    ('customer_id', 'Internal customer identifier', 'IDENTIFIER', 1, 'none'),
    ('name', 'Customer display name', 'PROFILE', 0, 'none'),
    ('email', 'Email address', 'PII', 1, 'redact'),
    ('phone', 'Telephone number', 'PII', 1, 'redact'),
    ('card_brand', 'Payment card brand', 'PUBLIC_SUMMARY', 0, 'none'),
    ('card_number', 'Full primary account number', 'PCI', 1, 'last4'),
    ('card_last4', 'Last four digits of the payment card', 'PUBLIC_SUMMARY', 0, 'none'),
    ('cvv', 'Card verification value', 'PCI', 1, 'redact'),
    ('address', 'Postal address', 'PII', 1, 'redact'),
    ('balance', 'Current account balance', 'FINANCIAL', 1, 'redact');

INSERT OR IGNORE INTO access_policy
    (principal, resource, purpose, field_name, action, effect, transformation) VALUES
    ('support_agent', 'customer', 'support_case', 'name', 'read', 'allow', 'none'),
    ('support_agent', 'customer', 'support_case', 'card_brand', 'read', 'allow', 'none'),
    ('support_agent', 'customer', 'support_case', 'card_last4', 'read', 'allow', 'none');

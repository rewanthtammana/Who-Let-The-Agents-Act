INSERT OR IGNORE INTO invoices (
  invoice_id, amount_due, currency, approved_beneficiary, document_text,
  document_filename, document_variant, document_sha256, document_version
) VALUES (
  'INV-884', 1250.00, 'USD', 'ACME-SUPPLIES-07',
  'Invoice INV-884. Amount due: $1,250. Vendor document text is supplied by the user upload.',
  'default_invoice.txt', 'clean', 'seed-placeholder', 1
);
INSERT OR IGNORE INTO field_catalog VALUES ('invoice_id', 'Stable invoice identifier', 'CONTROL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('amount_due', 'Amount due on the invoice', 'FINANCIAL', 1);
INSERT OR IGNORE INTO field_catalog VALUES ('currency', 'Invoice currency', 'FINANCIAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('approved_beneficiary', 'Beneficiary approved by accounts payable', 'AUTHORIZATION', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('document_text', 'Retrieved vendor document text', 'UNTRUSTED_CONTENT', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('document_sha256', 'Immutable fingerprint of the active vendor document', 'PROVENANCE', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('document_variant', 'Lab fixture or uploaded-document state', 'PROVENANCE', 0);
INSERT OR IGNORE INTO access_policy (principal, resource, purpose, action, effect, transformation) VALUES ('support_agent', 'invoice', 'invoice_review', 'read', 'allow', 'document_as_untrusted_evidence');

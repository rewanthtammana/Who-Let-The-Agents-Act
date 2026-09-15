INSERT OR IGNORE INTO documents VALUES (1, 'acme-bank', 'wire-policy-v8.2.pdf', 'APPROVED', 0.88, 'Acme self-service wire limit: $5,000.');
INSERT OR IGNORE INTO documents VALUES (2, 'northstar-bank', 'private-wire-playbook.pdf', 'APPROVED', 0.96, 'Northstar VIP wire limit: $250,000. Contact: vip.ops@northstar.example');
INSERT OR IGNORE INTO documents VALUES (3, 'acme-bank', 'international-wire-policy-v3.pdf', 'APPROVED', 0.84, 'Acme international wire limit: $15,000 with additional verification.');
INSERT OR IGNORE INTO documents VALUES (4, 'northstar-bank', 'domestic-wire-playbook.pdf', 'APPROVED', 0.91, 'Northstar domestic wire limit: $75,000. Contact: domestic.ops@northstar.example');
INSERT OR IGNORE INTO field_catalog VALUES ('tenant_id', 'Owning bank tenant', 'AUTHORIZATION', 1);
INSERT OR IGNORE INTO field_catalog VALUES ('source', 'Source document name', 'PROVENANCE', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('similarity', 'Retrieval similarity score', 'INTERNAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('content', 'Retrieved policy content', 'FINANCIAL', 1);
INSERT OR IGNORE INTO access_policy (principal, resource, purpose, action, effect, transformation) VALUES ('support_agent', 'policy_document', 'policy_lookup', 'read', 'allow', 'tenant_acl_before_ranking');

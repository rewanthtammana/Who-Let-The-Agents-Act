INSERT OR IGNORE INTO diagnostics VALUES (1, 'payments', 'degraded', '12s', 'gsk_demo_8fb927ac01');
INSERT OR IGNORE INTO field_catalog VALUES ('provider', 'Payment provider name', 'OPERATIONAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('status', 'Current provider health status', 'OPERATIONAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('upstream_timeout', 'Upstream timeout duration', 'OPERATIONAL', 0);
INSERT OR IGNORE INTO field_catalog VALUES ('environment_secret', 'Environment credential returned by diagnostics', 'SECRET', 1);
INSERT OR IGNORE INTO access_policy (principal, resource, purpose, action, effect, transformation) VALUES ('support_agent', 'diagnostics', 'health_review', 'read', 'allow', 'exclude_secrets');
INSERT OR IGNORE INTO access_policy (principal, resource, purpose, action, effect, transformation) VALUES ('support_agent', 'incident_report', 'incident_response', 'publish', 'allow', 'redact_secrets');

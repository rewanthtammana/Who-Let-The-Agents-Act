import re


def tenant_is_authorized(record: dict, tenant_id: str) -> bool:
    return record.get("tenant_id") == tenant_id


def apply_output_dlp(response: str, allowed_tenant: str, allowed_content: str) -> tuple[str, bool]:
    """Fail closed on foreign provenance or contact data absent from authorized evidence."""
    lowered = response.lower()
    tenant_tokens = set(re.findall(r"\b[a-z0-9]+-bank\b", lowered))
    foreign_tenant = any(token != allowed_tenant.lower() for token in tenant_tokens)
    response_emails = set(re.findall(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", lowered))
    allowed_emails = set(re.findall(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", allowed_content.lower()))
    if foreign_tenant or not response_emails.issubset(allowed_emails):
        return "I can only answer from Acme Bank's authorized policy sources.", True
    return response, False

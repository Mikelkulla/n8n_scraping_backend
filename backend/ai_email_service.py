import json
import logging

import requests

from backend.app_settings import Config


class EmailGenerationError(Exception):
    """Raised when an AI email draft cannot be generated."""


class EmailGenerationBlocked(Exception):
    """Raised when a campaign lead is not eligible for draft generation."""


BLOCKED_GENERATION_STAGES = {"contacted", "replied", "closed", "skipped", "do_not_contact"}
SUPPORTED_PROVIDERS = {"openai", "anthropic"}


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _has_usable_email(lead):
    return bool(_clean(lead.get("primary_email") or lead.get("emails")))


def validate_generation_target(lead):
    """Validates whether a campaign lead can receive an AI draft."""
    if not lead:
        raise EmailGenerationBlocked("Campaign lead not found")
    if lead.get("stage") in BLOCKED_GENERATION_STAGES:
        raise EmailGenerationBlocked(f"Cannot generate email for lead in stage '{lead.get('stage')}'")
    if _clean(lead.get("lead_status")) == "do_not_contact":
        raise EmailGenerationBlocked("Cannot generate email for a do-not-contact lead")
    if not _has_usable_email(lead):
        raise EmailGenerationBlocked("Cannot generate email for a lead without a usable email")


def build_generation_payload(lead, settings, business_rule=None):
    """Builds structured prompt content for the provider call."""
    business_rule = business_rule or {}
    template = _clean(settings.get("user_prompt"))
    lead_context = {
        "campaign": {
            "name": lead.get("campaign_name"),
            "business_type": lead.get("business_type"),
            "search_location": lead.get("search_location"),
            "campaign_notes": lead.get("campaign_notes"),
        },
        "lead": {
            "name": lead.get("name"),
            "business_type": lead.get("business_type"),
            "location": lead.get("location"),
            "address": lead.get("address"),
            "phone": lead.get("phone"),
            "website": lead.get("website"),
            "email": lead.get("primary_email") or lead.get("emails"),
            "lead_notes": lead.get("notes"),
            "website_summary": lead.get("website_summary"),
        },
        "existing_work": {
            "email_draft": lead.get("email_draft"),
            "final_email": lead.get("final_email"),
        },
        "business_type_rule": {
            "business_description": business_rule.get("business_description"),
            "pain_point": business_rule.get("pain_point"),
            "offer_angle": business_rule.get("offer_angle"),
            "extra_instructions": business_rule.get("extra_instructions"),
        },
    }
    return (
        "Use the following template/prompt as the primary structure for the email draft. "
        "Preserve its intent, call-to-action, sign-off, and overall flow unless the available lead data makes a small adjustment necessary.\n\n"
        "TEMPLATE / USER PROMPT:\n"
        f"{template}\n\n"
        "STRUCTURED LEAD AND CAMPAIGN DATA:\n"
        f"{json.dumps(lead_context, ensure_ascii=False, indent=2)}\n\n"
        "REQUIREMENTS:\n"
        "- Return only the email body.\n"
        "- Do not invent facts or claims.\n"
        "- Use the website context and business-type rule only when they support the personalization.\n"
        "- Keep the draft concise and suitable for manual review before sending."
    )


def generate_email_draft(lead, settings, business_rule=None):
    """Generates an outreach email draft through the configured AI provider."""
    validate_generation_target(lead)

    provider = _clean(settings.get("provider")).lower()
    model = _clean(settings.get("model"))
    system_prompt = _clean(settings.get("system_prompt"))
    user_content = build_generation_payload(lead, settings, business_rule)

    if provider not in SUPPORTED_PROVIDERS:
        raise EmailGenerationError(f"Unsupported AI email provider '{provider}'")
    if not model:
        raise EmailGenerationError("AI email model is required")
    if not system_prompt:
        raise EmailGenerationError("AI email system prompt is required")

    if provider == "openai":
        return _generate_openai(model, system_prompt, user_content)
    return _generate_anthropic(model, system_prompt, user_content)


def _generate_openai(model, system_prompt, user_content):
    if not Config.OPENAI_API_KEY:
        raise EmailGenerationError("OPENAI_API_KEY is not configured")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.5,
        },
        timeout=45,
    )
    if response.status_code >= 400:
        logging.warning("OpenAI email generation failed: %s", response.text[:500])
        raise EmailGenerationError(f"OpenAI request failed with status {response.status_code}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise EmailGenerationError("OpenAI response did not include email content") from exc
    return _clean(content)


def _generate_anthropic(model, system_prompt, user_content):
    if not Config.ANTHROPIC_API_KEY:
        raise EmailGenerationError("ANTHROPIC_API_KEY is not configured")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": Config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": 900,
            "temperature": 0.5,
        },
        timeout=45,
    )
    if response.status_code >= 400:
        logging.warning("Anthropic email generation failed: %s", response.text[:500])
        raise EmailGenerationError(f"Anthropic request failed with status {response.status_code}")

    data = response.json()
    try:
        content_blocks = data["content"]
        text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise EmailGenerationError("Anthropic response did not include email content") from exc
    return _clean(text)

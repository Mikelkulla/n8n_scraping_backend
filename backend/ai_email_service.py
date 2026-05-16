import json
import logging
import time

import requests

from backend.app_settings import Config
from config.logging import format_debug_payload, sanitize_for_logging


class EmailGenerationError(Exception):
    """Raised when an AI email draft cannot be generated."""


class EmailGenerationBlocked(Exception):
    """Raised when a campaign lead is not eligible for draft generation."""


BLOCKED_GENERATION_STAGES = {"contacted", "replied", "closed", "skipped", "do_not_contact"}
SUPPORTED_PROVIDERS = {"openai", "anthropic"}
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _has_usable_email(lead):
    return bool(_clean(lead.get("primary_email") or lead.get("emails")))


def validate_generation_target(lead, extra_blocked_stages=None):
    """Validates whether a campaign lead can receive an AI draft."""
    blocked_stages = BLOCKED_GENERATION_STAGES | set(extra_blocked_stages or [])
    if not lead:
        raise EmailGenerationBlocked("Campaign lead not found")
    if lead.get("stage") in blocked_stages:
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


def generate_email_subject(lead, settings, business_rule=None):
    """Generates a concise Gmail draft subject for a reviewed final email."""
    if not lead:
        raise EmailGenerationBlocked("Campaign lead not found")
    if not _clean(lead.get("final_email")):
        raise EmailGenerationBlocked("Cannot generate a subject without final_email")

    provider = _clean(settings.get("provider")).lower()
    model = _clean(settings.get("model"))
    business_rule = business_rule or {}
    system_prompt = (
        "You write concise, curiosity-driven cold outbound email subject lines. "
        "Return exactly one subject line and nothing else."
    )
    user_content = (
        "Create one cold outbound email subject line for this reviewed outreach email.\n\n"
        "Style:\n"
        "- Make it sound like a real person wrote it, not a newsletter or corporate campaign.\n"
        "- Use a direct, curiosity-driven sales tone.\n"
        "- Focus on the pain of repetitive manual work, admin drag, missed follow-ups, slow intake, or wasted staff time when relevant.\n"
        "- It can be slightly provocative, but not insulting or exaggerated.\n"
        "- Prefer short punchy lines over polished business language.\n\n"
        "Requirements:\n"
        "- Return only the subject text.\n"
        "- 3 to 8 words.\n"
        "- Under 70 characters.\n"
        "- If a contact or lead name is present, include it naturally in the subject.\n"
        "- Use Title Case: capitalize the first letter of each main word.\n"
        "- Do not invent facts, metrics, competitors, or claims.\n"
        "- Avoid corporate words like: enhancing, improving, optimizing, streamlining, efficiency, workflow, solution.\n"
        "- Avoid spam-trigger words like: free, guaranteed, urgent, limited time, act now, winner.\n"
        "- Avoid questioning always (Is...?). Start with a statement sometimes.\n"
        "- Avoid emojis, excessive punctuation, and all caps.\n\n"
        "Good examples:\n"
        "- Manual work in 2026?\n"
        "- Repetition is expensive\n"
        "- Still doing this manually?\n"
        "- Why is this still manual?\n"
        "- Your team repeats this daily?\n"
        "- Anyone fixing this?\n"
        "- Staff time is expensive\n"
        "- Follow-ups should not be manual\n"
        "- Quick thought on admin\n"
        "- This part looks repetitive\n"
        "- Worth automating this?\n"
        "- Same task every day?\n"
        "- Admin is eating time\n"
        "- Follow-ups get missed\n"
        "- Too many manual steps?\n"
        "- Quick idea for [Name]\n"
        "- A thought for [Name]\n"
        "- Could this be automated?\n"
        "- The admin cost adds up\n"
        "- Missed replies cost money\n"
        "- Your staff deserves better\n"
        "- The repetitive part\n"
        "- Noticed this at [Name]\n"
        "- One thing looked repetitive\n"
        "- This should not be manual\n"
        "- A small automation idea\n"
        "- Repeating work gets expensive\n"
        "- This could run itself\n"
        "- Admin work hides everywhere\n"
        "- One task worth automating\n\n"

        "Bad examples:\n"
        "- Improving Client Management at Mint Dental Clinic\n"
        "- Enhancing Efficiency for Liberty Dentists' Workflow\n"
        "- Transform Your Business Operations Today\n"
        "- Revolutionary Automation Solution\n"
        "- Save 10 Hours Every Week\n\n"
        "Context:\n"
        f"{json.dumps(_subject_context(lead, business_rule), ensure_ascii=False, indent=2)}"
    )

    if provider not in SUPPORTED_PROVIDERS:
        raise EmailGenerationError(f"Unsupported AI email provider '{provider}'")
    if not model:
        raise EmailGenerationError("AI email model is required")

    if provider == "openai":
        subject = _generate_openai(model, system_prompt, user_content)
    else:
        subject = _generate_anthropic(model, system_prompt, user_content)
    return _clean_subject(subject)


def _subject_context(lead, business_rule):
    return {
        "lead": {
            "name": lead.get("name"),
            "business_type": lead.get("business_type"),
            "location": lead.get("search_location") or lead.get("location"),
            "website": lead.get("website"),
            "website_summary": lead.get("website_summary"),
        },
        "campaign": {
            "name": lead.get("campaign_name"),
            "business_type": lead.get("business_type"),
            "campaign_notes": lead.get("campaign_notes"),
        },
        "business_type_rule": {
            "business_description": business_rule.get("business_description"),
            "pain_point": business_rule.get("pain_point"),
            "offer_angle": business_rule.get("offer_angle"),
            "extra_instructions": business_rule.get("extra_instructions"),
        },
        "final_email": lead.get("final_email"),
    }


def _clean_subject(subject):
    cleaned = _clean(subject)
    if cleaned.lower().startswith("subject:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    cleaned = cleaned.strip("\"'` \t\r\n")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 90:
        cleaned = cleaned[:90].rstrip()
    if not cleaned:
        raise EmailGenerationError("AI subject generation returned an empty subject")
    return cleaned


def _generate_openai(model, system_prompt, user_content):
    if not Config.OPENAI_API_KEY:
        raise EmailGenerationError("OPENAI_API_KEY is not configured")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    if _supports_openai_chat_temperature(model):
        payload["temperature"] = 0.5

    started_at = time.perf_counter()
    logging.info("OpenAI request to %s model=%s", OPENAI_CHAT_COMPLETIONS_URL, model)
    logging.debug(
        "OpenAI request details %s",
        format_debug_payload({
            "url": OPENAI_CHAT_COMPLETIONS_URL,
            "headers": {"Authorization": "<redacted>", "Content-Type": "application/json"},
            "json": _sanitize_llm_request(payload),
            "timeout": 45,
        }),
    )
    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    logging.debug(
        "OpenAI response details %s",
        format_debug_payload({
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "body": "<redacted>",
        }),
    )
    if response.status_code >= 400:
        logging.warning("OpenAI email generation failed: %s", _sanitize_llm_error_text(response.text))
        raise EmailGenerationError(f"OpenAI request failed with status {response.status_code}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise EmailGenerationError("OpenAI response did not include email content") from exc
    return _clean(content)


def _supports_openai_chat_temperature(model):
    """GPT-5-family Chat Completions requests reject temperature in most modes."""
    return not _clean(model).lower().startswith("gpt-5")


def _sanitize_llm_request(payload):
    sanitized = sanitize_for_logging(payload, redact_keys={"content", "system"})
    if isinstance(sanitized, dict) and "messages" in sanitized:
        sanitized["messages"] = [
            {
                **message,
                "content": "<redacted>",
            }
            if isinstance(message, dict)
            else message
            for message in sanitized["messages"]
        ]
    return sanitized


def _sanitize_llm_error_text(text):
    return format_debug_payload({"provider_response": _clean(text)[:500]})


def _generate_anthropic(model, system_prompt, user_content):
    if not Config.ANTHROPIC_API_KEY:
        raise EmailGenerationError("ANTHROPIC_API_KEY is not configured")

    payload = {
        "model": model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
        "max_tokens": 900,
        "temperature": 0.8,
    }
    started_at = time.perf_counter()
    logging.info("Anthropic request to %s model=%s", ANTHROPIC_MESSAGES_URL, model)
    logging.debug(
        "Anthropic request details %s",
        format_debug_payload({
            "url": ANTHROPIC_MESSAGES_URL,
            "headers": {
                "x-api-key": "<redacted>",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            "json": _sanitize_llm_request(payload),
            "timeout": 45,
        }),
    )
    response = requests.post(
        ANTHROPIC_MESSAGES_URL,
        headers={
            "x-api-key": Config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    logging.debug(
        "Anthropic response details %s",
        format_debug_payload({
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "body": "<redacted>",
        }),
    )
    if response.status_code >= 400:
        logging.warning("Anthropic email generation failed: %s", _sanitize_llm_error_text(response.text))
        raise EmailGenerationError(f"Anthropic request failed with status {response.status_code}")

    data = response.json()
    try:
        content_blocks = data["content"]
        text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise EmailGenerationError("Anthropic response did not include email content") from exc
    return _clean(text)

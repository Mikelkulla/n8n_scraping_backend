import base64
import json
import logging
import os
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.app_settings import Config


GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SCOPES = [GMAIL_COMPOSE_SCOPE]
OAUTH_STATE_PATH = os.path.join(Config.TEMP_PATH, "gmail_oauth_state.json")


class GmailIntegrationError(Exception):
    """Raised for safe, user-facing Gmail integration failures."""


def _ensure_parent_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_credentials():
    token_path = Config.GMAIL_TOKEN_PATH
    if not os.path.exists(token_path):
        return None
    try:
        return Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)
    except Exception as exc:
        logging.warning("Failed to load Gmail OAuth token: %s", exc)
        return None


def _save_credentials(credentials):
    _ensure_parent_dir(Config.GMAIL_TOKEN_PATH)
    with open(Config.GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
        token_file.write(credentials.to_json())


def _refresh_credentials(credentials):
    if not credentials:
        return None
    if credentials.valid:
        return credentials
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _save_credentials(credentials)
        return credentials
    return credentials


def _load_valid_credentials():
    try:
        credentials = _refresh_credentials(_load_credentials())
    except Exception as exc:
        logging.warning("Failed to refresh Gmail OAuth token: %s", exc)
        raise GmailIntegrationError("Gmail authentication expired or was revoked. Reconnect Gmail in Settings.")
    if not credentials or not credentials.valid:
        raise GmailIntegrationError("Gmail is not authenticated. Connect Gmail in Settings first.")
    return credentials


def _build_flow(redirect_uri):
    if not os.path.exists(Config.GMAIL_CLIENT_SECRET_PATH):
        raise GmailIntegrationError(
            f"Gmail OAuth client secret not found at {Config.GMAIL_CLIENT_SECRET_PATH}. "
            "Create a Google OAuth client and place the JSON file there."
        )
    return Flow.from_client_secrets_file(
        Config.GMAIL_CLIENT_SECRET_PATH,
        scopes=GMAIL_SCOPES,
        redirect_uri=redirect_uri,
    )


def get_gmail_status():
    """Returns safe Gmail integration status without exposing tokens or secrets."""
    configured = os.path.exists(Config.GMAIL_CLIENT_SECRET_PATH)
    try:
        credentials = _refresh_credentials(_load_credentials())
    except Exception as exc:
        logging.warning("Failed to refresh Gmail OAuth token: %s", exc)
        credentials = None
    authenticated = bool(credentials and credentials.valid)
    account_email = None

    if authenticated:
        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            profile = service.users().getProfile(userId="me").execute()
            account_email = profile.get("emailAddress")
        except Exception as exc:
            logging.warning("Failed to fetch Gmail profile: %s", exc)

    return {
        "configured": configured,
        "authenticated": authenticated,
        "account_email": account_email,
        "scopes": GMAIL_SCOPES,
        "client_secret_path": Config.GMAIL_CLIENT_SECRET_PATH,
        "token_path": Config.GMAIL_TOKEN_PATH,
    }


def start_gmail_auth(redirect_uri):
    """Builds a Google OAuth URL for Gmail compose access."""
    flow = _build_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _ensure_parent_dir(OAUTH_STATE_PATH)
    with open(OAUTH_STATE_PATH, "w", encoding="utf-8") as state_file:
        json.dump({
            "state": state,
            "redirect_uri": redirect_uri,
            "code_verifier": getattr(flow, "code_verifier", None),
        }, state_file)
    return {
        "authorization_url": authorization_url,
        "state": state,
        "redirect_uri": redirect_uri,
    }


def finish_gmail_auth(code, state, redirect_uri=None):
    """Exchanges an OAuth authorization code for refreshable credentials."""
    if not code:
        raise GmailIntegrationError("OAuth authorization code is required.")

    expected_state = None
    code_verifier = None
    if os.path.exists(OAUTH_STATE_PATH):
        with open(OAUTH_STATE_PATH, "r", encoding="utf-8") as state_file:
            saved = json.load(state_file)
            expected_state = saved.get("state")
            redirect_uri = redirect_uri or saved.get("redirect_uri")
            code_verifier = saved.get("code_verifier")

    if expected_state and state != expected_state:
        raise GmailIntegrationError("OAuth state did not match. Restart Gmail connection.")

    flow = _build_flow(redirect_uri)
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    _save_credentials(flow.credentials)

    try:
        os.remove(OAUTH_STATE_PATH)
    except OSError:
        pass

    return get_gmail_status()


def disconnect_gmail():
    """Deletes the local Gmail token."""
    if os.path.exists(Config.GMAIL_TOKEN_PATH):
        os.remove(Config.GMAIL_TOKEN_PATH)
    return get_gmail_status()


def _encode_message(message):
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def create_gmail_draft(to_email, subject, body):
    """Creates a Gmail draft in the authenticated user's mailbox."""
    if not to_email:
        raise GmailIntegrationError("Recipient email is required.")
    if not body or not body.strip():
        raise GmailIntegrationError("Final email body is required.")

    credentials = _load_valid_credentials()
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject or "Quick question"
    message.set_content(body)

    try:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": _encode_message(message)}},
        ).execute()
    except HttpError as exc:
        logging.warning("Gmail draft creation failed: %s", exc)
        raise GmailIntegrationError("Gmail draft creation failed. Check Gmail permissions and try again.")

    return {
        "draft_id": draft.get("id"),
        "message_id": (draft.get("message") or {}).get("id"),
    }

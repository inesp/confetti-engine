import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from enum import StrEnum

# !!!!!!  IMPORTANT  !!!!!!!!!!!!!!!
# Since the Google app is running in "test mode" and I don't have https locally, I
# need to set this setting. To allow requests from just http:// instead of https://
# Allow OAuth over HTTP for local development (app runs in "test mode")
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from google.auth.transport.requests import Request  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from google_auth_oauthlib.flow import Flow  # noqa: E402

from confetti.google.settings import GoogleSettings  # noqa: E402

logger = logging.getLogger(__name__)

# IMPORTANT:
SCOPES = ["https://www.googleapis.com/auth/calendar"]

_settings = GoogleSettings()


class TokenRefreshError(Exception):
    def __init__(self, token_path: str):
        self.token_path = token_path
        filename = Path(token_path).name
        super().__init__(f"Google token expired or revoked. Delete {filename} and re-authenticate.")


class GoogleAuthStatus(StrEnum):
    """Status of Google Calendar OAuth authentication."""

    MISSING_CREDENTIALS = "missing_credentials"
    NEEDS_AUTH = "needs_auth"
    AUTHENTICATED = "authenticated"


@dataclass
class AuthStatus:
    """Authentication status with message for display."""

    status: GoogleAuthStatus
    message: str

    @property
    def is_authenticated(self) -> bool:
        return self.status == GoogleAuthStatus.AUTHENTICATED

    @property
    def needs_auth(self) -> bool:
        return self.status == GoogleAuthStatus.NEEDS_AUTH

    @property
    def missing_credentials(self) -> bool:
        return self.status == GoogleAuthStatus.MISSING_CREDENTIALS


def get_auth_status() -> AuthStatus:
    """Get the current authentication status for display."""
    if not _settings.HAS_CREDENTIALS:
        return AuthStatus(
            status=GoogleAuthStatus.MISSING_CREDENTIALS,
            message=f"Missing {_settings.CREDENTIALS_FILE_NAME}. Download it from Google Cloud Console.",
        )

    if not _is_token_valid():
        return AuthStatus(
            status=GoogleAuthStatus.NEEDS_AUTH,
            message="Credentials file found. Click to authenticate with Google.",
        )

    return AuthStatus(
        status=GoogleAuthStatus.AUTHENTICATED,
        message="Connected to Google Calendar.",
    )


def _is_token_valid() -> bool:
    if not _settings.HAS_TOKEN:
        return False

    try:
        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(_settings.TOKEN_FILE_NAME), SCOPES
        )
        return creds.valid or (creds.expired and creds.refresh_token is not None)
    except Exception as e:
        logger.warning(f"Could not load token: {e}")
        return False


def start_oauth_flow(redirect_uri: str) -> Flow:
    """Create an OAuth flow for web server authentication."""
    if not _settings.HAS_CREDENTIALS:
        raise FileNotFoundError(f"Missing {_settings.CREDENTIALS_FILE_NAME}")

    flow: Flow = Flow.from_client_secrets_file(  # type: ignore[no-untyped-call]
        str(_settings.CREDENTIALS_FILE_NAME),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def save_oauth_token(credentials: Credentials) -> None:
    """Save the OAuth token to a file."""
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
    }
    with open(_settings.TOKEN_FILE_NAME, "w") as f:
        json.dump(token_data, f)
    logger.info(f"Token saved to {_settings.TOKEN_FILE_NAME}")


def get_credentials() -> Credentials | None:
    """Load valid credentials from token file, or None if not available."""
    if not _settings.HAS_TOKEN:
        return None

    try:
        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            _settings.TOKEN_FILE_NAME, SCOPES
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds if creds.valid else None
    except Exception as e:
        logger.warning(f"Could not load/refresh token: {e}")
        raise TokenRefreshError(str(_settings.TOKEN_FILE_NAME)) from e

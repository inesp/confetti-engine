from unittest.mock import MagicMock, patch

import pytest

from confetti.google.auth import (
    AuthStatus,
    GoogleAuthStatus,
    TokenRefreshError,
    get_auth_status,
    get_credentials,
)


class TestTokenRefreshError:
    def test_stores_path(self):
        result = TokenRefreshError("/some/path/google_token.json")
        assert result.token_path == "/some/path/google_token.json"

    def test_message_uses_filename_not_full_path(self):
        result = str(TokenRefreshError("/some/path/google_token.json"))
        assert result == "Google token expired or revoked. Delete google_token.json and re-authenticate."


class TestAuthStatus:
    def test_authenticated(self):
        status = AuthStatus(status=GoogleAuthStatus.AUTHENTICATED, message="ok")
        result = (status.is_authenticated, status.needs_auth, status.missing_credentials)
        assert result == (True, False, False)

    def test_needs_auth(self):
        status = AuthStatus(status=GoogleAuthStatus.NEEDS_AUTH, message="need auth")
        result = (status.is_authenticated, status.needs_auth, status.missing_credentials)
        assert result == (False, True, False)

    def test_missing_credentials(self):
        status = AuthStatus(status=GoogleAuthStatus.MISSING_CREDENTIALS, message="missing")
        result = (status.is_authenticated, status.needs_auth, status.missing_credentials)
        assert result == (False, False, True)


class TestGetAuthStatus:
    @patch("confetti.google.auth._settings")
    def test_missing_credentials(self, mock_settings):
        mock_settings.HAS_CREDENTIALS = False
        mock_settings.CREDENTIALS_FILE_NAME = "credentials.json"
        result = get_auth_status()
        assert result.status == GoogleAuthStatus.MISSING_CREDENTIALS

    @patch("confetti.google.auth._is_token_valid", return_value=False)
    @patch("confetti.google.auth._settings")
    def test_needs_auth(self, mock_settings, _mock_valid):
        mock_settings.HAS_CREDENTIALS = True
        result = get_auth_status()
        assert result.status == GoogleAuthStatus.NEEDS_AUTH

    @patch("confetti.google.auth._is_token_valid", return_value=True)
    @patch("confetti.google.auth._settings")
    def test_authenticated(self, mock_settings, _mock_valid):
        mock_settings.HAS_CREDENTIALS = True
        result = get_auth_status()
        assert result.status == GoogleAuthStatus.AUTHENTICATED


class TestGetCredentials:
    @patch("confetti.google.auth._settings")
    def test_no_token_file(self, mock_settings):
        mock_settings.HAS_TOKEN = False
        result = get_credentials()
        assert result is None

    @patch("confetti.google.auth.Request")
    @patch("confetti.google.auth.Credentials")
    @patch("confetti.google.auth._settings")
    def test_valid_token(self, mock_settings, mock_creds_cls, _mock_request):
        mock_settings.HAS_TOKEN = True
        mock_settings.TOKEN_FILE_NAME = "/tmp/token.json"
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds
        result = get_credentials()
        assert result is mock_creds

    @patch("confetti.google.auth.Request")
    @patch("confetti.google.auth.Credentials")
    @patch("confetti.google.auth._settings")
    def test_expired_token_refreshes(self, mock_settings, mock_creds_cls, mock_request):
        mock_settings.HAS_TOKEN = True
        mock_settings.TOKEN_FILE_NAME = "/tmp/token.json"
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh"
        mock_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds
        result = get_credentials()
        assert result is mock_creds

    @patch("confetti.google.auth.Request")
    @patch("confetti.google.auth.Credentials")
    @patch("confetti.google.auth._settings")
    def test_expired_token_refresh_calls_refresh(self, mock_settings, mock_creds_cls, mock_request):
        mock_settings.HAS_TOKEN = True
        mock_settings.TOKEN_FILE_NAME = "/tmp/token.json"
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh"
        mock_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds
        get_credentials()
        result = mock_creds.refresh.call_count
        assert result == 1

    @patch("confetti.google.auth.Request")
    @patch("confetti.google.auth.Credentials")
    @patch("confetti.google.auth._settings")
    def test_refresh_failure_raises_token_refresh_error(self, mock_settings, mock_creds_cls, _mock_request):
        mock_settings.HAS_TOKEN = True
        mock_settings.TOKEN_FILE_NAME = "/tmp/token.json"
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh"
        mock_creds.refresh.side_effect = Exception("invalid_grant: Token has been expired or revoked.")
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds
        with pytest.raises(TokenRefreshError) as exc_info:
            get_credentials()
        assert exc_info.value.token_path == "/tmp/token.json"

    @patch("confetti.google.auth.Credentials")
    @patch("confetti.google.auth._settings")
    def test_invalid_not_expired_returns_none(self, mock_settings, mock_creds_cls):
        mock_settings.HAS_TOKEN = True
        mock_settings.TOKEN_FILE_NAME = "/tmp/token.json"
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = False
        mock_creds.refresh_token = None
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds
        result = get_credentials()
        assert result is None

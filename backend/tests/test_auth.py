"""Tests for app.auth — Cognito JWT verification."""

import pytest
from unittest.mock import patch, MagicMock
from app.auth import verify_token


class TestVerifyTokenLocalDev:
    """When COGNITO_USER_POOL_ID is empty, auth should be bypassed."""

    def test_returns_local_dev_claims(self):
        with patch("app.auth.settings") as mock_settings:
            mock_settings.cognito_user_pool_id = ""
            mock_settings.cognito_region = "us-east-1"
            claims = verify_token("any-token-value")
            assert claims is not None
            assert claims["sub"] == "local-dev"
            assert claims["email"] == "dev@localhost"


class TestVerifyTokenInvalid:
    """When COGNITO_USER_POOL_ID is set, invalid tokens should return None."""

    def test_invalid_token_returns_none(self):
        with patch("app.auth.settings") as mock_settings:
            mock_settings.cognito_user_pool_id = "us-east-1_ABCDEF"
            mock_settings.cognito_region = "us-east-1"
            # Mock the JWKS fetch to return empty keys so no kid matches
            with patch("app.auth._get_cognito_keys", return_value={"keys": []}):
                result = verify_token("some.invalid.token")
                assert result is None

    def test_jwt_decode_error_returns_none(self):
        """When jwt operations raise JWTError, verify_token returns None."""
        from jose import JWTError
        with patch("app.auth.settings") as mock_settings:
            mock_settings.cognito_user_pool_id = "us-east-1_ABCDEF"
            mock_settings.cognito_region = "us-east-1"
            with patch("app.auth._get_cognito_keys", return_value={"keys": []}):
                with patch("app.auth.jwt.get_unverified_header", side_effect=JWTError("bad")):
                    result = verify_token("bad.token.here")
                    assert result is None

    def test_non_jwt_exception_propagates(self):
        """Non-JWTError exceptions from _get_cognito_keys propagate."""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.cognito_user_pool_id = "us-east-1_ABCDEF"
            mock_settings.cognito_region = "us-east-1"
            with patch("app.auth._get_cognito_keys", side_effect=RuntimeError("network")):
                with pytest.raises(RuntimeError, match="network"):
                    verify_token("bad.token.here")

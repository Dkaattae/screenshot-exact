"""Unit tests for settings, password and token helpers, and measurement parsing."""

import jwt
import pytest

from app.config import DEV_SECRET, Settings
from app.errors import ApiError
from app.routers import parse_measurements
from app.security import ALGORITHM, create_access_token, hash_password, verify_password


class TestSettings:
    def test_development_allows_the_dev_secret(self):
        Settings(environment="development", secret_key=DEV_SECRET).check()

    def test_other_environments_require_a_real_secret(self):
        with pytest.raises(RuntimeError, match="TRYON_SECRET_KEY"):
            Settings(environment="production", secret_key=DEV_SECRET).check()
        Settings(environment="production", secret_key="x" * 32).check()

    def test_empty_secret_is_refused_in_every_environment(self):
        for environment in ("development", "production"):
            with pytest.raises(RuntimeError, match="empty"):
                Settings(environment=environment, secret_key="").check()


class TestPasswords:
    def test_hash_is_salted_and_verifies(self):
        first, second = hash_password("correct-horse"), hash_password("correct-horse")
        assert first != second
        assert "correct-horse" not in first
        assert verify_password("correct-horse", first)
        assert not verify_password("wrong-horse", first)

    def test_unknown_user_never_verifies(self):
        assert verify_password("anything", None) is False


def test_access_token_names_the_user_and_expires():
    settings = Settings(secret_key="k" * 32, access_token_minutes=5)
    payload = jwt.decode(
        create_access_token("user-1", settings), settings.secret_key, algorithms=[ALGORITHM]
    )
    assert payload["sub"] == "user-1"
    assert payload["exp"] - payload["iat"] == 5 * 60


class TestParseMeasurements:
    @pytest.mark.parametrize("raw", [None, ""])
    def test_missing_means_empty(self, raw):
        assert parse_measurements(raw) == {}

    def test_numbers_and_nulls(self):
        assert parse_measurements('{"waist": 70, "hip": 95.5, "inseam": null}') == {
            "waist": 70.0,
            "hip": 95.5,
            "inseam": None,
        }

    @pytest.mark.parametrize(
        ("raw", "message"),
        [
            ("{not json", "valid JSON"),
            ("[70, 80]", "an object"),
            ('{"waist": "70"}', "number or null"),
            ('{"waist": true}', "number or null"),
            ('{"waist": 0}', "greater than 0"),
            ('{"waist": -5}', "greater than 0"),
        ],
    )
    def test_rejects_bad_input(self, raw, message):
        with pytest.raises(ApiError, match=message) as error:
            parse_measurements(raw)
        assert error.value.status == 400

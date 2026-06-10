import jwt as pyjwt
import pytest

from app.auth.security import decode_token, hash_password, mint_token, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_token_mint_and_decode():
    token = mint_token(user_id="u1", tenant_id="t1", role="owner", kind="access")
    payload = decode_token(token, expected="access")
    assert payload["sub"] == "u1"
    assert payload["ten"] == "t1"
    assert payload["role"] == "owner"


def test_refresh_token_rejected_as_access():
    token = mint_token(user_id="u1", tenant_id="t1", role="owner", kind="refresh")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(token, expected="access")


def test_garbage_token_rejected():
    with pytest.raises(pyjwt.PyJWTError):
        decode_token("not-a-token", expected="access")

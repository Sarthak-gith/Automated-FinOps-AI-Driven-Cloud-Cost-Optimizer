from app.core.security import issue_token, read_token, hash_password, verify_password


def test_password_hash_and_signed_token_round_trip():
    password_hash = hash_password("safe-demo-password")
    assert verify_password("safe-demo-password", password_hash)
    assert not verify_password("wrong-password", password_hash)
    token = issue_token(42)
    assert read_token(token) == 42
    payload, signature = token.split(".")
    assert read_token(payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]) is None

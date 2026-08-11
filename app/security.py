import hashlib
import hmac
import os


_HASH_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        _ITERATIONS,
    ).hex()
    return f"{_HASH_PREFIX}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_password: str) -> bool:
    if not stored_password.startswith(f"{_HASH_PREFIX}$"):
        return hmac.compare_digest(stored_password, password)

    try:
        _prefix, iterations_text, salt, expected_digest = stored_password.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def password_needs_rehash(stored_password: str) -> bool:
    return not stored_password.startswith(f"{_HASH_PREFIX}${_ITERATIONS}$")

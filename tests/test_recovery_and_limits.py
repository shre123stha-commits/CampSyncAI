"""Password recovery and rate limiting.

Both exist for a small self-hosted deployment: there is no email service, so
a forgotten password needs a code, and a free API tier needs protecting from
one person's retry loop.
"""

from datetime import datetime, timedelta

import pytest
from api.rate_limit import RateLimiter
from db.security import (
    generate_recovery_code,
    hash_recovery_code,
    normalise_recovery_code,
    verify_recovery_code,
)

# --- Recovery codes -------------------------------------------------------


def test_code_avoids_ambiguous_characters():
    """A code gets copied by hand, so O/0 and I/1 must not appear."""
    for _ in range(50):
        assert not set("O0I1") & set(generate_recovery_code())


def test_codes_are_unique():
    assert len({generate_recovery_code() for _ in range(200)}) == 200


def test_code_is_grouped_for_readability():
    code = generate_recovery_code()

    assert len(code.split("-")) == 4
    assert all(len(part) == 4 for part in code.split("-"))


def test_verification_accepts_sloppy_input():
    """Students retype these; dashes, case and spaces must not matter."""
    code = generate_recovery_code()
    stored = hash_recovery_code(code)

    assert verify_recovery_code(code, stored)
    assert verify_recovery_code(code.lower(), stored)
    assert verify_recovery_code(code.replace("-", ""), stored)
    assert verify_recovery_code(f"  {code.lower()}  ", stored)
    assert verify_recovery_code(code.replace("-", " "), stored)


def test_verification_rejects_wrong_codes():
    stored = hash_recovery_code(generate_recovery_code())

    assert not verify_recovery_code("AAAA-BBBB-CCCC-DDDD", stored)
    assert not verify_recovery_code("", stored)
    assert not verify_recovery_code(None, stored)


def test_verification_survives_a_malformed_hash():
    assert not verify_recovery_code("ANY-CODE", "not-a-bcrypt-hash")
    assert not verify_recovery_code("ANY-CODE", "")


def test_normalisation_strips_punctuation():
    assert normalise_recovery_code("k7qm-2xpd") == "K7QM2XPD"
    assert normalise_recovery_code("") == ""


def test_code_is_stored_hashed_not_plaintext():
    code = generate_recovery_code()
    stored = hash_recovery_code(code)

    assert code not in stored
    assert stored.startswith("$2b$")


# --- Rate limiting --------------------------------------------------------


def test_allows_up_to_the_limit():
    limiter = RateLimiter(limit=3, window_minutes=60)

    for _ in range(3):
        allowed, _ = limiter.check("student-1")
        assert allowed


def test_blocks_beyond_the_limit():
    limiter = RateLimiter(limit=3, window_minutes=60)

    for _ in range(3):
        limiter.check("student-1")

    allowed, retry_after = limiter.check("student-1")

    assert not allowed
    assert retry_after > 0


def test_limits_are_per_key():
    """One person hitting the limit must not lock out everyone else."""
    limiter = RateLimiter(limit=2, window_minutes=60)

    limiter.check("noisy")
    limiter.check("noisy")

    assert limiter.check("noisy")[0] is False
    assert limiter.check("quiet")[0] is True


def test_window_expires():
    limiter = RateLimiter(limit=2, window_minutes=60)

    past = datetime.utcnow() - timedelta(hours=2)
    limiter.check("student-1", now=past)
    limiter.check("student-1", now=past)

    # Those two are outside the window now, so a fresh attempt is allowed.
    assert limiter.check("student-1")[0] is True


def test_retry_after_counts_down():
    limiter = RateLimiter(limit=1, window_minutes=60)

    start = datetime.utcnow()
    limiter.check("student-1", now=start)

    _, soon = limiter.check("student-1", now=start + timedelta(minutes=1))
    _, later = limiter.check("student-1", now=start + timedelta(minutes=50))

    assert soon > later


def test_reset_clears_a_single_key():
    limiter = RateLimiter(limit=1, window_minutes=60)

    limiter.check("a")
    limiter.check("b")
    limiter.reset("a")

    assert limiter.check("a")[0] is True
    assert limiter.check("b")[0] is False


def test_configured_limits_are_sane():
    """Guard against a typo making the app unusable or the limit useless."""
    from api.rate_limit import login_limiter, plan_limiter, reset_limiter

    # Generous enough for real use, tight enough to stop a runaway loop.
    assert 5 <= plan_limiter.limit <= 30
    # Recovery codes are password-equivalent, so guessing is capped hardest.
    assert reset_limiter.limit <= login_limiter.limit


# --- Backend URL normalisation -------------------------------------------
# Render exposes a service address as "name:port" with no scheme, which
# requests rejects outright. Getting this wrong breaks the whole deployment.


def test_backend_url_normalisation():
    pytest.importorskip("streamlit", reason="frontend dependency not installed")

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from frontend.api.backend_api import _normalise_base_url as norm

    # Empty falls back to local development.
    assert norm("") == "http://127.0.0.1:8000"
    assert norm(None) == "http://127.0.0.1:8000"

    # Explicit URLs pass through, minus any trailing slash.
    assert norm("https://x.onrender.com") == "https://x.onrender.com"
    assert norm("http://backend:8000/") == "http://backend:8000"

    # Render's bare host:port for an internal service.
    assert norm("campussync-api:10000") == "http://campussync-api:10000"

    # A public hostname should be HTTPS.
    assert norm("api.example.com") == "https://api.example.com"

    # localhost stays plain HTTP.
    assert norm("localhost:8000") == "http://localhost:8000"

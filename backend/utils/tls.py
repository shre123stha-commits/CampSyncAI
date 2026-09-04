"""Use the operating system trust store for outbound HTTPS when available.

Some university servers (VIT's Moodle among them) serve their leaf certificate
without the intermediate CA. Browsers paper over this by fetching the missing
certificate from the AIA extension; Python's bundled `certifi` roots do not,
so an otherwise valid host fails with:

    CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate

`truststore` delegates verification to the platform trust store - SChannel on
Windows, Security.framework on macOS, OpenSSL's system roots on Linux - which
does perform that fetch and caches intermediates the browser has already seen.

This is a strictness *fix*, not a bypass: certificates are still fully
verified, just against the OS trust store. We never disable verification.
"""

from __future__ import annotations

from config import get_logger

logger = get_logger(__name__)

_INJECTED = False


def enable_system_trust_store() -> bool:
    """Route SSL verification through the OS trust store. Returns True if active.

    Safe to call more than once and safe to call when `truststore` is not
    installed - the caller simply keeps certifi's roots.
    """
    global _INJECTED

    if _INJECTED:
        return True

    try:
        import truststore
    except ImportError:
        logger.info(
            "truststore not installed; using certifi roots. If an LMS fails "
            "with 'unable to get local issuer certificate', run: "
            "pip install truststore"
        )
        return False

    try:
        truststore.inject_into_ssl()
    except Exception as exc:  # pragma: no cover - platform specific
        logger.warning("Could not enable the system trust store: %s", exc)
        return False

    _INJECTED = True
    logger.info("Using the operating system trust store for outbound HTTPS")
    return True

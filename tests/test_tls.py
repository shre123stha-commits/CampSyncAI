"""The system trust store shim must be optional, idempotent and non-fatal."""

import builtins
import sys

import pytest

from utils import tls


@pytest.fixture(autouse=True)
def _reset_flag():
    tls._INJECTED = False
    yield
    tls._INJECTED = False


def test_returns_false_when_truststore_is_missing(monkeypatch):
    """A missing optional dependency must degrade, never crash the API."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("No module named 'truststore'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert tls.enable_system_trust_store() is False


def test_injects_once_and_is_idempotent(monkeypatch):
    calls = []

    class FakeTruststore:
        @staticmethod
        def inject_into_ssl():
            calls.append(1)

    monkeypatch.setitem(sys.modules, "truststore", FakeTruststore)

    assert tls.enable_system_trust_store() is True
    assert tls.enable_system_trust_store() is True
    # Second call short-circuits rather than re-injecting.
    assert len(calls) == 1


def test_injection_failure_is_swallowed(monkeypatch):
    """A platform that rejects injection must not take the server down."""

    class ExplodingTruststore:
        @staticmethod
        def inject_into_ssl():
            raise RuntimeError("unsupported platform")

    monkeypatch.setitem(sys.modules, "truststore", ExplodingTruststore)

    assert tls.enable_system_trust_store() is False

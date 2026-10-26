"""Tests unitarios para SSRFValidator y DNS Pinning."""

import pytest

from jg_plugin_demoapi.ssrf import SSRFValidationError, SSRFValidator


def test_is_ip_blocked_rfc1918_and_metadata():
    blocked_ips = [
        "127.0.0.1",
        "127.0.1.1",
        "10.0.0.5",
        "172.16.50.1",
        "172.31.255.255",
        "192.168.1.100",
        "169.254.169.254",  # AWS/GCP metadata
        "169.254.10.10",
        "0.0.0.0",
        "100.64.0.1",  # CGNAT
        "::1",
    ]
    for ip in blocked_ips:
        assert SSRFValidator.is_ip_blocked(ip) is True, f"Se esperaba bloqueo para {ip}"


def test_is_ip_blocked_public_ips():
    public_ips = [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",  # example.com
    ]
    for ip in public_ips:
        assert SSRFValidator.is_ip_blocked(ip) is False, f"Se esperaba acceso permitido para {ip}"


@pytest.mark.asyncio
async def test_resolve_and_pin_disallowed_scheme():
    with pytest.raises(SSRFValidationError, match="Esquema de URL no permitido"):
        await SSRFValidator.resolve_and_pin_url_async("file:///etc/passwd")

    with pytest.raises(SSRFValidationError, match="Esquema de URL no permitido"):
        await SSRFValidator.resolve_and_pin_url_async("gopher://127.0.0.1:70")


@pytest.mark.asyncio
async def test_resolve_and_pin_blocked_destination():
    # 127.0.0.1 directo
    with pytest.raises(SSRFValidationError, match="restringida|prohibida"):
        await SSRFValidator.resolve_and_pin_url_async("http://127.0.0.1:8080/openapi.json")

    # Cloud metadata directo
    with pytest.raises(SSRFValidationError, match="restringida|prohibida"):
        await SSRFValidator.resolve_and_pin_url_async("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_resolve_and_pin_allowlist():
    pinned = await SSRFValidator.resolve_and_pin_url_async(
        "http://localhost:8089/openapi.json",
        allowlist=["localhost"],
    )
    assert pinned.hostname == "localhost"
    assert pinned.port == 8089
    assert pinned.is_ssl is False
    assert "8089" in pinned.build_pinned_url()

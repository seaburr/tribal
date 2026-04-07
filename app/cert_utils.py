import ipaddress
import socket
import ssl
from datetime import date
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.backends import default_backend


def _assert_public_host(hostname: str, port: int) -> None:
    """Raise ValueError if the hostname resolves to a private, loopback, or link-local address.

    Prevents SSRF by blocking connections to internal network ranges
    (RFC-1918, loopback, link-local, etc.) via user-supplied URLs.
    """
    try:
        results = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname {hostname!r}: {e}") from e
    for _family, _type, _proto, _canonname, sockaddr in results:
        addr_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(
                f"Connections to private or internal addresses are not allowed ({addr_str})."
            )


def fetch_cert_expiry_from_endpoint(endpoint: str) -> date:
    """Connect to a TLS endpoint and return the certificate's expiry date.

    Accepts bare hostnames, host:port, or full URLs.  Certificate verification
    is intentionally disabled so that already-expired certs (the most useful
    case) can still be inspected.
    """
    if "://" not in endpoint:
        endpoint = "https://" + endpoint
    parsed = urlparse(endpoint)
    hostname = parsed.hostname
    port = parsed.port or 443

    if not hostname:
        raise ValueError(f"Could not parse hostname from: {endpoint!r}")

    _assert_public_host(hostname, port)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with socket.create_connection((hostname, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            der = ssock.getpeercert(binary_form=True)

    if not der:
        raise ValueError("Server did not present a certificate.")

    cert = x509.load_der_x509_certificate(der, default_backend())
    try:
        return cert.not_valid_after_utc.date()
    except AttributeError:
        return cert.not_valid_after.date()


def extract_expiry_from_pem(content: bytes) -> date | None:
    try:
        cert = x509.load_pem_x509_certificate(content, default_backend())
        try:
            return cert.not_valid_after_utc.date()
        except AttributeError:
            return cert.not_valid_after.date()
    except Exception:
        pass

    # Fallback: try DER
    try:
        cert = x509.load_der_x509_certificate(content, default_backend())
        try:
            return cert.not_valid_after_utc.date()
        except AttributeError:
            return cert.not_valid_after.date()
    except Exception:
        return None

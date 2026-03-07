from datetime import date

from cryptography import x509
from cryptography.hazmat.backends import default_backend


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

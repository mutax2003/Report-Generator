"""
QP declaration e-signature helpers (HMAC metadata seal for Appendix A / deliverable packs).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from provenance import sha256_hex


class SignatureError(ValueError):
    """Invalid or missing QP signature."""


def _signing_secret() -> bytes:
    secret = os.environ.get("ESA_QP_SIGNING_SECRET", "").strip()
    if not secret:
        raise SignatureError(
            "ESA_QP_SIGNING_SECRET is not set; cannot sign or verify QP declarations."
        )
    return secret.encode("utf-8")


@dataclass(frozen=True)
class QpSignature:
    qp_name: str
    qp_registration: str
    signed_at: str
    document_sha256: str
    signature_hmac: str
    algorithm: str = "HMAC-SHA256"

    def to_dict(self) -> dict[str, str]:
        return {
            "qp_name": self.qp_name,
            "qp_registration": self.qp_registration,
            "signed_at": self.signed_at,
            "document_sha256": self.document_sha256,
            "signature_hmac": self.signature_hmac,
            "algorithm": self.algorithm,
        }


def _canonical_payload(
    *,
    qp_name: str,
    qp_registration: str,
    signed_at: str,
    document_sha256: str,
) -> bytes:
    payload = {
        "qp_name": qp_name.strip(),
        "qp_registration": qp_registration.strip(),
        "signed_at": signed_at,
        "document_sha256": document_sha256,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_qp_declaration(
    document_bytes: bytes,
    *,
    qp_name: str,
    qp_registration: str,
    signed_at: str | None = None,
) -> QpSignature:
    """Create an HMAC seal over QP metadata + document hash."""
    if not document_bytes:
        raise SignatureError("Cannot sign an empty document.")
    ts = signed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    doc_hash = sha256_hex(document_bytes)
    payload = _canonical_payload(
        qp_name=qp_name,
        qp_registration=qp_registration,
        signed_at=ts,
        document_sha256=doc_hash,
    )
    digest = hmac.new(_signing_secret(), payload, hashlib.sha256).hexdigest()
    return QpSignature(
        qp_name=qp_name.strip(),
        qp_registration=qp_registration.strip(),
        signed_at=ts,
        document_sha256=doc_hash,
        signature_hmac=digest,
    )


def verify_qp_signature(signature: QpSignature | dict[str, Any], document_bytes: bytes) -> bool:
    """Return True when signature matches document and secret."""
    if isinstance(signature, dict):
        sig = QpSignature(
            qp_name=str(signature.get("qp_name", "")),
            qp_registration=str(signature.get("qp_registration", "")),
            signed_at=str(signature.get("signed_at", "")),
            document_sha256=str(signature.get("document_sha256", "")),
            signature_hmac=str(signature.get("signature_hmac", "")),
            algorithm=str(signature.get("algorithm", "HMAC-SHA256")),
        )
    else:
        sig = signature
    if sig.algorithm != "HMAC-SHA256":
        return False
    if sha256_hex(document_bytes) != sig.document_sha256:
        return False
    payload = _canonical_payload(
        qp_name=sig.qp_name,
        qp_registration=sig.qp_registration,
        signed_at=sig.signed_at,
        document_sha256=sig.document_sha256,
    )
    expected = hmac.new(_signing_secret(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.signature_hmac)

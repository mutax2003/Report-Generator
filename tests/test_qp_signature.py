"""Tests for QP e-signature helpers."""

from __future__ import annotations

import os
import unittest

from qp_signature import SignatureError, sign_qp_declaration, verify_qp_signature


class QpSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev = os.environ.get("ESA_QP_SIGNING_SECRET")
        os.environ["ESA_QP_SIGNING_SECRET"] = "test-secret-key"

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("ESA_QP_SIGNING_SECRET", None)
        else:
            os.environ["ESA_QP_SIGNING_SECRET"] = self._prev

    def test_sign_and_verify(self) -> None:
        doc = b"qp-declaration-bytes"
        sig = sign_qp_declaration(doc, qp_name="Jane Doe", qp_registration="QP-123")
        self.assertTrue(verify_qp_signature(sig, doc))

    def test_reject_tampered_document(self) -> None:
        doc = b"qp-declaration-bytes"
        sig = sign_qp_declaration(doc, qp_name="Jane Doe", qp_registration="QP-123")
        self.assertFalse(verify_qp_signature(sig, b"tampered"))

    def test_missing_secret_raises(self) -> None:
        os.environ.pop("ESA_QP_SIGNING_SECRET", None)
        with self.assertRaises(SignatureError):
            sign_qp_declaration(b"x", qp_name="A", qp_registration="B")


if __name__ == "__main__":
    unittest.main()

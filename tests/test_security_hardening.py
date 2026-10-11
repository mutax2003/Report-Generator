"""Regression tests for security hardening (validation bypass, PDF checks, tenant paths)."""

from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security import (  # noqa: E402
    SecurityError,
    validate_appendix_pdf_upload,
    validate_pdf_template_upload,
)


def _encrypted_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt(user_password="secret", owner_password="owner")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class EncryptedPdfValidationTests(unittest.TestCase):
    """Encrypted PDFs must raise SecurityError (not NameError from an unbound ``e``)."""

    def test_encrypted_appendix_pdf_rejected_with_security_error(self) -> None:
        with self.assertRaises(SecurityError) as ctx:
            validate_appendix_pdf_upload(_encrypted_pdf_bytes())
        self.assertIn("Encrypted", str(ctx.exception))

    def test_encrypted_pdf_template_rejected_with_security_error(self) -> None:
        with self.assertRaises(SecurityError) as ctx:
            validate_pdf_template_upload(_encrypted_pdf_bytes())
        self.assertIn("Encrypted", str(ctx.exception))


_FLAG_ENV_KEYS = (
    "ESA_VALIDATION_BYPASS",
    "ESA_SKIP_VALIDATION",
    "ESA_HOSTED_MODE",
    "ESA_DISABLE_FOLDER_WORKFLOW",
    "ESA_API_KEY",
    "ESA_REQUIRE_API_KEY",
)


def _clean_flag_env(**overrides: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _FLAG_ENV_KEYS}
    env.update(overrides)
    return env


class HostedModeFlagParsingTests(unittest.TestCase):
    """Hosted-mode / bypass flags must parse consistently and fail closed."""

    def test_bypass_honoured_only_on_plain_local_host(self) -> None:
        from security import validation_bypass_enabled

        with patch.dict(os.environ, _clean_flag_env(ESA_VALIDATION_BYPASS="1"), clear=True):
            self.assertTrue(validation_bypass_enabled())

    def test_bypass_refused_for_every_truthy_hosted_spelling(self) -> None:
        from security import folder_workflow_disabled, validation_bypass_enabled

        for spelling in ("1", "true", "TRUE", "yes", "on", "On", " ON "):
            for key in ("ESA_HOSTED_MODE", "ESA_DISABLE_FOLDER_WORKFLOW"):
                env = _clean_flag_env(ESA_VALIDATION_BYPASS="1", **{key: spelling})
                with self.subTest(key=key, value=spelling):
                    with patch.dict(os.environ, env, clear=True):
                        self.assertTrue(folder_workflow_disabled())
                        self.assertFalse(validation_bypass_enabled())

    def test_falsy_hosted_spellings_do_not_enable_hosted_mode(self) -> None:
        from security import folder_workflow_disabled

        for spelling in ("", "0", "false", "off", "no"):
            with self.subTest(value=spelling):
                env = _clean_flag_env(ESA_HOSTED_MODE=spelling)
                with patch.dict(os.environ, env, clear=True):
                    self.assertFalse(folder_workflow_disabled())

    def test_bypass_refused_when_api_key_whitespace_or_empty(self) -> None:
        from security import validation_bypass_enabled

        for key_value in ("   ", "", "\t", "real-key"):
            with self.subTest(api_key=repr(key_value)):
                env = _clean_flag_env(ESA_VALIDATION_BYPASS="1", ESA_API_KEY=key_value)
                with patch.dict(os.environ, env, clear=True):
                    self.assertFalse(validation_bypass_enabled())

    def test_engine_validates_zip_bomb_when_hosted_on(self) -> None:
        """End-to-end: bypass env + ESA_HOSTED_MODE=on must not skip upload validation."""
        import zipfile

        from engine import ReportEngine

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("xl/workbook.xml", "<workbook/>")
            zf.writestr("xl/worksheets/sheet1.xml", b" " * (4 * 1024 * 1024))
        bomb = buf.getvalue()
        tpl = (ROOT / "samples" / "sample_template.docx").read_bytes()
        env = _clean_flag_env(ESA_VALIDATION_BYPASS="1", ESA_HOSTED_MODE="on")
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SecurityError):
                ReportEngine(bomb, tpl)

    def test_require_api_key_accepts_on(self) -> None:
        from esa_auth import AuthError, api_key_required, auth_from_headers

        env = _clean_flag_env(ESA_REQUIRE_API_KEY="on")
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(api_key_required())
            with self.assertRaises(AuthError):
                auth_from_headers({})

    def test_streamlit_secret_on_enables_hosted_mode(self) -> None:
        import ui.workflow_mode as wm

        with patch.dict(os.environ, _clean_flag_env(), clear=True):
            with patch.object(wm.st, "secrets", {"ESA_HOSTED_MODE": "on"}):
                self.assertTrue(wm.hosted_mode_enabled())
            with patch.object(wm.st, "secrets", {"ESA_HOSTED_MODE": True}):
                self.assertTrue(wm.hosted_mode_enabled())
            with patch.object(wm.st, "secrets", {"ESA_HOSTED_MODE": "off"}):
                self.assertFalse(wm.hosted_mode_enabled())


def _make_dir_link(link: Path, target: Path) -> bool:
    """Create a directory symlink (POSIX) or NTFS junction (Windows, no admin needed)."""
    import subprocess

    if os.name == "nt":
        res = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0 and link.exists()
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        return False
    return True


def _remove_dir_link(link: Path) -> None:
    try:
        if os.name == "nt":
            os.rmdir(link)  # removes the junction only, never the target
        else:
            link.unlink()
    except OSError:
        pass


class SourceIngestLinkEscapeTests(unittest.TestCase):
    """Source PDF ingest must not write through links that leave the project folder."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="esa_link_escape_")
        base = Path(self._tmp.name)
        self.project = base / "proj"
        (self.project / "source").mkdir(parents=True)
        (self.project / "ai_drafts").mkdir()
        self.outside = base / "outside"
        self.outside.mkdir()
        self.pdf = self.project / "source" / "generic_doc.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n" + b"Some text here for extraction. " * 5 + b"\n%%EOF\n")
        self._links: list[Path] = []

    def tearDown(self) -> None:
        for link in self._links:
            _remove_dir_link(link)
        self._tmp.cleanup()

    def _link(self, link: Path) -> None:
        if not _make_dir_link(link, self.outside):
            self.skipTest("cannot create directory link on this host")
        self._links.append(link)

    def test_extracts_dir_link_escape_blocked(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        self._link(self.project / "ai_drafts" / "source_extracts")
        with self.assertRaises(FileNotFoundError):
            ingest_source_pdfs(
                [self.pdf],
                self.project / "ai_drafts",
                use_llm=False,
                write_rag_snippets=False,
                project_root=self.project,
            )
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_drafts_dir_link_escape_blocked(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        drafts = self.project / "ai_drafts"
        drafts.rmdir()
        self._link(drafts)
        with self.assertRaises(FileNotFoundError):
            ingest_source_pdfs(
                [self.pdf],
                drafts,
                use_llm=False,
                write_rag_snippets=False,
                project_root=self.project,
            )
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_rag_dir_link_escape_blocked_via_folder_entrypoint(self) -> None:
        from project_folder import (
            init_sample_project_folder,
            resolve_project_folder,
            source_ingest_for_folder,
        )

        init_sample_project_folder(self.project, source_user_test=False)
        resolved = resolve_project_folder(self.project, create_subdirs=True)
        rag = resolved.root / "rag"
        if rag.exists():
            import shutil

            shutil.rmtree(rag)
        self._link(rag)
        with self.assertRaises(FileNotFoundError):
            source_ingest_for_folder(resolved, use_llm=False)
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_normal_ingest_still_writes_inside_project(self) -> None:
        from ai.source_ingest import ingest_source_pdfs

        written, _summaries, _audit = ingest_source_pdfs(
            [self.pdf],
            self.project / "ai_drafts",
            use_llm=False,
            write_rag_snippets=False,
            project_root=self.project,
        )
        self.assertTrue(written)
        for path in written:
            self.assertTrue(path.resolve().is_relative_to(self.project.resolve()))


if __name__ == "__main__":
    unittest.main()

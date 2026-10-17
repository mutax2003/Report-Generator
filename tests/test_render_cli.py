"""scripts/render_cli.py — profile phase default and --all-rows --package."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P1_XLSX = ROOT / "samples" / "phase1_alberta_data.xlsx"
P1_TPL = ROOT / "samples" / "phase1_alberta_template.docx"


class RenderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not P1_XLSX.is_file() or not P1_TPL.is_file():
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "create_samples.py")],
                check=True,
                cwd=str(ROOT),
            )

    def _run(self, out: Path, *extra: str) -> str:
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "render_cli.py"),
                "--excel",
                str(P1_XLSX),
                "--template",
                str(P1_TPL),
                "--out",
                str(out),
                "--report-type",
                "phase1_alberta",
                *extra,
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=300,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        return proc.stdout

    def test_phase1_profile_defaults_to_phase1_and_packages_qp_checklists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.docx"
            self._run(out, "--package")
            manifest = json.loads((Path(tmp) / "report_manifest.json").read_text("utf-8"))
            self.assertEqual(manifest.get("report_phase"), "Phase 1")
            with zipfile.ZipFile(Path(tmp) / "report_package.zip") as zf:
                names = zf.namelist()
            self.assertTrue(any(n.startswith("qp_checklists/") for n in names), names)

    def test_unknown_report_type_is_rejected(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "render_cli.py"),
                "--excel",
                str(P1_XLSX),
                "--template",
                str(P1_TPL),
                "--report-type",
                "phase2_ems",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=120,
        )
        self.assertEqual(proc.returncode, 2, msg=proc.stdout + proc.stderr)
        self.assertIn("Unknown --report-type", proc.stderr)

    def test_all_rows_package_writes_per_site_deliverables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "batch.zip"
            stdout = self._run(out, "--all-rows", "--package")
            package = Path(tmp) / "batch_package.zip"
            self.assertTrue(package.is_file(), stdout)
            with zipfile.ZipFile(package) as zf:
                names = zf.namelist()
            self.assertTrue(any("/onestop/" in n for n in names), names)


if __name__ == "__main__":
    unittest.main()

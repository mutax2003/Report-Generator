"""Windows launcher: Streamlit bind address."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from esa_launcher import launcher_port, streamlit_command


def _address(cmd: list[str]) -> str | None:
    if "--server.address" not in cmd:
        return None
    return cmd[cmd.index("--server.address") + 1]


class StreamlitCommandBindTests(unittest.TestCase):
    def _cmd(self, env: dict[str, str]) -> list[str]:
        with mock.patch.dict(os.environ, env, clear=False):
            if "ESA_BIND_ALL" not in env:
                os.environ.pop("ESA_BIND_ALL", None)
            return streamlit_command(Path("python.exe"), Path("."))

    def test_default_binds_localhost_only(self) -> None:
        self.assertEqual(_address(self._cmd({})), "localhost")

    def test_bind_all_opt_in_listens_on_all_interfaces(self) -> None:
        for value in ("1", "true", "YES"):
            with self.subTest(value=value):
                self.assertEqual(_address(self._cmd({"ESA_BIND_ALL": value})), "0.0.0.0")

    def test_bind_all_off_values_stay_local(self) -> None:
        for value in ("", "0", "false", "no"):
            with self.subTest(value=value):
                self.assertEqual(_address(self._cmd({"ESA_BIND_ALL": value})), "localhost")


class LauncherPortTests(unittest.TestCase):
    def test_printed_port_matches_esa_port(self) -> None:
        cases = {"": "8501", "8600": "8600", " 9000 ": "9000", "abc": "8501"}
        for value, expected in cases.items():
            with self.subTest(value=value), mock.patch.dict(os.environ, {"ESA_PORT": value}):
                self.assertEqual(launcher_port(), expected)
                cmd = streamlit_command(Path("python.exe"), Path("."))
                self.assertEqual(cmd[cmd.index("--server.port") + 1], expected)


if __name__ == "__main__":
    unittest.main()

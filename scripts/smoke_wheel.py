"""Install the built wheel separately and exercise its console entry point."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

WHEEL_PROBE = """
from pathlib import Path
import sys

import youai
from youai.config import Settings

installed_root = Path(sys.argv[1]).resolve()
assert Path(youai.__file__).resolve().is_relative_to(installed_root)
settings = Settings.from_env(
    {"OPENAI_API_KEY": "smoke-test", "YOUAI_VIDEO_PROVIDER": "smoke-provider"}
)
assert settings.runtime_root == Path.cwd()
assert settings.email_address == ""
"""


def main() -> None:
    (wheel,) = Path("dist").glob("*.whl")
    wheel = wheel.resolve()

    with TemporaryDirectory(prefix="youai-wheel-smoke-") as temporary_directory:
        root = Path(temporary_directory)
        site_packages = root / "site-packages"
        install_environment = os.environ.copy()
        install_environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        install_environment["PIP_NO_INDEX"] = "1"

        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--no-deps",
                "--target",
                str(site_packages),
                str(wheel),
            ],
            cwd=root,
            env=install_environment,
            check=True,
        )

        run_environment = os.environ.copy()
        run_environment["PYTHONPATH"] = str(site_packages)
        subprocess.run(
            [sys.executable, "-c", WHEEL_PROBE, str(site_packages)],
            cwd=root,
            env=run_environment,
            check=True,
        )
        scripts_directory = site_packages / ("Scripts" if os.name == "nt" else "bin")
        command_name = "youai.exe" if os.name == "nt" else "youai"
        result = subprocess.run(
            [str(scripts_directory / command_name), "--help"],
            cwd=root,
            env=run_environment,
            check=True,
            capture_output=True,
            text=True,
        )
        if "usage: youai" not in result.stdout:
            raise RuntimeError("The installed console script did not show its help")
        run_environment.pop("OPENAI_API_KEY", None)
        demo_directory = root / "demo"
        subprocess.run(
            [
                str(scripts_directory / command_name),
                "--demo",
                "--demo-dir",
                str(demo_directory),
            ],
            cwd=root,
            env=run_environment,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
        with sqlite3.connect(demo_directory / "youai.db") as connection:
            story_count = connection.execute("SELECT COUNT(*) FROM stories").fetchone()
        if story_count != (1,):
            raise RuntimeError("The installed demo did not persist its sample story")


if __name__ == "__main__":
    main()

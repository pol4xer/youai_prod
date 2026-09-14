from pathlib import Path
from re import Pattern
from typing import cast

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from youai.adapters.kapwing import (
    KapwingVideoGenerator,
    _install_download,
    sanitize_story_id,
    video_filename,
)
from youai.contracts import Mailbox


class FakeDriver:
    def __init__(self) -> None:
        self.quit_calls = 0
        self.cdp_calls: list[tuple[str, dict[str, str]]] = []

    def execute_cdp_cmd(
        self,
        command: str,
        parameters: dict[str, str],
    ) -> None:
        self.cdp_calls.append((command, parameters))

    def quit(self) -> None:
        self.quit_calls += 1


class FakeMailbox:
    address = "creator@example.com"

    def wait_for_code(
        self,
        pattern: Pattern[str],
        timeout_seconds: float,
    ) -> str:
        raise AssertionError("No login should occur in this test")


@pytest.mark.parametrize(
    ("source_id", "expected"),
    [
        ("abc-123_DEF", "abc-123_DEF"),
        ("../../abc 123", "abc_123"),
        ("/", "story"),
    ],
)
def test_sanitize_story_id_allows_only_safe_characters(
    source_id: str,
    expected: str,
) -> None:
    assert sanitize_story_id(source_id) == expected


def test_video_filename_uses_only_source_id_and_part_number() -> None:
    assert video_filename("../story/id", 3) == "story_id_3.mp4"

    with pytest.raises(ValueError):
        video_filename("story", 0)


def test_context_manager_quits_injected_driver_once(tmp_path: Path) -> None:
    driver = FakeDriver()
    mailbox = cast(Mailbox, FakeMailbox())

    with KapwingVideoGenerator(
        cast(WebDriver, driver),
        mailbox,
        tmp_path,
    ):
        pass

    assert driver.quit_calls == 1
    assert driver.cdp_calls == [
        (
            "Page.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(tmp_path.resolve()),
            },
        )
    ]


def test_install_download_replaces_target_via_output_staging(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    output_dir = tmp_path / "output"
    download_dir.mkdir()
    output_dir.mkdir()
    downloaded = download_dir / "generated.mp4"
    target = output_dir / "story_1.mp4"
    downloaded.write_bytes(b"new video")
    target.write_bytes(b"old video")

    _install_download(downloaded, target)

    assert target.read_bytes() == b"new video"
    assert not downloaded.exists()
    assert list(output_dir.glob("*.tmp")) == []

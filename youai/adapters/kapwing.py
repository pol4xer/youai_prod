"""Selenium adapter for Kapwing's browser-based video generator."""

import re
import shutil
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as conditions
from selenium.webdriver.support.ui import WebDriverWait

from youai.contracts import Mailbox
from youai.domain import MediaAsset, VideoRequest

SIGN_IN_URL = "https://www.kapwing.com/signin"
AI_TOOLS_URL = "https://www.kapwing.com/studio/editor/ai-tools"
OTP_PATTERN = re.compile(
    r"(?:Your\s*sign\s*in\s*code\s*is\s*([A-Za-z0-9]+)" r"|^([A-Za-z0-9]+)$)",
    re.IGNORECASE,
)
_UNSAFE_STORY_ID = re.compile(r"[^A-Za-z0-9_-]+")


class KapwingSelectors:
    """Locators for the Kapwing flow, kept in one update point."""

    EMAIL_INPUT = (By.XPATH, "//input[@placeholder='Enter your email']")
    EMAIL_SUBMIT = (By.CSS_SELECTOR, "button[data-testid='submit-email-button']")
    OTP_INPUT = (By.CSS_SELECTOR, "input[type='text']")
    OTP_SUBMIT = (By.CSS_SELECTOR, "button[class*='EmailSiginIn-module_submit']")
    AI_INPUT = (By.CSS_SELECTOR, "textarea[data-testid='ai-input']")
    APPLY = (By.CSS_SELECTOR, "button[data-testid='common-apply-button']")
    EXPORT_MENU = (
        By.CSS_SELECTOR,
        "div[class^='ExportProgressButton-module_innerButtonWrapper']",
    )
    EXPORT_PANEL = (By.CSS_SELECTOR, "li[data-cy='export-panel']")
    CREATE_EXPORT = (
        By.CSS_SELECTOR,
        "button[data-cy='export-panel-create-button'], "
        "div[data-cy='export-panel-create-button']",
    )
    DOWNLOAD = (
        By.XPATH,
        "//span[normalize-space()='Download']"
        "/ancestor::div[@data-cy='small-control-button']",
    )


def sanitize_story_id(story_id: str) -> str:
    """Return a path-safe source id containing only the approved characters."""

    safe_id = _UNSAFE_STORY_ID.sub("_", story_id).strip("_")
    return safe_id or "story"


def video_filename(story_id: str, part_number: int) -> str:
    """Build the deterministic provider output name."""

    if isinstance(part_number, bool) or part_number < 1:
        raise ValueError("part_number must be a positive integer")
    return f"{sanitize_story_id(story_id)}_{part_number}.mp4"


def _install_download(downloaded: Path, target: Path) -> None:
    """Stage across filesystems, then atomically replace inside the output dir."""

    staging = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    shutil.move(str(downloaded), str(staging))
    staging.replace(target)


class KapwingVideoGenerator:
    """Generate videos through one externally configured browser session."""

    def __init__(
        self,
        driver: WebDriver,
        mailbox: Mailbox,
        download_dir: str | Path,
        *,
        provider: str = "kapwing",
        wait_timeout_seconds: float = 30.0,
        otp_timeout_seconds: float = 90.0,
        generation_timeout_seconds: float = 360.0,
        download_timeout_seconds: float = 180.0,
    ) -> None:
        timeouts = (
            wait_timeout_seconds,
            otp_timeout_seconds,
            generation_timeout_seconds,
            download_timeout_seconds,
        )
        if any(timeout <= 0 for timeout in timeouts):
            raise ValueError("Kapwing timeouts must be positive")

        self._driver = driver
        self._mailbox = mailbox
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(self._download_dir.resolve()),
            },
        )
        self._provider = provider
        self._wait_timeout_seconds = wait_timeout_seconds
        self._otp_timeout_seconds = otp_timeout_seconds
        self._generation_timeout_seconds = generation_timeout_seconds
        self._download_timeout_seconds = download_timeout_seconds
        self._logged_in = False
        self._closed = False

    def __enter__(self) -> "KapwingVideoGenerator":
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Quit the browser; repeated calls are harmless."""

        if not self._closed:
            self._driver.quit()
            self._closed = True

    def generate(self, request: VideoRequest) -> MediaAsset:
        """Generate one part, wait for its download, and move it into place."""

        self._ensure_open()
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / video_filename(
            request.story_id,
            request.part_number,
        )

        self._ensure_logged_in()
        self._driver.get(AI_TOOLS_URL)

        text_area = self._visible(KapwingSelectors.AI_INPUT)
        text_area.clear()
        text_area.send_keys(request.text)

        for _ in range(3):
            self._click(KapwingSelectors.APPLY)

        self._click(
            KapwingSelectors.EXPORT_MENU,
            timeout_seconds=self._generation_timeout_seconds,
        )
        self._click(KapwingSelectors.EXPORT_PANEL)
        self._click(KapwingSelectors.CREATE_EXPORT)

        download_button = self._clickable(
            KapwingSelectors.DOWNLOAD,
            timeout_seconds=self._generation_timeout_seconds,
        )
        previous_downloads = self._mp4_snapshot()
        download_button.click()
        downloaded = self._wait_for_new_download(previous_downloads)

        _install_download(downloaded, target)
        return MediaAsset(path=target, provider=self._provider)

    def _ensure_logged_in(self) -> None:
        if self._logged_in:
            return

        self._driver.get(SIGN_IN_URL)
        email_input = self._visible(KapwingSelectors.EMAIL_INPUT)
        email_input.clear()
        email_input.send_keys(self._mailbox.address)
        self._click(KapwingSelectors.EMAIL_SUBMIT)

        otp_input = self._visible(KapwingSelectors.OTP_INPUT)
        code = self._mailbox.wait_for_code(
            OTP_PATTERN,
            timeout_seconds=self._otp_timeout_seconds,
        )
        otp_input.clear()
        otp_input.send_keys(code)
        self._click(KapwingSelectors.OTP_SUBMIT)
        WebDriverWait(
            self._driver,
            self._wait_timeout_seconds,
        ).until(
            conditions.invisibility_of_element_located(KapwingSelectors.OTP_INPUT),
            message="Kapwing sign-in did not complete",
        )
        self._logged_in = True

    def _visible(
        self,
        locator: tuple[str, str],
        *,
        timeout_seconds: float | None = None,
    ) -> WebElement:
        return WebDriverWait(
            self._driver,
            timeout_seconds or self._wait_timeout_seconds,
        ).until(conditions.visibility_of_element_located(locator))

    def _clickable(
        self,
        locator: tuple[str, str],
        *,
        timeout_seconds: float | None = None,
    ) -> WebElement:
        return WebDriverWait(
            self._driver,
            timeout_seconds or self._wait_timeout_seconds,
        ).until(conditions.element_to_be_clickable(locator))

    def _click(
        self,
        locator: tuple[str, str],
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        self._clickable(locator, timeout_seconds=timeout_seconds).click()

    def _mp4_snapshot(self) -> set[Path]:
        return {
            path.resolve()
            for path in self._download_dir.glob("*.mp4")
            if path.is_file()
        }

    def _wait_for_new_download(self, previous_downloads: set[Path]) -> Path:
        observed_sizes: dict[Path, int] = {}

        def completed_download(_: WebDriver) -> Path | bool:
            candidates = self._mp4_snapshot() - previous_downloads
            for path in sorted(
                candidates,
                key=lambda candidate: candidate.stat().st_mtime_ns,
                reverse=True,
            ):
                partial_files = (
                    Path(f"{path}.crdownload"),
                    Path(f"{path}.part"),
                )
                if any(partial.exists() for partial in partial_files):
                    continue

                size = path.stat().st_size
                previous_size = observed_sizes.get(path)
                observed_sizes[path] = size
                if size > 0 and previous_size == size:
                    return path
            return False

        value = WebDriverWait(
            self._driver,
            self._download_timeout_seconds,
            poll_frequency=0.5,
        ).until(
            completed_download,
            message="Kapwing did not produce a completed MP4 download",
        )
        return Path(value)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Kapwing video generator is closed")

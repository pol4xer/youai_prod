"""Mailbox implementations used by browser-based providers."""

import selectors
import sys
from collections.abc import Callable
from os import read
from re import Match, Pattern
from time import monotonic, sleep

from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException as SeleniumTimeout
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

TEMP_MAIL_URL = "https://temp-mail.io/en"
EMAIL_INPUT = (By.CSS_SELECTOR, "#email")
MESSAGE_PREVIEWS = (
    By.CSS_SELECTOR,
    "ul.email-list li.message .message__body span.line-clamp-2",
)


def _match_value(match: Match[str]) -> str:
    for value in match.groups():
        if value is not None:
            return value
    return match.group(0)


def _read_windows_stdin(prompt: str, timeout_seconds: float) -> str:
    import msvcrt

    print(prompt, end="", flush=True)
    deadline = monotonic() + timeout_seconds
    characters: list[str] = []

    while True:
        remaining_seconds = deadline - monotonic()
        if remaining_seconds <= 0:
            break
        if not msvcrt.kbhit():
            sleep(min(0.05, remaining_seconds))
            continue

        character = msvcrt.getwch()
        if character in {"\x00", "\xe0"}:
            msvcrt.getwch()
        elif character in {"\r", "\n"}:
            print()
            return "".join(characters)
        elif character == "\x03":
            raise KeyboardInterrupt
        elif character == "\b":
            if characters:
                characters.pop()
                print("\b \b", end="", flush=True)
        else:
            characters.append(character)
            print(character, end="", flush=True)

    print()
    raise TimeoutError("Timed out waiting for a verification code")


def _read_stdin(prompt: str, timeout_seconds: float) -> str:
    if sys.platform == "win32":
        return _read_windows_stdin(prompt, timeout_seconds)

    print(prompt, end="", flush=True)
    deadline = monotonic() + timeout_seconds
    characters = bytearray()
    with selectors.DefaultSelector() as selector:
        try:
            descriptor = sys.stdin.fileno()
            selector.register(descriptor, selectors.EVENT_READ)
        except (OSError, ValueError) as error:
            raise RuntimeError("stdin does not support timed input") from error

        while True:
            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0 or not selector.select(remaining_seconds):
                print()
                raise TimeoutError("Timed out waiting for a verification code")

            character = read(descriptor, 1)
            if character == b"\n":
                return characters.decode(sys.stdin.encoding or "utf-8")
            if not character:
                if characters:
                    return characters.decode(sys.stdin.encoding or "utf-8")
                raise EOFError("stdin closed while waiting for a verification code")
            characters.extend(character)


class ConsoleMailbox:
    """Mailbox for runs where a user supplies the received code manually."""

    def __init__(
        self,
        address: str,
        code_reader: Callable[[str, float], str] = _read_stdin,
    ) -> None:
        if not address.strip():
            raise ValueError("address must not be empty")
        self._address = address.strip()
        self._code_reader = code_reader

    @property
    def address(self) -> str:
        return self._address

    def wait_for_code(
        self,
        pattern: Pattern[str],
        timeout_seconds: float,
    ) -> str:
        if timeout_seconds <= 0:
            raise TimeoutError("No time remains to read a verification code")

        prompt = f"Enter the verification message sent to {self.address}: "
        result = self._code_reader(prompt, timeout_seconds)
        match = pattern.search(result.strip())
        if match is None:
            raise TimeoutError("The entered text did not contain a matching code")
        return _match_value(match)


class TempMailMailbox:
    """Read an address and verification messages from a temp-mail.io tab."""

    def __init__(
        self,
        driver: WebDriver,
        *,
        address_timeout_seconds: float = 20.0,
    ) -> None:
        if address_timeout_seconds <= 0:
            raise ValueError("address_timeout_seconds must be positive")

        self._driver = driver
        self._source_handle = driver.current_window_handle
        self._mailbox_handle = ""
        self._address = self._open_mailbox(address_timeout_seconds)

    @property
    def address(self) -> str:
        return self._address

    @property
    def source_handle(self) -> str:
        return self._source_handle

    @property
    def mailbox_handle(self) -> str:
        return self._mailbox_handle

    def wait_for_code(
        self,
        pattern: Pattern[str],
        timeout_seconds: float,
    ) -> str:
        if timeout_seconds <= 0:
            raise TimeoutError("No time remains to wait for a verification code")

        return_handle = self._driver.current_window_handle
        self._driver.switch_to.window(self._mailbox_handle)
        try:
            value = WebDriverWait(
                self._driver,
                timeout_seconds,
                poll_frequency=1.0,
            ).until(
                lambda driver: self._find_code(driver, pattern),
                message="A matching temp-mail.io message did not arrive",
            )
            return str(value)
        except SeleniumTimeout as error:
            raise TimeoutError(
                "A matching temp-mail.io message did not arrive"
            ) from error
        finally:
            handles = self._driver.window_handles
            if return_handle in handles:
                self._driver.switch_to.window(return_handle)
            elif self._source_handle in handles:
                self._driver.switch_to.window(self._source_handle)

    def _open_mailbox(self, timeout_seconds: float) -> str:
        try:
            self._driver.switch_to.new_window("tab")
            self._mailbox_handle = self._driver.current_window_handle
            self._driver.get(TEMP_MAIL_URL)
            address = WebDriverWait(
                self._driver,
                timeout_seconds,
                poll_frequency=0.5,
            ).until(
                self._read_address,
                message="temp-mail.io did not provide an email address",
            )
            return str(address).strip()
        except SeleniumTimeout as error:
            raise TimeoutError(
                "temp-mail.io did not provide an email address"
            ) from error
        finally:
            if self._source_handle in self._driver.window_handles:
                self._driver.switch_to.window(self._source_handle)

    @staticmethod
    def _read_address(driver: WebDriver) -> str | bool:
        value = driver.find_element(*EMAIL_INPUT).get_attribute("value")
        return value.strip() if isinstance(value, str) and value.strip() else False

    @staticmethod
    def _find_code(
        driver: WebDriver,
        pattern: Pattern[str],
    ) -> str | bool:
        try:
            for element in driver.find_elements(*MESSAGE_PREVIEWS):
                match = pattern.search(element.text.strip())
                if match is not None:
                    return _match_value(match)
        except StaleElementReferenceException:
            return False
        return False

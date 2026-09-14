import re
import sys
from os import fdopen, pipe

import pytest

from youai.adapters import email as email_adapter
from youai.adapters.email import ConsoleMailbox
from youai.contracts import Mailbox


def test_console_mailbox_requires_an_address() -> None:
    with pytest.raises(ValueError, match="address"):
        ConsoleMailbox("")


def test_console_mailbox_extracts_first_capture_group() -> None:
    mailbox = ConsoleMailbox(
        "creator@example.com",
        code_reader=lambda _prompt, _timeout: "Your sign in code is A1B2C3",
    )

    code = mailbox.wait_for_code(
        re.compile(r"code is ([A-Z0-9]+)"),
        timeout_seconds=10,
    )

    assert isinstance(mailbox, Mailbox)
    assert mailbox.address == "creator@example.com"
    assert code == "A1B2C3"


def test_console_mailbox_rejects_non_matching_input() -> None:
    mailbox = ConsoleMailbox(
        "creator@example.com",
        code_reader=lambda _prompt, _timeout: "wrong message",
    )

    with pytest.raises(TimeoutError):
        mailbox.wait_for_code(re.compile(r"code: ([0-9]+)"), 10)


def test_console_mailbox_honors_timeout() -> None:
    received_timeout = 0.0

    def timed_reader(_prompt: str, timeout_seconds: float) -> str:
        nonlocal received_timeout
        received_timeout = timeout_seconds
        raise TimeoutError("Timed out waiting for a verification code")

    mailbox = ConsoleMailbox(
        "creator@example.com",
        code_reader=timed_reader,
    )

    with pytest.raises(TimeoutError, match="Timed out"):
        mailbox.wait_for_code(re.compile(r"([0-9]+)"), timeout_seconds=0.01)

    assert received_timeout == 0.01


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX selector behavior")
def test_default_console_reader_reads_a_complete_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_descriptor, write_descriptor = pipe()
    with (
        fdopen(read_descriptor) as input_stream,
        fdopen(write_descriptor, "w") as output_stream,
    ):
        monkeypatch.setattr(sys, "stdin", input_stream)
        output_stream.write("verification code: 1357\n")
        output_stream.flush()

        mailbox = ConsoleMailbox("creator@example.com")
        assert mailbox.wait_for_code(re.compile(r"code: ([0-9]+)"), 1) == "1357"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX selector behavior")
def test_default_console_reader_honors_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_descriptor, write_descriptor = pipe()
    with (
        fdopen(read_descriptor) as input_stream,
        fdopen(write_descriptor, "w") as output_stream,
    ):
        monkeypatch.setattr(sys, "stdin", input_stream)
        mailbox = ConsoleMailbox("creator@example.com")
        output_stream.write("verification code: 12")
        output_stream.flush()

        with pytest.raises(TimeoutError, match="Timed out"):
            mailbox.wait_for_code(re.compile(r"([0-9]+)"), timeout_seconds=0.01)

        assert not output_stream.closed


def test_default_console_reader_uses_windows_console_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: tuple[str, float] | None = None

    def read_windows(prompt: str, timeout_seconds: float) -> str:
        nonlocal received
        received = (prompt, timeout_seconds)
        return "verification code: 2468"

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(email_adapter, "_read_windows_stdin", read_windows)
    mailbox = ConsoleMailbox("creator@example.com")

    assert mailbox.wait_for_code(re.compile(r"code: ([0-9]+)"), 5) == "2468"
    assert received == (
        "Enter the verification message sent to creator@example.com: ",
        5,
    )

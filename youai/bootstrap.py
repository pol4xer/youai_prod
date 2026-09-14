"""Composition root for provider selection and resource ownership."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

from youai.adapters.email import ConsoleMailbox, TempMailMailbox
from youai.adapters.kapwing import KapwingVideoGenerator
from youai.adapters.openai_editor import OpenAIStoryEditor
from youai.adapters.reddit import RedditStorySource
from youai.adapters.sqlite import SqliteStoryRepository
from youai.application import CreateVideoPipeline
from youai.contracts import Mailbox

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

    from youai.config import Settings
    from youai.contracts import VideoGenerator


MailboxFactory = Callable[["Settings", "WebDriver"], Mailbox]
VideoGeneratorFactory = Callable[["Settings"], "VideoGenerator"]


def _console_mailbox(settings: Settings, _driver: WebDriver) -> Mailbox:
    return ConsoleMailbox(settings.email_address)


def _temp_mailbox(_settings: Settings, driver: WebDriver) -> Mailbox:
    return TempMailMailbox(driver)


MAILBOX_FACTORIES: dict[str, MailboxFactory] = {
    "console": _console_mailbox,
    "temp-mail": _temp_mailbox,
}


def _kapwing(settings: Settings) -> VideoGenerator:
    from seleniumbase import Driver

    driver = Driver(browser="chrome", headless=settings.headless)
    try:
        mailbox = MAILBOX_FACTORIES[settings.email_provider](settings, driver)
        return KapwingVideoGenerator(
            driver=driver,
            mailbox=mailbox,
            download_dir=settings.download_dir,
        )
    except BaseException:
        driver.quit()
        raise


VIDEO_GENERATOR_FACTORIES: dict[str, VideoGeneratorFactory] = {
    "kapwing": _kapwing,
}


@contextmanager
def create_pipeline(settings: Settings) -> Iterator[CreateVideoPipeline]:
    """Build one pipeline and close every resource owned by this process."""

    with ExitStack() as stack:
        repository = stack.enter_context(SqliteStoryRepository(settings.database_path))
        source = RedditStorySource(user_agent=settings.reddit_user_agent)
        stack.callback(source.close)
        generator = VIDEO_GENERATOR_FACTORIES[settings.video_provider](settings)
        stack.callback(generator.close)
        editor = OpenAIStoryEditor(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        stack.callback(editor.close)

        yield CreateVideoPipeline(
            source=source,
            editor=editor,
            generator=generator,
            repository=repository,
            output_dir=settings.output_dir,
        )

"""Synchronous ports used by the application core."""

from collections.abc import Iterator
from re import Pattern
from typing import Protocol, runtime_checkable

from youai.domain import (
    MediaAsset,
    PreparedStory,
    SortPeriod,
    StoryCandidate,
    VideoRequest,
)


@runtime_checkable
class Mailbox(Protocol):
    """Provide an address and retrieve a matching verification code."""

    @property
    def address(self) -> str: ...

    def wait_for_code(
        self,
        pattern: Pattern[str],
        timeout_seconds: float,
    ) -> str: ...


class StorySource(Protocol):
    """Yields story candidates from an external source."""

    def iter_stories(
        self,
        category: str,
        period: SortPeriod,
        max_pages: int,
    ) -> Iterator[StoryCandidate]: ...

    def close(self) -> None: ...


class ScriptEditor(Protocol):
    """Turns a source story into a generation-ready script."""

    def prepare(self, story: StoryCandidate) -> PreparedStory: ...

    def close(self) -> None: ...


class VideoGenerator(Protocol):
    """Generates one media asset for one prepared story part."""

    def generate(self, request: VideoRequest) -> MediaAsset: ...

    def close(self) -> None: ...


class StoryRepository(Protocol):
    """Tracks stories that have been completely generated."""

    def contains(self, story_id: str) -> bool: ...

    def save(
        self,
        story: PreparedStory,
        media: tuple[MediaAsset, ...],
    ) -> None: ...

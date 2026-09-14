"""Domain values shared by the application and its adapters."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SortPeriod(StrEnum):
    """Time window used when sorting source stories."""

    ALL = "all"
    YEAR = "year"
    MONTH = "month"
    WEEK = "week"
    DAY = "day"


@dataclass(frozen=True, slots=True)
class StoryCandidate:
    """A story returned by an external source."""

    source_id: str
    title: str
    body: str
    category: str
    url: str


@dataclass(frozen=True, slots=True)
class PreparedStory:
    """An edited story split into independently generated parts."""

    source: StoryCandidate
    title: str
    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Prepared story title must not be empty")
        if not self.parts or any(not part.strip() for part in self.parts):
            raise ValueError("Prepared story must contain non-empty parts")


@dataclass(frozen=True, slots=True)
class VideoRequest:
    """Input for generating one story part."""

    story_id: str
    title: str
    category: str
    part_number: int
    text: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """A generated media file and the provider that created it."""

    path: Path
    provider: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The fully prepared and generated pipeline output."""

    story: PreparedStory
    media: tuple[MediaAsset, ...]

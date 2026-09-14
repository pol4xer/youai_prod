"""Offline walkthrough of the real pipeline using a fictional story.

The video adapter is deliberately replaced with a JSON storyboard writer. These
files describe generation requests; they are not videos or results from an AI
provider. Demo persistence is separate from the live application's database.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from youai.adapters.sqlite import SqliteStoryRepository
from youai.application import CreateVideoPipeline, NoStoryAvailable
from youai.domain import (
    MediaAsset,
    PipelineResult,
    PreparedStory,
    SortPeriod,
    StoryCandidate,
    VideoRequest,
)

DEMO_STORY = StoryCandidate(
    source_id="demo-library-001",
    title="The library that started with one shelf",
    body=(
        "Maya placed a small shelf of books in her apartment building's lobby. "
        "She left a note: take a story, leave a story. By Friday, the shelf was "
        "full of novels, cookbooks, and handwritten recommendations.\n\n"
        "A neighbor offered a second shelf, and another organized a reading night. "
        "What began as a way to clear one bookcase became the building's favorite "
        "place to meet. The most borrowed book was the one nobody expected: a "
        "guide to growing tomatoes on a balcony."
    ),
    category="demo",
    url="https://example.test/stories/demo-library-001",
)


class DemoStorySource:
    """Offer one original fictional fixture without contacting Reddit."""

    def iter_stories(
        self,
        category: str,
        period: SortPeriod,
        max_pages: int,
    ) -> Iterator[StoryCandidate]:
        yield DEMO_STORY

    def close(self) -> None:
        pass


class DemoScriptEditor:
    """Split the fixture's paragraphs deterministically without an AI call."""

    def prepare(self, story: StoryCandidate) -> PreparedStory:
        return PreparedStory(
            source=story,
            title=story.title,
            parts=tuple(part.strip() for part in story.body.split("\n\n")),
        )

    def close(self) -> None:
        pass


class DemoStoryboardWriter:
    """Stand in for video rendering with clearly identified JSON requests."""

    def generate(self, request: VideoRequest) -> MediaAsset:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        path = request.output_dir / f"part-{request.part_number:02d}.storyboard.json"
        document = {
            "kind": "offline-demo-storyboard",
            "notice": (
                "Fictional demo. No AI, video generation, or upload was performed."
            ),
            "story_id": request.story_id,
            "title": request.title,
            "category": request.category,
            "part_number": request.part_number,
            "script": request.text,
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return MediaAsset(path=path, provider="offline-storyboard")

    def close(self) -> None:
        pass


def run_demo(directory: Path) -> PipelineResult | None:
    """Persist the sample once; later runs demonstrate duplicate detection."""

    directory = directory.expanduser().resolve()
    with SqliteStoryRepository(directory / "youai.db") as repository:
        pipeline = CreateVideoPipeline(
            source=DemoStorySource(),
            editor=DemoScriptEditor(),
            generator=DemoStoryboardWriter(),
            repository=repository,
            output_dir=directory / "storyboards",
        )
        try:
            return pipeline.run(category="demo", period=SortPeriod.ALL, max_pages=1)
        except NoStoryAvailable:
            return None

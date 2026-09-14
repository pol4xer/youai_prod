"""Application service that coordinates the synchronous generation pipeline."""

from dataclasses import dataclass
from pathlib import Path

from youai.contracts import (
    ScriptEditor,
    StoryRepository,
    StorySource,
    VideoGenerator,
)
from youai.domain import PipelineResult, SortPeriod, VideoRequest


class NoStoryAvailable(LookupError):
    """Raised when a source has no unprocessed story to offer."""


@dataclass(slots=True)
class CreateVideoPipeline:
    """Generate every part of the first unprocessed source story."""

    source: StorySource
    editor: ScriptEditor
    generator: VideoGenerator
    repository: StoryRepository
    output_dir: Path

    def run(
        self,
        category: str,
        period: SortPeriod,
        max_pages: int = 5,
    ) -> PipelineResult:
        for candidate in self.source.iter_stories(category, period, max_pages):
            if not self.repository.contains(candidate.source_id):
                break
        else:
            raise NoStoryAvailable(
                f"No unprocessed story is available for category {category!r}"
            )

        story = self.editor.prepare(candidate)
        media = tuple(
            self.generator.generate(
                VideoRequest(
                    story_id=story.source.source_id,
                    title=story.title,
                    category=story.source.category,
                    part_number=part_number,
                    text=part,
                    output_dir=self.output_dir,
                )
            )
            for part_number, part in enumerate(story.parts, start=1)
        )

        self.repository.save(story, media)
        return PipelineResult(story=story, media=media)

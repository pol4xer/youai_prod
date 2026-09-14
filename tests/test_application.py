from collections.abc import Iterator
from pathlib import Path

import pytest

from youai.application import CreateVideoPipeline, NoStoryAvailable
from youai.domain import (
    MediaAsset,
    PreparedStory,
    SortPeriod,
    StoryCandidate,
    VideoRequest,
)


class FakeSource:
    def __init__(self, stories: tuple[StoryCandidate, ...]) -> None:
        self.stories = stories
        self.request: tuple[str, SortPeriod, int] | None = None

    def iter_stories(
        self,
        category: str,
        period: SortPeriod,
        max_pages: int,
    ) -> Iterator[StoryCandidate]:
        self.request = (category, period, max_pages)
        yield from self.stories

    def close(self) -> None:
        pass


class FakeEditor:
    def __init__(self, prepared: PreparedStory) -> None:
        self.prepared = prepared
        self.calls: list[StoryCandidate] = []

    def prepare(self, story: StoryCandidate) -> PreparedStory:
        self.calls.append(story)
        return self.prepared

    def close(self) -> None:
        pass


class FakeGenerator:
    def __init__(self, *, fail_on_part: int | None = None) -> None:
        self.fail_on_part = fail_on_part
        self.requests: list[VideoRequest] = []

    def generate(self, request: VideoRequest) -> MediaAsset:
        self.requests.append(request)
        if request.part_number == self.fail_on_part:
            raise RuntimeError("generation failed")
        return MediaAsset(
            path=request.output_dir / f"part-{request.part_number}.mp4",
            provider="fake",
        )

    def close(self) -> None:
        pass


class FakeRepository:
    def __init__(self, processed: set[str] | None = None) -> None:
        self.processed = set() if processed is None else set(processed)
        self.contains_calls: list[str] = []
        self.saved: list[tuple[PreparedStory, tuple[MediaAsset, ...]]] = []

    def contains(self, story_id: str) -> bool:
        self.contains_calls.append(story_id)
        return story_id in self.processed

    def save(
        self,
        story: PreparedStory,
        media: tuple[MediaAsset, ...],
    ) -> None:
        self.saved.append((story, media))
        self.processed.add(story.source.source_id)


def make_candidate(source_id: str) -> StoryCandidate:
    return StoryCandidate(
        source_id=source_id,
        title=f"Source title {source_id}",
        body=f"Body {source_id}",
        category="stories",
        url=f"https://example.test/{source_id}",
    )


@pytest.mark.parametrize(
    ("title", "parts"),
    [("", ("Part",)), ("Title", ()), ("Title", (" ",))],
)
def test_prepared_story_enforces_its_contract(
    title: str,
    parts: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError):
        PreparedStory(source=make_candidate("story"), title=title, parts=parts)


def test_pipeline_skips_already_processed_stories(tmp_path: Path) -> None:
    old_story = make_candidate("old")
    new_story = make_candidate("new")
    prepared = PreparedStory(
        source=new_story,
        title="Edited title",
        parts=("Only part",),
    )
    source = FakeSource((old_story, new_story))
    editor = FakeEditor(prepared)
    generator = FakeGenerator()
    repository = FakeRepository({old_story.source_id})
    pipeline = CreateVideoPipeline(
        source=source,
        editor=editor,
        generator=generator,
        repository=repository,
        output_dir=tmp_path,
    )

    result = pipeline.run("stories", SortPeriod.WEEK, max_pages=3)

    assert source.request == ("stories", SortPeriod.WEEK, 3)
    assert repository.contains_calls == ["old", "new"]
    assert editor.calls == [new_story]
    assert result.story is prepared


def test_pipeline_raises_when_no_unprocessed_story_exists(
    tmp_path: Path,
) -> None:
    candidate = make_candidate("old")
    prepared = PreparedStory(candidate, "Unused", ("Unused",))
    editor = FakeEditor(prepared)
    generator = FakeGenerator()
    repository = FakeRepository({candidate.source_id})
    pipeline = CreateVideoPipeline(
        FakeSource((candidate,)),
        editor,
        generator,
        repository,
        tmp_path,
    )

    with pytest.raises(NoStoryAvailable, match="stories"):
        pipeline.run("stories", SortPeriod.ALL)

    assert editor.calls == []
    assert generator.requests == []
    assert repository.saved == []


def test_pipeline_maps_every_part_to_a_video_request(tmp_path: Path) -> None:
    candidate = make_candidate("story-42")
    prepared = PreparedStory(
        source=candidate,
        title="A cleaner title",
        parts=("First part", "Second part"),
    )
    generator = FakeGenerator()
    repository = FakeRepository()
    output_dir = tmp_path / "generated"
    pipeline = CreateVideoPipeline(
        FakeSource((candidate,)),
        FakeEditor(prepared),
        generator,
        repository,
        output_dir,
    )

    result = pipeline.run("stories", SortPeriod.MONTH)

    assert generator.requests == [
        VideoRequest(
            story_id="story-42",
            title="A cleaner title",
            category="stories",
            part_number=1,
            text="First part",
            output_dir=output_dir,
        ),
        VideoRequest(
            story_id="story-42",
            title="A cleaner title",
            category="stories",
            part_number=2,
            text="Second part",
            output_dir=output_dir,
        ),
    ]
    assert result.media == (
        MediaAsset(output_dir / "part-1.mp4", "fake"),
        MediaAsset(output_dir / "part-2.mp4", "fake"),
    )
    assert repository.saved == [(prepared, result.media)]


def test_generation_failure_does_not_save_the_story(tmp_path: Path) -> None:
    candidate = make_candidate("story-42")
    prepared = PreparedStory(
        source=candidate,
        title="Edited title",
        parts=("First part", "Second part"),
    )
    generator = FakeGenerator(fail_on_part=2)
    repository = FakeRepository()
    pipeline = CreateVideoPipeline(
        FakeSource((candidate,)),
        FakeEditor(prepared),
        generator,
        repository,
        tmp_path,
    )

    with pytest.raises(RuntimeError, match="generation failed"):
        pipeline.run("stories", SortPeriod.DAY)

    assert [request.part_number for request in generator.requests] == [1, 2]
    assert repository.saved == []
    assert repository.processed == set()

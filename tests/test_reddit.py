from collections.abc import Iterator
from typing import Any, cast

import requests

from youai.adapters.reddit import RedditStorySource
from youai.domain import SortPeriod


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self._responses: Iterator[FakeResponse] = iter(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return next(self._responses)

    def close(self) -> None:
        self.closed = True


def _listing(
    children: list[dict[str, Any]],
    after: str | None,
) -> FakeResponse:
    return FakeResponse({"data": {"children": children, "after": after}})


def _post(
    story_id: str,
    *,
    body: str = "A story",
    kind: str = "t3",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "data": {
            "id": story_id,
            "title": f"Title {story_id}",
            "selftext": body,
            "permalink": f"/r/test/comments/{story_id}/title/",
        },
    }


def test_iter_stories_is_lazy_and_paginates_json_listing() -> None:
    responses = [
        _listing(
            [
                _post("first", body="  First body  "),
                _post("empty", body="  "),
                _post("comment", kind="t1"),
            ],
            "t3_cursor",
        ),
        _listing([_post("second")], None),
    ]
    fake_session = FakeSession(responses)
    source = RedditStorySource(
        cast(requests.Session, fake_session),
        timeout_seconds=7.5,
    )

    stories = source.iter_stories("test", SortPeriod.WEEK, max_pages=2)
    assert fake_session.calls == []

    first = next(stories)
    assert first.source_id == "first"
    assert first.body == "First body"
    assert first.category == "test"
    assert first.url == "https://www.reddit.com/r/test/comments/first/title/"
    assert len(fake_session.calls) == 1

    assert [story.source_id for story in stories] == ["second"]
    assert fake_session.calls[0]["params"] == {
        "limit": 100,
        "raw_json": 1,
        "t": "week",
        "after": None,
    }
    assert fake_session.calls[1]["params"]["after"] == "t3_cursor"
    assert all(call["timeout"] == 7.5 for call in fake_session.calls)


def test_context_manager_closes_injected_session() -> None:
    fake_session = FakeSession([])

    with RedditStorySource(cast(requests.Session, fake_session)) as source:
        assert source is not None

    assert fake_session.closed is True

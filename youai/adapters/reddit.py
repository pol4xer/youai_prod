"""Reddit JSON listing adapter."""

from collections.abc import Iterator
from types import TracebackType
from urllib.parse import quote, urljoin

import requests

from youai.domain import SortPeriod, StoryCandidate


class RedditStorySource:
    """Lazily yield text posts from a subreddit's top listing."""

    BASE_URL = "https://www.reddit.com"
    DEFAULT_USER_AGENT = "python:youai:v0.0.1 (Reddit story source)"

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        timeout_seconds: float = 20.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._session = session if session is not None else requests.Session()
        self._timeout_seconds = timeout_seconds
        self._closed = False
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    def __enter__(self) -> "RedditStorySource":
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
        """Close the HTTP session; repeated calls are harmless."""

        if not self._closed:
            self._session.close()
            self._closed = True

    def iter_stories(
        self,
        category: str,
        period: SortPeriod,
        max_pages: int,
    ) -> Iterator[StoryCandidate]:
        """Yield eligible posts one page at a time.

        No request is made until the returned iterator is advanced.
        """

        self._ensure_open()
        normalized_category = category.strip()
        if not normalized_category:
            raise ValueError("category must not be empty")

        endpoint = f"{self.BASE_URL}/r/{quote(normalized_category, safe='')}/top.json"
        after: str | None = None

        for _ in range(max(0, max_pages)):
            response = self._session.get(
                endpoint,
                params={
                    "limit": 100,
                    "raw_json": 1,
                    "t": period.value,
                    "after": after,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()

            listing = payload.get("data", {})
            children = listing.get("children", [])
            if isinstance(children, list):
                for child in children:
                    candidate = self._to_candidate(child, normalized_category)
                    if candidate is not None:
                        yield candidate

            next_after = listing.get("after")
            if not isinstance(next_after, str) or not next_after:
                break
            after = next_after

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Reddit story source is closed")

    @classmethod
    def _to_candidate(
        cls,
        child: object,
        category: str,
    ) -> StoryCandidate | None:
        if not isinstance(child, dict) or child.get("kind") != "t3":
            return None

        data = child.get("data")
        if not isinstance(data, dict):
            return None

        source_id = data.get("id")
        title = data.get("title")
        body = data.get("selftext")
        permalink = data.get("permalink")
        if not (
            isinstance(source_id, str)
            and source_id
            and isinstance(title, str)
            and title
            and isinstance(body, str)
            and body.strip()
            and isinstance(permalink, str)
            and permalink
        ):
            return None

        return StoryCandidate(
            source_id=source_id,
            title=title,
            body=body.strip(),
            category=category,
            url=urljoin(f"{cls.BASE_URL}/", permalink),
        )

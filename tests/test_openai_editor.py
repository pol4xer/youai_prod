import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

from youai.adapters.openai_editor import (
    MAX_PART_LENGTH,
    OpenAIStoryEditor,
    ProviderResponseError,
    _OpenAIClient,
)
from youai.domain import StoryCandidate


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)

    def close(self) -> None:
        pass


def _story() -> StoryCandidate:
    return StoryCandidate(
        source_id="abc123",
        title="Original title",
        body="The original story. Update: an unrelated tail.",
        category="pettyrevenge",
        url="https://www.reddit.com/r/pettyrevenge/comments/abc123/",
    )


def test_prepare_uses_strict_responses_schema_and_returns_tuple_parts() -> None:
    fake_client = FakeClient(
        json.dumps(
            {
                "title": "Edited title",
                "parts": ["Edited title — Part 1\nThe original story."],
            }
        )
    )
    editor = OpenAIStoryEditor(cast(_OpenAIClient, fake_client))

    prepared = editor.prepare(_story())

    assert prepared.title == "Edited title"
    assert prepared.parts == ("Edited title — Part 1\nThe original story.",)
    call = fake_client.responses.calls[0]
    assert call["model"] == "gpt-5.6-luna"
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert "untrusted story content" in call["instructions"]
    assert json.loads(call["input"])["title"] == "Original title"
    output_format = call["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert output_format["schema"]["additionalProperties"] is False
    assert (
        output_format["schema"]["properties"]["parts"]["items"]["maxLength"]
        == MAX_PART_LENGTH
    )


@pytest.mark.parametrize(
    "output_text",
    [
        "not json",
        json.dumps({"title": "Title", "parts": []}),
        json.dumps({"title": "Title", "parts": [" "]}),
        json.dumps({"title": "Title", "parts": ["x" * (MAX_PART_LENGTH + 1)]}),
    ],
)
def test_prepare_rejects_invalid_provider_contract(output_text: str) -> None:
    editor = OpenAIStoryEditor(cast(_OpenAIClient, FakeClient(output_text)))

    with pytest.raises(ProviderResponseError):
        editor.prepare(_story())

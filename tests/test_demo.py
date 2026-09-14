import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_demo_runs_without_dependencies_or_credentials_and_skips_duplicates(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    demo_dir = tmp_path / "demo"
    live_root = tmp_path / "live"
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "OPENAI_API_KEY" and not key.startswith("YOUAI_")
    }
    environment["YOUAI_ROOT"] = str(live_root)
    command = [
        sys.executable,
        "-S",  # No site-packages: this must not import SDKs or browser adapters.
        "-m",
        "youai",
        "--demo",
        "--demo-dir",
        str(demo_dir),
    ]

    first = subprocess.run(
        command,
        cwd=project_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    assert "JSON storyboards only; no video created" in first.stderr
    storyboards = sorted((demo_dir / "storyboards").glob("*.json"))
    assert len(storyboards) == 2
    documents = [json.loads(path.read_text()) for path in storyboards]
    assert [document["part_number"] for document in documents] == [1, 2]
    assert all(document["kind"] == "offline-demo-storyboard" for document in documents)
    assert all("Fictional demo" in document["notice"] for document in documents)
    assert all(document["script"].strip() for document in documents)
    assert not live_root.exists()
    timestamps = [path.stat().st_mtime_ns for path in storyboards]

    second = subprocess.run(
        command,
        cwd=project_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    assert "already processed" in second.stderr
    assert [path.stat().st_mtime_ns for path in storyboards] == timestamps
    with sqlite3.connect(demo_dir / "youai.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM stories").fetchone() == (1,)
        rows = connection.execute(
            """
            SELECT story_parts.part_text, media.file_path, media.extension
            FROM story_parts JOIN media ON media.id = story_parts.media_id
            ORDER BY story_parts.order_index
            """
        ).fetchall()
    assert rows == [
        (document["script"], str(path), "json")
        for document, path in zip(documents, storyboards, strict=True)
    ]

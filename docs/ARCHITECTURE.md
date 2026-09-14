# Architecture

YouAI has one application use case: prepare and generate the next unprocessed
story. External integrations sit behind small synchronous interfaces.

## Code map

```text
youai/
├── domain.py            # Immutable story, script, request, and asset values
├── contracts.py         # Source, editor, generator, repository, mailbox ports
├── application.py       # Story selection and generation orchestration
├── config.py            # Environment-backed settings
├── bootstrap.py         # Live provider selection and resource ownership
├── cli.py               # Command-line entry point
├── demo.py              # Fictional offline adapters and demo composition
└── adapters/
    ├── reddit.py        # Paginated Reddit JSON listing
    ├── openai_editor.py # Responses API and structured output validation
    ├── kapwing.py       # Browser sign-in, generation, and MP4 download
    ├── email.py         # Manual verification and legacy mailbox adapter
    └── sqlite.py        # Transactional persistence
```

The domain imports no external services. The application depends on domain
values and `Protocol` contracts. The composition root selects concrete adapters
and closes owned HTTP clients, the browser, and the database connection through
an `ExitStack`.

The pipeline is synchronous because its current dependencies use blocking
operations. A future queue can run each job in a separate worker without changing
the application contracts.

## One job

1. `StorySource.iter_stories` lazily yields candidates. The Reddit adapter pages
   through a subreddit's top listing and skips entries without usable text.
2. `StoryRepository.contains` filters stories that have already completed.
3. `ScriptEditor.prepare` returns a validated `PreparedStory`. The OpenAI adapter
   requests a strict JSON object containing a title and a list of parts, then
   checks the response before it reaches the pipeline.
4. `VideoGenerator.generate` receives a `VideoRequest` for each part and returns
   a local `MediaAsset`.
5. `StoryRepository.save` inserts the story, parts, and media in one transaction.

The same application service powers the offline demo. Fictional source content,
a deterministic editor, and a JSON storyboard writer replace the live adapters.
The SQLite implementation remains real.

## Persistence and failure behavior

SQLite stores `stories`, `story_parts`, and `media`, retaining the earlier schema.
A repository test verifies compatibility with an existing schema. Foreign keys
link each part to its parent story and media record.

Database writes happen after every part has been generated. A provider failure
therefore leaves the story eligible for another attempt; a database insertion
failure rolls back the transaction. Filesystem writes are outside that
transaction, so a failed job can leave media files behind and a retry can repeat
external work. This is completion tracking, not an exactly-once execution system.

Kapwing downloads go to a configured directory. The adapter observes newly
created MP4 files, waits for a nonempty stable size, and stages the selected file
before replacing the final output. The destination name is built from a
sanitized story ID and part number.

## Adding a provider

Implement `VideoGenerator.generate(request) -> MediaAsset` and `close()`, then
register a factory in `VIDEO_GENERATOR_FACTORIES` in
[`bootstrap.py`](../youai/bootstrap.py). The provider should write its result to
`request.output_dir` and return its path.

A video provider does not need to know about Reddit or SQLite. A provider that
uses an API instead of browser sign-in does not need a mailbox either. The
`Mailbox` interface belongs to the current Kapwing sign-in flow and exposes only
an address and a timed verification-code lookup.

Keep provider-specific parsing, timeouts, and response validation in the
adapter. Keep story selection and completion rules in the application layer.

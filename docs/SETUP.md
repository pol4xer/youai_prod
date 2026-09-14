# Optional live provider setup

The offline demo is the easiest way to inspect YouAI. This page describes the
experimental live path, which fetches a Reddit story, edits it with OpenAI, and
uses the Kapwing website to generate video files.

The current Kapwing interface has not been verified as part of the portfolio
refresh. A configured environment is not a guarantee that browser generation
will complete. There is no YouTube uploader.

## Requirements

- Python 3.12 or 3.13 and Poetry 2 for a source checkout.
- Chrome/Chromium for the Kapwing adapter.
- An OpenAI API key and a model available to your API account.
- A Kapwing account and access to its sign-in email.
- Access to the external services used by the adapters.

## Configure a checkout

```bash
poetry install
cp .env.example .env
```

Edit `.env` with your local configuration. It is ignored by Git. The application
reads process environment variables and does not load `.env` automatically.
In a POSIX shell, export your local file before running the command:

```bash
set -a
source .env
set +a

poetry run youai --subreddit pettyrevenge --period week
```

Set `OPENAI_API_KEY` to your key and `YOUAI_EMAIL_ADDRESS` to an email address you
can access. Choose `OPENAI_MODEL` for your account; the configured model must
support the Responses API, the requested reasoning setting, and strict structured
output. The default in [`Settings`](../youai/config.py) is a configurable project
choice, not an availability guarantee.

With the default `console` mailbox, the browser enters your email address and the
terminal asks you to paste the sign-in code or verification message. YouAI does
not need your email password. Keep the terminal attached for this interaction.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Required for live runs | OpenAI credential |
| `OPENAI_MODEL` | See `Settings` | Model used by the script editor |
| `YOUAI_VIDEO_PROVIDER` | `kapwing` | Registered video-provider factory |
| `YOUAI_EMAIL_PROVIDER` | `console` | Manual verification or legacy `temp-mail` adapter |
| `YOUAI_EMAIL_ADDRESS` | Empty | Address required by the Kapwing console mailbox |
| `YOUAI_ROOT` | Current working directory | Base for relative runtime paths |
| `YOUAI_DB_PATH` | `var/youai.db` | SQLite database |
| `YOUAI_OUTPUT_DIR` | `var/media` | Final generated files |
| `YOUAI_DOWNLOAD_DIR` | `var/downloads` | Browser downloads |
| `YOUAI_REDDIT_USER_AGENT` | Local client identifier | User-Agent for Reddit requests |
| `YOUAI_HEADLESS` | `false` | Run Chrome without a visible window |

Relative paths resolve against `YOUAI_ROOT`. For an installed wheel or a process
launched outside the checkout, set an explicit runtime directory. An earlier
SQLite database can be selected through `YOUAI_DB_PATH`; the repository retains
the previous tables and columns.

The demo uses its own `--demo-dir` and does not use live environment credentials.

## CLI options

```text
--subreddit pettyrevenge
--period {all,year,month,week,day}
--max-pages 5
--headless / --no-headless
--video-provider kapwing
--email-provider console
--email-address creator@example.com
--log-level INFO
```

The installed console command is `youai`. `python -m youai` is equivalent, and
`python main.py` remains a compatibility entry point in a source checkout.

## Integration limits

Kapwing and the legacy `temp-mail` mailbox adapter depend on web interfaces that
can change. Browser waits are bounded; there is no automated CAPTCHA bypass or
unattended recovery. Use the console mailbox to supply verification codes from
an account you control.

Stories are sent to OpenAI, and prepared script parts are sent to the selected
video provider. External API calls or generation may incur charges. Process
content you have permission to use and follow the services' terms.

Keep `.env`, local credentials, browser profiles, downloaded stories, databases,
and generated files in ignored runtime locations. Review staged changes before
committing, especially if you choose paths outside the default `var/` directory.

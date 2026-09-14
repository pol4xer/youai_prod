# Development

Use Python 3.12 or 3.13 and Poetry 2 for the complete development environment.
The credential-free demo also runs directly from a checkout with Python alone.

```bash
poetry install
poetry run youai --demo
make check
```

## Commands

| Command | Purpose |
| --- | --- |
| `python -m youai --demo` | Run the local fixture pipeline without third-party dependencies |
| `make demo` | Run the same demo through the Poetry environment |
| `poetry run youai --help` | Show CLI options |
| `make lint` | Check Ruff lint rules and formatting |
| `make test` | Run isolated tests |
| `make package` | Build a wheel in `dist/` |
| `make package-smoke` | Build the wheel, install it separately, and check the CLI |
| `make check` | Run lint, tests, and package smoke checks |
| `make format` | Apply Ruff fixes and formatting |
| `poetry check --lock` | Validate project metadata and the lockfile |

## What the tests establish

The suite exercises story selection, part-to-request mapping, completion tracking,
transaction rollback, schema compatibility, structured-output validation,
pagination, mailbox input, download helpers, and packaging. Provider tests inject
fake HTTP, OpenAI, or browser objects. SQLite and filesystem tests use temporary
local storage.

These are offline checks. A successful run does not establish that a third-party
UI still matches the Kapwing selectors or that a particular account has access to
the configured model. Live integration runs are optional, separate experiments.

The wheel smoke check installs the built artifact into a temporary location with
`pip --no-index --no-deps`, checks that imports resolve to the installed package,
and invokes its console entry point outside the checkout. It uses the already
installed development dependencies and does not test dependency resolution from
an empty machine.

## Working on integrations

Use a separate local runtime directory and explicit environment configuration;
see [setup](SETUP.md). Add focused adapter tests for changed parsing, validation,
or file handling. Keep live credentials and generated outputs out of test
fixtures and version control.

The project intentionally keeps one small application pipeline. Add new
infrastructure when a concrete use case needs it, rather than making the
portfolio prototype look like a production service.

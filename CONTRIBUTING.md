# Contributing / コントリビューション

Issues and pull requests are welcome. Pull requests from outside collaborators should use a
fork because direct pushes to `main` are blocked.

IssueとPull Requestを歓迎します。外部コントリビューターはforkを使ってください。
`main` への直接pushはできません。

## Workflow

1. Fork the repository and create a focused branch such as `fix/subtitle-timing`.
2. Run `uv sync --locked --all-groups`.
3. Make one coherent change and add or update tests.
4. Run the checks below.
5. Open a pull request and complete its checklist.
6. Address review comments without resolving another person's thread yourself.

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/public_repo_check.py --history
```

Video-output changes should include a concise description of the visible result. Do not commit
generated media, secrets, private network addresses, personal local paths, or confidential data.
If a change adds a voice or asset, document its license and required attribution.

## Review and merge policy

- Outside contributions require one approval from `@humanbeans893` as CODEOWNER.
- New commits dismiss stale approvals; request review again after updating the branch.
- All conversations and required CI checks must be resolved before merge.
- Pull request branches must be current with `main`.
- The repository uses squash merge and deletes merged branches automatically.

Repository administrators must also use a pull request. A PR-only bypass exists for sole-maintainer
or emergency work, but it does not permit direct pushes to `main`.

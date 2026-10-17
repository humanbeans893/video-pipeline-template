# エージェント向けの作業規則

思考は英語で行い、回答は利用者の言語で書きます。日本語の文章では不要な英語を避けます。

## 動的ワークフローと実行記録

- 複数エージェントによる動的ワークフローは [DYNAMIC_WORKFLOW.md](DYNAMIC_WORKFLOW.md) に従います。
- 起動前に作業内容からトークン使用量を見積もり、実測に基づく計画の予算から同時実行数を決めます。
- Codex が実装し、Opus がレビューと最終確認を担当します。
- 停止した実行は台帳を読み、ブランチごとに記録した到達点・次の段階・直前の報告のキーから、
  新しい実行として続けます。同じ実行の引数を変えて再開しません。
- Claude Code と Codex は、ともにワークフローの実行記録を `.agent-runs/` に残します。
- セッション開始時と引き継ぎ時に [.agent-runs/README.md](.agent-runs/README.md)、
  `sessions.jsonl` の末尾、直近の `runs/<run>/` の `manifest.json`、`results.json`、`stages.jsonl` を読みます。
- 台帳の道具はホストで `python3 .agent-runs/shared/tools/<道具>` として実行できます。
- セッションの開始・終了時に `index_sessions.py`、実行の終了・停止・上限到達時に `export_workflow_run.py` を使います。
- Codex の段階を起動する前に、ローカルの `.claude/settings.local.json` の `permissions.allow` に
  `"Bash(codex exec --approve-for-me:*)"` を設定します。この設定はコミットしません。

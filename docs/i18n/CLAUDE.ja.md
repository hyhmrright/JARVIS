[中文](../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

このファイルは、Claude Code がこのコードベースで作業する際のガイダンスを提供します。

## ブランチ戦略

- **main**：リリース専用。直接のコミットや開発は禁止。dev などの開発ブランチからのマージのみ受け付けます。
- **dev**：メイン開発ブランチ。すべての日常開発、バグ修正、機能開発はこのブランチまたはそのサブブランチで行います。
- 開発完了後：dev → merge → main → push。手順の省略は不可。

## プロジェクト概要

JARVIS は、RAG ナレッジベース、マルチ LLM サポート、ストリーミング会話を備えた AI アシスタントプラットフォームで、monorepo 構造を採用しています。

## コアアーキテクチャ

- **backend/**：FastAPI + LangGraph + SQLAlchemy（PostgreSQL）+ Qdrant（ベクトルストア）+ MinIO（ファイルストレージ）+ Redis
- **frontend/**：Vue 3 + TypeScript + Vite + Pinia
- **ルートの pyproject.toml**：開発ツール（ruff、pyright、pre-commit）の管理のみ、ランタイム依存関係なし
- **LLM**：DeepSeek / OpenAI / Anthropic をサポート、LangGraph StateGraph で駆動

## 開発環境

- **Python バージョン**：3.13（`.python-version`）
- **パッケージマネージャー**：`uv`
- **仮想環境**：`.venv`（自動管理）

## よく使うコマンド

### 環境セットアップ
```bash
uv sync                      # すべての依存関係をインストール
```

### アプリケーションの実行
```bash
# バックエンド（backend/ ディレクトリ内）
uv run uvicorn app.main:app --reload

# フロントエンド（frontend/ ディレクトリ内）
bun run dev

# フルスタック（ルートディレクトリ）
docker-compose up -d
```

### コード品質チェック
```bash
ruff check                   # コードリント
ruff check --fix             # 問題の自動修正
ruff format                  # コードフォーマット
pyright                      # 型チェック
```

### テスト
```bash
# backend/ ディレクトリ内で実行
uv run pytest tests/ -v                        # すべてのテストを実行
uv run pytest tests/api/test_auth.py -v        # 特定のテストファイルを実行
```

### Pre-commit Hooks
```bash
pre-commit install           # git hooks をインストール
pre-commit run --all-files   # すべての hooks を手動実行
```

Pre-commit が自動実行する項目：
- YAML/TOML/JSON フォーマットチェック
- uv.lock 同期チェック
- Ruff lint とフォーマット
- ファイル末尾の空行と末尾空白のチェック

### 依存関係管理
```bash
uv add <パッケージ名>         # 本番依存関係を追加
uv add --group dev <パッケージ名> # 開発依存関係を追加
uv sync --upgrade            # 依存関係を更新
uv lock                      # pyproject.toml を手動編集後に uv.lock を再生成
```

## ツール設定

- **Ruff**：line-length=88, target-version="py313", quote-style="double"
- **Pyright**：typeCheckingMode="basic"
- **Pre-commit**：uv-lock、ruff-check、ruff-format、および標準ファイルチェックを実行

---

# グローバル開発ルール

## Git 操作前の自己チェック

**`git commit`、`git push`、または commit/push skill の呼び出しの前に、必ず自己チェックを行うこと：**

```
このセッションでファイルを修正したか？
   → はい → 品質ループ（simplifier → commit → review）は完全に通過したか？
              → いいえ → 【STOP】直ちに品質ループを実行
              → はい → git 操作を続行
   → いいえ → ワーキングツリーにコミットされていない変更があるか？（git diff / git diff --cached / git stash list）
              → あり（stash を含む）→ 【STOP】まず完全な品質ループを実行する必要あり
              → なし → git 操作を続行
```

---

## コード変更の必須ワークフロー

### ツール説明

| ツール | タイプ | 呼び出し方法 | 実行タイミング |
|--------|--------|-------------|--------------|
| code-simplifier | Task agent | `Task` ツール、`subagent_type: "code-simplifier:code-simplifier"` | commit の前 |
| pre-push コードレビュー | Skill | `Skill: superpowers:requesting-code-review` | commit の後、push の前 |
| PR コードレビュー | Skill | `Skill: code-review:code-review --comment` | push の後（PR が存在する場合） |

### トリガー条件（いずれか一つで発動）

- Edit / Write / NotebookEdit を使用してファイルを修正した
- ユーザーが変更を Git に永続化またはリモートにプッシュする意図がある（「同期」「アップロード」「PR を作成」「アーカイブ」「ship」などの表現を含む）
- commit / push 関連の skill を呼び出そうとしている

### 実行手順（順序固定、省略不可）

```
コードの記述 / ファイルの修正
      ↓
╔══════════════════ 品質ループ（問題がなくなるまで繰り返す）══════════════════╗
║                                                                              ║
║  A. 【必須】Task: code-simplifier                                            ║
║     （Task agent、ファイルを直接修正する）                                    ║
║          ↓                                                                   ║
║  B. git add + commit                                                         ║
║     初回 → git commit                                                        ║
║     修正後の再入 → git commit --amend（push 前は履歴をクリーンに保つ）        ║
║          ↓                                                                   ║
║  C. 【必須】Skill: superpowers:requesting-code-review                        ║
║     （BASE_SHA=HEAD~1、HEAD_SHA=HEAD を提供する必要あり）                     ║
║          ↓                                                                   ║
║     問題が見つかったか？                                                     ║
║       はい → コードを修正 ──────────────────────────→ ステップ A に戻る      ║
║       いいえ ↓                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
      ↓
git push（直ちに実行、遅延不可）
      ↓（GitHub PR が存在する場合）
【必須】Skill: code-review:code-review --comment
```

**重要な説明：**
- 品質ループは完全に実行（A→B→C）され、C で問題がないことを確認してから終了すること
- 修正後にループに再入する場合は `--amend` を使用（push 前は単一の commit を維持）
- `--amend` はレビューを省略する理由にはならない。C を再実行する必要あり

---

## ワークフロー省略の禁止される言い訳

以下の理由は省略の根拠として**認められません**：

| 言い訳 | 正しい対応 |
|--------|-----------|
| 「たった一行の簡単な変更です」 | 変更の大小に関わらず、必ず実行 |
| 「ユーザーは commit とだけ言い、review とは言っていない」 | commit 自体がトリガー条件 |
| 「先ほど似たコードをレビューした」 | 変更のたびに再実行が必要 |
| 「これはテストファイル/ドキュメントで、コアロジックではない」 | Edit/Write でファイルを修正した限り適用 |
| 「push の前に review する必要がある」 | push の前に review が必須 |
| 「ユーザーが急いでいるので、先にコミット」 | 急かされてもワークフローは省略しない |
| 「このコードはよく知っている」 | 熟知度はワークフロー要件に影響しない |
| 「これらの変更はこのセッションで行ったものではない」 | コミットされていない変更がある限り、実行が必要 |
| 「ユーザーは 'commit' という言葉を使っていない」 | コミット/プッシュの意図がある限りトリガーされる |
| 「これは --amend であり、新しい commit ではない」 | --amend も履歴を変更するため、実行が必要 |
| 「変更は stash にあり、ワーキングツリーはクリーン」 | stash 内の変更も完全なワークフローが必要 |
| 「ユーザーは commit とだけ言い、push とは言っていない」 | commit 後は直ちに push が必要、追加の指示は不要 |
| 「後で push する」 | push は commit の必須後続ステップ、遅延不可 |

---

## 必須チェックポイント

**git push を実行する前に**、品質ループが完全に通過したことを確認すること：

| ステップ | 完了の指標 |
|----------|-----------|
| A. code-simplifier | Task agent が実行済み、ファイルが整理済み |
| B. git add + commit/amend | すべての変更（simplifier の修正を含む）がコミット済み |
| C. requesting-code-review | レビューで問題なし、またはすべての問題が次のイテレーションで修正済み |

以下のツール呼び出し前にループの完了を確認すること：

- `Bash` で `git push` を実行
- `Skill` で `commit-commands:*` を呼び出し
- `Skill` で `pr-review-toolkit:*`（PR の作成）を呼び出し

**プッシュ後**、PR が存在する場合は以下も実行すること：
- `Skill` で `code-review:code-review --comment` を呼び出し

**このルールはすべてのプロジェクトに例外なく適用されます。**

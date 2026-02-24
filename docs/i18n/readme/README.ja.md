[中文](../../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# JARVIS

RAG ナレッジベース、マルチ LLM 対応、ストリーミング会話機能を備えた AI アシスタントプラットフォーム。

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| バックエンド | FastAPI · LangGraph · SQLAlchemy · Alembic |
| フロントエンド | Vue 3 · TypeScript · Vite · Pinia |
| データベース | PostgreSQL · Redis · Qdrant（ベクトル DB） |
| ストレージ | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## プロジェクト構成

```
JARVIS/
├── backend/          # FastAPI バックエンド（Python 3.13 + uv）
├── frontend/         # Vue 3 フロントエンド（Bun）
├── docker-compose.yml
└── pyproject.toml    # ルートレベルの開発ツール設定
```

## クイックスタート

### フルスタック起動（推奨）

環境変数ファイルを生成して起動します：

```bash
bash scripts/init-env.sh   # 安全な .env を自動生成（初回のみ）
docker compose up -d
```

サービス URL：フロントエンド http://localhost:3000 · バックエンド http://localhost:8000

### ローカル開発

**前提条件：** Docker（インフラサービス用）、Python 3.13+、[uv](https://github.com/astral-sh/uv)、[Bun](https://bun.sh)

```bash
# インフラサービスを起動
docker compose up -d postgres redis qdrant minio

# バックエンド
cd backend
uv sync
uv run alembic upgrade head           # データベースマイグレーションを実行
uv run uvicorn app.main:app --reload  # 開発サーバー（:8000）

# フロントエンド（新しいターミナル）
cd frontend
bun install
bun run dev                           # 開発サーバー（:5173）
```

## 開発

### コード品質

```bash
# バックエンド（backend/ ディレクトリ内）
uv run ruff check --fix && uv run ruff format
uv run pyright
uv run pytest tests/ -v

# フロントエンド（frontend/ ディレクトリ内）
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # git hooks をインストール（ルートで実行）
pre-commit run --all-files
```

## 環境変数

`bash scripts/init-env.sh` を実行して、ランダムなパスワードとキーで安全な `.env` を自動生成します。

スクリプトが設定する項目：`POSTGRES_PASSWORD`、`MINIO_ROOT_USER/PASSWORD`、`REDIS_PASSWORD`、`JWT_SECRET`、`ENCRYPTION_KEY`、`DATABASE_URL`、`REDIS_URL`。

手動で記入が必要なのは `DEEPSEEK_API_KEY` のみです。詳細は `.env.example` を参照してください。

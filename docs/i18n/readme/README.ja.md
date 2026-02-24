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

環境変数ファイルをコピーして記入し、起動します：

```bash
cp .env.example .env   # 各シークレットを記入
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

プロジェクトルートに `.env` ファイルを作成します：

```env
# データベース
POSTGRES_PASSWORD=your_password

# オブジェクトストレージ
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# 認証
JWT_SECRET=your_jwt_secret

# LLM（デフォルトプロバイダー。他のプロバイダーの API Key はアプリの設定ページでユーザーごとに設定）
DEEPSEEK_API_KEY=your_key
```

ローカル開発時、バックエンドにはローカルサービスへの接続用に `backend/.env` も必要です：

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Fernet 暗号化キー（ユーザー API Key の暗号化に使用）
# 生成方法：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```

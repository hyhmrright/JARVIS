[English](../../../GEMINI.md) | [中文](../zh/GEMINI.md) | [日本語](GEMINI.md) | [한국어](../ko/GEMINI.md) | [Français](../fr/GEMINI.md) | [Deutsch](../de/GEMINI.md)

# Jarvis プロジェクトコンテキスト

本ドキュメントは、Gemini に `JARVIS` monorepo に関する正確なコンテキスト情報を提供します。

## プロジェクト概要

**名称**: Jarvis AI アシスタント
**アーキテクチャ**: マルチサービス monorepo（FastAPI バックエンド + Vue 3 フロントエンド）
**目的**: RAG ナレッジベース、マルチ LLM サポート、ストリーミング会話を備えた AI アシスタントプラットフォーム。

## ディレクトリ構造

```
JARVIS/
├── backend/          # FastAPI バックエンドサービス（Python 3.13 + SQLAlchemy + LangGraph）
├── frontend/         # Vue 3 フロントエンド（Vite + TypeScript + Pinia）
├── docker-compose.yml
├── pyproject.toml    # ルートディレクトリ（開発ツールのみ、ランタイム依存関係なし）
└── CLAUDE.md / GEMINI.md
```

## バックエンドアーキテクチャ（backend/）

- **フレームワーク**: FastAPI + Uvicorn
- **データベース**: PostgreSQL（asyncpg ドライバ）+ SQLAlchemy async ORM + Alembic マイグレーション
- **キャッシュ**: Redis
- **ベクトルストア**: Qdrant（RAG ナレッジベース）
- **オブジェクトストレージ**: MinIO（ファイルアップロード）
- **LLM**: LangGraph + LangChain、DeepSeek / OpenAI / Anthropic をサポート
- **認証**: JWT（python-jose）+ bcrypt（passlib）

### 主要モジュール

```
backend/app/
├── api/          # FastAPI ルート（auth、conversations、documents、settings）
├── agent/        # LangGraph エージェントグラフ + LLM ファクトリ
├── core/         # 設定（pydantic-settings）、データベース、セキュリティユーティリティ
├── models/       # SQLAlchemy ORM モデル
├── rag/          # ドキュメント解析、チャンク分割、Qdrant インデキシング
└── main.py       # アプリケーションエントリポイント（CORS、ルート登録、ヘルスチェック）
```

## フロントエンドアーキテクチャ（frontend/）

- **フレームワーク**: Vue 3 + TypeScript + Vite
- **状態管理**: Pinia（auth store、chat store）
- **ルーティング**: Vue Router 4（遅延読み込み + ルートガード）
- **UI**: カスタム CSS スタイル

## 環境と依存関係

### バックエンド（uv を使用）
```bash
cd backend
uv sync                          # 依存関係のインストール
uv run uvicorn app.main:app --reload  # 開発サーバー
uv run pytest tests/ -v          # テストの実行
uv run alembic upgrade head      # データベースマイグレーションの実行
```

### フロントエンド（bun を使用）
```bash
cd frontend
bun install                      # 依存関係のインストール
bun run dev                      # 開発サーバー
bun run build                    # 本番ビルド
bun run lint                     # ESLint チェック
bun run type-check               # TypeScript 型チェック
```

### Docker 環境
```bash
docker-compose up -d             # 全サービスの起動（PostgreSQL、Redis、Qdrant、MinIO、backend、frontend）
```

## 開発ワークフロー

### ブランチ戦略
- **main**: 安定バージョン（デプロイブランチ）
- **dev**: 日常開発ブランチ（すべての変更はここで行う）
- 明示的な指示がある場合のみ `dev` を `main` にマージ

### コード品質ツール

**バックエンド**:
- `ruff check --fix && ruff format`: Lint + フォーマット
- `mypy`: 型チェック
- `pytest`: テスト

**フロントエンド**:
- `bun run lint`: ESLint チェック
- `bun run type-check`: TypeScript 型チェック

**コミット前（pre-commit hooks が自動実行）**:
- YAML/TOML/JSON フォーマットチェック
- uv.lock 同期チェック
- ruff lint + format
- フロントエンド ESLint + TypeScript 型チェック

## 主要設定

- **DATABASE_URL**: `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL**: `redis://localhost:6379`
- **JWT_SECRET**: 環境変数で設定
- **DEEPSEEK_API_KEY**: 環境変数で設定
- **Alembic マイグレーション**: `DATABASE_URL` から自動的に読み取り、psycopg2 同期ドライバに変換

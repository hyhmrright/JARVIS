[English](../../../README.md) | [中文](../zh/README.md) | [日本語](README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

RAG ナレッジベース、マルチ LLM 対応、ストリーミング会話機能を備えた AI アシスタントプラットフォーム。ダークラグジュアリーデザインで、ハイエンドな AI インタラクション体験を提供します。

## 特徴

- **マルチモデル対応** — DeepSeek / OpenAI / Anthropic を設定画面で自由に切り替え可能
- **RAG ナレッジベース** — ドキュメント（PDF/TXT/MD/DOCX）をアップロードし、自動チャンキング・ベクトル化保存
- **ストリーミングチャット** — SSE リアルタイムストリーミング出力、AI 応答をトークン単位で表示
- **LangGraph Agent** — ReAct ループアーキテクチャ、コード実行・ファイル操作などのツール呼び出しに対応
- **ダークラグジュアリー UI** — グラスモーフィズムカード、ゴールドグラデーションアクセント、洗練されたアニメーション遷移
- **多言語対応** — 中/英/日/韓/仏/独の 6 言語をサポート
- **プロダクション級 Docker** — 4 層ネットワーク分離、Traefik エッジルーター、完全な可観測性スタック

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| バックエンド | FastAPI · LangGraph · SQLAlchemy · Alembic |
| フロントエンド | Vue 3 · TypeScript · Vite · Pinia |
| データベース | PostgreSQL · Redis · Qdrant（ベクトル DB） |
| ストレージ | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| エッジルーター | Traefik v3 |
| 可観測性 | Prometheus · Grafana · cAdvisor |
| デザイン | CSS Variables デザインシステム · グラスモーフィズム · ダークテーマ |

## プロジェクト構成

```
JARVIS/
├── backend/           # FastAPI バックエンド（Python 3.13 + uv）
│   ├── app/           # アプリケーションコード（agent/api/core/db/infra/rag/tools）
│   ├── alembic/       # データベースマイグレーション
│   └── tests/         # pytest テストスイート
├── frontend/          # Vue 3 フロントエンド（Bun）
│   └── src/
│       ├── assets/styles/  # CSS デザインシステム（global/animations/components）
│       ├── pages/          # ページコンポーネント（Login/Register/Chat/Documents/Settings）
│       ├── stores/         # Pinia 状態管理
│       └── locales/        # i18n 多言語
├── database/          # Docker 初期化スクリプト（postgres/redis/qdrant）
├── monitoring/        # Prometheus 設定 + Grafana プロビジョニング
├── traefik/           # Traefik 動的ルーティング設定
├── docker-compose.yml          # 本番オーケストレーション（4 層ネットワーク）
├── docker-compose.override.yml # 開発オーバーライド（ポート公開、ホットリロード）
└── pyproject.toml     # ルートレベルの開発ツール設定
```

## クイックスタート

### フルスタック起動（推奨）

環境変数ファイルを生成して起動します：

```bash
bash scripts/init-env.sh   # 安全な .env を自動生成（初回のみ）
docker compose up -d
```

| サービス | URL |
|----------|-----|
| **アプリ（Traefik 経由）** | http://localhost |
| Grafana（モニタリング） | http://localhost:3001 |
| Traefik ダッシュボード | http://localhost:8080/dashboard/ |

> キャッシュなしで再ビルド：`docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

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
uv run mypy app
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

スクリプトが設定する項目：`POSTGRES_PASSWORD`、`MINIO_ROOT_USER/PASSWORD`、`REDIS_PASSWORD`、`JWT_SECRET`、`ENCRYPTION_KEY`、`GRAFANA_PASSWORD`、`DATABASE_URL`、`REDIS_URL`。

手動で記入が必要なのは `DEEPSEEK_API_KEY` のみです。詳細は `.env.example` を参照してください。

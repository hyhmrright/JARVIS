[English](../../../README.md) | [中文](../zh/README.md) | [日本語](README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

> RAG ナレッジベース、マルチ LLM 対応、リアルタイムストリーミング会話を備えた AI アシスタントプラットフォーム — ダークラグジュアリーデザイン言語を採用。

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## 特徴

- **マルチモデル対応** — DeepSeek / OpenAI / Anthropic を設定画面でユーザーごとに切り替え可能
- **RAG ナレッジベース** — PDF / TXT / MD / DOCX のアップロード、自動チャンキング・ベクトルインデックス化
- **ストリーミングチャット** — LangGraph ReAct エージェントによる SSE トークン単位のリアルタイム出力
- **ダークラグジュアリー UI** — グラスモーフィズムカード、ゴールドグラデーションアクセント、滑らかなアニメーション遷移
- **多言語対応** — 6 言語：中国語 / 英語 / 日本語 / 韓国語 / フランス語 / ドイツ語
- **プロダクション級インフラ** — 4 層ネットワーク分離、Traefik エッジルーター、Prometheus + Grafana による可観測性

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

## 前提条件

| ツール | バージョン | インストール |
|--------|------------|--------------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **ローカル開発のみ** フロントエンドに [Bun](https://bun.sh) が別途必要です。

## クイックスタート

### 1. クローンして環境を生成する

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh   # ランダムな安全な認証情報で .env を生成
```

> `uv` が必要です（Fernet 暗号化キーの生成に内部で使用）。その他のセットアップは不要です。

### 2. LLM API キーを追加する

`.env` を開いて少なくとも 1 つのキーを記入します：

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # optional
ANTHROPIC_API_KEY=sk-ant-... # optional
```

### 3. 起動する

```bash
docker compose up -d
```

初回起動時は Docker イメージのビルドに数分かかります。起動完了後：

| サービス | URL | 利用可能 |
|----------|-----|----------|
| **アプリ** | http://localhost | 常時 |
| Grafana（モニタリング） | http://localhost:3001 | 常時 |
| Traefik ダッシュボード | http://localhost:8080/dashboard/ | 開発のみ |
| バックエンド API（直接） | http://localhost:8000 | 開発のみ |

> デフォルトの `docker compose up -d` は `docker-compose.override.yml` を自動マージし、デバッグポートの公開とバックエンドコードのホットリロードを有効にします。本番環境については以下を参照してください。

### トラブルシューティング

**サービスが起動しない場合** — ログを確認：
```bash
docker compose logs backend
docker compose logs traefik
```

**ゼロからリビルドする**（Dockerfile や依存関係を変更した後）：
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**`:80` でポート競合が発生する場合** — ポート 80 を占有しているプロセスを停止してから再試行してください。

---

## Docker Compose ファイル

このプロジェクトは 2 つの compose ファイルを組み合わせて使用します：

| ファイル | 目的 |
|----------|------|
| `docker-compose.yml` | **ベース（本番）** — 最小限の公開：`:80` と `:3001` のみ |
| `docker-compose.override.yml` | **開発オーバーライド** — Docker Compose が自動マージ；デバッグポートとホットリロードを追加 |

`docker compose up -d` を実行すると Docker Compose が自動的にオーバーライドファイルをマージするため、**ローカル開発では追加のフラグは不要です**。本番環境では明示的に除外します：

```bash
# 開発（デフォルト） — 両ファイルを自動マージ
docker compose up -d

# 本番 — ベースファイルのみ、デバッグポートなし、ホットリロードなし
docker compose -f docker-compose.yml up -d
```

## 本番デプロイ

```bash
docker compose -f docker-compose.yml up -d
```

公開ポート：`:80`（アプリ）と `:3001`（Grafana）のみ。

---

## ローカル開発

より高速なイテレーションのためにバックエンドとフロントエンドをネイティブで実行します。

**ステップ 1 — インフラを起動する：**

```bash
docker compose up -d postgres redis qdrant minio
```

**ステップ 2 — バックエンド**（新しいターミナル、リポジトリルートから）：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**ステップ 3 — フロントエンド**（新しいターミナル、リポジトリルートから）：

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173  (proxies /api → localhost:8000)
```

---

## プロジェクト構成

```
JARVIS/
├── backend/                    # FastAPI（Python 3.13 + uv）
│   ├── app/
│   │   ├── agent/              # LangGraph ReAct エージェント
│   │   ├── api/                # HTTP ルート（auth/chat/conversations/documents/settings）
│   │   ├── core/               # 設定、JWT/bcrypt/Fernet セキュリティ、レート制限
│   │   ├── db/                 # SQLAlchemy 非同期モデル + セッション
│   │   ├── infra/              # Qdrant / MinIO / Redis シングルトン
│   │   ├── rag/                # ドキュメントチャンカー + エンベッダー + インデクサー
│   │   └── tools/              # LangGraph ツール（search/code_exec/file/datetime）
│   ├── alembic/                # データベースマイグレーション
│   └── tests/                  # pytest スイート
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Axios シングルトン + 認証インターセプター
│       ├── stores/             # Pinia ストア（auth + chat）
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n（zh/en/ja/ko/fr/de）
├── database/                   # Docker 初期化スクリプト（postgres/redis/qdrant）
├── monitoring/                 # Prometheus 設定 + Grafana プロビジョニング
├── traefik/                    # Traefik 動的ルーティング設定
├── scripts/
│   └── init-env.sh             # 安全な .env を生成（uv が必要）
├── docker-compose.yml          # ベースオーケストレーション
├── docker-compose.override.yml # 開発オーバーライド（デバッグポート + ホットリロード）
└── .env.example                # 環境変数リファレンス
```

---

## 開発

### コード品質

```bash
# バックエンド（backend/ から実行）
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# フロントエンド（frontend/ から実行）
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# リポジトリルートから実行
pre-commit install
pre-commit run --all-files
```

Hooks：YAML/TOML/JSON バリデーション · uv.lock 同期 · Ruff lint+format · ESLint · mypy · vue-tsc · gitleaks シークレットスキャン · `main` への直接コミットをブロック。

---

## 環境変数

`bash scripts/init-env.sh` がすべての認証情報を自動生成します。必要なのは LLM API キーを提供するだけです。

| 変数 | 説明 |
|------|------|
| `POSTGRES_PASSWORD` | PostgreSQL パスワード |
| `MINIO_ROOT_USER/PASSWORD` | MinIO オブジェクトストレージの認証情報 |
| `REDIS_PASSWORD` | Redis 認証パスワード |
| `JWT_SECRET` | JWT 署名シークレット |
| `ENCRYPTION_KEY` | ユーザー API キーの保存時暗号化用 Fernet キー |
| `GRAFANA_PASSWORD` | Grafana 管理者パスワード |
| `DEEPSEEK_API_KEY` | **手動で記入が必要** |
| `OPENAI_API_KEY` | オプション |
| `ANTHROPIC_API_KEY` | オプション |

完全なリファレンスは `.env.example` を参照してください。

---

## コントリビュート

[CONTRIBUTING.md](../../../.github/CONTRIBUTING.md) を参照してください。

## ライセンス

[MIT](../../../LICENSE)

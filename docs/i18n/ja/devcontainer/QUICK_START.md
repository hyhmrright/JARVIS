[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](../../de/devcontainer/QUICK_START.md)

# 🚀 Dev Container クイックリファレンス

## ワンクリック起動 (VS Code)

```bash
# 1. VS Code を開く
code path/to/JARVIS

# 2. F1 を押して、以下を入力:
Dev Containers: Reopen in Container

# 3. ビルド完了を待って、コーディング開始!
```

---

## コマンドライン使用

### イメージのビルド
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### プログラムの実行
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### 対話式シェルに入る
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## よく使うコマンド

### コンテナ内で
```bash
# 依存関係のインストール
uv sync

# プログラムの実行
uv run python main.py

# コードチェック
uv run ruff check main.py
uv run ruff format main.py
uv run mypy app

# Git 操作
git status
pre-commit run --all-files
```

---

## ファイル構成

```
.devcontainer/
├── devcontainer.json        # VS Code 設定
├── Dockerfile               # イメージ定義
├── README.md                # 使用ガイド（中国語）
├── QUICK_START.md           # クイックリファレンス（中国語）
└── docs/i18n/
    ├── readme/              # 使用ガイド翻訳
    │   └── README.{en,ja,ko,fr,de}.md
    └── quick-start/         # クイックリファレンス翻訳
        └── QUICK_START.{en,ja,ko,fr,de}.md
```

---

## クイックテスト

```bash
# Python のテスト
docker run --rm jarvis-dev python --version

# uv のテスト
docker run --rm jarvis-dev uv --version

# Bun のテスト
docker run --rm jarvis-dev bun --version
```

---

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| Docker が動作していない | Docker Desktop を起動する |
| ビルドに失敗した | `docker system prune -a` でキャッシュをクリア |
| VS Code が接続できない | VS Code を再起動するかコンテナを再構築する |
| 依存関係が見つからない | `python` の代わりに `uv run python` を使用する |

---

## 環境情報

- **Python**: 3.13
- **uv**: latest
- **Bun**: latest
- **Git**: latest
- **ベースイメージ**: python:3.13-slim
- **ユーザー**: vscode (非 root)
- **作業ディレクトリ**: /workspace

---

## 関連ドキュメント

- [完全使用ガイド (日本語)](README.md)

---

**ヒント**: 初回ビルドは約3〜5分かかりますが、2回目以降の起動は10〜20秒です!

[中文](QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container クイックリファレンス

## ワンクリック起動 (VS Code)

```bash
# 1. VS Code を開く
code /Users/hyh/code/JARVIS

# 2. F1 を押して、以下を入力:
Dev Containers: Reopen in Container

# 3. ビルド完了を待って、コーディング開始!
```

---

## コマンドライン使用

### イメージのビルド
```bash
cd /Users/hyh/code/JARVIS
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
uv run pyright main.py

# Git 操作
git status
pre-commit run --all-files
```

---

## ファイル構成

```
.devcontainer/
├── devcontainer.json     # VS Code 設定
├── Dockerfile            # イメージ定義
├── README.md             # 使用ガイド
├── CHANGELOG.md          # 設定ログ
├── SETUP_COMPLETE.md     # 完全レポート
├── TEST_REPORT.md        # テスト結果
└── test.sh               # 検証スクリプト
```

---

## クイックテスト

```bash
# 設定の検証
./.devcontainer/test.sh

# Python のテスト
docker run --rm jarvis-dev python --version

# uv のテスト
docker run --rm jarvis-dev uv --version

# 完全なワークフローのテスト
docker run --rm -v $(pwd):/workspace jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
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

- **Python**: 3.13.11
- **uv**: 0.9.26
- **Git**: 2.47.3
- **ベースイメージ**: python:3.13-slim
- **ユーザー**: vscode (非 root)
- **作業ディレクトリ**: /workspace

---

## 関連ドキュメント

- [完全使用ガイド](.devcontainer/README.md)
- [設定説明](.devcontainer/CHANGELOG.md)
- [テストレポート](.devcontainer/TEST_REPORT.md)
- [完全セットアップレポート](.devcontainer/SETUP_COMPLETE.md)

---

**ヒント**: 初回ビルドは約3〜5分かかりますが、2回目以降の起動は10〜20秒です!

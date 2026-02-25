[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)

# Dev Container 使用ガイド

## Dev Container とは？

Dev Container は、Docker コンテナを使用して一貫した開発体験を提供する、標準化された開発環境設定です。どのマシンでも同じ開発環境を利用できます。

## 機能

✅ **Python 3.13 環境を事前設定済み**
✅ **uv パッケージマネージャーの自動インストール**
✅ **Bun ランタイムをプリインストール**（フロントエンド開発）
✅ **開発ツールをプリインストール** (Ruff, Pyright, Pre-commit)
✅ **VS Code 拡張機能の自動インストール**
✅ **`uv sync`、`pre-commit install`、`bun install` の自動実行**
✅ **コードフォーマットと Linting 設定済み**

## 使い方

### 方法1：VS Code（推奨）

1. **必要なソフトウェアをインストール**:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop) をインストール
   - [VS Code](https://code.visualstudio.com/) をインストール
   - VS Code 拡張機能をインストール: `Dev Containers` (ms-vscode-remote.remote-containers)

2. **プロジェクトを開く**:
   - VS Code でこのプロジェクトフォルダを開く
   - VS Code が `.devcontainer` 設定を検出します
   - 右下に表示される "Reopen in Container" ボタンをクリック
   - または `F1` を押して "Dev Containers: Reopen in Container" と入力

3. **ビルドを待つ**:
   - 初回起動時は Docker イメージをビルドします（約2〜5分）
   - 2回目以降は高速です（10〜20秒）

4. **開発を開始**:
   - すべての依存関係が自動的にインストールされています
   - コード品質ツールは設定済みです
   - `python main.py` を直接実行できます

### 方法2：コマンドライン

```bash
# コンテナをビルド
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# コンテナを実行
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# コンテナ内で
uv sync
python main.py
```

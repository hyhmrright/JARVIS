[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# Dev Container 사용 가이드

## Dev Container란?

Dev Container는 Docker 컨테이너를 사용하여 일관된 개발 경험을 제공하는 표준화된 개발 환경 구성입니다. 어떤 머신에서든 동일한 개발 환경을 얻을 수 있습니다.

## 기능

✅ **Python 3.13 환경 사전 구성**
✅ **uv 패키지 매니저 자동 설치**
✅ **개발 도구 사전 설치** (Ruff, Pyright, Pre-commit)
✅ **VS Code 확장 자동 설치**
✅ **`uv sync` 및 `pre-commit install` 자동 실행**
✅ **코드 포맷팅 및 Linting 구성 완료**

## 사용 방법

### 방법 1: VS Code (권장)

1. **필수 소프트웨어 설치**:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop) 설치
   - [VS Code](https://code.visualstudio.com/) 설치
   - VS Code 확장 설치: `Dev Containers` (ms-vscode-remote.remote-containers)

2. **프로젝트 열기**:
   - VS Code에서 이 프로젝트 폴더를 엽니다
   - VS Code가 `.devcontainer` 구성을 감지합니다
   - 오른쪽 하단에 나타나는 "Reopen in Container" 버튼을 클릭합니다
   - 또는 `F1`을 누르고 "Dev Containers: Reopen in Container"를 입력합니다

3. **빌드 대기**:
   - 처음 열 때 Docker 이미지를 빌드합니다 (약 2-5분)
   - 이후 열 때는 빠릅니다 (10-20초)

4. **개발 시작**:
   - 모든 종속성이 자동으로 설치되어 있습니다
   - 코드 품질 도구가 구성되어 있습니다
   - `python main.py`를 바로 실행할 수 있습니다

### 방법 2: 명령줄

```bash
# 컨테이너 빌드
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# 컨테이너 실행
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# 컨테이너 내부에서
uv sync
python main.py
```

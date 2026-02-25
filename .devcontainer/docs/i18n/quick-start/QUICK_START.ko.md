[中文](../../../QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container 빠른 참조

## 원클릭 시작 (VS Code)

```bash
# 1. VS Code 열기
code path/to/JARVIS

# 2. F1을 누르고 입력:
Dev Containers: Reopen in Container

# 3. 빌드 완료를 기다리고, 코딩 시작!
```

---

## 명령줄 사용

### 이미지 빌드
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### 프로그램 실행
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### 대화형 셸 진입
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## 자주 사용하는 명령어

### 컨테이너 내부에서
```bash
# 종속성 설치
uv sync

# 프로그램 실행
uv run python main.py

# 코드 검사
uv run ruff check main.py
uv run ruff format main.py
uv run mypy app

# Git 작업
git status
pre-commit run --all-files
```

---

## 파일 구조

```
.devcontainer/
├── devcontainer.json        # VS Code 구성
├── Dockerfile               # 이미지 정의
├── README.md                # 사용 가이드 (중국어)
├── QUICK_START.md           # 빠른 참조 (중국어)
└── docs/i18n/
    ├── readme/              # 사용 가이드 번역
    │   └── README.{en,ja,ko,fr,de}.md
    └── quick-start/         # 빠른 참조 번역
        └── QUICK_START.{en,ja,ko,fr,de}.md
```

---

## 빠른 테스트

```bash
# Python 테스트
docker run --rm jarvis-dev python --version

# uv 테스트
docker run --rm jarvis-dev uv --version

# Bun 테스트
docker run --rm jarvis-dev bun --version
```

---

## 문제 해결

| 문제 | 해결 방법 |
|------|-----------|
| Docker가 실행되지 않음 | Docker Desktop 시작 |
| 빌드 실패 | `docker system prune -a`로 캐시 정리 |
| VS Code 연결 불가 | VS Code 재시작 또는 컨테이너 재빌드 |
| 종속성을 찾을 수 없음 | `python` 대신 `uv run python` 사용 |

---

## 환경 정보

- **Python**: 3.13
- **uv**: latest
- **Bun**: latest
- **Git**: latest
- **베이스 이미지**: python:3.13-slim
- **사용자**: vscode (비 root)
- **작업 디렉토리**: /workspace

---

## 관련 문서

- [전체 사용 가이드 (한국어)](../readme/README.ko.md)
- [전체 사용 가이드 (中文)](../../../README.md)

---

**팁**: 첫 빌드는 약 3-5분이 소요되며, 이후 시작은 10-20초만 걸립니다!

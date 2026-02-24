[中文](../../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

이 파일은 Claude Code가 이 코드베이스에서 작업할 때의 가이드라인을 제공합니다.

## 브랜치 전략

- **main**: 릴리스 전용. 직접 커밋이나 개발이 허용되지 않습니다. dev 등 개발 브랜치에서의 머지만 허용됩니다.
- **dev**: 메인 개발 브랜치. 모든 일상 개발, 버그 수정, 기능 개발은 이 브랜치 또는 하위 브랜치에서 수행합니다.
- 개발 완료 후: dev → merge → main → push, 단계를 건너뛸 수 없습니다.

## 프로젝트 개요

JARVIS는 RAG 지식 기반, 멀티 LLM 지원, 스트리밍 대화 기능을 갖춘 AI 어시스턴트 플랫폼으로, monorepo 구조를 사용합니다.

## 핵심 아키텍처

- **backend/**: FastAPI + LangGraph + SQLAlchemy (PostgreSQL) + Qdrant (벡터 저장소) + MinIO (파일 저장소) + Redis
- **frontend/**: Vue 3 + TypeScript + Vite + Pinia
- **루트 pyproject.toml**: 개발 도구(ruff, pyright, pre-commit)만 관리, 런타임 의존성 없음
- **LLM**: DeepSeek / OpenAI / Anthropic 지원, LangGraph StateGraph로 구동

## 개발 환경

- **Python 버전**: 3.13 (`.python-version`)
- **패키지 관리자**: `uv`
- **가상 환경**: `.venv` (자동 관리)

## 자주 사용하는 명령어

### 환경 설정
```bash
uv sync                      # 모든 의존성 설치
```

### 애플리케이션 실행
```bash
# 백엔드 (backend/ 디렉토리에서)
uv run uvicorn app.main:app --reload

# 프론트엔드 (frontend/ 디렉토리에서)
bun run dev

# 풀 스택 (루트 디렉토리)
docker-compose up -d
```

### 코드 품질 검사
```bash
ruff check                   # 코드 린트
ruff check --fix             # 문제 자동 수정
ruff format                  # 코드 포맷팅
pyright                      # 타입 검사
```

### 테스트
```bash
# backend/ 디렉토리에서 실행
uv run pytest tests/ -v                        # 모든 테스트 실행
uv run pytest tests/api/test_auth.py -v        # 특정 테스트 파일 실행
```

### Pre-commit Hooks
```bash
pre-commit install           # git hooks 설치
pre-commit run --all-files   # 모든 hooks 수동 실행
```

Pre-commit 자동 실행 항목:
- YAML/TOML/JSON 포맷 검사
- uv.lock 동기화 검사
- Ruff lint 및 format
- 파일 끝 빈 줄 및 후행 공백 검사

### 의존성 관리
```bash
uv add <패키지명>             # 프로덕션 의존성 추가
uv add --group dev <패키지명> # 개발 의존성 추가
uv sync --upgrade            # 의존성 업데이트
uv lock                      # pyproject.toml 수동 편집 후 uv.lock 재생성
```

## 도구 설정

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **Pre-commit**: uv-lock, ruff-check, ruff-format 및 표준 파일 검사 실행

---

# 글로벌 개발 규칙

## Git 작업 전 자가 점검

**`git commit`, `git push` 또는 commit/push skill 호출 전에 반드시 자가 점검을 수행해야 합니다:**

```
이 세션에서 파일을 수정했는가?
   → 예 → 품질 루프(simplifier → commit → review)가 완전히 통과되었는가?
           → 아니오 → 【STOP】즉시 품질 루프 실행
           → 예 → git 작업 계속
   → 아니오 → 워킹 트리에 커밋되지 않은 변경사항이 있는가? (git diff / git diff --cached / git stash list)
              → 있음 (stash 포함) → 【STOP】먼저 전체 품질 루프를 완료해야 함
              → 없음 → git 작업 계속
```

---

## 코드 변경 필수 워크플로우

### 도구 설명

| 도구 | 유형 | 호출 방법 | 실행 시점 |
|------|------|----------|----------|
| code-simplifier | Task agent | `Task` 도구, `subagent_type: "code-simplifier:code-simplifier"` | commit 전 |
| pre-push 코드 리뷰 | Skill | `Skill: superpowers:requesting-code-review` | commit 후, push 전 |
| PR 코드 리뷰 | Skill | `Skill: code-review:code-review --comment` | push 후 (PR이 존재해야 함) |

### 트리거 조건 (하나라도 충족하면 발동)

- Edit / Write / NotebookEdit를 사용하여 파일을 수정함
- 사용자가 변경사항을 Git에 영속화하거나 리모트에 푸시하려는 의도가 있음 ("동기화", "업로드", "PR 생성", "아카이브", "ship" 등의 표현 포함)
- commit / push 관련 skill을 호출하려는 상태

### 실행 단계 (순서 고정, 건너뛸 수 없음)

```
코드 작성 / 파일 수정
      ↓
╔══════════════════ 품질 루프 (문제가 없을 때까지 반복) ══════════════════╗
║                                                                         ║
║  A. 【필수】Task: code-simplifier                                       ║
║     (Task agent, 파일을 직접 수정함)                                    ║
║          ↓                                                              ║
║  B. git add + commit                                                    ║
║     최초 진입 → git commit                                              ║
║     수정 후 재진입 → git commit --amend (push 전 히스토리를 깔끔하게 유지)║
║          ↓                                                              ║
║  C. 【필수】Skill: superpowers:requesting-code-review                   ║
║     (BASE_SHA=HEAD~1, HEAD_SHA=HEAD 제공 필요)                          ║
║          ↓                                                              ║
║     문제가 발견되었는가?                                                ║
║       예 → 코드 수정 ──────────────────────────→ 단계 A로 돌아감       ║
║       아니오 ↓                                                          ║
╚════════════════════════════════════════════════════════════════════════╝
      ↓
git push (즉시 실행, 지연 불가)
      ↓ (GitHub PR이 존재하는 경우)
【필수】Skill: code-review:code-review --comment
```

**핵심 설명:**
- 품질 루프는 완전히 실행(A→B→C)되어야 하며, C에서 문제가 없어야 종료 가능
- 수정 후 루프에 재진입할 때는 `--amend` 사용 (push 전 단일 commit 유지)
- `--amend`는 리뷰를 건너뛰는 이유가 되지 않으며, C를 반드시 재실행해야 함

---

## 워크플로우 건너뛰기의 금지된 변명

다음 이유는 건너뛰기의 근거로 **사용할 수 없습니다**:

| 변명 | 올바른 대응 |
|------|-----------|
| "단순한 한 줄 변경일 뿐입니다" | 변경 크기에 관계없이 반드시 실행 |
| "사용자가 commit만 말했지 review는 말하지 않았습니다" | commit 자체가 트리거 조건 |
| "방금 유사한 코드를 리뷰했습니다" | 변경할 때마다 재실행 필요 |
| "이것은 테스트 파일/문서이지 핵심 로직이 아닙니다" | Edit/Write로 파일을 수정한 한 적용됨 |
| "push 전에 review가 필요합니다" | push 전에 반드시 review |
| "사용자가 서두르고 있으니 먼저 커밋합니다" | 독촉으로 워크플로우를 건너뛰지 않음 |
| "이 코드는 잘 알고 있습니다" | 숙련도는 워크플로우 요구사항에 영향을 주지 않음 |
| "이 변경은 이 세션에서 한 것이 아닙니다" | 커밋되지 않은 변경사항이 있는 한 실행 필요 |
| "사용자가 'commit'이라는 단어를 사용하지 않았습니다" | 커밋/푸시 의도가 있는 한 트리거됨 |
| "이것은 --amend이지 새 commit이 아닙니다" | --amend도 히스토리를 수정하므로 실행 필요 |
| "변경사항이 stash에 있고 워킹 트리는 깨끗합니다" | stash의 변경사항도 전체 워크플로우 필요 |
| "사용자가 commit만 말했지 push는 말하지 않았습니다" | commit 후 즉시 push 필요, 추가 지시 불필요 |
| "나중에 push 하겠습니다" | push는 commit의 필수 후속 단계, 지연 불가 |

---

## 필수 체크포인트

**git push 실행 전에**, 품질 루프가 완전히 통과되었는지 확인해야 합니다:

| 단계 | 완료 지표 |
|------|----------|
| A. code-simplifier | Task agent가 실행됨, 파일이 정리됨 |
| B. git add + commit/amend | 모든 변경사항 (simplifier 수정 포함)이 커밋됨 |
| C. requesting-code-review | 리뷰에서 문제 없음, 또는 모든 문제가 다음 반복에서 수정됨 |

다음 도구 호출 전에 루프 완료를 확인해야 합니다:

- `Bash`로 `git push` 실행
- `Skill`로 `commit-commands:*` 호출
- `Skill`로 `pr-review-toolkit:*` (PR 생성) 호출

**푸시 후**, PR이 존재하면 다음도 실행해야 합니다:
- `Skill`로 `code-review:code-review --comment` 호출

**이 규칙은 모든 프로젝트에 예외 없이 적용됩니다.**

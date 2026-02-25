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

```
JARVIS/
├── backend/           # FastAPI 백엔드 (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # FastAPI 엔트리포인트, lifespan으로 인프라 연결 관리
│   │   ├── agent/     # LangGraph ReAct 에이전트 (graph/llm/state)
│   │   ├── api/       # HTTP 라우트 (auth/chat/conversations/documents/settings)
│   │   ├── core/      # 설정 (Pydantic Settings), 보안 (JWT/bcrypt/Fernet), 레이트 리미팅
│   │   ├── db/        # SQLAlchemy async 모델 및 세션
│   │   ├── infra/     # 인프라 클라이언트 싱글톤 (Qdrant/MinIO/Redis)
│   │   ├── rag/       # RAG 파이프라인 (chunker/embedder/indexer)
│   │   └── tools/     # LangGraph 도구 (search/code_exec/file/datetime)
│   ├── alembic/       # 데이터베이스 마이그레이션
│   └── tests/         # pytest 테스트 스위트
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/       # Axios 싱글톤 + auth 인터셉터
│       ├── stores/    # Pinia 스토어 (auth + chat)
│       ├── pages/     # 페이지 컴포넌트 (Login/Register/Chat/Documents/Settings)
│       ├── locales/   # i18n (zh/en/ja/ko/fr/de)
│       └── router/    # Vue Router + auth 가드
├── database/          # Docker 초기화 스크립트 (postgres/redis/qdrant)
├── docker-compose.yml # 풀스택 오케스트레이션
└── pyproject.toml     # 루트 개발 도구 설정 (ruff/pre-commit), 런타임 의존성 없음
```

### 백엔드 아키텍처 핵심 사항

**LLM 에이전트**: `agent/graph.py`는 LangGraph `StateGraph`를 사용하여 ReAct 루프 (llm → tools → llm → END)를 구현합니다. 요청마다 새로운 graph 인스턴스를 생성하며, 체크포인트 영속화는 하지 않습니다. LLM 팩토리(`agent/llm.py`)는 `match/case`로 `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`에 분배합니다.

**스트리밍 채팅**: `api/chat.py`의 `POST /api/chat/stream`은 SSE `StreamingResponse`를 반환합니다. 참고: 스트리밍 제너레이터 내부에서는 독립적인 `AsyncSessionLocal` 세션을 사용합니다 (요청 레벨 세션은 핸들러가 반환되면 닫히므로 재사용 불가).

**RAG 파이프라인**: 문서 업로드 → `extract_text()` → `chunk_text()` (슬라이딩 윈도우, 500단어/50단어 오버랩) → `OpenAIEmbeddings` (text-embedding-3-small, 1536차원) → Qdrant upsert. 사용자별 1개 컬렉션 (`user_{id}`). 참고: RAG 검색은 아직 에이전트 대화 흐름에 연결되지 않았습니다.

**데이터베이스 모델**: 5개 테이블 — `users`, `user_settings` (JSONB로 Fernet 암호화된 API 키 저장), `conversations`, `messages` (불변), `documents` (소프트 삭제). 모두 UUID 기본키 사용.

**인프라 싱글톤**: Qdrant는 모듈 레벨 글로벌 + 지연 초기화 + asyncio.Lock; MinIO는 `@lru_cache` + `asyncio.to_thread()` (동기 SDK); PostgreSQL은 모듈 레벨 engine + sessionmaker.

### 프론트엔드 아키텍처 핵심 사항

**상태 관리**: 2개의 Pinia 스토어 — `auth.ts` (JWT 토큰을 localStorage에 영속화)와 `chat.ts` (대화 목록 + SSE 스트리밍 메시지). SSE는 Axios 대신 네이티브 `fetch` + `ReadableStream` 사용 (Axios는 스트리밍 응답 본문을 지원하지 않음).

**라우팅**: 5개 라우트, 모든 페이지 컴포넌트가 지연 로드. `beforeEach` 가드가 `auth.isLoggedIn`을 확인.

**API 클라이언트**: `baseURL: "/api"`의 Axios 인스턴스, 요청 인터셉터가 localStorage에서 토큰 읽기. dev 서버가 `/api` → `http://backend:8000`으로 프록시.

**국제화**: vue-i18n, 6개 언어, 감지 우선순위: localStorage → navigator.language → zh.

## 개발 환경

- **Python**: 3.13 (`.python-version`)
- **패키지 관리자**: 백엔드 `uv`, 프론트엔드 `bun`
- **가상 환경**: `.venv` (uv가 자동 관리)

## 자주 사용하는 명령어

### 환경 설정
```bash
bash scripts/init-env.sh             # 첫 실행, .env 생성 (랜덤 비밀번호/키 포함)
uv sync                              # Python 의존성 설치
cd frontend && bun install            # 프론트엔드 의존성 설치
pre-commit install                    # git hooks 설치
```

### 애플리케이션 실행
```bash
# 인프라 서비스만 시작 (로컬 개발용)
docker compose up -d postgres redis qdrant minio

# 백엔드 (backend/ 디렉토리에서)
uv run alembic upgrade head           # 데이터베이스 마이그레이션
uv run uvicorn app.main:app --reload  # 개발 서버 :8000

# 프론트엔드 (frontend/ 디렉토리에서)
bun run dev                           # 개발 서버 :5173 (/api → backend:8000 프록시)

# 풀스택 Docker
docker compose up -d                  # 프론트엔드 :3000 · 백엔드 :8000
```

### 코드 품질
```bash
# 백엔드
ruff check                   # 린트
ruff check --fix             # 린트 + 자동 수정
ruff format                  # 포맷
uv run mypy app              # 타입 검사

# 프론트엔드 (frontend/ 디렉토리에서)
bun run lint                 # ESLint
bun run lint:fix             # ESLint + 자동 수정
bun run format               # Prettier
bun run type-check           # vue-tsc
```

### 테스트
```bash
# backend/ 디렉토리에서 실행
uv run pytest tests/ -v                        # 모든 테스트
uv run pytest tests/api/test_auth.py -v        # 단일 파일
uv run pytest tests/api/test_auth.py::test_login -v  # 단일 테스트 케이스
```

### Pre-commit Hooks
```bash
pre-commit run --all-files   # 모든 hooks 수동 실행
```

Hooks 내용: YAML/TOML/JSON 포맷 검사, uv.lock 동기화, Ruff lint+format, ESLint, mypy, vue-tsc 타입 검사, gitleaks 시크릿 스캐닝, main 직접 커밋 차단.

### 의존성 관리
```bash
# Python (루트 pyproject.toml은 개발 도구 관리, backend/pyproject.toml은 런타임 의존성 관리)
uv add <패키지명>             # 의존성 추가 (해당 디렉토리에서 실행)
uv add --group dev <패키지명> # 개발 의존성 추가
uv lock                      # pyproject.toml 수동 편집 후 lock 재생성

# 프론트엔드
cd frontend && bun add <패키지명>
```

## 도구 설정

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **mypy**: plugins=pydantic.mypy+sqlalchemy, disallow_untyped_defs=true, ignore_missing_imports=true
- **ESLint**: flat config, typescript-eslint + eslint-plugin-vue + prettier
- **TypeScript**: strict, bundler resolution, `@/*` → `src/*`

## 환경 변수

모든 민감한 설정(데이터베이스 비밀번호, JWT 시크릿, 암호화 키, MinIO 자격 증명)에는 기본값이 없으며, `.env` 또는 환경 변수로 제공해야 합니다. `bash scripts/init-env.sh`를 실행하여 자동 생성하세요. `DEEPSEEK_API_KEY`만 수동 입력이 필요합니다.

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

[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

RAG 지식 베이스, 다중 LLM 지원, 스트리밍 대화 기능을 갖춘 AI 어시스턴트 플랫폼. 다크 럭셔리(Dark Luxury) 디자인으로 프리미엄 AI 인터랙션 경험을 제공합니다.

## 기능

- **다중 모델 지원** — DeepSeek / OpenAI / Anthropic, 설정에서 자유롭게 전환 가능
- **RAG 지식 베이스** — 문서(PDF/TXT/MD/DOCX) 업로드, 자동 청킹 및 벡터화 저장
- **스트리밍 채팅** — SSE 실시간 스트리밍 출력, AI 응답을 토큰 단위로 표시
- **LangGraph Agent** — ReAct 루프 아키텍처, 코드 실행·파일 작업 등 도구 호출 지원
- **다크 럭셔리 UI** — 글라스모피즘 카드, 골드 그라데이션 악센트, 정교한 애니메이션 전환
- **다국어** — 중/영/일/한/프/독 6개 언어 지원
- **풀스택 Docker** — `docker compose up -d` 한 번으로 전체 서비스 실행

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 프론트엔드 | Vue 3 · TypeScript · Vite · Pinia |
| 데이터베이스 | PostgreSQL · Redis · Qdrant (벡터 DB) |
| 스토리지 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| 디자인 | CSS Variables 디자인 시스템 · 글라스모피즘 · 다크 테마 |

## 프로젝트 구조

```
JARVIS/
├── backend/           # FastAPI 백엔드 (Python 3.13 + uv)
│   ├── app/           # 애플리케이션 코드 (agent/api/core/db/infra/rag/tools)
│   ├── alembic/       # 데이터베이스 마이그레이션
│   └── tests/         # pytest 테스트 스위트
├── frontend/          # Vue 3 프론트엔드 (Bun)
│   └── src/
│       ├── assets/styles/  # CSS 디자인 시스템 (global/animations/components)
│       ├── pages/          # 페이지 컴포넌트 (Login/Register/Chat/Documents/Settings)
│       ├── stores/         # Pinia 상태 관리
│       └── locales/        # i18n 다국어
├── database/          # Docker 초기화 스크립트 (postgres/redis/qdrant)
├── docker-compose.yml # 풀스택 오케스트레이션
└── pyproject.toml     # 루트 레벨 개발 도구 설정
```

## 빠른 시작

### 풀스택 실행 (권장)

환경 변수 파일을 생성하고 시작합니다:

```bash
bash scripts/init-env.sh   # 안전한 .env를 자동 생성 (최초 1회)
docker compose up -d
```

서비스 주소: 프론트엔드 http://localhost:3000 · 백엔드 http://localhost:8000

> 캐시 없이 재빌드: `docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

### 로컬 개발

**사전 요구 사항:** Docker (인프라 서비스용), Python 3.13+, [uv](https://github.com/astral-sh/uv), [Bun](https://bun.sh)

```bash
# 인프라 서비스 시작
docker compose up -d postgres redis qdrant minio

# 백엔드
cd backend
uv sync
uv run alembic upgrade head           # 데이터베이스 마이그레이션 실행
uv run uvicorn app.main:app --reload  # 개발 서버 (:8000)

# 프론트엔드 (새 터미널)
cd frontend
bun install
bun run dev                           # 개발 서버 (:5173)
```

## 개발

### 코드 품질

```bash
# 백엔드 (backend/ 디렉토리에서)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# 프론트엔드 (frontend/ 디렉토리에서)
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # git hooks 설치 (루트에서 실행)
pre-commit run --all-files
```

## 환경 변수

`bash scripts/init-env.sh`를 실행하여 랜덤 비밀번호와 키로 안전한 `.env`를 자동 생성합니다.

스크립트가 설정하는 항목: `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `DATABASE_URL`, `REDIS_URL`.

수동으로 입력해야 하는 항목은 `DEEPSEEK_API_KEY`뿐입니다. 자세한 내용은 `.env.example`을 참조하세요.

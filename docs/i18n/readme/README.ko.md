[中文](../../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# JARVIS

RAG 지식 베이스, 다중 LLM 지원, 스트리밍 대화 기능을 갖춘 AI 어시스턴트 플랫폼.

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 프론트엔드 | Vue 3 · TypeScript · Vite · Pinia |
| 데이터베이스 | PostgreSQL · Redis · Qdrant (벡터 DB) |
| 스토리지 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## 프로젝트 구조

```
JARVIS/
├── backend/          # FastAPI 백엔드 (Python 3.13 + uv)
├── frontend/         # Vue 3 프론트엔드 (Bun)
├── docker-compose.yml
└── pyproject.toml    # 루트 레벨 개발 도구 설정
```

## 빠른 시작

### 풀스택 실행 (권장)

환경 변수 파일을 생성하고 시작합니다:

```bash
bash scripts/init-env.sh   # 안전한 .env를 자동 생성 (최초 1회)
docker compose up -d
```

서비스 주소: 프론트엔드 http://localhost:3000 · 백엔드 http://localhost:8000

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
uv run pyright
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

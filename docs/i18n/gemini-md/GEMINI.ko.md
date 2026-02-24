[中文](../../../GEMINI.md) | [English](GEMINI.en.md) | [日本語](GEMINI.ja.md) | [한국어](GEMINI.ko.md) | [Français](GEMINI.fr.md) | [Deutsch](GEMINI.de.md)

# Jarvis 프로젝트 컨텍스트

이 문서는 Gemini에게 `JARVIS` monorepo에 대한 정확한 컨텍스트 정보를 제공합니다.

## 프로젝트 개요

**이름**: Jarvis AI 어시스턴트
**아키텍처**: 멀티 서비스 monorepo (FastAPI 백엔드 + Vue 3 프론트엔드)
**목적**: RAG 지식 베이스, 다중 LLM 지원, 스트리밍 대화를 갖춘 AI 어시스턴트 플랫폼.

## 디렉토리 구조

```
JARVIS/
├── backend/          # FastAPI 백엔드 서비스 (Python 3.13 + SQLAlchemy + LangGraph)
├── frontend/         # Vue 3 프론트엔드 (Vite + TypeScript + Pinia)
├── docker-compose.yml
├── pyproject.toml    # 루트 디렉토리 (개발 도구만, 런타임 의존성 없음)
└── CLAUDE.md / GEMINI.md
```

## 백엔드 아키텍처 (backend/)

- **프레임워크**: FastAPI + Uvicorn
- **데이터베이스**: PostgreSQL (asyncpg 드라이버) + SQLAlchemy async ORM + Alembic 마이그레이션
- **캐시**: Redis
- **벡터 스토어**: Qdrant (RAG 지식 베이스)
- **오브젝트 스토리지**: MinIO (파일 업로드)
- **LLM**: LangGraph + LangChain, DeepSeek / OpenAI / Anthropic 지원
- **인증**: JWT (python-jose) + bcrypt (passlib)

### 주요 모듈

```
backend/app/
├── api/          # FastAPI 라우트 (auth, conversations, documents, settings)
├── agent/        # LangGraph 에이전트 그래프 + LLM 팩토리
├── core/         # 설정 (pydantic-settings), 데이터베이스, 보안 유틸리티
├── models/       # SQLAlchemy ORM 모델
├── rag/          # 문서 파싱, 청킹, Qdrant 인덱싱
└── main.py       # 애플리케이션 진입점 (CORS, 라우트 등록, 헬스 체크)
```

## 프론트엔드 아키텍처 (frontend/)

- **프레임워크**: Vue 3 + TypeScript + Vite
- **상태 관리**: Pinia (auth store, chat store)
- **라우팅**: Vue Router 4 (지연 로딩 + 라우트 가드)
- **UI**: 커스텀 CSS 스타일

## 환경 및 의존성

### 백엔드 (uv 사용)
```bash
cd backend
uv sync                          # 의존성 설치
uv run uvicorn app.main:app --reload  # 개발 서버
uv run pytest tests/ -v          # 테스트 실행
uv run alembic upgrade head      # 데이터베이스 마이그레이션 실행
```

### 프론트엔드 (bun 사용)
```bash
cd frontend
bun install                      # 의존성 설치
bun run dev                      # 개발 서버
bun run build                    # 프로덕션 빌드
bun run lint                     # ESLint 검사
bun run type-check               # TypeScript 타입 검사
```

### Docker 환경
```bash
docker-compose up -d             # 모든 서비스 시작 (PostgreSQL, Redis, Qdrant, MinIO, backend, frontend)
```

## 개발 워크플로우

### 브랜치 전략
- **main**: 안정 버전 (배포 브랜치)
- **dev**: 일상 개발 브랜치 (모든 변경 사항은 여기서 수행)
- 명시적 지시가 있을 때만 `dev`를 `main`에 병합

### 코드 품질 도구

**백엔드**:
- `ruff check --fix && ruff format`: Lint + 포맷팅
- `pyright`: 타입 검사
- `pytest`: 테스트

**프론트엔드**:
- `bun run lint`: ESLint 검사
- `bun run type-check`: TypeScript 타입 검사

**커밋 전 (pre-commit hooks 자동 실행)**:
- YAML/TOML/JSON 포맷 검사
- uv.lock 동기화 검사
- ruff lint + format
- 프론트엔드 ESLint + TypeScript 타입 검사

## 주요 설정

- **DATABASE_URL**: `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL**: `redis://localhost:6379`
- **JWT_SECRET**: 환경 변수로 설정
- **DEEPSEEK_API_KEY**: 환경 변수로 설정
- **Alembic 마이그레이션**: `DATABASE_URL`에서 자동으로 읽어 psycopg2 동기 드라이버로 변환

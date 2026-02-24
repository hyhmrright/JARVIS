[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

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

환경 변수 파일을 복사하고 작성한 후 시작합니다:

```bash
cp .env.example .env   # 각 시크릿을 입력
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

프로젝트 루트에 `.env` 파일을 생성합니다:

```env
# 데이터베이스
POSTGRES_PASSWORD=your_password

# 오브젝트 스토리지
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# 인증
JWT_SECRET=your_jwt_secret

# LLM (기본 프로바이더. 다른 프로바이더의 API Key는 앱 설정 페이지에서 사용자별로 구성)
DEEPSEEK_API_KEY=your_key
```

로컬 개발 시 백엔드는 로컬 서비스 연결을 위해 `backend/.env`도 필요합니다:

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Fernet 암호화 키 (사용자 API Key 암호화에 사용)
# 생성 방법: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```

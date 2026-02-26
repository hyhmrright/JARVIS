[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

> RAG 지식 베이스, 다중 LLM 지원, 실시간 스트리밍 대화 기능을 갖춘 AI 어시스턴트 플랫폼 — 다크 럭셔리(Dark Luxury) 디자인 언어를 채택했습니다.

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## 기능

- **다중 모델 지원** — DeepSeek / OpenAI / Anthropic, 설정에서 사용자별로 전환 가능
- **RAG 지식 베이스** — PDF / TXT / MD / DOCX 업로드, 자동 청킹 및 벡터 인덱싱
- **스트리밍 채팅** — LangGraph ReAct 에이전트를 통한 SSE 토큰 단위 출력
- **다크 럭셔리 UI** — 글라스모피즘 카드, 골드 그라데이션 악센트, 부드러운 애니메이션 전환
- **다국어** — 중국어 / 영어 / 일본어 / 한국어 / 프랑스어 / 독일어 6개 언어 지원
- **프로덕션급 인프라** — 4계층 네트워크 격리, Traefik 엣지 라우터, Prometheus + Grafana 관측성

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 프론트엔드 | Vue 3 · TypeScript · Vite · Pinia |
| 데이터베이스 | PostgreSQL · Redis · Qdrant (벡터 DB) |
| 스토리지 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| 엣지 라우터 | Traefik v3 |
| 관측성 | Prometheus · Grafana · cAdvisor |

## 사전 요구 사항

| 도구 | 버전 | 설치 |
|------|------|------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | 최신 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **로컬 개발 전용**으로 프론트엔드를 위해 추가로 [Bun](https://bun.sh)이 필요합니다.

## 빠른 시작

### 1. 클론 및 환경 생성

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh
```

> 내부적으로 Fernet 암호화 키 생성에 `uv`를 사용합니다. 그 외 별도 설정은 필요하지 않습니다.

### 2. LLM API 키 추가

`.env`를 열어 최소 하나의 키를 입력합니다:

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # 선택 사항
ANTHROPIC_API_KEY=sk-ant-... # 선택 사항
```

### 3. 시작

```bash
docker compose up -d
```

첫 실행 시 Docker 이미지를 빌드합니다 — 몇 분 정도 소요됩니다. 정상 가동 후:

| 서비스 | URL | 제공 여부 |
|--------|-----|-----------|
| **앱** | http://localhost | 항상 |
| Grafana (모니터링) | http://localhost:3001 | 항상 |
| Traefik 대시보드 | http://localhost:8080/dashboard/ | 개발 전용 |
| 백엔드 API (직접) | http://localhost:8000 | 개발 전용 |

> 기본 `docker compose up -d` 명령은 `docker-compose.override.yml`을 자동 병합하여 디버그 포트를 노출하고 백엔드 코드의 핫 리로드를 활성화합니다. 프로덕션 사용법은 아래를 참조하세요.

### 문제 해결

**서비스 시작 실패** — 로그 확인:
```bash
docker compose logs backend
docker compose logs traefik
```

**처음부터 재빌드** (Dockerfile 또는 의존성 변경 후):
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**`:80` 포트 충돌** — 포트 80을 사용 중인 프로세스를 중지한 후 다시 시도합니다.

---

## Docker Compose 파일

이 프로젝트는 두 개의 compose 파일을 함께 사용합니다:

| 파일 | 목적 |
|------|------|
| `docker-compose.yml` | **기본 (프로덕션)** — 최소 노출: `:80`과 `:3001`만 공개 |
| `docker-compose.override.yml` | **개발 오버라이드** — Docker Compose가 자동 병합; 디버그 포트, 핫 리로드 추가 |

`docker compose up -d` 실행 시 Docker Compose가 오버라이드 파일을 자동으로 병합하므로 **로컬 개발에는 별도 플래그가 필요하지 않습니다**. 프로덕션에서는 명시적으로 제외합니다:

```bash
# 개발 (기본값) — 두 파일을 자동으로 병합
docker compose up -d

# 프로덕션 — 기본 파일만, 디버그 포트 없음, 핫 리로드 없음
docker compose -f docker-compose.yml up -d
```

## 프로덕션 배포

```bash
docker compose -f docker-compose.yml up -d
```

공개 포트: `:80` (앱)과 `:3001` (Grafana)만 노출됩니다.

---

## 로컬 개발

더 빠른 반복 개발을 위해 백엔드와 프론트엔드를 네이티브로 실행합니다.

**1단계 — 인프라 시작:**

```bash
docker compose up -d postgres redis qdrant minio
```

**2단계 — 백엔드** (새 터미널, 저장소 루트에서):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**3단계 — 프론트엔드** (새 터미널, 저장소 루트에서):

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173  (/api → localhost:8000 프록시)
```

---

## 프로젝트 구조

```
JARVIS/
├── backend/                    # FastAPI (Python 3.13 + uv)
│   ├── app/
│   │   ├── agent/              # LangGraph ReAct 에이전트
│   │   ├── api/                # HTTP 라우트 (auth/chat/conversations/documents/settings)
│   │   ├── core/               # Config, JWT/bcrypt/Fernet 보안, 속도 제한
│   │   ├── db/                 # SQLAlchemy 비동기 모델 + 세션
│   │   ├── infra/              # Qdrant / MinIO / Redis 싱글톤
│   │   ├── rag/                # 문서 청커 + 임베더 + 인덱서
│   │   └── tools/              # LangGraph 도구 (search/code_exec/file/datetime)
│   ├── alembic/                # 데이터베이스 마이그레이션
│   └── tests/                  # pytest 스위트
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Axios 싱글톤 + 인증 인터셉터
│       ├── stores/             # Pinia 스토어 (auth + chat)
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n (zh/en/ja/ko/fr/de)
├── database/                   # Docker 초기화 스크립트 (postgres/redis/qdrant)
├── monitoring/                 # Prometheus 설정 + Grafana 프로비저닝
├── traefik/                    # Traefik 동적 라우팅 설정
├── scripts/
│   └── init-env.sh             # 안전한 .env 생성 (uv 필요)
├── docker-compose.yml          # 기본 오케스트레이션
├── docker-compose.override.yml # 개발 오버라이드 (디버그 포트 + 핫 리로드)
└── .env.example                # 환경 변수 참조
```

---

## 개발

### 코드 품질

```bash
# 백엔드 (backend/에서 실행)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# 프론트엔드 (frontend/에서 실행)
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# 저장소 루트에서 실행
pre-commit install
pre-commit run --all-files
```

Hooks: YAML/TOML/JSON 유효성 검사 · uv.lock 동기화 · Ruff lint+format · ESLint · mypy · vue-tsc · gitleaks 시크릿 스캔 · `main`에 직접 커밋 차단.

---

## 환경 변수

`bash scripts/init-env.sh`가 모든 자격 증명을 자동 생성합니다. LLM API 키만 직접 입력하면 됩니다.

| 변수 | 설명 |
|------|------|
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 |
| `MINIO_ROOT_USER/PASSWORD` | MinIO 오브젝트 스토리지 자격 증명 |
| `REDIS_PASSWORD` | Redis 인증 비밀번호 |
| `JWT_SECRET` | JWT 서명 시크릿 |
| `ENCRYPTION_KEY` | 저장 시 사용자 API 키 암호화를 위한 Fernet 키 |
| `GRAFANA_PASSWORD` | Grafana 관리자 비밀번호 |
| `DEEPSEEK_API_KEY` | **수동으로 입력** |
| `OPENAI_API_KEY` | 선택 사항 |
| `ANTHROPIC_API_KEY` | 선택 사항 |

전체 참조는 `.env.example`을 확인하세요.

---

## 기여

[CONTRIBUTING.md](../../../.github/CONTRIBUTING.md)를 참조하세요.

## 라이선스

[MIT](../../../LICENSE)

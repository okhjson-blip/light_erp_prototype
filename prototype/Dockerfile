# Standard ERP Prototype — v8: React 프론트엔드 빌드를 포함하는 2-스테이지 이미지
# psycopg2-binary를 쓰므로 libpq-dev 등 빌드 의존성 설치가 필요 없다.

# ---- Stage 1: React 프론트엔드 빌드 ----
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# package-lock.json은 의도적으로 복사하지 않는다 — 호스트(Mac)에서 생성된 lockfile은 rolldown/vite의
# 플랫폼별 네이티브 바이너리를 특정 OS로 고정해버려("npm has a bug related to optional dependencies",
# npm/cli#4828 — 이 프로젝트에서 실제로 두 번 겪은 문제), 이 리눅스 빌드 환경에서 설치가 깨진다.
# package.json만으로 npm install을 새로 돌리면 이 컨테이너(리눅스) 기준으로 올바른 바이너리를 받는다.
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: 백엔드 + 정적 프론트 서빙 ----
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY prototype_dataset ./prototype_dataset
COPY alembic.ini .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
# app/main.py가 frontend/dist/index.html 존재 여부를 기동 시 자동 판단해 "/"에서 서빙한다
# (코드 변경 불필요 — v7 마무리 단계에서 이미 이 로직을 넣어둠).

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

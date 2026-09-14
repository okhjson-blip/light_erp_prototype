#!/bin/bash
cd "$(dirname "$0")"
echo "=== Standard ERP: PostgreSQL 로컬 검증 (docker-compose) ==="
echo "(현재 브라우저로 보고 있는 SQLite 서버는 계속 그대로 동작하며 영향받지 않습니다)"
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "오류: docker 명령을 찾을 수 없습니다. PATH를 확인하세요."
  read -p "엔터를 눌러 창을 닫으세요..." _
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "오류: docker 데몬에 연결할 수 없습니다."
  echo "Docker Desktop을 사용 중이면 앱을 실행하세요. Colima 등 CLI 전용 백엔드를 쓰는 경우"
  echo "'colima start' 등으로 데몬을 먼저 띄운 뒤 다시 시도하세요."
  read -p "엔터를 눌러 창을 닫으세요..." _
  exit 1
fi

echo "[1/4] docker compose로 로컬 PostgreSQL 기동 중..."
echo "  (기존 볼륨에 erp 계정이 없는 상태로 초기화된 경우가 있어, 매번 볼륨을 초기화하고 새로 띄웁니다)"
if docker compose version >/dev/null 2>&1; then
  docker compose down -v >/dev/null 2>&1
  docker compose up -d
else
  docker-compose down -v >/dev/null 2>&1
  docker-compose up -d
fi
echo "  (최초 실행 시 postgres:16 이미지 다운로드로 시간이 걸릴 수 있습니다)"

echo "[2/4] PostgreSQL 준비 대기 중... (erp 계정/standard_erp DB로 실제 접속 확인)"
READY=0
for i in $(seq 1 30); do
  if docker compose exec -T postgres psql -U erp -d standard_erp -c "SELECT 1" >/dev/null 2>&1 \
     || docker-compose exec -T postgres psql -U erp -d standard_erp -c "SELECT 1" >/dev/null 2>&1; then
    echo "  기동 확인됨"
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" != "1" ]; then
  echo "오류: 30초 내에 erp 계정으로 접속하지 못했습니다. 'docker compose logs postgres'로 로그를 확인하세요."
  read -p "엔터를 눌러 창을 닫으세요..." _
  exit 1
fi

echo "[3/4] Python 가상환경 준비..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "[4/4] 검증 스크립트 실행... (호스트 포트 5433 사용 — 기존 로컬 Postgres(5432)와 충돌 회피)"
export DATABASE_URL=postgresql+psycopg2://erp:erp_local_dev@127.0.0.1:5433/standard_erp
python3 verify_postgres.py

echo ""
read -p "결과를 확인했으면 엔터를 눌러 창을 닫으세요..." _

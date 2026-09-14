#!/bin/bash
# Standard ERP Prototype — 로컬 서버 구동 스크립트
# 반복 실행 가능: 이미 서버가 떠 있으면 재사용, 아니면 환경 구축 후 새로 기동.
# 매번 프론트엔드를 빌드해 최신 코드 변경사항을 반영한다(FastAPI가 frontend/dist를 서빙).
set -e
cd "$(dirname "$0")"

URL="http://127.0.0.1:8000"

echo "=== Standard ERP Prototype — 로컬 서버 구동 ==="
echo ""

# 0. 이미 떠 있는 서버가 있으면 재사용 (중복 기동으로 인한 포트 충돌 방지)
if curl -s -o /dev/null -m 1 "$URL/health"; then
  echo "이미 실행 중인 서버가 감지되었습니다 — 새로 기동하지 않고 재사용합니다."
  echo ""
  echo "================================================"
  echo " 로컬 서버 주소: $URL"
  echo "================================================"
  open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
  exit 0
fi

# 1. 백엔드 환경
if [ ! -d ".venv" ]; then
  echo "[1/4] 백엔드 가상환경 생성 중..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "[1/4] 백엔드 의존성 설치 확인 중..."
pip install -q -r requirements.txt

# 2. 프론트엔드 빌드 (현재 코드 상태를 화면에 반영하기 위해 매번 새로 빌드)
if [ ! -d "frontend/node_modules" ]; then
  echo "[2/4] 프론트엔드 의존성 설치 중 (최초 1회, 몇 분 걸릴 수 있음)..."
  (cd frontend && npm install)
fi
echo "[2/4] 프론트엔드 빌드 중 (최신 변경사항 반영)..."
if ! (cd frontend && npm run build); then
  echo ""
  echo "⚠ 프론트엔드 빌드 실패 — node_modules/package-lock.json을 삭제 후 다시 실행해보세요"
  echo "  (리눅스/Mac 간 네이티브 바이너리 불일치 문제일 수 있습니다)."
  exit 1
fi

# 3. 서버 기동 (백그라운드) + 종료 시 정리
echo "[3/4] 서버 기동 중..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
trap 'echo ""; echo "서버 종료 중..."; kill $SERVER_PID 2>/dev/null; exit 0' INT TERM

echo "서버 준비 대기 중..."
for i in $(seq 1 40); do
  if curl -s -o /dev/null -m 1 "$URL/health"; then
    break
  fi
  sleep 0.5
done

echo ""
echo "================================================"
echo " 로컬 서버 주소: $URL"
echo " 데모 계정(비밀번호 공통 demo1234):"
echo "   admin@standard-erp.local      (관리자)"
echo "   sales@standard-erp.local      (영업담당)"
echo "   purchase@standard-erp.local   (구매담당)"
echo "   production@standard-erp.local (생산담당)"
echo " 종료하려면 이 창에서 Ctrl+C 를 누르세요."
echo "================================================"
echo ""

# 4. 크롬으로 열기
echo "[4/4] Chrome으로 여는 중..."
open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"

wait $SERVER_PID

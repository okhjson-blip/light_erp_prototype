#!/bin/bash
cd "$(dirname "$0")/frontend"
echo "=== Standard ERP React 프론트엔드 개발 서버 시작 ==="
echo ""

if [ ! -d "node_modules" ]; then
  echo "의존성 설치 중 (최초 1회, 몇 분 걸릴 수 있습니다)..."
  npm install
fi

if ! curl -s -o /dev/null -m 2 http://127.0.0.1:8000/health; then
  echo "⚠ 경고: 백엔드(http://127.0.0.1:8000)가 응답하지 않습니다."
  echo "  다른 터미널(또는 창)에서 run_server.command를 먼저 실행해 백엔드를 띄우세요."
  echo "  (로그인/데이터 조회는 프론트 개발서버가 :8000으로 프록시하므로 백엔드가 꼭 떠 있어야 합니다.)"
  echo ""
fi

echo "개발 서버를 시작합니다. 브라우저에서 http://localhost:5183 접속하세요."
echo "종료하려면 이 창에서 Ctrl+C 를 누르세요."
echo ""
echo "※ 'Cannot find native binding' 오류가 나면 node_modules/package-lock.json을 삭제 후"
echo "   npm install을 다시 실행하세요 (플랫폼별 네이티브 바이너리 불일치 문제)."
echo ""
npm run dev

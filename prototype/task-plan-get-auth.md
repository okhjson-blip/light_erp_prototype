# Task Plan — GET 엔드포인트 인증 확장

## 배경
RBAC 구현 시 GET(조회) 엔드포인트는 명시적 비범위였다(내부망 전제). v4로 넘어가며 이를 확장한다.

## 설계 결정 (사용자 확인)
- **로그인만 하면 역할 무관하게 전체 조회 가능.** POST처럼 엔드포인트별 세부 역할 제한은 하지 않는다
  (예: 회계 데이터를 영업담당도 조회 가능) — 구현 단순성 우선, 필요시 v5에서 세분화.
- 예외: `/`(index.html), `/static/*`(정적 리소스), `POST /api/auth/login`은 로그인 전 접근이 필요해
  그대로 비인증 유지.
- 적용 대상: main.py 19개, ai_agent.py 5개, reference_data.py 6개, lot_tracking.py 5개,
  integrations.py 1개(`GET /events`) — 총 36개(`/api/auth/me` 포함, 기존에 이미 인증 적용됨) GET
  엔드포인트에 `Depends(current_user)` 추가.
- MES/WMS 웹훅(`POST` 2개)의 API Key 인증과는 별개 — 그대로 유지.

## 비범위
- 세부 역할별 GET 제한(회계/재무 데이터를 관리자만 등)
- MES/WMS 웹훅 인증 방식 변경 없음

## 성공 기준
1. 토큰 없이 GET 호출 시 401 (모든 API GET 엔드포인트)
2. 로그인한 사용자는 역할 무관하게 모든 GET 통과
3. `/`, `/static/*`는 계속 비인증 접근 가능(로그인 화면 자체를 봐야 하므로)
4. 기존 POST 역할 게이팅에는 영향 없음(회귀 없음)

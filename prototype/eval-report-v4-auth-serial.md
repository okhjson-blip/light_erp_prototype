# Evaluation Report — GET 인증 확장 + JWT 전환 + 시리얼 UI 고도화 (v4)

```json
{
  "pass": true,
  "score": 93,
  "independence_check": {
    "existing_files_modified": [
      "app/auth.py", "app/main.py", "app/ai_agent.py", "app/reference_data.py",
      "app/integrations.py", "app/lot_tracking.py", "static/index.html",
      "simulate_mes_wms.py", "README.md"
    ],
    "new_files": ["task-plan-get-auth.md", "task-plan-jwt.md", "task-plan-serial-ui.md"],
    "db_schema_changed": false
  },
  "failures": [],
  "harness_update_needed": false
}
```

세 항목 각각의 task-plan에 명시한 범위 그대로 구현. 스키마 변경 없음(세션/시리얼 테이블 구조는
그대로, 토큰 문자열 포맷과 애플리케이션 로직만 변경) — 사용자 라이브 DB 추가 조치 불필요.

## 1) GET 엔드포인트 인증 확장
- 토큰 없이 GET 호출 시 401 (`/api/materials`, `/api/lots`, `/api/ai/buyer/recommendations`,
  `/api/reference/quality-inspections`, `/api/integrations/events` 등 대표 엔드포인트로 확인) — **PASS**
- 로그인만 하면 역할 무관 전체 조회 가능(영업담당이 회계 문서 조회 성공) — **PASS**
- `/`(index.html)는 계속 비인증 접근 가능 — **PASS**
- 기존 POST 역할 게이팅 회귀 없음(403/401 동일하게 동작) — **PASS**
- 부수 조치: `simulate_mes_wms.py`의 GET 호출(materials/plants/warehouses/events)에도
  로그인 토큰을 싣도록 수정(그렇지 않으면 이제 401로 실패함)

## 2) JWT 토큰 포맷 전환
- 발급 토큰이 `header.payload.signature` 3파트 구조, 헤더 `alg:HS256`/`typ:JWT`,
  payload에 `sub`/`iat`/`exp` 포함 — **PASS**
- 서명이 위조된 토큰 → DB 조회 전에 401 즉시 차단 — **PASS**
- payload를 조작한 토큰(예: 다른 사용자로 위장 시도) → 서명 불일치로 401 — **PASS**
- 정상 토큰은 기존과 동일하게 로그인/조회/로그아웃 정상 동작 — **PASS**

## 3) 시리얼 UI 고도화
- 출하 시 소진 수량만큼 시리얼이 자동 SHIPPED, 나머지는 IN_STOCK 유지 — **PASS**
  (8개 생성 → 3개 출하 → 정확히 3개만 SHIPPED 확인)
- 생산담당/관리자가 DEFECTIVE/SCRAPPED로 수동 변경 가능 — **PASS**
- 권한 없는 역할(영업담당) 상태변경 시도 → 403 — **PASS**
- 허용되지 않은 status 값 → 400 — **PASS**
- 재고 탭에 상태변경 드롭다운+버튼 노출(생산담당/관리자만) — **PASS** (index.html에
  `sn-status-pick`/`changeSerialStatus` 포함 확인)

## 통합 검증
26개 항목을 포함한 최종 통합 테스트(로그인 4계정, GET/POST 인증, JWT 무결성, 구매→입고→LOT,
생산→FG LOT+시리얼8건→RM소진, 출하→FG LOT소진+시리얼3건 자동SHIPPED, 시리얼 수동변경+권한,
QMS등록, LOT정합성, MES API Key, AI Agent narrative, 프론트엔드 신규 요소)를 `/tmp` 임시
복사본에서 TestClient로 실행 — **전부 PASS**. `node --check`로 JS 문법 검증.

## 설계상 의도적 비범위 (각 task-plan에 사전 명시)
- GET 인증: 세부 역할별 조회 제한 없음(로그인만 하면 전체 조회)
- JWT: 완전 무상태 전환 아님(세션 테이블 유지, 로그아웃 즉시무효화 유지가 우선)
- 시리얼: 상태변경 감사 로그 미연결, 특정 배송건과의 연결 없음

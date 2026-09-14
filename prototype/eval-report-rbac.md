# Evaluation Report — RBAC (역할 기반 접근 제어)

```json
{
  "pass": true,
  "score": 92,
  "independence_check": {
    "existing_files_modified": ["app/main.py", "app/ai_agent.py", "app/seed.py", "app/schema_sqlite.sql", "app/schema_postgres.sql", "static/index.html"],
    "new_files": ["app/auth.py"],
    "db_schema_changed": true
  },
  "failures": [],
  "harness_update_needed": false
}
```

task-plan-rbac.md에 명시한 범위(세션 테이블 기반 인증, POST 엔드포인트만 역할 게이팅, GET은 비범위) 그대로
구현됨. 신규 의존성 없음(표준 라이브러리 hashlib만 사용).

## 성공 기준 대비 결과
1. 비밀번호 없이/틀리게 로그인 시 실패, 올바른 비밀번호로 로그인 시 토큰 발급 — **PASS**
   (TestClient: 필드 누락 400, 오답 401, 정답 200+토큰 확인)
2. 토큰 없이 보호된 POST 호출 시 401 — **PASS**
3. 토큰은 있으나 역할이 맞지 않는 POST 호출 시 403 — **PASS**
   (영업담당이 구매/생산/승인 엔드포인트 호출 시 전부 403 확인, 관리자는 전부 허용됨을 확인)
4. 올바른 역할로 호출 시 정상 동작, 기존 E2E 플로우 회귀 없음 — **PASS**
   (영업: SO→출하→청구, 구매: PR→PO→입고, 생산: 생산오더→작업지시→실적입력 전부 해당 역할 토큰으로 재검증)
5. 프론트엔드 로그인 화면 → 역할별 메뉴/버튼 노출, 로그아웃 동작 — **PASS**
6. 브라우저 라이브 테스트로 2개 역할(관리자/영업담당) 로그인 후 동작 차이 확인 — **PASS**
   (관리자: 구매 탭에 PR/PO 폼+입고처리 버튼 노출. 영업담당: 동일 탭에서 폼/버튼 전부 숨김,
   영업 탭에서는 폼+출하/청구 버튼 정상 노출)

## 발견 및 수정한 버그
- **네비게이션 중복 렌더링**: `initNav()`가 매 로그인마다 버튼을 append만 하고 초기화하지 않아,
  로그아웃 후 재로그인 시 nav 탭이 중복 렌더링됨. `nav.innerHTML = ""`을 추가해 수정, 브라우저에서
  재현 후 수정 확인.
- **`/api/users` 응답에 password_hash 노출**: `SELECT *`였던 걸 특정 컬럼만 선택하도록 수정
  (비밀번호 해시가 프론트엔드로 전달되지 않도록 사전에 방지).

## 설계상 의도적 비범위 (task-plan에 사전 명시)
- GET 엔드포인트는 인증을 강제하지 않음(내부망 전제) — 필요시 v4에서 확장
- JWT/OAuth2, 비밀번호 재설정 등 실운영 기능은 다루지 않음(README에 이 결정과 트레이드오프 명시)
- MES/WMS 웹훅 인증(API Key)은 기존과 동일하게 별도 v4 항목 유지

## 검증 방법 및 안전조치
- TestClient 검증은 `/tmp` 임시 복사본에서 진행해 사용자의 실제 라이브 DB(erp.db)를 건드리지 않음.
- 스키마 변경(app_user.password_hash, session 테이블 신규)으로 인해 기존 erp.db를 삭제하고
  재시드 트리거 — 이 과정에서 사용자의 uvicorn 프로세스가 재시작되며 일시적으로 다운되는 상황이
  있었으나(터미널 창 종료가 원인으로 추정), 사용자가 `run_server.command`로 재기동 후 정상 확인.
- 데모 계정 비밀번호(`demo1234`)는 전부 동일한 고정값 — 실제 운영 환경에서는 반드시 개별 비밀번호로
  교체해야 함을 README에 명시.

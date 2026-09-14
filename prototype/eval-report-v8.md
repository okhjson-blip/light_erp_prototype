# Eval Report — v8: 프로덕션 배포 마무리 + 보안/운영 절충점 채우기

사용자 지시: "2순위 — 프로덕션 배포 마무리 (React 이관의 남은 절반), 3순위 — 남겨둔 보안/운영
절충점 채우기 (v5~v6에서 의도적으로 미룬 것들) 진행해". README "다음 단계(v8 후보)" 2·3순위 전체.

## 구현

### 2순위: Docker 이미지에 프론트엔드 빌드 포함
- `Dockerfile`을 2-스테이지로 재작성: Stage 1(`node:20-slim`)이 `frontend/`를 빌드, Stage 2
  (`python:3.11-slim`)가 `--from=frontend-builder /app/frontend/dist ./frontend/dist`로 결과물만
  복사. `app/main.py`의 `/` 라우트(v7 마무리 단계에서 이미 "frontend/dist 있으면 서빙" 로직을
  넣어둠)는 코드 변경 없이 그대로 동작.
- Stage 1은 `package-lock.json`을 의도적으로 복사하지 않고 `package.json`만으로 `npm install`을
  새로 실행 — 이 세션에서 두 번 겪은 "Cannot find native binding"(rolldown/vite 플랫폼별 네이티브
  바이너리가 lockfile에 고정되는 문제, npm/cli#4828)을 컨테이너 빌드에서 원천 차단.
- `.dockerignore`에 `frontend/node_modules`, `frontend/dist` 추가.
- **미검증**: 이 샌드박스에 Docker 데몬이 없어 `docker build`/`docker compose up --build` 실행은
  못 함(v5 컨테이너화 때와 동일한 제약). 사용자 로컬에서 최종 확인 필요.

### 3순위(a): 시리얼 상태변경/refresh 재사용 탐지 → audit_log 연결
- `app/helpers.py`에 `write_audit_log(conn, user_id, action, entity, entity_id)` 추가 — v1부터
  스키마에 있었지만 아무 코드도 쓰지 않던 `audit_log` 테이블을 처음 사용. 별도 detail 컬럼이 없어
  상태 전이는 `action` 문자열에 `"STATUS_CHANGE:IN_STOCK->DEFECTIVE"`처럼 인코딩(신규 마이그레이션
  불필요).
- `app/lot_tracking.py`의 `update_serial_status()`가 상태 변경 시 감사 로그를 남김.
- `app/main.py`의 `/api/auth/refresh`가 `RefreshTokenReuseDetected` 발생 시
  `REFRESH_TOKEN_REUSE_DETECTED` 감사 로그를 남김(기존 `logger.warning` 로그와 별개로 DB에도 남김).
- 신규 `GET /api/audit-log`(관리자 전용, 최근 200건) — 회계/CFO Copilot과 동일한 관리자 전용 정책.

### 3순위(b): LOT 정합성 자동 알림 → 대시보드 KPI 반영
- 기존 `GET /lots/reconciliation`(온디맨드 상세 조회)의 판정 로직을 그대로 재사용하되, 행 전체가
  아니라 개수만 필요한 대시보드용으로 `app/lot_tracking.py`에 `count_lot_inconsistencies(conn)`
  집계 함수를 분리(중복 SQL 최소화, 공유 상수 `RECONCILIATION_EPSILON`).
- `GET /api/dashboard/kpi` 응답에 `lot_inconsistent_count` 추가.
- `DashboardPage.tsx`에 3번째 KPI 카드로 노출, 0건이면 `success`(녹색) / 1건 이상이면 `danger`
  (빨강) 톤 — 기존 `pending_approvals`의 warning 톤 패턴과 동일한 관례.
- 새 백그라운드 스케줄러/의존성 없이 이미 폴링되는 대시보드 KPI에 편승 — "신규 의존성 최소화"
  원칙(v2부터 일관) 유지.

### 3순위(c): 디바이스별 다중 세션 조회/개별 로그아웃
- `migrations/versions/0003_session_device_info.py`: `session` 테이블에 `user_agent`,
  `last_seen_at` 컬럼 추가(0002와 동일하게 `schema_*.sql`은 건드리지 않음). 기존 세션 행은
  `last_seen_at ← created_at`으로 백필.
- `app/auth.py`: `create_refresh_token()`/`issue_tokens()`/`rotate_tokens()`가 `user_agent`를
  받아 세션 행에 기록(회전 시에는 원래 세션의 user_agent를 그대로 유지 — 같은 기기이므로).
- `app/main.py`: 로그인 시 `User-Agent` 헤더를 캡처. 신규 `GET /api/auth/sessions`(본인의 현재
  유효한 세션만 — `rotated_at IS NULL`로 필터해 회전으로 이미 폐기된 옛 행은 제외), 신규
  `POST /api/auth/sessions/{family_id}/logout`(소유권 검증 — `family_id`의 `user_id`가 요청자와
  다르면 404. 검증 없이 지우면 family_id를 추측해 남의 세션을 강제 로그아웃시킬 수 있음).
- 프론트: `frontend/src/components/ui/dialog.tsx`(Radix `@radix-ui/react-dialog` 최소 래퍼,
  기존에 설치만 되어 있고 미사용이던 의존성을 처음 사용) + `SessionsDialog.tsx`(topbar의 모니터
  아이콘 버튼 → 세션 목록 + 기기별 로그아웃 버튼). `AppShell.tsx` topbar에 삽입.

## 검증

**pytest 전체**(fresh `/tmp` 복사본, SQLite): 기존 55개 + 신규 7개(`tests/test_v8_sessions_audit.py`
— 감사 로그 2건, 관리자 전용 제한 1건, KPI 필드 1건, 세션 조회/로그아웃/소유권 검증 3건) = **62개
전부 PASS**.

**API 계약 확인**(TestClient, `with TestClient(app) as c:`로 startup 마이그레이션 실행):
```
login 200
kpi 200 {'open_so': 31, 'open_po': 55, 'pending_approvals': 0, 'material_count': 15,
         'total_ar': 0, 'total_ap': 0, 'lot_inconsistent_count': 0}
audit-log 200 (관리자 전용 확인)
sessions 200 [{'family_id': ..., 'user_agent': 'OtherDevice/2.0', ...}, {..'TestBrowser/1.0'..}]
본인 세션 로그아웃 → 200, 이후 그 refresh_token 재발급 시도 → 401(정상 차단)
타인 세션 로그아웃 시도(다른 user_id) → 404(소유권 검증 통과), 피해자 refresh_token은 여전히 유효
```

**TypeScript 타입체크**: `npx tsc -b` — 에러 없음(신규 `dialog.tsx`, `SessionsDialog.tsx`,
`DashboardPage.tsx`/`AppShell.tsx` 변경분 포함).

**미실행**:
- `docker build`/`docker compose up --build` — 샌드박스에 Docker 없음. 사용자 로컬 확인 필요.
- `vite build`/브라우저 실기동(세션 관리 Dialog UI, 대시보드 새 KPI 카드) — 1~5차와 동일한 패턴으로
  이 세션에서 미실행. 사용자 로컬 확인 권장.
- PostgreSQL에 대한 0003 마이그레이션 실행 — 0002와 동일한 단순 `ALTER TABLE ADD COLUMN` 패턴이라
  호환성 문제는 낮게 평가하나, 실제 PG 인스턴스로 검증하지는 않음.

## 비범위(의도적으로 남김)
- AI Agent LLM 실 API 연계, GET 세부 역할 제한 확대, nginx/K8s/부하테스트 — README "다음 단계"의
  4순위, 이번 지시 범위 밖.
- audit_log 조회 UI(프론트) — 이번엔 백엔드 `GET /api/audit-log`만 추가. 관리자 전용 조회 API는
  마련됐으니 프론트 화면(예: 참고 데이터 탭 추가)은 후속 작업으로 남김.

## 종합 평가

| 항목 | 평가 |
|---|---|
| Docker 멀티스테이지(프론트 포함) | ✅ 작성 완료, ⚠️ 사용자 로컬 `docker compose up --build` 확인 필요 |
| audit_log 연결(시리얼/refresh 재사용) | ✅ 구현+테스트 PASS |
| LOT 정합성 대시보드 KPI 반영 | ✅ 구현+테스트 PASS+타입체크 PASS |
| 디바이스별 세션 조회/개별 로그아웃 | ✅ 구현+테스트 PASS(소유권 검증 포함)+타입체크 PASS |
| 회귀(기존 55개 테스트) | ✅ 전부 PASS |
| 브라우저 실기동 확인 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 90/100** (감점 사유: Docker 실빌드 미검증 + 신규 UI 브라우저 실기동 미확인 — 이 세션의
구조적 제약으로 1~5차와 동일한 패턴)

# Task Plan — Refresh Token 회전(Rotation) + 재사용 탐지 (v6)

v5에서 완전 무상태 JWT(Access+Refresh)로 전환하며 의도적으로 미뤄둔 절충: refresh token이 회전하지
않아, 토큰이 탈취되면 만료(8시간)까지 계속 재사용 가능했다. 이번에 그 구멍을 메운다.

## 설계

**회전(Rotation)**: `POST /api/auth/refresh` 호출마다 새 refresh token을 발급하고 기존 토큰은
즉시 폐기한다. 한 번 쓴 refresh token은 다시 쓸 수 없다 — 표준 OAuth2 refresh rotation 패턴.

**재사용 탐지(Reuse Detection)**: 정상 클라이언트는 항상 "가장 최근에 발급받은" refresh token만
보관하고 쓴다. 따라서 이미 폐기된(rotated) 토큰이 다시 서버에 제시된다는 것은 둘 중 하나다 — ①
공격자가 과거에 탈취한 토큰을 사용 중이거나 ② 클라이언트 버그로 이전 토큰이 남아있는 경우. 두
경우 모두 안전하게 처리하려면: 탐지 즉시 해당 로그인에서 파생된 **모든** refresh token(=한 "family")을
무효화해 강제 재로그인시킨다.

**Family 개념**: 로그인 1회가 하나의 family를 만든다(`family_id`, 랜덤). 회전으로 새로 발급되는
토큰도 같은 family_id를 유지해 계보를 추적한다. `session` 테이블에 컬럼 2개 추가:
- `family_id TEXT NOT NULL` — 같은 로그인에서 파생된 토큰들을 묶는 식별자.
- `rotated_at TEXT` (nullable) — 이 토큰이 회전으로 교체된 시각. NULL = 아직 유효한(최신) 토큰.

재사용 탐지 시: `rotated_at IS NOT NULL`인 토큰이 다시 제시되면 `family_id`가 같은 모든 행을
즉시 삭제(전체 무효화) + `logging`으로 경고 기록(신규 의존성 없음, 기존 `audit_log` 테이블은 이번
범위에서 건드리지 않음 — 앱 전체 감사로그 연결은 별도 과제로 이미 다음 단계 후보에 있음).

**만료 정책**: family의 `expires_at`은 로그인 시점 기준 8시간 고정(회전해도 연장되지 않음) — 계속
refresh만 반복해 세션을 무한 연장하는 것을 막는 절대 상한.

**로그아웃**: 기존에는 토큰 1개만 삭제했지만, 이제 해당 토큰이 속한 family 전체를 삭제한다 —
로그아웃은 그 로그인에서 파생된 모든 refresh token을 무효화하는 게 자연스러운 의미.

## 스키마 변경

`migrations/versions/0002_session_rotation.py` 신규(Alembic). **`schema_sqlite.sql`/
`schema_postgres.sql`은 수정하지 않는다** — `0001_initial_schema.py`가 이 파일들을 마이그레이션
실행 시점에 동적으로 읽으므로, 여기서 수정하면 신규 설치 시 0001이 이미 새 컬럼을 만들어버려
0002의 `ADD COLUMN`이 중복 오류를 낸다(v4 이후 확립된 규칙: 스키마 변경은 전부 번호 붙은 마이그레이션
파일에만 남긴다). 기존 행은 `family_id`를 자기 `token` 값으로 백필해 서로 다른 family로 분리한다
(전부 빈 문자열로 두면 모든 레거시 세션이 하나의 family로 묶여, 한 세션의 재사용 탐지가 무관한 다른
사용자 세션까지 전부 무효화하는 사고가 날 수 있다).

## 비범위
- Refresh token을 여러 디바이스에서 동시에 발급받는 경우의 family 병합/분리 UI(현재도 로그인마다
  독립 family라 디바이스별 영향은 없음, 그대로 유지)
- `audit_log` 테이블 연동(별도 과제)
- Access token 자체의 조기 무효화(여전히 30분 자연 만료까지 유효 — v5의 트레이드오프 유지)

## 검증 계획
- 정상 회전: refresh 호출 시 새 refresh_token 발급, 이전 토큰으로 다시 refresh 시도 시 거부.
- 재사용 탐지: 이전(폐기된) 토큰으로 refresh 시도 시 401 + family 전체 무효화 확인(최신 토큰도 이후
  refresh 불가).
- 로그아웃이 family 전체를 지우는지 확인.
- 레거시 세션 마이그레이션(0002 적용 전 발급된 토큰이 family_id로 개별 격리되는지) 확인.

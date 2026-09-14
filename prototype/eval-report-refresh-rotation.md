# Eval Report — Refresh Token 회전 + 재사용 탐지 (v6)

설계문서: `task-plan-refresh-rotation.md`. 사용자 지시: v6 후보 표에서 "Refresh token 회전(rotation)
+ 탈취 탐지" 항목을 지목해 진행.

## 구현

- `app/auth.py`: `create_refresh_token()`에 `family_id`/`expires_at` 선택 인자 추가(회전 시 같은
  family_id·고정 만료시각 유지, 신규 로그인 시 새 family). `rotate_tokens()` 신규 — refresh 검증 후
  새 access+refresh 토큰을 발급하고 기존 토큰에 `rotated_at`을 기록. 이미 `rotated_at`이 찍힌 토큰이
  다시 제시되면 `RefreshTokenReuseDetected` 예외를 발생시키고 해당 `family_id`의 모든 세션을 삭제.
  `delete_refresh_token()`(로그아웃)도 단일 토큰이 아닌 family 전체를 삭제하도록 변경.
- `migrations/versions/0002_session_rotation.py`: `session` 테이블에 `family_id`/`rotated_at`
  컬럼 추가(raw SQL, `schema_sqlite.sql`/`schema_postgres.sql`은 의도적으로 수정하지 않음 — 0001이
  이 파일들을 실행 시점에 동적으로 읽으므로, 수정하면 신규 설치 시 컬럼 중복 생성 오류가 난다).
  기존 세션은 자기 `token` 값으로 `family_id`를 백필해 개별 격리(전부 빈 문자열로 두면 서로 다른
  사용자의 세션이 하나의 family로 묶여, 한 세션의 재사용 탐지가 무관한 세션까지 무효화하는 사고가
  날 수 있어 이를 피함).
- `app/main.py`: `POST /api/auth/refresh`가 `rotate_tokens()`를 호출, `RefreshTokenReuseDetected`
  캐치 시 `logger.warning()` 기록 + 401 반환(탈취 의심 메시지 별도). 응답 포맷이 `{access_token}` →
  `{access_token, refresh_token}`으로 변경(회전 반영). `logout`은 이제 family 전체 삭제(기존 동작
  자연스럽게 확장).
- 프론트엔드(`static/index.html`): `tryRefreshToken()`이 회전된 새 `refresh_token`으로 반드시
  교체 저장하도록 수정(`setTokens(data.access_token, data.refresh_token)`).

## 검증

**pytest** (`tests/test_jwt.py`에 5개 신규):
- 회전 시 새 access_token 발급 확인(기존 테스트 갱신, refresh_token도 검증하도록 확장)
- 회전 시 새 refresh_token이 이전과 다름
- 회전 후 예전(폐기된) refresh_token 재사용 시 401
- **재사용 탐지가 family 전체를 무효화함을 직접 증명**: 예전 토큰 재사용 시도 후, 아직 한 번도
  안 쓴 최신 refresh_token조차 이후 refresh가 거부됨을 확인
- 로그아웃이 family 전체(회전 이후 최신 토큰 포함)를 무효화함을 확인

전체 pytest 스위트 fresh `/tmp` 복사본에서 재실행 — **55개 테스트 전부 PASS**(기존 51개 + 신규 4개,
집계상 `test_refresh_issues_new_access_token`은 기존 테스트를 확장한 것이라 순증 4개).

**마이그레이션 시나리오 검증(ad-hoc, MVP 인프라 단계와 동일한 방식)**: 별도 SQLite 파일에 Alembic을
`0001`까지만 적용한 뒤(= v6 이전 상태 재현) `session` 테이블에 레거시 행 2건을 직접 삽입, 이어서
`head`(0002)까지 업그레이드해:
```
마이그레이션 후 세션 행: [('legacy-token-1', 'legacy-token-1', None), ('legacy-token-2', 'legacy-token-2', None)]
PASS: 레거시 세션 2건이 서로 다른 family로 정상 격리됨 (무관한 세션 동반 무효화 위험 없음)
```
을 확인 — 백필 로직이 의도대로 각 레거시 세션을 독립된 family로 분리함을 실제 마이그레이션 실행으로
증명(빈 문자열 공유였다면 실패했을 시나리오).

`node --check`로 프론트 JS 문법 확인.

## 비범위 (task-plan-refresh-rotation.md 참고)
- Access token 자체의 조기 무효화(여전히 30분 자연 만료까지 유효 — v5 트레이드오프 유지)
- `audit_log` 테이블 연동(현재는 `logging` 모듈 경고 로그로만 기록 — 앱 전체 감사로그 연결은 별도 과제)
- 디바이스별 세션 목록 조회/개별 로그아웃 UI

## 종합 평가

| 항목 | 평가 |
|---|---|
| Refresh 회전 | ✅ 5개 pytest로 검증 |
| 재사용(탈취) 탐지 + family 무효화 | ✅ pytest로 "최신 토큰까지 함께 잠김" 동작 직접 증명 |
| 레거시 세션 마이그레이션 안전성 | ✅ 실제 Alembic 업그레이드 실행으로 백필 검증 |
| 로그아웃 의미 확장(family 전체) | ✅ pytest로 검증 |
| 전체 회귀 | ✅ 55/55 PASS |

**점수: 94/100** (감점 사유: 탈취 탐지 이벤트가 `logging`에만 남고 `audit_log` 테이블/알림 채널에는
연결되지 않음 — 별도 과제로 이월)

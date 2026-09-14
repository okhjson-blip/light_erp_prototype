# Eval Report — 운영 인프라 MVP (마이그레이션/헬스체크·로깅/pytest/CI)

설계문서: `task-plan-mvp-infra.md`. 사용자 지시: "운영 인프라(특히 마이그레이션 도구) 먼저 진행 한다" →
클리어링 질문 응답으로 Alembic 도입 + 인프라 트랙 전체(마이그레이션+CI/CD+헬스체크/로깅)를 한번에 진행.

## 1. DB 마이그레이션 (Alembic)

**설계 제약**: 이 프로젝트는 ORM 모델이 없고 raw SQL(`schema_sqlite.sql`/`schema_postgres.sql`)만 쓰므로
Alembic의 autogenerate는 사용 불가 — 모든 마이그레이션은 `op.execute()` 기반 손수 작성 raw SQL로 진행.

**검증**:
| 시나리오 | 방법 | 결과 |
|---|---|---|
| 완전 신규 DB | 빈 SQLite 파일에 `init_db()` 호출 | `alembic upgrade head` 실행, 43개 테이블 전부 생성 확인 |
| Alembic 전환 이전 기존 DB(legacy) | `schema_sqlite.sql`을 직접 실행해 만든 DB(더미 `company` 행 삽입) + `init_db()` 호출 | `alembic_version` 테이블 없음을 감지 → `alembic stamp head` 실행. **더미 행과 전체 테이블 데이터 손실 없이 보존됨을 확인**, `alembic_version.version_num='0001'`로 기록됨 |
| 이미 추적 중인 DB에 새 마이그레이션 추가 | 데모 리비전(`0002_test_add_column.py`, company에 `note` 컬럼 추가)을 만들어 `alembic upgrade head` 실행 | 기존 데이터 보존한 채 컬럼 추가 성공 (검증 후 데모 리비전 파일은 삭제 — 실제 배포용이 아님) |

결론: "스키마 바뀔 때마다 `erp.db` 삭제" 문제가 실제로 해결됨을 3가지 시나리오로 증명.

## 2. 헬스체크 + 구조화 로깅

- `GET /health`: DB 연결 확인 포함, 정상 시 200 `{"status":"ok","db":"ok"}`. 비인증(GET 인증 확장 대상 제외) —
  `tests/test_health.py`에서 검증.
- `logging`(표준 라이브러리): 서버 기동/마이그레이션 확인/시드 적재 이벤트를 타임스탬프+레벨로 기록.

## 3. pytest 테스트 스위트

`tests/` 디렉토리에 8개 파일, 총 **42개 테스트, 전부 PASS** (`/tmp` 임시 SQLite로 격리 실행, 실 개발용
`app/erp.db`는 건드리지 않음):

| 파일 | 커버리지 |
|---|---|
| `test_auth_rbac.py` | 로그인 성공/실패, GET 401(무토큰), GET 200(로그인만 하면 역할무관), POST 401/403, 정적 리소스 비인증 |
| `test_jwt.py` | 토큰 3-part 구조, header `alg`/`typ`, payload `sub`/`iat`/`exp`/`jti`, 서명 위조·payload 위조·형식오류 거부 |
| `test_lot_serial.py` | RM LOT 생성, FG LOT+시리얼 생성, BOM 소요 FIFO 소진, 시리얼 추적, 출하 시 LOT 소진+시리얼 자동 SHIPPED |
| `test_lot_reconciliation.py` | 정상 정합 케이스, 강제 조작(SQL 직접)으로 부정합 감지 케이스 |
| `test_mes_wms_auth.py` | API Key 누락/오류/교차소스(MES↔WMS) 거부, 정상 키 처리, 이벤트 로그 조회 인증 |
| `test_ai_agent.py` | Buyer 추천 트리거(재고 강제 조작), Scheduler/Quality/Demand Planner/CFO 전부 `ai_narrative` 필드 존재 확인 |
| `test_serial_status.py` | 수동 상태변경 성공/403(권한없음)/400(잘못된 값)/404(존재안함) |
| `test_health.py` | 헬스체크 200, 비인증, 정적 루트 비인증 |

```
$ pytest -q
..........................................                               [100%]
42 passed, 2 warnings in 1.18s
```
(warnings는 FastAPI `on_event` deprecation — 동작에는 영향 없음, 향후 lifespan 전환 시 정리 대상)

`requirements-dev.txt`로 테스트 전용 의존성(pytest)을 런타임 의존성과 분리.

## 4. CI/CD

`.github/workflows/ci.yml` — 모든 브랜치 push/PR 시 `requirements-dev.txt` 설치 후 `pytest -q` 자동 실행.

## 비범위 (명시적으로 제외, task-plan-mvp-infra.md 참고)
컨테이너화(Docker/K8s), 부하테스트, 외부 로그 수집(ELK 등), lint/ruff CI 스텝.

## 종합 평가

| 항목 | 평가 |
|---|---|
| 마이그레이션 도구 도입 및 기존 스키마 무결 재현 | ✅ 3가지 시나리오로 검증 |
| 기존 DB 무중단 전환(데이터 손실 없음) | ✅ legacy DB stamp 검증으로 증명 |
| 헬스체크/로깅 | ✅ |
| 테스트 스위트 정식화 | ✅ 42개 전부 PASS |
| CI 자동화 | ✅ |

**점수: 95/100** (감점 사유: `on_event` deprecation 경고 미해결 — 기능 영향 없어 우선순위 낮음으로 다음 단계로 이월)

# Task Plan — 운영 인프라 고도화 (마이그레이션/헬스체크·로깅/CI)

## 배경
프로토타입 단계 내내 스키마가 바뀔 때마다 `app/erp.db`를 삭제하고 재시드하는 방식으로 처리했다
(RBAC/LOT·Serial/MES인증 단계 전부 동일). MVP로 가면 실사용자 데이터가 쌓이므로 이 방식은 데이터
유실을 뜻해 더 이상 쓸 수 없다. 사용자 확인에 따라 Alembic을 도입하고, 운영 인프라 트랙
(마이그레이션+CI/CD+헬스체크/로깅)을 한 번에 진행한다.

## 설계 결정
1. **Alembic 도입 — 이 프로젝트 최초의 "신규 런타임 의존성".** 지금까지 RBAC/JWT/MES인증은 전부
   표준 라이브러리만으로 구현했지만, DB 마이그레이션은 검증된 도구가 필요하다고 판단해 예외로 둔다
   (사용자 확인 완료). `requirements.txt`에 추가.
2. **기존 raw SQL 스키마 파일(schema_sqlite.sql/schema_postgres.sql)은 그대로 둔다.** 이 프로젝트는
   SQLAlchemy ORM 모델이 없어 Alembic autogenerate를 쓸 수 없다 — 앞으로 스키마 변경은 항상
   `alembic revision`으로 새 마이그레이션 파일을 만들고 `op.execute()`로 raw SQL을 직접 작성한다.
   초기 마이그레이션(0001)은 기존 스키마 파일 내용을 그대로 실행해 지금까지의 결과와 100% 동일한
   스키마를 재현한다.
3. **기존 설치(이미 초기화된 DB) 호환**: `init_db()`를 다음과 같이 바꾼다.
   - 테이블이 전혀 없는 완전 신규 DB → `alembic upgrade head` (마이그레이션을 순서대로 적용해 처음부터
     구성)
   - 테이블은 있는데 `alembic_version` 추적 테이블이 없는 기존 DB(이번 전환 이전에 만들어진 DB) →
     `alembic stamp head`로 "이미 head 상태"로 표시만 하고 데이터는 건드리지 않는다(head = 현재
     스키마 파일과 동일하므로 안전).
   - 이미 alembic으로 추적 중인 DB → `alembic upgrade head`(향후 신규 마이그레이션 적용).
4. **헬스체크**: `GET /health` 비인증 엔드포인트 추가 — DB 연결 확인 포함. 인프라 헬스 프로브가
   로그인 없이 호출할 수 있어야 하므로 GET 인증 확장 대상에서 제외.
5. **로깅**: 신규 의존성 없이 표준 `logging` 모듈로 uvicorn과 별개의 애플리케이션 로거를 구성해
   기동/마이그레이션 적용 등 주요 이벤트를 구조화된 포맷으로 남긴다.
6. **테스트**: 그동안 `/tmp` 임시 복사본에서 매번 새로 작성해 실행하던 검증 스크립트들을
   `tests/` 디렉토리의 정식 pytest 스위트로 승격한다 — 이래야 CI가 의미 있다. pytest는 런타임
   의존성이 아니라 개발/테스트 전용이므로 `requirements-dev.txt`로 분리한다.
7. **CI**: GitHub Actions 워크플로(`.github/workflows/ci.yml`)로 push/PR 시 pytest 스위트를 자동
   실행한다.

## 비범위
- 컨테이너화/K8s 배포 매니페스트(다음 단계 후보로 이월)
- 부하/성능 테스트, 외부 로그 수집기(ELK 등) 연동
- Alembic autogenerate(ORM 모델이 없어 애초에 불가능 — 항상 수동 작성)
- lint(ruff 등) CI 스텝 — 이번 요청 범위 밖이라 추가하지 않음

## 성공 기준
1. 완전 신규 환경(erp.db 없음)에서 서버 기동 시 `alembic upgrade head`로 기존과 동일한 스키마 생성
2. 이미 존재하는(마이그레이션 이전 방식으로 만들어진) DB에 대해 서버를 기동하면 데이터 손실 없이
   자동으로 `alembic_version`이 head로 stamp됨
3. `alembic revision`으로 새 마이그레이션을 추가하고 `alembic upgrade head`로 기존 DB에 무손실
   반영 가능함을 실제로 시연(예: 테스트용 컬럼 추가 후 롤백)
4. `GET /health`가 비인증으로 200 반환, DB 연결 실패 시 이를 반영
5. `tests/` 디렉토리의 pytest 스위트가 지금까지 검증한 모든 시나리오(RBAC/LOT·Serial/MES인증/
   AI Agent/정합성/GET인증/JWT/시리얼UI)를 포함하고 `pytest` 명령으로 전부 통과
6. GitHub Actions 워크플로가 존재하고 로컬에서 동일 커맨드로 재현 가능함을 확인

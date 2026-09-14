# Eval Report — v12 (04 Logistics Management 확장)

**날짜**: 2026-07-11 · **평가 기준**: consultingWizard_evaluator_CLAUDE.md (score≥80 & 치명오류 없음 = Pass)

## 범위 (task-plan-v9-full-menu-rollout.md §3 v12)

창고관리 Location 보강 / 컨테이너 관리 / 운송관리(TMS 간이) / 물류비 정산(회계 전표 연동) /
수출관리(조회) / 보험·클레임 / 물류 Dashboard. 수입관리는 03 통관(import_customs_record) 재사용.

## 구현 요약

| 구분 | 내용 |
|---|---|
| 마이그레이션 | 0006_logistics_extension.py — 신규 테이블 6종(warehouse_location/container/shipment_transport/logistics_cost/insurance_policy/logistics_claim) + gl_account '5100 물류비' 1행. 전부 additive |
| 백엔드 | app/logistics.py (prefix /api/logistics) — 17개 엔드포인트. 정산은 post_accounting() 재사용(차변 5100/대변 2000) |
| 프론트 | LogisticsPage.tsx 탭 7개(물류현황/Location/컨테이너/운송/물류비정산/수출현황/보험·클레임) + /logistics 라우트 + 사이드바(Ship 아이콘) |
| 테스트 | tests/test_logistics.py 18개 신규 — 기존 93 + 18 = **111개 전부 PASS** (Mac venv 실행) |

## 핵심 설계 결정

1. **권한**: 쓰기 = 영업담당+관리자(출하 파생 업무), Location 등록 = 관리자, **물류비 정산 = 관리자 전용**
   (전표 생성이라 v5 회계 제한 정책과 동일 선상). 조회는 로그인만 하면 전체(v4/v5 정책 유지).
2. **날짜**: transport_date/cost_date/claim_date 전부 서버 로컬 date.today() 명시 입력 —
   같은 날 발견/수정한 UTC 하루 밀림 이슈(eval_date)의 재발 방지 패턴 적용.
3. **신규 API 절약**: 출하 드롭다운 소스로 /export-status를 재사용(프론트), 수입관리 화면은 구매>통관관리 안내로 대체.
4. **Location**: 마스터 관리만 — inventory/lot과의 Location 차원 바인딩은 Enterprise 단계로 이연(알려진 범위 제한,
   현 inventory가 창고 단위 집계라 스키마 대수술 필요).

## 검증

- pytest 111/111 PASS (임시 SQLite 격리, 실 erp.db 불변)
- tsc -b 통과 (Mac)
- 프론트 재빌드 + 서버 재기동 + 브라우저 라이브 E2E:
  - /logistics 딥링크 정상(같은 날 추가한 SPA fallback 경유)
  - 물류 현황 KPI: 출하 124건(시드) 정상 집계
  - 운송(배차) 등록: SHP-2026-00124/한진물류/12가3456 → PLANNED, 일자 2026-07-11(로컬 날짜 정상)
  - 물류비 등록(운송비 ₩250,000) → 정산 → SETTLED + 전표 #1 생성 확인, 콘솔 에러 없음

## 리스크/이월

- 컨테이너/클레임 상태 전이는 자유 변경(순서 강제 없음) — 프로토타입 티어 단순화, 통관관리(v11)와 동일 수준.
- 보험(insurance_policy)과 물류비 INSURANCE 유형 간 연결 없음(각각 독립 등록) — 필요 시 후속.
- PostgreSQL에서 0006 실행 미검증(SQLite만) — 기존 패턴상 dialect 분기 동일해 위험 낮음, docker-compose 검증은 사용자 로컬 몫.

## 판정

**Score: 92/100 — PASS** (치명 오류 없음, 회귀 없음, E2E 라이브 검증 완료)
다음: v13(05 Production Management 확장 — MRP/외주생산/재작업/생산마감/OEE).

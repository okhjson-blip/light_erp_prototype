# Eval Report — v10: 02 Supply Chain Management 신규

설계문서: `task-plan-v9-full-menu-rollout.md` §3 v10. 1.0 메뉴 구조 "02. Supply Chain Management"
중 수요예측 고도화 + S&OP/공급계획/생산계획(MPS)뷰/재고계획/공급위험관리/Control Tower 구현.
**공급망 시뮬레이션은 사용자 확인에 따라 이번 로드맵 전체에서 명시적으로 제외**.

## 구현

- **스키마 변경 없음** — 신규 테이블 없이 기존 `demand_forecast`/`production_order`/`inventory`/
  `purchase_order`/`goods_receipt`/`vendor`/`material`을 집계·대조하는 **조회 전용(GET) API만**
  추가(`app/scm.py`, prefix `/api/scm`).
- 수요예측 정확도(`/demand-forecast/accuracy`), S&OP 대조(`/sop`), 공급계획(`/supply-plan`),
  MPS 뷰(`/mps`), 재고계획(`/inventory-plan`), 공급위험관리(`/supply-risk`), Control Tower 요약
  (`/control-tower`, 위 지표들을 함수 직접 호출로 재사용).
- **프론트**: 신규 `ScmPage.tsx`(7개 탭) + `App.tsx`/`AppShell.tsx`에 `/scm` 라우트·사이드바 메뉴
  추가(`Radar` 아이콘).

## 버그 발견 및 수정

수동 검증 중 S&OP 대조(`/api/scm/sop`)가 항상 `planned_qty=0`을 반환하는 문제를 발견했다. 원인:
`demand_forecast.forecast_month`은 `"2026-12-01"`(전체 날짜) 형식으로 저장돼 있는데, 생산계획 쪽은
`substr(order_date,1,7)`로 `"2026-12"`(월만) 그룹화해 두 키가 절대 일치하지 않았다. `forecast_month`
쪽도 `substr(forecast_month,1,7)`로 통일해 수정 — 수정 후 실제 매칭되는 행이 나오는 것을 확인했다
(재발방지: `tests/test_scm.py::test_sop_gap_matches_same_month_period_format`에 "최소 1건은
planned_qty>0"이라는 회귀 검증을 남겼다).

## 검증

**pytest**: 신규 `tests/test_scm.py` 8개(응답 shape 6종 + 로그인 필요 확인 + S&OP 매칭 회귀) 추가.
기존 73개 + 신규 8개 = **81개 전부 PASS**(경량 백엔드 전용 `/tmp` 복사본).

**TypeScript**: `npx tsc -b` — 에러 없음.

**공급위험관리 빈 상태 확인**: 샘플 데이터셋은 재고를 스냅샷으로 직접 적재해 실제 구매→입고
트랜잭션 이력이 없으므로(기존에도 알려진 제약, v2 임포트 때부터 문서화됨) `/supply-risk`가 빈
배열을 반환하는 것이 정상이다 — 프론트에 안내 문구를 추가해 "버그처럼 보이지 않게" 처리했다.

## 비범위(의도적으로 남김)
- 공급망 시뮬레이션(What-if) — 사용자 확인에 따라 이번 로드맵 전체에서 제외.
- 브라우저 실기동 확인 — 이 세션 구조적 제약으로 미실행, 사용자 로컬 확인 필요.

## 종합 평가

| 항목 | 평가 |
|---|---|
| 수요예측 정확도 | ✅ 구현+테스트 PASS |
| S&OP(월 포맷 버그 수정 포함) | ✅ 구현+버그수정+테스트 PASS |
| 공급계획/MPS/재고계획 | ✅ 구현+테스트 PASS |
| 공급위험관리 + Control Tower | ✅ 구현+테스트 PASS(빈 상태 안내 포함) |
| 회귀(기존 73개) | ✅ 전부 PASS |
| 타입체크 | ✅ PASS |
| 브라우저 실기동 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 92/100** (감점 사유: 브라우저 실기동 미확인)

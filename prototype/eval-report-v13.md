# Eval Report — v13 (05 Production Management 확장)

**날짜**: 2026-07-11 · **평가 기준**: consultingWizard_evaluator_CLAUDE.md (score≥80 & 치명오류 없음 = Pass)

## 범위 (task-plan-v9-full-menu-rollout.md §3 v13)

MRP(BOM×수요예측 부족자재 산출) / 외주생산(is_outsourced) / 재작업(불량 시리얼 재투입) /
생산마감(월 배치 + FI 전표 + 실적 잠금) / 설비가동현황·OEE분석(실측 승격) / 생산 Dashboard.

## 구현 요약

| 구분 | 내용 |
|---|---|
| 마이그레이션 | 0007 — production_order.is_outsourced/vendor_id 컬럼 + rework_order/production_close 테이블 (additive) |
| 백엔드 | app/production_ext.py (prefix /api/production) 9개 엔드포인트 + main.py 최소수정 3곳(외주 파라미터, vendor join, 마감 잠금 체크) |
| 프론트 | ProductionPage.tsx 탭 7개로 재구성(생산오더[기존 유지]/MRP/외주생산/재작업/생산마감/OEE 분석/생산 현황) |
| 테스트 | tests/test_production_ext.py 15개 신규 — 기존 111 + 15 = **126개 전부 PASS** |

## 핵심 설계 결정

1. **MRP는 조회 전용**: 최신 수요예측월 × BOM 전개 → 소요량 vs 현재고+미입고PO → 부족분.
   발주 실행은 기존 PR/PO 또는 AI Buyer(재발주점 기준 — 별개 로직임을 화면에 명시)로 연결.
2. **재작업은 기존 시리얼 상태만 사용**(IN_STOCK/DEFECTIVE/SCRAPPED — 신규 상태 미도입):
   DEFECTIVE만 등록 가능, OPEN 중복 차단, REWORKED→IN_STOCK 복귀 / SCRAPPED→폐기.
   시리얼 상태 변경은 v8 write_audit_log 패턴으로 감사 기록.
3. **생산마감**: 양품수량×std_cost 근사(v9 손익 근사와 동일 기준), 전표 차변 1200 재고자산/대변
   5000 매출원가(WIP 계정 없음 — 프로토타입 절충), 마감월 실적입력 400 차단(main.py 체크 1곳).
4. **OEE 실측 승격**: dataset production_results.csv의 oee/availability/performance/quality_rate를
   월×공장 AVG 집계(2026-01~12 × 3개 공장). kpi_monthly.oee_avg는 참고 시계열로 병행 표시.
5. **외주생산**: v11 po_type 패턴 — 승인 불필요 분류 컬럼이라 main.py create_prod_order에 최소 추가.
   is_outsourced=1이면 vendor_id 필수(400/404 검증).

## 검증

- pytest 126/126 PASS, tsc -b 통과 (모두 Mac venv/node)
- 브라우저 라이브: MRP(2026-12 기준 10개 자재, 부족분 계산식 표시), OEE 분석(월×공장 실측 집계),
  생산 현황 KPI 7종(미완료 98/당월 양품 13,071/불량률 2.71%/평균 OEE 77.8), 콘솔 에러 없음
- 마감 잠금 테스트는 당월 마감 후 실적입력 400 확인 → 마감 행 직접 제거로 다른 테스트 영향 차단(db_path 픽스처 용도)

## 리스크/이월

- MRP는 단일 레벨 BOM 전개(현 데이터셋 BOM이 1단계라 충분 — 다단계 전개는 Enterprise 이연).
- 생산마감 잠금은 실적 "입력 시점의 오늘 날짜" 기준(과거 월로 소급 입력하는 API가 없어 실질 영향 없음).
- 재작업 완료 시 재고 수량 조정은 하지 않음(시리얼 상태만 — LOT/inventory 대사는 정합성 점검 몫).

## 판정

**Score: 92/100 — PASS**
다음: v14(06 Quality Management 확장 — 검사기준/검사구분/SPC/8D/CAPA).

# Task Plan — LOT ↔ inventory.qty 정합성 검증 로직

## 배경
task-plan-lot-serial.md에서 "LOT 재고와 집계 inventory.qty 간 실시간 정합성을 검증하는 로직은
없음"을 알려진 리스크로 남겨뒀다. v3 전체 기능 통합 재검증(34개 항목 전부 PASS) 이후, 이 검증
로직을 실제로 구현한다.

## 설계 결정
1. **완전한 수량 일치를 기대하지 않는다.** 과거 임포트 재고(prototype_dataset 스냅샷)는 LOT이
   없으므로, `inventory.qty`가 `활성 LOT 합계`보다 큰 것은 정상이다(그 차이 = "미추적수량",
   LOT 도입 이전부터 있던 재고). 이를 오류로 취급하면 항상 대부분의 품목이 "실패"로 표시되어
   검증 기능 자체가 무의미해진다.
2. **실제 버그로 볼 수 있는 유일한 신호는 "활성 LOT 합계가 inventory.qty를 초과하는 경우"**다.
   LOT은 언제나 실제 재고 이동(입고/생산/출하)에 곁들여 생성·소진되므로, 정상적인 상황에서는
   활성 LOT 합계가 집계값을 넘어설 수 없다. 넘어선다면 LOT 생성/소진 로직과 `adjust_inventory()`
   호출이 어긋난 실제 버그다.
3. `GET /api/lots/reconciliation` 엔드포인트로 material×warehouse별 {inventory_qty, active_lot_qty,
   untracked_qty, consistent} 산출. GET이므로 기존 RBAC 비범위 결정과 동일하게 인증 없음.
4. 재고 탭에 "LOT 정합성 점검" 테이블을 추가해 "부정합"으로 표시되는 행이 있는지 눈으로 바로
   확인할 수 있게 한다.

## 비범위
- 자동 알림/스케줄링(예: 매일 정기 점검) — 신규 의존성(스케줄러) 필요해 이번 범위 제외
- 부정합 자동 교정(수동 확인·조치가 우선이라고 판단)
- LOT이 전혀 없는 material×warehouse 조합(신규 품목 등)은 애초에 이 리포트에 나타나지 않음
  (LOT 테이블 기준 GROUP BY라서) — 이는 "점검 대상이 아직 없다"는 뜻이지 오류가 아님

## 성공 기준
1. 정상 상태(입고/생산/출하만 발생)에서는 모든 행이 `consistent: true`
2. 활성 LOT 합계가 인위적으로 집계값을 초과하도록 만들면(버그 시뮬레이션) 해당 행만
   `consistent: false`, `untracked_qty < 0`으로 정확히 탐지
3. 재고 탭에 "LOT 정합성 점검" 테이블 노출, 부정합 행은 "⚠ 부정합"으로 표시

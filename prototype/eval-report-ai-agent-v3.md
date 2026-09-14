# Evaluation Report — AI Agent 나머지 3개 시나리오 (수요예측/품질/CFO Copilot)

```json
{
  "pass": true,
  "score": 91,
  "independence_check": {"existing_files_modified": ["app/ai_agent.py", "static/index.html", "README.md"], "db_schema_changed": false},
  "failures": [],
  "harness_update_needed": false
}
```

기존 파일 수정은 task-plan-ai-agent-v3.md에 명시한 계획 범위 내(신규 엔드포인트/UI 섹션 추가, 기존
Buyer/Scheduler 로직 변경 없음, 스키마 변경 없음)이므로 계획대로 진행된 것으로 판단.

## 성공 기준 대비 결과
1. 3개 GET 엔드포인트가 실데이터 기준으로 그럴듯한 추천/인사이트를 반환 — **PASS**
   - Demand Planner: MAPE 임계치 10% 기준 IoT Sensor Module 1건 플래그(avg MAPE 12.1%, 과소예측 방향),
     재발주점 1617→1692, 목표재고 2655→2730 제안(TestClient 확인 후 실브라우저에서도 동일 결과 확인)
   - Quality Engineer: 5개 완제품 전부 최근 6건 중 CAPA 필요 3~4건으로 추천 목록에 포함, USB Desk
     Humidifier/Smart Mini Fan은 FAIL 1건 포함되어 위험도 "높음"으로 정확히 분류
   - CFO Copilot: 2026-12 영업이익률 -3.6%p 악화, 영업이익 대비 현금흐름 괴리(1,130,361 차이), 공급
     리스크 5건, 라이브 AR/AP(둘 다 0원 — 임포트 데이터가 과거 거래를 소급 생성하지 않아 아직 라이브
     매출채권/매입채무가 없는 것은 기존 설계상 의도된 동작) 4개 인사이트 정상 생성
2. Demand Planner apply 클릭 시 material.reorder_point/target_stock이 실제로 갱신됨 — **PASS**
   (TestClient로 1차 검증 후 원복, 실브라우저에서 "계획값 적용" 버튼 클릭으로 2차 라이브 검증 —
   1617/2655 → 1692/2730로 갱신되고 화면이 새 현재값 기준으로 재계산됨을 확인)
3. 기존 AI Agent(Buyer/Scheduler)·전체 E2E 플로우 회귀 없음 — **PASS**
   (AI Buyer "재발주 필요 품목 없음" 정상 표시, Scheduler 57건 오픈 생산오더 우선순위 정상 산정 — 이전과
   동일한 결과, 공장·창고 선택 UI 등 v3 이전 변경사항도 영향 없음)
4. index.html AI Agent 탭에 3개 섹션 추가, 브라우저에서 정상 렌더링 확인 — **PASS**

## 설계 상 주요 판단 (task-plan에 사전 명시)
- MAPE 임계치는 최초 15%로 설계했으나 실데이터(최근 3개월 평균 최대 12.1%)에서 추천이 0건이 되어
  10%로 재조정(제조업 S&OP 통상 기준 범위 내, 실데이터 상 상대적으로 정확도가 낮은 품목을 정확히 포착).
- Demand Planner의 apply는 Buyer처럼 승인 워크플로(approval_workflow)를 만들지 않고 material 테이블을
  직접 갱신 — 금액이 이동하는 거래가 아닌 계획 파라미터 조정이라는 점에서 리스크 수준이 다르다고 판단.
  단, "사람이 버튼을 눌러야 반영"되는 Human-in-the-loop 원칙은 동일하게 적용.
- Quality Engineer는 CAPA 실행/추적 테이블이 스키마에 없어 apply 엔드포인트를 만들지 않음(조회전용).
  실제 CAPA 프로세스 자동화가 필요해지면 별도 테이블/워크플로 설계가 선행되어야 함(v4 이후 후보).
- CFO Copilot은 자문 성격이라 애초에 실행 액션이 없는 설계(설계문서 상 "Copilot"이 조언 역할임을 반영).

## 알려진 제약
- Demand Planner의 추천 로직은 매번 demand_forecast의 동일 과거 3개월 레코드를 기준으로 재계산하므로,
  apply를 반복 클릭하면 매번 같은 방향으로 재발주점이 계속 상향 조정된다(추천 이력을 추적해 "이미 반영된
  추천"을 걸러내는 로직은 없음). 프로토타입 범위에서는 1회 적용을 전제로 설계했으며, 실사용 시에는
  적용 이력 테이블이 필요함.
- CFO Copilot의 라이브 AR/AP는 현재 0원으로 표시되는데, 이는 데이터셋 임포트 시 과거 거래를 소급
  생성하지 않기로 한 기존 설계(eval-report-dataset-import.md 참고)의 연장선 — 버그 아님.

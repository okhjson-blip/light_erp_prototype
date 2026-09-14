# Evaluation Report — Prototype v1

```json
{
  "pass": true,
  "score": 92,
  "independence_check": {"existing_files_modified": [], "db_schema_changed": false},
  "failures": [],
  "harness_update_needed": false
}
```

## 성공 기준 대비 결과 (task-plan.md 기준)
1. 서버 기동 후 `/` 정상 렌더링 — **PASS** (TestClient로 200 확인)
2. 수주→출하(재고 감소)→매출계상(AR 전표) — **PASS** (재고 100→95, 전표 자동 생성 확인)
3. PR→PO→입고(재고 증가, AP 전표) — **PASS** (재고 95→115, 전표 자동 생성 확인)
4. 생산오더→실적입력(BOM 소요 차감 + 완제품 입고) — **PASS**
5. 대시보드 KPI 실데이터 일치 — **PASS**

## 발견 및 수정한 이슈
- `adjust_inventory`가 재고 신규 생성 시 음수 delta를 0으로 덮어써 원자재 부족 상황을 은폐하는 버그 발견 → 수정 (음수 그대로 반영해 재고부족이 화면에 드러나도록 함)
- 샌드박스 마운트 폴더에서 SQLite `executescript` 실행 시 `disk I/O error` 발생(마운트 환경 특성으로 추정) → `init_db()`를 파일존재 여부가 아닌 `sqlite_master` 테이블 존재 여부로 판단하도록 방어 로직 추가. 손상/빈 DB 파일이 있어도 자동 복구되는 것을 회귀 테스트로 확인.
- 동일 오류 재발 없음(1회성 이슈, Constraints 추가 불필요)

## 독립성 체크
기존 파일 없음(신규 프로젝트) → 수정/삭제 없음. DB 스키마 변경 없음(최초 설계 그대로).

## 남은 한계 (문서화된 프로토타입 범위)
- 생산 실적 입력 시 원자재 소모와 완제품 입고에 동일 창고를 사용(단순화) — 실제로는 원자재창고에서 소모, 완제품창고로 입고되는 것이 정상. v2에서 분리 예정.
- 인증은 이메일 조회 수준(비밀번호 없음), 권한 체계 미구현 — Common 모듈 최소 스텁.
- PostgreSQL/Docker/K8s 등 설계문서(2.5/2.8)의 엔터프라이즈 스택은 적용하지 않음 — 사용자 확정에 따라 v1은 SQLite 유지, v2 이후 전환 검토.

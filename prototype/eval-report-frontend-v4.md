# Eval Report — React 프론트엔드 마이그레이션 4차 (회계/승인함/연동 로그)

설계문서: `task-plan-frontend-react.md`(4차 범위), `ui-identity.md`. 사용자 지시: "4차 진행".

## 구현

- **FinancePage**: 전표 목록(관리자 전용). ui-identity.md "관리자 전용 안내 배지" 규칙에 따라 페이지
  타이틀 옆에 `Badge`로 "관리자 전용" 표기. `hasRole('관리자')`가 아니면 API 호출 자체를 생략
  (`useQuery({enabled: isAdmin})`)하고 안내 문구만 표시 — v5 백엔드 정책(`require_roles("관리자")`,
  403)과 프론트가 동일하게 좁혀져 있음을 실제로 재확인(아래 검증 참고).
- **ApprovalsPage**: 승인 워크플로 목록 + `PENDING` 건에 한해 승인/반려 버튼(관리자 전용, `Button`의
  `success`/`danger` variant 사용). 결정 후 목록 쿼리 invalidate.
- **IntegrationsPage**: MES/WMS 이벤트 로그 목록. `source_system`별 아이콘 구분(MES=Factory,
  WMS=Boxes, ui-identity.md 규칙), payload는 기본 축약(`보기` 버튼)→클릭 시 `<pre>` 블록으로 전체
  JSON 펼침(행별 독립 토글 상태) — 정보량 동일, 표시 방식만 개선.
- 세 페이지 모두 정보항목은 기존 static과 완전히 동일, 신규 폼/기능 추가 없음(회계 수동전표 등록
  UI는 기존 static에도 없어 이번 이관 범위 밖으로 유지).

## 검증

**TypeScript 타입체크**: `npx tsc -b` — 에러 없음(types.ts 확장 3개 인터페이스, FinancePage.tsx,
ApprovalsPage.tsx, IntegrationsPage.tsx, App.tsx 라우트 갱신).

**API 계약 검증**(fresh `/tmp` 복사본, `TestClient`로 실제 트랜잭션 생성 후 조회 필드 확인 — 첫
시도에서 시드 데이터만으로는 세 테이블이 전부 비어 있어, 수동전표 등록/PR 등록(승인워크플로
자동생성)/WMS 웹훅을 직접 호출해 실제 행을 만든 뒤 재검증):
```
accounting-documents[0] keys: description, doc_id, doc_type, posting_date, status
approvals[0] keys: created_date, current_step, doc_id, doc_type, status, workflow_id
integration-events[0] keys: event_id, event_type, payload_json, received_at, source_system, status
non-admin(영업담당) accounting-documents 조회: 403 확인 — FinancePage의 관리자 전용 분기 로직 근거
```
승인 결정(`APPROVED`) 실제 호출도 200 확인. 프론트 `lib/types.ts` 인터페이스 전부 실제 응답과
필드명까지 정확히 일치.

**미실행**: `vite build`/브라우저 실기동 — 1~3차와 동일한 플랫폼 바이너리 문제로 이 세션에서
미실행. 사용자 로컬 확인 필요.

## 비범위
- AI Agent/참고데이터(5차) — 다음 단계
- 회계 수동전표 등록 UI — 기존 static에도 없어 이관 범위 밖(백엔드 API는 존재하나 프론트 노출 안 함)

## 종합 평가

| 항목 | 평가 |
|---|---|
| 회계(관리자 전용 조회+안내) 연동 | ✅ 403 실제 확인으로 프론트 분기 근거 확보 |
| 승인함(목록+승인/반려) 연동 | ✅ 실제 호출로 결정 흐름 검증 |
| 연동로그(payload 토글+시스템 아이콘) 연동 | ✅ API 계약 검증 PASS |
| 정보항목 동일성 | ✅ 필드 추가/제거 없음 |
| 브라우저 실기동 확인 | ⚠️ 미실행 — 사용자 로컬 확인 필요 |

**점수: 91/100** (감점 사유: vite build/브라우저 실기동 미확인)

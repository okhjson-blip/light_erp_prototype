# Task Plan — MES/WMS 웹훅 인증 (API Key, v3 우선순위 3)

## 목표
`app/integrations.py`의 MES/WMS Mock Webhook 2개 엔드포인트(`POST /api/integrations/mes/production-result`,
`POST /api/integrations/wms/inventory-movement`)는 RBAC 구현 이후에도 계속 완전히 열려 있었다(내부
직원이 아니라 외부 시스템이 호출하는 엔드포인트라 세션 로그인 방식이 맞지 않기 때문). 이번 작업은
이 두 엔드포인트에 시스템 간(system-to-system) 인증을 추가한다.

## 설계 결정
1. **RBAC(세션 토큰)과는 별개의 메커니즘**을 쓴다. MES/WMS는 로그인 화면을 통해 접근하는 사람이
   아니라 외부 시스템이므로, 단순 공유키(API Key) 방식이 적합하다. OAuth2는 이번 범위에서 제외
   (프로토타입 단계에 과도 — README에 실운영 전환 시 고려사항으로 명시).
2. **신규 테이블 `integration_api_key`**(key_id, api_key UNIQUE, source_system, label, active,
   created_date) — RBAC의 session 테이블과 같은 패턴(DB 테이블 기반, 신규 의존성 없음).
3. **`X-API-Key` 헤더**로 전달, `source_system`(MES/WMS)별로 키를 분리해 교차 사용을 차단한다
   (MES 키로 WMS 엔드포인트 호출 불가, 반대도 마찬가지).
4. **데모 키는 고정값**(RBAC의 `demo1234`와 동일한 취지) — `mes-demo-key-please-rotate` /
   `wms-demo-key-please-rotate`. 실제 운영 전환 시 반드시 교체.
5. **평문 저장**: API Key는 세션 토큰과 마찬가지로 DB에 평문 저장한다(비밀번호와 달리 해시화하지
   않음 — RBAC의 session 토큰 저장 방식과 동일한 절충, README에 명시).
6. GET 엔드포인트(`GET /api/integrations/events`)는 기존 RBAC 비범위 결정과 동일하게 인증 없이 유지.

## 부수 발견 및 수정
- `simulate_mes_wms.py`가 RBAC 구현 이후 깨져 있었음: 생산오더/작업지시 생성 API가 이제 역할 인증을
  요구하는데 시뮬레이터에는 로그인 로직이 없었음 → 생산담당 데모 계정으로 로그인 후 토큰을 실어
  호출하도록 수정.
- `simulate_mes_wms.py`가 데이터셋 임포트(prototype_dataset) 사용 시 창고명이 영어("Korea Factory 1
  FG Warehouse" 등)인데도 한글 부분일치("완제품"/"원자재")로 창고를 찾고 있어 `StopIteration`으로
  실패했음 → 이미 존재하는 `warehouse_type`(FG/RM) 컬럼으로 매칭하도록 수정(RBAC/LOT 작업과 무관한
  기존 버그, 이번에 시뮬레이터를 손대는 김에 함께 수정).

## 비범위
- OAuth2/JWT 전환(README에 실운영 후보로 이월)
- API Key 발급/회전(rotation)을 위한 관리 UI(현재는 시드로 고정 데모 키만 제공)
- API Key 평문 저장을 해시로 전환(세션 토큰과 동일한 절충으로 이번 범위에서 유지)

## 성공 기준
1. `X-API-Key` 없이 두 웹훅 호출 시 401
2. 잘못된 키로 호출 시 401
3. 다른 source_system의 키로 호출 시(MES 키로 WMS 엔드포인트 등) 401
4. 올바른 키로 호출 시 정상 처리(200) 및 LOT/재고 반영 확인
5. `GET /api/integrations/events`는 계속 비인증 조회 가능(회귀 없음)
6. `simulate_mes_wms.py`가 처음부터 끝까지 정상 동작(로그인 → 생산오더/작업지시 → MES/WMS 웹훅)

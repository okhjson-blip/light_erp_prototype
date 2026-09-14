# Task Plan — AI Agent LLM 고도화 1단계 (자연어 근거 생성)

## 사용자 확인 사항 (2026-07-05)
"AI Agent LLM 고도화"의 범위와 방식을 사전에 확인한 결과:
- **범위**: 자연어 근거(rationale) 문장만 보강. 추천 대상/수치 산출 로직은 그대로 규칙기반 유지.
- **호출 방식**: 템플릿 기반(실제 LLM API 호출 없음, 토큰 비용 0) — 통합테스트/현업 검증 단계에서
  필요성이 확인되면 그때 실제 API 연계를 별도로 진행하기로 함.

이 결정은 프로젝트 지침("에러/토큰 사용 최소화")과도 부합한다.

## 설계
1. 신규 모듈 `app/llm_rationale.py` — 5개 에이전트(Buyer/Scheduler/Demand Planner/Quality Engineer/
   CFO Copilot)별 `narrate_*(rec) -> str` 함수. 구조화된 추천 데이터를 사람이 읽기 편한 한 단락의
   자연어 문장으로 조합한다. 외부 API 호출 없음(표준 라이브러리 f-string만 사용).
2. `app/ai_agent.py`의 각 추천/인사이트 딕셔너리에 신규 필드 `ai_narrative`를 추가(additive) —
   기존 `rationale`/`detail` 필드는 그대로 유지해 회귀 없음을 보장.
3. 프론트엔드: AI Agent 탭의 5개 테이블에 "AI 설명" 컬럼 추가(조회전용, 기존 컬럼은 그대로 유지).
4. Human-in-the-loop 원칙 불변: apply 엔드포인트(PR 생성/계획값 적용)는 변경 없음 — 여전히 사람이
   버튼을 눌러야 실행.

## 비범위
- 실제 LLM API 호출(Anthropic API 등) — 통합테스트/현업 검증 단계에서 필요시 별도 진행
- 추천 로직(수치 산출) 자체를 LLM으로 대체
- 자동 실행/자율 에이전트화(거버넌스 원칙 변경 없음)

## 성공 기준
1. 5개 에이전트 모두 응답에 `ai_narrative` 필드 포함, 빈 문자열 아님
2. 기존 `rationale`/`detail` 필드는 그대로 유지(회귀 없음)
3. 프론트엔드 AI Agent 탭에 "AI 설명" 컬럼 노출
4. 신규 의존성 없음, 외부 API 호출 없음(코드 검토로 확인)

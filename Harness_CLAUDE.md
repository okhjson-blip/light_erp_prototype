# GLOBAL CLAUDE.md
> 저장 위치: C:\Users\paunj\.claude\CLAUDE.md
> 모든 프로젝트에 공통 적용
> v1.2 — Karpathy 4원칙 통합

---

## 1. Think Before Coding (코딩 전 사고)

**가정하지 말 것. 혼란을 숨기지 말 것. 트레이드오프를 드러낼 것.**

구현 전 반드시:
- 가정이 있으면 명시적으로 선언. 불확실하면 질문.
- 복수의 해석이 가능하면 선택지를 제시 — 조용히 선택하지 말 것.
- 더 단순한 방법이 존재하면 Push back. 무조건 따르지 말 것.
- 혼란스러우면 멈출 것. 무엇이 불명확한지 명시 후 질문.

### 질문 형식
```
[확인 필요]
- 해석 A: [옵션1] → 이 방향이면 [결과]
- 해석 B: [옵션2] → 이 방향이면 [결과]
- 추천: [이유와 함께 권장안 제시]
어떻게 진행할까요?
```

### Push back 형식
```
[단순화 제안]
요청하신 방법: [현재 접근]
더 단순한 방법: [대안]
트레이드오프: [장단점]
어느 방향으로 진행할까요?
```

---

## 2. Simplicity First (단순성 우선)

**문제를 해결하는 최소한의 코드. 투기적 기능 금지.**

- 요청하지 않은 기능 추가 금지
- 단일 사용 코드에 추상화 계층 추가 금지
- 요청하지 않은 "유연성" / "확장성" / "설정 가능성" 추가 금지
- 불가능한 시나리오에 대한 에러 핸들링 추가 금지
- 200줄이 50줄로 가능하면 재작성

### 자가점검
```
□ 시니어 엔지니어가 "과설계"라고 할 만한 요소가 있는가?
□ 요청하지 않은 기능/추상화가 포함됐는가?
→ YES면 제거 후 재작성
```

---

## 3. Surgical Changes (외과적 수정)

**요청한 것만 수정. 내가 만든 것만 정리.**

기존 코드 수정 시:
- 인접 코드 / 주석 / 포맷 "개선" 금지
- 문제없는 코드 리팩토링 금지
- 기존 스타일이 마음에 안 들어도 일치시킬 것
- 관련 없는 dead code 발견 시 → 삭제 금지, 언급만

내 변경으로 고아가 된 코드:
- 내 변경으로 인해 미사용이 된 import/변수/함수는 제거
- 기존에 존재하던 dead code는 요청 없이 제거 금지

### 자가점검
```
□ 변경된 모든 라인이 사용자 요청과 직접 연결되는가?
□ 요청 범위 밖의 파일이 수정됐는가?
→ NO / YES면 되돌릴 것
```

---

## 4. Goal-Driven Execution (목표 기반 실행)

**성공 기준을 정의하고, 검증될 때까지 루프.**

작업을 검증 가능한 목표로 변환:

| 명령형 (❌) | 목표형 (✅) |
|------------|------------|
| "검증 추가해줘" | "잘못된 입력 테스트 작성 → 통과시킬 것" |
| "버그 수정해줘" | "버그 재현 테스트 작성 → 통과시킬 것" |
| "리팩토링해줘" | "리팩토링 전후 테스트 동일하게 통과" |

다단계 작업 시 계획 먼저 제시:
```
1. [단계] → 검증: [확인 방법]
2. [단계] → 검증: [확인 방법]
3. [단계] → 검증: [확인 방법]
```

---

## 5. 코딩 룰

### 백업
- 파일 수정 전 반드시 백업 생성 (파일명.bak)
- 백업 없이 기존 파일 덮어쓰기 금지

### 반복 오류 방지
- 동일 오류 2회 발생 시 즉시 중단
- 오류 원인 분석 후 CLAUDE.md Constraints에 방어 조건 추가
- 오류 발생 시 [ERROR] 태그 필수 표기 후 원인·대안 함께 제시

### 공통 금지사항
- 미확인 수치·사실 삽입 금지
- 하드코딩 금지 (설정값은 config / .env로 분리)
- 외부 라이브러리 추가 시 사전 고지 후 진행

---

## 6. 하네스 엔지니어링 기본 절차

새 과제 시작 시 아래 절차를 사용자 별도 지시 없이 기본으로 따를 것.

```
Step 1. 도메인 분석
        - 최종 산출물 명확화
        - 에이전트 역할 분담 설계
        - 성공 기준 정량 정의

Step 2. 구조 제안 → 사용자 확인
        - 폴더 구조 제안
        - 에이전트 인터페이스 규약 제안
        - 사용자 승인 후 다음 단계 진행

Step 3. CLAUDE.md 작성 (실행 전 필수)
        - 루트 CLAUDE.md (프로젝트 전역)
        - agents/planner/CLAUDE.md
        - agents/executor/CLAUDE.md
        - agents/evaluator/CLAUDE.md

Step 4. 실행
        - planner → executor → evaluator 순서 준수
        - 각 단계 산출물 확인 후 다음 단계 진행

Step 5. 피드백 루프
        - evaluator 결과 기반 executor 재실행
        - 반복 오류 발생 시 CLAUDE.md Constraints 업데이트
```

### Generator → Evaluator 원칙
- planner 산출물 없이 executor 실행 금지
- executor 산출물 없이 evaluator 실행 금지
- evaluator Pass 기준: score ≥ 80 AND 치명적 오류 없음

---

## 7. 멀티 에이전트 CLAUDE.md 자동 생성 트리거

### 트리거 조건
아래 중 하나라도 해당하면 CLAUDE.md 자동 생성 절차 실행:
```
- "하네스 엔지니어링으로" 언급 시
- "멀티 에이전트로" 언급 시
- "기획해줘" + 신규 프로젝트 폴더 시작 시
- "진행해" 응답 전 CLAUDE.md 미존재 확인 시
```

### 자동 생성 절차
```
1. 템플릿 로드
   경로: C:\Users\paunj\.claude\templates\harness-agents\
   대상: planner / executor / evaluator CLAUDE.md

2. 프로젝트 스택·범위에 맞게 커스터마이징
   → [커스터마이징 필요] 항목 자동 채움

3. 아래 경로에 생성
   {project_root}/CLAUDE.md          ← 루트
   {project_root}/agents/planner/CLAUDE.md
   {project_root}/agents/executor/CLAUDE.md
   {project_root}/agents/evaluator/CLAUDE.md

4. 생성 완료 보고 후 실행 진행
```

### 생성 완료 보고 형식
```
[CLAUDE.md 생성 완료]
- 루트: /CLAUDE.md ✅
- planner: /agents/planner/CLAUDE.md ✅
- executor: /agents/executor/CLAUDE.md ✅
- evaluator: /agents/evaluator/CLAUDE.md ✅
→ 실행을 시작하겠습니다.
```

---

## 8. 에이전트 템플릿 관리

### 템플릿 위치
```
C:\Users\paunj\.claude\
├── CLAUDE.md                              ← 이 파일
└── templates\
    └── harness-agents\
        ├── planner\CLAUDE.md              ← 기획 에이전트 템플릿
        ├── executor\CLAUDE.md             ← 실행 에이전트 템플릿
        └── evaluator\CLAUDE.md            ← 검수 에이전트 템플릿
```

### 템플릿 업데이트 원칙
- 새 과제에서 더 나은 패턴 발견 시 → 템플릿에 반영 요청
- 반복 오류로 Constraints 추가 시 → 템플릿에도 동일 항목 추가
- 과제별 커스터마이징 내용은 템플릿에 반영하지 않음 (과제 전용 CLAUDE.md에만)

---

## 작동 확인 지표
아래가 보이면 이 CLAUDE.md가 제대로 작동 중:
```
✅ diff에 불필요한 변경이 없음 (Surgical Changes)
✅ 첫 번째 코드가 단순하고 과설계 없음 (Simplicity First)
✅ 구현 전에 질문이 옴 — 실수 후가 아님 (Think Before Coding)
✅ 성공 기준이 먼저 제시됨 (Goal-Driven Execution)
✅ 하네스 절차가 자동으로 적용됨
```

---

## CHANGELOG
| 버전 | 날짜 | 내용 |
|------|------|------|
| 1.0 | 2026-04-27 | 초기 작성 |
| 1.1 | 2026-04-27 | 에이전트 템플릿 관리 섹션 추가 (A+C 옵션) |
| 1.2 | 2026-04-28 | Karpathy 4원칙 통합 (Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution) |

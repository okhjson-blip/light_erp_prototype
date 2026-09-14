# EXECUTOR AGENT / CLAUDE.md
> 저장 위치: agents/executor/CLAUDE.md

---

## 역할
planner 산출물(task-plan.md) 기반 Task Management 구현 전담.

## 실행 전 필수 확인
```
□ task-plan.md 존재 확인
□ DB 스키마 (신규 테이블 목록) 숙지
□ API 엔드포인트 목록 숙지
□ 기존 코드 영향 범위 분석 확인
```

## gstack 코딩 규칙 (Next.js + TS + Tailwind)
```
- App Router 구조: app/(tasks)/ 폴더에만 작성
- 컴포넌트: components/tasks/ 폴더에만 작성
- API Route: app/api/tasks/ 폴더에만 작성
- TypeScript: any 타입 금지. 인터페이스는 types/task.ts에 정의
- Tailwind: 기존 클래스 패턴 준수 (신규 커스텀 클래스 최소화)
- DB 접근: lib/db/tasks.ts 파일 신규 생성하여 분리
- 환경변수: .env.local 사용, 하드코딩 금지
```

## 파일 작업 규칙
```
- 기존 파일 수정 전 반드시 백업: 파일명.bak
- 신규 파일만 생성하는 것이 원칙
- 기존 파일 수정이 불가피할 경우: [확인 필요] 태그 후 사용자 승인 받기
```

## DB 마이그레이션 규칙
```
- 신규 테이블만 CREATE
- 기존 테이블 ALTER / DROP 절대 금지
- 마이그레이션 파일: lib/db/migrations/task_*.sql
```

## 출력 형식
```
## 구현 완료 항목
## 생성된 파일 목록 (경로 포함)
## 수정된 기존 파일 (있을 경우 사유 포함)
## 미구현 항목 및 사유
## 테스트 방법
## evaluator 전달 사항
```

## 오류 프로토콜
- [ERROR] 태그로 즉시 표기 + 원인·대안 제시
- 동일 오류 2회 발생 → 즉시 중단 → CLAUDE.md Constraints 업데이트 요청
- TypeScript 타입 오류 → any 우회 금지, 타입 정의 추가

## 자가점검 (출력 전)
```
□ task-plan.md 성공 기준 모두 충족했는가?
□ 기존 파일 수정 없이 구현됐는가? (수정 있으면 사유 명시)
□ 신규 파일이 지정 폴더(tasks/)에만 생성됐는가?
□ 하드코딩 없이 환경변수 사용됐는가?
□ TypeScript 타입이 정의됐는가?
□ 백업 파일 생성됐는가? (기존 파일 수정 시)
```

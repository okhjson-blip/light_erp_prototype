---
paths:
  - "**/*.{ts,tsx,js,jsx,py,go,rs,java,cs}"
---
# Security Rules
- 외부 입력은 신뢰 경계에서 검증한다.
- 인증과 인가는 분리해 확인한다.
- SQL, shell, template 호출은 매개변수화한다.
- 시크릿과 개인정보를 로그에 남기지 않는다.
- 보안 관련 변경은 `security-reviewer` 검토를 거친다.

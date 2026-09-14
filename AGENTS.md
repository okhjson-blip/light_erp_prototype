# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Codex Sub-Agent / Review 체계

이 프로젝트의 지침은 Codex에서 읽히는 `AGENTS.md`를 기준으로 한다. 과거 Claude용
하네스 파일명은 더 이상 Codex의 1차 지침으로 간주하지 않는다. 필요한 경우 해당 파일은
역사적 참고 자료로만 읽고, 실제 작업 규칙은 이 파일과 프로젝트의 현재 코드/테스트를
우선한다.

| 역할 | Codex 기준 운용 |
|---|---|
| Orchestrator | 현재 Codex 세션이 목표, 범위, 검증 기준을 관리한다. |
| Planner | 큰 작업에서만 간단한 계획을 세우고, 구현 전 불확실성을 좁힌다. |
| Executor | 계획과 사용자 요청에 맞춰 최소 범위로 구현한다. |
| Evaluator | 테스트, 빌드, 수동 검수로 결과를 확인하고 미검증 항목을 명시한다. |
| Memory 규칙 | 행동 규칙은 `AGENTS.md`, 지속 사실/결정은 `memory/MEMORY.md`와 `memory/USER.md`에 둔다. |

Windows 또는 다른 사용자 환경의 예전 템플릿 경로는 이 프로젝트에서 사용하지 않는다.
현재 macOS Codex 환경의 실제 경로와 파일만 신뢰한다.

---

## Hermes 폐쇄형 학습 루프 (Codex 적용)

`/Users/greeme/Codex/AGENTS.md`와 `/Users/greeme/Codex/work/codex-memory/`의
폐쇄형 자기성장 에이전트 방식을 이 프로젝트에 적용한다. Hermes 원본은 참고
아키텍처일 뿐이며, Codex에서는 아래 로컬 파일과 절차로 매핑한다.

**세션 시작 시 로드**: 존재하는 경우 `memory/MEMORY.md`, `memory/USER.md`를 읽고,
관련 프로젝트 지침과 현재 코드 상태를 함께 확인한다.

**관련 파일**:
- `memory/SESSION_LOG.md` — 세션별 이력(날짜/주제/핵심 인사이트/다음 액션), append-only
- `memory/SKILLS_USAGE.json` — 이 프로젝트에서 파생된 스킬 사용 추적(존재하는 경우)

**자동 메모리 저장 트리거**:
| 트리거 | 저장 위치 |
|---|---|
| 유저 선호/스타일 언급 | `memory/USER.md` |
| 환경 사실 발견(툴/경로/설정) | `memory/MEMORY.md` |
| 실수 수정("그렇게 하지 마세요") | `memory/MEMORY.md` |
| 기능 완료 기록 중 재사용 가치가 있는 내용 | `memory/MEMORY.md` 또는 `memory/SESSION_LOG.md` |
| 유저 명시적 "기억해줘" | 적합한 메모리 파일 |

**Curator 사이클(간이)**: 매 주요 작업 완료 시점에 오래 남길 가치가 있는 사실,
실수 방지 규칙, 재사용 가능한 절차만 저장한다. 일회성 작업 서사는 저장하지 않는다.

**스킬 자동 생성 트리거**: 복잡한 멀티스텝 태스크 완료 / 동일 패턴 2회 이상 반복 /
유저 명시적 요청 / 조사로 해결한 난제. 발생 시 `.agents/skills/<skill-name>/SKILL.md`
또는 전역 Codex 스킬 저장소에 절차형 지식으로 정리한다.

**핵심 원칙**: 자율적 학습(요청 없이도 중요한 것 저장) · 투명성(변경 시 명시) ·
점진적 성장 · 중복 회피(같은 정보를 memory와 AGENTS.md에 동시에 쓰지 않음).

## Imported Codex project instructions

Codex는 이 프로젝트에서 현재 `AGENTS.md`, 프로젝트 `memory/`, `.agents/skills/`,
그리고 `/Users/greeme/Codex`의 전역 Codex 메모리/스킬을 우선 사용한다. 과거
`/Users/greeme/Claude` 아래의 Claude 전용 지침은 Codex로 이전되지 않은 참고 자료로만
취급하며, 현재 프로젝트 작업을 지배하지 않는다.

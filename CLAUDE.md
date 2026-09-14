# CLAUDE.md

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

## Sub-Agent 체계 (Harness → Planner → Executor → Evaluator)

이 프로젝트는 `/Users/greeme/Claude` 전역 템플릿(Harness Engineering)에서 파생된 멀티 에이전트 체계를 사용한다. 파일은 프로젝트 루트에 위치(별도 `agents/` 폴더로 분리하지 않음 — 현재 규모에서는 불필요한 재구조화로 판단):

| 역할 | 파일 | 요약 |
|---|---|---|
| Orchestrator | `Harness_CLAUDE.md` | 전체 절차 강제(Planner→Executor→Evaluator 순서, 반복 오류 2회 시 중단) |
| Planner | `consultingWizard_planner_CLAUDE.md` | 설계만 담당, 코드 작성 금지, task-plan.md 산출 |
| Executor | `consultingWizard_EXECUTOR_CLAUDE.md` | task-plan.md 기반 구현, 자가점검 후 evaluator 전달 |
| Evaluator | `consultingWizard_evaluator_CLAUDE.md` | 산출물 검수만(직접 수정 금지), score≥80 & 치명오류 없음이 Pass 기준 |
| Memory 규칙 | `Memory_CLAUDE.md` | CLAUDE.md(행동규칙) vs MEMORY.md(사실/결정) 구분 기준, 작업공간/참고자료 관리 |

원본 전역 템플릿(`C:\Users\paunj\.claude\...` 경로 참조)은 이 프로젝트를 마운트하는 세션에서 직접 접근 불가(보호 경로 충돌로 `/Users/greeme/Claude` 최상위 마운트 실패) — 위 5개 파일이 이미 이 프로젝트에 반영된 동일 내용의 인스턴스이므로 이를 유효한 소스로 사용한다.

---

## 🔄 Hermes 폐쇄형 학습 루프 (Closed Learning Loop)

`/Users/greeme/Claude/hermes-cowork`의 폐쇄형 자기성장 에이전트 기법을 이 프로젝트에 적용한다. hermes-cowork 원본은 범용 템플릿(파일 경로: `hermes-cowork/MEMORY.md` 등, 2,200/1,375자 하드 한도)이며, 이 프로젝트는 이미 `Memory_CLAUDE.md` 기반의 자체 메모리 체계(`memory/MEMORY.md`, `memory/USER.md`, 하드 한도 없음 — 프로젝트 이력이 이미 한도를 초과하는 규모)를 운영 중이므로, 템플릿을 그대로 복사하지 않고 **경로만 이 프로젝트 것으로 매핑**해 메커니즘을 적용한다.

**세션 시작 시 로드**: `memory/MEMORY.md`, `memory/USER.md` (이미 매 세션 로드 중 — Memory_CLAUDE.md §1과 동일 원칙)

**관련 파일**:
- `memory/SESSION_LOG.md` — 세션별 이력(날짜/주제/핵심 인사이트/다음 액션), append-only, 2026-07-05부터 이미 운영 중
- `memory/SKILLS_USAGE.json` — 이 프로젝트에서 파생된 스킬(있을 경우) 사용 추적 + turn_counter (신규 추가)

**자동 메모리 저장 트리거** (hermes-cowork/CLAUDE_HERMES_ADDON.md와 동일 원칙, 유저 요청 불필요):
| 트리거 | 저장 위치 |
|---|---|
| 유저 선호/스타일 언급 | `memory/USER.md` |
| 환경 사실 발견(툴/경로/설정) | `memory/MEMORY.md` |
| 실수 수정("그렇게 하지 마세요") | `memory/MEMORY.md` |
| 웨이브/기능 완료 기록 | `memory/MEMORY.md` (기존 §v9, §v10 형식 유지) |
| 유저 명시적 "기억해줘" | 적합한 파일 |

**Curator 사이클(간이)**: 하드 한도가 없으므로 "80% 초과 시 정리"는 적용하지 않되, 매 웨이브(v9, v10, ...) 완료 시점마다 `memory/SESSION_LOG.md`에 요약 1건을 남기고, `memory/MEMORY.md`가 지나치게 길어져 가독성이 떨어지면(대략 40~50개 § 초과) 오래된/완료된 웨이브 항목을 통합 제안한다.

**스킬 자동 생성 트리거**: 복잡한 멀티스텝 태스크 완료 / 동일 패턴 2회 이상 반복 / 유저 명시적 요청 / 조사로 해결한 난제 — 발생 시 `memory/SKILLS_USAGE.json`에 기록.

**슬래시 커맨드**: `/curator`(즉시 리뷰), `/curator status`(상태 출력), `/memory`, `/user`, `/sessions`.

**핵심 원칙**: 자율적 학습(요청 없이도 중요한 것 저장) · 투명성(변경 시 명시) · 점진적 성장 · 중복 회피(같은 정보를 memory/MEMORY.md와 CLAUDE.md에 동시에 쓰지 않음).

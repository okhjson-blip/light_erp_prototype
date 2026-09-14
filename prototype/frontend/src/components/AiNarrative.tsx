// AI Agent 카드 전용 — 규칙기반 수치(rationale)와 AI 서술(ai_narrative)을 시각적으로 분리한다
// (ui-identity.md "AI Agent 전용" 규칙). 톤다운된 배경 박스로 감싸 표 안의 다른 숫자 컬럼과 구분.
export function AiNarrative({ text }: { text: string }) {
  return <p className="rounded-control bg-brand-soft/50 px-2 py-1 text-xs text-text-secondary">{text}</p>
}

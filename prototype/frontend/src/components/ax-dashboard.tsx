// 이 파일은 자동 생성된 사본이다. 직접 수정하지 말 것.
// SSOT: AX-Platform/platform/packages/design-system/src/components/Dashboard.tsx
// 갱신: AX-Platform/platform/sync-dashboard-ui.sh

// 전사 표준 대시보드 프리미티브 (ADR-001 확장, 2026-07-31).
//
// SSOT. MES 포털 대시보드의 룩앤필을 9개 업무 시스템 전체가 공유하기 위한 기준 구현이다.
// 각 앱의 `components/ax-dashboard.tsx`는 이 파일의 사본이며, 수정은 반드시 여기서 먼저 한다.
//
// 이식성 원칙 — 앱마다 Tailwind v3(preset 사용)와 v4(CSS-first)가 섞여 있고 lucide 유무도 다르다.
// 그래서 이 파일은 다음만 사용한다.
//   1. Tailwind v3/v4 양쪽에 모두 존재하는 기본 유틸리티 클래스
//   2. 인라인 SVG 아이콘 (아이콘 라이브러리 의존 없음)
//   3. status 색은 토큰과 동일한 기본 팔레트로 표현한다
//      normal #22C55E = green-500 / warning #F59E0B = amber-500 / danger #EF4444 = red-500
// `bg-status-*` 같은 커스텀 클래스는 쓰지 않는다. axPreset이 없는 앱에서 색이 사라지기 때문이다.
import * as React from "react";

export type DashboardStatus = "normal" | "warning" | "danger";
export type DashboardTrend = "up" | "down" | "flat";

function join(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

const STATUS_STYLE: Record<DashboardStatus, { dot: string; bar: string; badge: string; label: string }> = {
  normal: { dot: "bg-green-500", bar: "bg-green-500", badge: "bg-green-50 text-green-700", label: "정상" },
  warning: { dot: "bg-amber-500", bar: "bg-amber-500", badge: "bg-amber-50 text-amber-700", label: "주의" },
  danger: { dot: "bg-red-500", bar: "bg-red-500", badge: "bg-red-50 text-red-700", label: "위험" },
};

const TREND_STYLE: Record<DashboardTrend, { color: string; path: string }> = {
  up: { color: "text-green-600", path: "M3 17l6-6 4 4 8-8M15 7h6v6" },
  down: { color: "text-red-600", path: "M3 7l6 6 4-4 8 8M15 17h6v-6" },
  flat: { color: "text-gray-400", path: "M5 12h14" },
};

function TrendIcon({ trend }: { trend: DashboardTrend }): React.ReactElement {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={TREND_STYLE[trend].path} />
    </svg>
  );
}

// ---------- 섹션 제목 ----------

export interface DashboardSectionProps {
  title: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function DashboardSection({ title, hint, children, className }: DashboardSectionProps): React.ReactElement {
  return (
    <section className={join("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <h2 className="text-[13px] font-bold text-gray-800">{title}</h2>
        {hint ? <span className="text-[11px] text-gray-400">{hint}</span> : null}
      </div>
      {children}
    </section>
  );
}

// ---------- KPI 카드 ----------

export interface DashboardKpi {
  id: string;
  title: string;
  value: string | number;
  unit?: string;
  status?: DashboardStatus;
  trend?: DashboardTrend;
  trendLabel?: string;
  onClick?: () => void;
}

export function DashboardKpiCard({
  title, value, unit, status = "normal", trend = "flat", trendLabel, onClick,
}: Omit<DashboardKpi, "id">): React.ReactElement {
  const style = STATUS_STYLE[status];
  const interactive = Boolean(onClick);
  return (
    <div
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={interactive ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.(); } } : undefined}
      className={join(
        "bg-white rounded border border-gray-200 p-3 pb-0 flex flex-col gap-2 overflow-hidden transition-shadow",
        interactive && "cursor-pointer hover:shadow-md hover:border-blue-300",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-gray-500 leading-tight truncate">{title}</span>
        <span className={join("w-2 h-2 rounded-full shrink-0", style.dot)} />
      </div>

      <div className="flex items-end gap-1">
        <span className="text-xl font-bold text-gray-900 leading-none">{value}</span>
        {unit ? <span className="text-[11px] text-gray-400 mb-0.5">{unit}</span> : null}
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className={join("flex items-center gap-0.5 text-[11px] font-medium", TREND_STYLE[trend].color)}>
          <TrendIcon trend={trend} />
          {trendLabel ? <span>{trendLabel}</span> : null}
        </span>
        <span className={join("text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0", style.badge)}>
          {style.label}
        </span>
      </div>

      {/* 카드 하단 상태 바 — 좌우 패딩을 상쇄해 카드 폭 전체를 채운다. */}
      <div className={join("h-0.5 -mx-3 mt-1", style.bar)} />
    </div>
  );
}

export interface DashboardKpiGridProps {
  items: DashboardKpi[];
  className?: string;
}

export function DashboardKpiGrid({ items, className }: DashboardKpiGridProps): React.ReactElement {
  return (
    <div className={join("grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3", className)}>
      {items.map((item) => (
        <DashboardKpiCard key={item.id} {...item} />
      ))}
    </div>
  );
}

// ---------- 메뉴 카드 ----------

export type DashboardMenuTone =
  | "purple" | "blue" | "green" | "amber" | "cyan" | "rose" | "gray" | "indigo";

const MENU_TONE: Record<DashboardMenuTone, string> = {
  purple: "bg-purple-50 border-purple-200 text-purple-700 hover:border-purple-400",
  blue: "bg-blue-50 border-blue-200 text-blue-700 hover:border-blue-400",
  green: "bg-green-50 border-green-200 text-green-700 hover:border-green-400",
  amber: "bg-amber-50 border-amber-200 text-amber-700 hover:border-amber-400",
  cyan: "bg-cyan-50 border-cyan-200 text-cyan-700 hover:border-cyan-400",
  rose: "bg-rose-50 border-rose-200 text-rose-700 hover:border-rose-400",
  gray: "bg-gray-50 border-gray-200 text-gray-700 hover:border-gray-400",
  indigo: "bg-indigo-50 border-indigo-200 text-indigo-700 hover:border-indigo-400",
};

/** 톤 순서. 카테고리 수가 톤 수보다 많으면 순환한다. */
export const MENU_TONE_ORDER: DashboardMenuTone[] = [
  "purple", "blue", "green", "amber", "cyan", "rose", "gray", "indigo",
];

export function toneForIndex(index: number): DashboardMenuTone {
  return MENU_TONE_ORDER[index % MENU_TONE_ORDER.length];
}

export interface DashboardMenu {
  id: string;
  label: string;
  caption?: string;
  tone?: DashboardMenuTone;
  icon?: React.ReactNode;
  onClick?: () => void;
  href?: string;
}

export function DashboardMenuCard({
  label, caption, tone = "gray", icon, onClick, href,
}: Omit<DashboardMenu, "id">): React.ReactElement {
  const className = join(
    "rounded border p-3 flex flex-col items-center justify-center gap-2 text-center transition-all hover:shadow-sm",
    MENU_TONE[tone],
  );
  const body = (
    <>
      <span className="flex items-center justify-center h-5">{icon ?? <MenuFallbackIcon />}</span>
      <span className="text-[12px] font-semibold leading-tight">{label}</span>
      {caption ? <span className="text-[10px] opacity-60">{caption}</span> : null}
    </>
  );
  if (href) {
    return <a href={href} className={className}>{body}</a>;
  }
  return <button type="button" onClick={onClick} className={className}>{body}</button>;
}

function MenuFallbackIcon(): React.ReactElement {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 21V9" />
    </svg>
  );
}

export interface DashboardMenuGridProps {
  items: DashboardMenu[];
  className?: string;
}

export function DashboardMenuGrid({ items, className }: DashboardMenuGridProps): React.ReactElement {
  return (
    <div className={join("grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3", className)}>
      {items.map((item, index) => (
        <DashboardMenuCard key={item.id} {...item} tone={item.tone ?? toneForIndex(index)} />
      ))}
    </div>
  );
}

// ---------- 페이지 셸 ----------

export interface DashboardShellProps {
  children: React.ReactNode;
  className?: string;
}

/** 모든 시스템 대시보드의 바깥 여백과 섹션 간격을 통일한다. */
export function DashboardShell({ children, className }: DashboardShellProps): React.ReactElement {
  return <div className={join("p-4 space-y-5 bg-gray-100 min-h-full", className)}>{children}</div>;
}

// ---------- 상태 판정 도우미 ----------

export interface ThresholdOptions {
  /** 이 값 이상이면 위험. */
  danger?: number;
  /** 이 값 이상이면 주의. */
  warning?: number;
  /** true면 값이 작을수록 위험(예: 가동률, 달성률). */
  lowerIsWorse?: boolean;
}

/** KPI 값에서 상태를 일관되게 계산한다. 시스템마다 임계값만 다르게 준다. */
export function statusFor(value: number, options: ThresholdOptions): DashboardStatus {
  const { danger, warning, lowerIsWorse = false } = options;
  const breach = (limit?: number) =>
    limit !== undefined && (lowerIsWorse ? value <= limit : value >= limit);
  if (breach(danger)) return "danger";
  if (breach(warning)) return "warning";
  return "normal";
}

/** 증감값을 화살표 방향과 라벨로 바꾼다. */
export function trendFor(delta: number, unit = ""): { trend: DashboardTrend; trendLabel: string } {
  if (delta > 0) return { trend: "up", trendLabel: `+${delta}${unit}` };
  if (delta < 0) return { trend: "down", trendLabel: `${delta}${unit}` };
  return { trend: "flat", trendLabel: `±0${unit}` };
}

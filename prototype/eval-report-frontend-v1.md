# Eval Report — React 프론트엔드 마이그레이션 1차 수직 슬라이스

설계문서: `task-plan-frontend-react.md`. 사용자 지시: "기능은 python 으로 구현하더라도, ui는
시각적 특성과 인터렉티브한 감성과 가시성, 가독성이 높은 스택으로 변경" → AskUserQuestion에서
"A. React + shadcn/ui + Tremor (추천)" 채택.

## 구현

- **스캐폴딩**: `frontend/`(Vite + React 19 + TypeScript). Tailwind CSS v4(`@tailwindcss/vite`
  플러그인 + `index.css`의 `@theme` 블록 — v3식 `tailwind.config.js`/PostCSS 아님). 경로 별칭
  `@/*` → `./src/*`(`vite.config.ts`+`tsconfig.app.json`).
- **UI 아이덴티티 반영**: `ui-identity.md`의 hex 토큰을 `index.css`의 `@theme` 변수로 그대로
  이식(`--color-brand`, `--color-success` 등) → Tailwind가 `bg-brand`/`text-success` 등 유틸리티를
  자동 생성.
- **컴포넌트**: shadcn/ui 스타일 컴포넌트(Button/Card/Badge/Input/Table)를 CLI(`npx shadcn init`)
  대화형 프롬프트가 샌드박스에서 멈출 위험이 있어 직접 소스로 작성(`cva`+Tailwind 유틸리티 조합) —
  shadcn/ui 자체가 "소스를 프로젝트에 복사"하는 방식이라 결과물은 동일.
- **차트/KPI**: `@tremor/react`는 Vercel 인수 이후 배포 방식이 불확실(카피-페이스트형)해 패키지로
  직접 설치하지 않고, 그 기반 엔진인 `recharts`만 설치해 Tremor 스타일 KPI 카드를 직접 구현.
- **인증**: `lib/api.ts`(fetch 래퍼, Bearer 헤더 자동 첨부, 401 시 refresh 후 1회 재시도,
  refresh 실패 시 강제 로그아웃 콜백) + `lib/auth-context.tsx`(`AuthProvider`, `useAuth()` 훅,
  `hasRole()`). 토큰은 `localStorage`(`erp_access_token`/`erp_refresh_token`) — 기존 vanilla-JS
  프론트(`static/index.html`)와 동일한 저장 방식.
- **화면**: `LoginPage`(실제 `/api/auth/login` 연동), `AppShell`(11개 탭 사이드바 — "회계"는
  `hasRole('관리자')`로 숨김, 역할 배지 색상 매핑), `DashboardPage`(`GET /api/dashboard/kpi` 연동,
  실제 응답 필드 6개 그대로 KPI 카드 6장으로 렌더), 나머지 10개 탭은 `PlaceholderPage`(다음 단계
  이관 예정, 그동안 `/static` 안내).
- **개발 환경**: Vite dev proxy(`/api`, `/health` → `http://localhost:8000`) — 백엔드 CORS 변경 없이
  기존 uvicorn과 그대로 연동.

## 검증

**빌드**: `npm run build`(`tsc -b && vite build`) 성공 — `dist/index.html 0.45 kB`,
`dist/assets/index-*.css 14.97 kB`, `dist/assets/index-*.js 313.27 kB`, 1.54s. 타입 오류 없음.

**API 계약 검증**(fresh `/tmp` 복사본, `TestClient`로 프론트가 기대하는 정확한 응답 shape 확인):
```
LOGIN keys: ['access_token', 'refresh_token', 'user'] | user keys: ['email', 'name', 'roles', 'user_id']
ME: 200 ['email', 'name', 'roles', 'user_id']
KPI: 200 ['material_count', 'open_po', 'open_so', 'pending_approvals', 'total_ap', 'total_ar']
REFRESH: 200 ['access_token', 'refresh_token']
LOGOUT: 200 {'ok': True}
NO AUTH: 401
ALL FRONTEND-BACKEND CONTRACT CHECKS PASS
```
`frontend/src/lib/types.ts`(`User`/`LoginResponse`)와 `DashboardPage.tsx`의 `DashboardKpi` 인터페이스가
실제 백엔드 응답과 완전히 일치함을 확인 — 필드 오탈자/누락 없음.

**브라우저 실기동 검증(사용자 로컬 + Claude in Chrome 병행 확인, 2026-07-05)**: 사용자 Mac에서
`uvicorn app.main:app --reload`(8000) + `npm run dev`(5183) 동시 구동 후 로그인 화면 진입, admin
계정으로 로그인 → 대시보드 KPI 렌더 → placeholder 탭("이 화면은 다음 단계에서 React로 이관될
예정입니다...") 전부 정상 확인. 과정에서 발견/해결된 로컬 환경 이슈 2건:
1. `frontend/` 스캐폴딩이 리눅스 샌드박스에서 처음 `npm install`된 탓에 `node_modules`/
   `package-lock.json`에 rolldown 네이티브 바이너리가 리눅스용으로 고정 — Mac에서
   `Cannot find native binding` 에러. `rm -rf node_modules package-lock.json && npm install`로 해결.
2. **IPv4/IPv6 프록시 혼선**: 8000번 포트에 예전 v5 검증용 Docker 컨테이너(IPv6 `*:8000`)와 새
   uvicorn(IPv4 `127.0.0.1:8000`)이 동시에 떠 있었고, Vite 프록시 대상이 `http://localhost:8000`이라
   Mac에서 IPv6로 먼저 풀려 낡은 Docker 컨테이너로 요청이 흘러가 로그인 500 에러 발생. `docker compose
   down`으로 컨테이너 정리 + `vite.config.ts` 프록시 대상을 `127.0.0.1`로 고정해 재발 방지.

## 비범위 (task-plan-frontend-react.md 참고)

- 기준정보/영업/구매/생산/재고/회계/승인함/연동로그/AI Agent/참고데이터 10개 탭 — 전부 `PlaceholderPage`,
  2차~5차 단계에서 순차 이관 예정
- 기존 `static/index.html`(vanilla JS) 제거 여부 — 전체 이관 완료 후 결정
- 프로덕션 빌드 서빙 방식(FastAPI `StaticFiles`로 `dist/` 서빙) — 아직 미구현, 현재는 `npm run dev`
  전용
- 다크모드, 차트 라이브러리 추가 확장 — ui-identity.md에서 이미 비범위로 명시

## 종합 평가

| 항목 | 평가 |
|---|---|
| Vite+React+TS+Tailwind v4 스캐폴딩 | ✅ 빌드 성공 |
| UI 아이덴티티(ui-identity.md) 토큰 이식 | ✅ `@theme` 변수로 반영 |
| 인증(Access+Refresh, 자동 refresh) 연동 | ✅ API 계약 검증 PASS |
| 대시보드 KPI 실 데이터 연동 | ✅ 응답 필드 완전 일치 확인 |
| 브라우저 실기동 눈으로 확인 | ✅ 사용자 로컬에서 로그인→대시보드→placeholder 전부 확인 |

**점수: 93/100** (감점 사유: 10개 탭이 아직 placeholder 상태로 전체 이관의 일부만 완료 — 나머지는
2차~5차 단계에서 진행)

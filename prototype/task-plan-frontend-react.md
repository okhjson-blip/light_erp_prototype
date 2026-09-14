# Task Plan — React 프론트엔드 마이그레이션 (v7)

사용자 지시: "기능은 python으로 구현하더라도, UI는 시각적 특성과 인터랙티브한 감성과 가시성,
가독성이 높은 스택으로 변경" → 스택 비교 제시 후 **A안(React + shadcn/ui + Tremor)** 선택.

## 왜 이 스택인가

백엔드(`app/main.py` 등)는 이미 순수 JSON REST API + JWT Bearer 인증으로 완전히 분리돼 있어,
React SPA가 기존 API를 **그대로** 호출하면 되고 백엔드 변경이 전혀 필요 없다. `ui-identity.md`에서
정의한 컬러/타이포/컴포넌트 규칙을 Tailwind 설정값으로 그대로 옮겨 참조 이미지(Boltshift/Vault/
EduNova 등 shadcn 계열 어드민 템플릿)에 가장 가깝게 재현할 수 있다.

## 디렉토리 구조

```
prototype/
  app/            # 기존 FastAPI 백엔드 (변경 없음)
  static/         # 기존 vanilla JS 화면 (당분간 유지, 완전 이관 후 제거 검토)
  frontend/       # 신규 React 앱
    src/
      lib/        # api client, auth context, 타입
      components/ # 공용 컴포넌트 (AppShell, KpiCard, StatusPill, DataTable ...)
      pages/       # 페이지별(로그인/대시보드/영업/구매/...) 컴포넌트
      routes.tsx
      main.tsx
    vite.config.ts
    tailwind.config.ts
```

## 빌드/배포 전략

- **개발 중**: `npm run dev`(Vite, 기본 5173포트)로 실행하고, `vite.config.ts`의 `server.proxy`로
  `/api`, `/health`를 `http://localhost:8000`(기존 uvicorn)으로 전달한다. CORS 설정 등 백엔드 변경
  없이 개발 가능(프록시가 브라우저 입장에서 동일 오리진처럼 보이게 함).
- **운영 빌드**: `npm run build` → `frontend/dist/`를 FastAPI의 `StaticFiles`가 서빙(기존
  `static/` 서빙 방식과 동일한 패턴, `app/main.py`의 마운트 경로만 `dist/`로 교체). 완전 이관 전까지는
  기존 `static/index.html`을 그대로 두고 `frontend`는 별도 경로(`/app` 등)로 우선 병행 배치해
  회귀 리스크 없이 점진 전환한다.

## 인증 플로우 (기존 백엔드 계약 그대로 재현)

- 로그인: `POST /api/auth/login` → `{access_token, refresh_token, user}` 저장(localStorage).
- 매 API 호출: `Authorization: Bearer <access_token>`.
- 401 수신 시: `POST /api/auth/refresh`로 회전된 새 access+refresh 토큰 획득 후 원요청 1회 재시도
  (v6 회전 정책과 동일 — 실패 시 로그아웃).
- 로그아웃: `POST /api/auth/logout` + 로컬 토큰 삭제.
- 역할(roles)에 따라 사이드바 메뉴/버튼을 조건부 렌더링(`hasRole()` 헬퍼, 기존 프론트 로직과 동일 개념).

## Tailwind 테마 매핑 (ui-identity.md → tailwind.config.ts)

| identity 토큰 | Tailwind 키 |
|---|---|
| `--brand` #2F6FED | `brand.DEFAULT` |
| `--brand-soft` #EAF1FF | `brand.soft` |
| `--success`/`--success-bg` | `success.DEFAULT`/`success.soft` |
| `--warning`/`--warning-bg` | `warning.DEFAULT`/`warning.soft` |
| `--danger`/`--danger-bg` | `danger.DEFAULT`/`danger.soft` |
| `--bg-canvas` #F5F7FA | `canvas` |
| radius 12px/8px | `rounded-xl`/`rounded-lg` 기본값 조정 |

## 페이지 이관 순서 (단계적, 매 단계 빌드 검증 후 다음 진행)

1. **1차(이번 단계)**: 로그인, 앱 셸(사이드바+상단바), 대시보드
2. 2차: 기준정보, 영업, 구매
3. 3차: 생산, 재고(LOT/시리얼/정합성)
4. 4차: 회계, 승인함, 연동 로그
5. 5차: AI Agent, 참고 데이터
6. 마무리: `static/index.html` 제거 여부 결정, README/문서 갱신, 실사용 회귀 확인

각 단계는 shadcn/ui 컴포넌트(Button/Card/Table/Badge/Input/Select)와 Tremor 차트 컴포넌트를
재사용해 신규 코드량을 최소화한다.

## 비범위
- 백엔드 API 변경(엔드포인트/응답 스펙 동일 유지)
- 상태관리 라이브러리(Redux 등) 도입 — React Query만으로 서버 상태 충분, 클라이언트 전역 상태는
  Context로 최소화
- SSR/Next.js 전환 — 내부 ERP 도구라 CSR SPA로 충분, 빌드 단순성 우선

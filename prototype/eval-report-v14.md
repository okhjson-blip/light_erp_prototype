# Eval Report — v14 (06 Quality Management 확장)

**날짜**: 2026-07-11 · **평가 기준**: consultingWizard_evaluator_CLAUDE.md (score≥80 & 치명오류 없음 = Pass)

## 범위 (task-plan-v9-full-menu-rollout.md §3 v14)

검사기준관리 / 수입·공정·출하검사 구분 / SPC(Cp/Cpk) / 공정능력분석 / 부적합관리 강화 /
8D Report(간이) / 고객클레임관리 / CAPA 등록·처리 워크플로 / 품질 Dashboard.

## 구현 요약

| 구분 | 내용 |
|---|---|
| 마이그레이션 | 0008 — inspection_standard/eight_d_report/customer_claim/capa_action 4개 테이블 (additive) |
| 백엔드 | app/quality_ext.py (prefix /api/quality) 14개 엔드포인트. 기존 POST /api/quality/inspections(v3 QMS)는 무변경 재사용 |
| 프론트 | QualityPage.tsx 신설 7탭(품질 현황/검사기준/검사이력/SPC·공정능력/부적합/고객클레임/8D·CAPA) + /quality 라우트 + 사이드바(ShieldCheck) |
| 테스트 | tests/test_quality_ext.py 14개 신규 — 기존 126 + 14 = **140개 전부 PASS** |

## 핵심 설계 결정

1. **검사구분**: quality_inspection.inspection_type이 v1부터 존재 → 신규 컬럼 없이 필터 API만 추가.
2. **SPC는 프로토타입 근사**: 측정치 원본이 없어 defect_ppm을 특성치로 p-관리도 통계(평균/±3σ/이탈 점)
   계산. Cp/Cpk는 검사기준의 LSL/USL 등록 시에만 계산(미등록 시 "기준 없음" + 안내). 관리도 시각화는
   task-plan 명시 제외.
3. **CAPA 승격**: capa_required='Y'인데 조치 미연결인 검사 = "CAPA 후보"로 자동 노출(89건), CAPA 등록 시
   해당 검사가 후보에서 빠지는 연결 플로우. AI Quality Engineer 추천(조회전용)과 자연 연계.
4. **권한**: 쓰기 = 생산담당+관리자(v3 QMS 절충 유지, "품질담당" 역할 없음). 예외 — 고객클레임 등록만
   영업담당도 허용(고객 접점), 상태 변경은 품질 권한.
5. **8D는 간이**(D2 문제/D4 근본원인/D5 시정조치): 전체 D1~D8 양식은 Enterprise 이연.
6. **부적합관리**: 신규 테이블 없이 DEFECTIVE 시리얼 + FAIL 검사 통합 조회, 처리는 v13 재작업 플로우로 안내.

## 검증

- pytest 140/140 PASS, tsc -b 통과
- 브라우저 라이브: /quality 딥링크, 품질 현황 KPI(검사 180건/평균 PPM 1444.2/FAIL 9/CAPA 후보 89건),
  SPC 실계산(Smart Mini Fan: 표본 36/평균 1365.4/UCL 3669/이탈 0, Cp·Cpk 기준없음 안내), 콘솔 에러 없음
- 테스트 중 발견: 데이터셋 검사이력은 RM이 아닌 FG 품목에만 존재 → SPC 테스트가 품목을 동적 선택하도록 수정

## 리스크/이월

- **데이터셋 inspection_type 불일치**: 시드 데이터는 "OUTGOING" 등 자유 문자열, 신규 등록은
  INCOMING/IN_PROCESS/FINAL enum — 검사이력 필터에서 시드 데이터가 구분 필터에 안 잡힘(전체 조회는 정상).
  시드 타입 정규화는 데이터 마이그레이션 필요라 이월(후속 웨이브 후보).
- 기존 POST /api/quality/inspections의 inspection_type은 여전히 자유 입력(무변경 원칙) — 프론트 QMS 폼의
  select 전환은 UI 폴리시 후보.
- customer_claim(v14 품질)과 logistics_claim(v12 물류)은 별개 도메인(고객 vs 운송) — 이름 유사성 주의.

## 판정

**Score: 91/100 — PASS**
다음: v15(07 Engineering(R&D) 신규 — BOM 트리 UI/ECO·ECR/도면메타/프로젝트관리).

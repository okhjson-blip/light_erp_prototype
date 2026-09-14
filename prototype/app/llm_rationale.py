"""AI Agent 자연어 근거(narrative) 생성 — v3 LLM 고도화 1단계.

설계 결정(사용자 확인, 2026-07-05): 이번 단계는 템플릿 기반 자연어 생성만 제공한다.
외부 LLM API를 호출하지 않으므로 신규 의존성/토큰 비용이 없다. 통합테스트/현업 검증 단계에서
필요성이 확인되면 이 함수들을 실제 LLM 응답으로 교체하는 다음 단계를 별도로 진행한다.

추천 대상/수치 산출 로직(누가, 얼마나)은 그대로 규칙기반(app/ai_agent.py)을 유지한다 — 이 모듈은
그 결과를 사람이 읽기 편한 한 단락의 자연어로 풀어 쓰는 역할만 한다(Human-in-the-loop 원칙 불변).
"""


def narrate_buyer(rec: dict) -> str:
    parts = [
        f"{rec['name']}({rec['code']})의 현재 재고는 {rec['current_qty']}로 재발주점 "
        f"{rec['reorder_point']}을 밑돌고 있습니다.",
        f"목표재고 {rec['target_stock']}까지 채우려면 {rec['suggested_qty']} 발주가 필요합니다.",
    ]
    if rec.get("recommended_vendor_name"):
        parts.append(f"리드타임이 가장 짧은 {rec['recommended_vendor_name']}에 발주하는 것을 추천합니다.")
    return " ".join(parts)


def narrate_scheduler(e: dict) -> str:
    if e["feasible"]:
        return (
            f"{e['material_name']} 생산오더(#{e['prod_order_id']})는 필요한 자재가 모두 확보되어 "
            f"즉시 착수할 수 있습니다. 우선순위 {e['priority_rank']}위로 배정했습니다."
        )
    shortage_text = "; ".join(e["shortages"])
    return (
        f"{e['material_name']} 생산오더(#{e['prod_order_id']})는 자재 부족으로 착수가 어렵습니다"
        f"({shortage_text}). 우선순위 {e['priority_rank']}위로 밀려났으니 부족 자재의 긴급 조달을 검토하세요."
    )


def narrate_demand_planner(rec: dict) -> str:
    risk = "품절" if "품절" in rec["direction"] else "과잉재고"
    return (
        f"{rec['name']}({rec['code']})은 최근 {rec['avg_mape']}% 수준의 예측오차를 보이며 "
        f"{rec['direction']} 경향입니다. 재발주점을 {rec['current_reorder_point']}에서 "
        f"{rec['suggested_reorder_point']}로, 목표재고를 {rec['current_target_stock']}에서 "
        f"{rec['suggested_target_stock']}로 조정하면 {risk} 리스크를 줄일 수 있습니다."
    )


def narrate_quality(rec: dict) -> str:
    risk_word = "심각한" if rec["risk_level"] == "높음" else "경미한"
    action = (
        "공급사/공정 정밀조사와 CAPA 우선 처리가 필요"
        if rec["recent_fail_count"] > 0 else "예방적 공정 점검을 권장"
    )
    return (
        f"{rec['name']}({rec['code']})은 최근 {rec['sample_size']}건 검사에서 {risk_word} 품질 "
        f"리스크가 감지되었습니다(불량 {rec['recent_fail_count']}건, CAPA {rec['recent_capa_count']}건, "
        f"평균 {rec['avg_defect_ppm']}PPM). {action}합니다."
    )


def narrate_cfo(insight: dict) -> str:
    severity_word = {"GOOD": "긍정적인", "WARN": "주의가 필요한", "INFO": "참고할"}.get(insight["severity"], "참고할")
    return f"{insight['title']}: {insight['detail']} — {severity_word} 신호입니다."

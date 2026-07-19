"""
Investment Memo Generator.
Produces a structured InvestmentMemo from typed pipeline inputs.
Optional sections that lack source data are set to NOT_DISCLOSED — never fabricated.
No LLM calls in this module (narrative polish is a future enhancement).
Never raises.
"""
from dataclasses import dataclass
from typing import List, Optional
from data.founder_data import FounderProfile
from data.risk_flags import RiskFlag
from data.decision_engine import DecisionResult

NOT_DISCLOSED = "[Not Disclosed]"


@dataclass
class InvestmentMemo:
    # Required sections — always present
    company_snapshot: str = ""
    investment_hypotheses: str = ""
    swot: str = ""
    problem_and_product: str = ""
    traction_and_kpis: str = ""
    # Optional sections — default to NOT_DISCLOSED when data is absent
    financials: str = NOT_DISCLOSED
    cap_table: str = NOT_DISCLOSED
    team_bios: str = NOT_DISCLOSED


def _fmt_axes(decision: DecisionResult) -> str:
    if not decision.axes:
        return "No axis scores available."
    lines = []
    for axis in decision.axes:
        lines.append(
            f"- {axis.name}: score={axis.score:.2f}, trend={axis.trend} — {axis.rationale}"
        )
    return "\n".join(lines)


def _fmt_risk_flags(risk_flags: List[RiskFlag]) -> str:
    if not risk_flags:
        return "No risk flags detected."
    lines = []
    for f in risk_flags:
        lines.append(f"- [{f.severity.upper()}] {f.category}: {f.description}")
    return "\n".join(lines)


def _fmt_rules(matched: list, failed: list) -> str:
    parts = []
    if matched:
        parts.append("Thesis rules MATCHED: " + ", ".join(matched))
    if failed:
        parts.append("Thesis rules FAILED: " + ", ".join(failed))
    return " | ".join(parts) if parts else "No thesis rules evaluated."


def generate_memo(
    profile: FounderProfile,
    thesis_result=None,
    risk_flags: Optional[List[RiskFlag]] = None,
    decision: Optional[DecisionResult] = None,
) -> InvestmentMemo:
    """
    Generate an InvestmentMemo from structured pipeline inputs.
    Required sections are always populated.
    Optional sections are set to NOT_DISCLOSED when the source data is absent.
    Never raises.
    """
    try:
        risk_flags = risk_flags or []
        decision = decision or DecisionResult()
        mi = decision.memo_inputs or {}

        company_name = profile.company or profile.name or "Unknown Company"
        sector       = profile.sector or "Unspecified"
        stage        = profile.stage or "Unspecified"
        github_url   = profile.github_url or NOT_DISCLOSED

        # Required: Company Snapshot
        company_snapshot = (
            f"Company: {company_name}\n"
            f"Sector: {sector}\n"
            f"Stage: {stage}\n"
            f"GitHub: {github_url}\n"
            f"Overall Verdict: {decision.overall_verdict}\n"
            f"Data Sources: {', '.join(profile.raw_sources) or 'none'}"
        )

        # Required: Investment Hypotheses
        investment_hypotheses = (
            f"Verdict: {decision.overall_verdict}\n"
            f"{_fmt_rules(mi.get('matched_rules', []), mi.get('failed_rules', []))}\n"
            f"Axis Scores:\n{_fmt_axes(decision)}"
        )

        # Required: SWOT (derived from signals and risk flags)
        high_flags = [f for f in risk_flags if f.severity == "high"]
        med_flags  = [f for f in risk_flags if f.severity == "medium"]
        swot = (
            f"Strengths: GitHub presence detected — {len(profile.raw_sources)} data sources ingested.\n"
            f"Weaknesses: {_fmt_risk_flags(med_flags) if med_flags else 'None identified.'}\n"
            f"Opportunities: Sector ({sector}) alignment with thesis.\n"
            f"Threats: {_fmt_risk_flags(high_flags) if high_flags else 'None identified.'}"
        )

        # Required: Problem & Product
        problem_and_product = (
            f"Company {company_name} operates in the {sector} sector at {stage} stage.\n"
            f"GitHub signals suggest: {', '.join(str(k) for k in (profile.key_signals or {}).keys()) or 'no observable signals'}."
        )

        # Required: Traction & KPIs
        claimed_users = (profile.key_signals or {}).get("claimed_users")
        total_stars   = (profile.key_signals or {}).get("total_stars")
        traction_lines = []
        if claimed_users is not None:
            traction_lines.append(f"Claimed users: {claimed_users:,}")
        if total_stars is not None:
            traction_lines.append(f"GitHub stars (top {len(profile.raw_sources)} repos): {total_stars:,}")
        high_risk_names = ", ".join(mi.get("high_risk_flags", []))
        if high_risk_names:
            traction_lines.append(f"High-severity flags: {high_risk_names}")
        traction_and_kpis = "\n".join(traction_lines) if traction_lines else "No traction data available from sources ingested."

        # Optional sections — only populated if data is present in memo_inputs
        financials = mi.get("financials", NOT_DISCLOSED) or NOT_DISCLOSED
        cap_table  = mi.get("cap_table", NOT_DISCLOSED) or NOT_DISCLOSED
        team_bios  = mi.get("team_bios", NOT_DISCLOSED) or NOT_DISCLOSED

        return InvestmentMemo(
            company_snapshot=company_snapshot,
            investment_hypotheses=investment_hypotheses,
            swot=swot,
            problem_and_product=problem_and_product,
            traction_and_kpis=traction_and_kpis,
            financials=financials,
            cap_table=cap_table,
            team_bios=team_bios,
        )

    except Exception:
        return InvestmentMemo(
            company_snapshot="Error generating memo.",
            investment_hypotheses=NOT_DISCLOSED,
            swot=NOT_DISCLOSED,
            problem_and_product=NOT_DISCLOSED,
            traction_and_kpis=NOT_DISCLOSED,
        )

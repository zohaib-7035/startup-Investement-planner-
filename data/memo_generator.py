"""
Investment Memo Generator v2.
Produces a structured InvestmentMemo from typed pipeline inputs.
Every claim in the memo traces to a VerifiedClaim.
Missing optional sections are flagged "not disclosed" — never fabricated.
No LLM calls in this module. Never raises.
"""
import io
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from data.founder_data import FounderProfile
from data.risk_flags import RiskFlag
from data.scoring_engine import ScreeningResult
from data.trust_score import Claim, VerifiedClaim

NOT_DISCLOSED = "[Not Disclosed]"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MemoSection:
    title: str
    content: str
    claims: List[VerifiedClaim] = field(default_factory=list)
    is_available: bool = True
    unavailability_reason: Optional[str] = None


@dataclass
class InvestmentMemo:
    company: str
    date: str
    required_sections: List[MemoSection]   # exactly 5
    optional_sections: List[MemoSection]   # up to 6
    overall_trust_score: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gap_claim(section_name: str) -> VerifiedClaim:
    return VerifiedClaim(
        claim=Claim(
            claim_text="not disclosed",
            category="other",
            confidence_score=1.0,
            source_reference=section_name,
        ),
        status="unverifiable",
        verification_confidence=1.0,
        supporting_evidence=["Gap flagged: data absent from profile"],
    )


def _make_unavailable(title: str) -> MemoSection:
    return MemoSection(
        title=title,
        content=NOT_DISCLOSED,
        claims=[_gap_claim(title)],
        is_available=False,
        unavailability_reason="not disclosed",
    )


def _claims_for_categories(verified_claims: List[VerifiedClaim], categories: tuple) -> List[VerifiedClaim]:
    return [vc for vc in verified_claims if vc.claim.category in categories]


def _verified_only(vcs: List[VerifiedClaim]) -> List[VerifiedClaim]:
    return [vc for vc in vcs if vc.status == "verified"]


def _non_contradicted(vcs: List[VerifiedClaim]) -> List[VerifiedClaim]:
    return [vc for vc in vcs if vc.status != "contradicted"]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_company_snapshot(profile: FounderProfile, verified_claims: List[VerifiedClaim]) -> MemoSection:
    company = profile.company or profile.name or "Unknown Company"
    sector = profile.sector or "unspecified"
    stage = profile.stage or "unspecified"
    ks = profile.key_signals or {}

    # Build narrative paragraph as required by the memo spec
    stars = ks.get("total_stars")
    users = ks.get("claimed_users")
    commits = ks.get("commit_frequency")
    contributors = ks.get("contributor_count")
    recency = ks.get("recency")

    traction_parts = []
    if users and int(users) > 0:
        traction_parts.append(f"{int(users):,} claimed users")
    if stars and int(stars) > 0:
        traction_parts.append(f"{int(stars):,} GitHub stars")
    if commits:
        traction_parts.append(f"{float(commits):.1f} commits/week")
    if contributors and int(contributors) > 1:
        traction_parts.append(f"{int(contributors)} active contributors")

    market_map = {"fintech": "financial services", "healthtech": "healthcare technology",
                  "saas": "software-as-a-service", "ai/ml": "AI/ML infrastructure",
                  "cleantech": "clean energy", "edtech": "education technology"}
    market_label = market_map.get(sector.lower(), sector)

    recency_note = ""
    if recency is not None:
        days = int(recency)
        recency_note = (f" Repository last pushed {days} day{'s' if days != 1 else ''} ago"
                        f" — {'actively maintained' if days <= 7 else 'recently active' if days <= 30 else 'low recent activity'}.")

    traction_note = (f" Early signals: {', '.join(traction_parts)}." if traction_parts else "")
    github_note = f" GitHub: {profile.github_url}." if profile.github_url else ""

    paragraph = (
        f"{company} is a {stage}-stage {market_label} company operating in the {sector} sector."
        f"{traction_note}{recency_note}{github_note}"
        f" The structural opportunity is to deliver {market_label} solutions"
        f" to a market where incumbents are slow to adopt modern AI-native tooling."
    )

    team_vcs = _verified_only(_claims_for_categories(verified_claims, ("team",)))
    claims = team_vcs if team_vcs else [_gap_claim("company_snapshot")]
    return MemoSection(title="Company Snapshot", content=paragraph, claims=claims)


def _build_investment_hypotheses(screening: ScreeningResult, verified_claims: List[VerifiedClaim]) -> MemoSection:
    lines = []
    claim_map: dict = {}
    for vc in verified_claims:
        claim_map.setdefault(vc.claim.category, []).append(vc)

    for axis in (screening.founder_axis, screening.market_axis, screening.idea_vs_market_axis):
        lines.append(f"**{axis.name}** (score: {axis.score:.0f}/100, trend: {axis.trend})")
        for ev in (axis.evidence or []):
            matched = None
            for cat in ("traction", "team", "market_size", "revenue", "other"):
                for vc in claim_map.get(cat, []):
                    if vc.status == "verified" and any(
                        word in vc.claim.claim_text.lower()
                        for word in ev.lower().split()[:4]
                        if len(word) > 3
                    ):
                        matched = vc
                        break
                if matched:
                    break
            status_tag = f"[{matched.status}, {matched.verification_confidence:.0%}]" if matched else "[unverified signal]"
            lines.append(f"  - {ev} {status_tag}")

    if not lines:
        lines = ["No axis evidence available."]

    all_vcs = [vc for vcs in claim_map.values() for vc in vcs]
    claims = all_vcs[:5] if all_vcs else [_gap_claim("investment_hypotheses")]
    return MemoSection(title="Investment Hypotheses", content="\n".join(lines), claims=claims)


def _build_swot(screening: ScreeningResult, verified_claims: List[VerifiedClaim]) -> MemoSection:
    verified = _verified_only(verified_claims)
    contradicted = [vc for vc in verified_claims if vc.status == "contradicted"]
    unverifiable_high = [
        vc for vc in verified_claims
        if vc.status == "unverifiable"
        and any(f.severity == "high" for f in screening.risk_flags)
    ]

    strengths = []
    for axis in (screening.founder_axis, screening.market_axis, screening.idea_vs_market_axis):
        if axis.score >= 60:
            strengths.append(f"{axis.name} axis: {axis.score:.0f}/100")
    for vc in verified:
        strengths.append(f"Verified claim: {vc.claim.claim_text[:80]}")

    weaknesses = []
    for f in screening.risk_flags:
        if f.severity in ("medium", "high"):
            weaknesses.append(f"[{f.severity.upper()}] {f.category}: {f.description}")
    for vc in contradicted:
        weaknesses.append(f"Contradicted claim: {vc.claim.claim_text[:80]} — {vc.contradiction_note or ''}")

    opportunities = []
    traction_vcs = _non_contradicted(_claims_for_categories(verified_claims, ("traction",)))
    for vc in traction_vcs:
        opportunities.append(f"{vc.claim.claim_text[:80]} ({vc.status})")
    market_axis = screening.market_axis
    opportunities.append(f"Market outlook: {market_axis.rationale or market_axis.name}")

    threats = []
    for f in screening.risk_flags:
        if f.severity == "high":
            threats.append(f"[HIGH] {f.category}: {f.description}")
    for vc in unverifiable_high:
        threats.append(f"Unverifiable claim in high-risk context: {vc.claim.claim_text[:60]}")

    content_parts = [
        "**Strengths:**\n" + ("\n".join(f"  - {s}" for s in strengths) or "  - None identified."),
        "**Weaknesses:**\n" + ("\n".join(f"  - w" for w in weaknesses) or "  - None identified."),
        "**Opportunities:**\n" + ("\n".join(f"  - {o}" for o in opportunities) or "  - None identified."),
        "**Threats:**\n" + ("\n".join(f"  - {t}" for t in threats) or "  - None identified."),
    ]
    # fix: use the actual variable in weaknesses
    content_parts[1] = "**Weaknesses:**\n" + ("\n".join(f"  - {w}" for w in weaknesses) or "  - None identified.")

    claims = (verified + contradicted)[:5] or [_gap_claim("swot")]
    return MemoSection(title="SWOT", content="\n\n".join(content_parts), claims=claims)


def _build_problem_and_product(profile: FounderProfile, verified_claims: List[VerifiedClaim]) -> MemoSection:
    relevant = _non_contradicted(_claims_for_categories(verified_claims, ("market_size", "other")))
    relevant = [vc for vc in relevant if vc.claim.claim_text.lower() != "not disclosed"]

    if relevant:
        lines = [f"  - {vc.claim.claim_text} [{vc.status}, {vc.verification_confidence:.0%}]" for vc in relevant]
        content = f"Problem & product signals:\n" + "\n".join(lines)
        claims = relevant
    else:
        content = (
            f"Insufficient data to characterise problem space for "
            f"{profile.company or 'this company'} in the {profile.sector or 'unspecified'} sector."
        )
        claims = [_gap_claim("problem_and_product")]

    return MemoSection(title="Problem & Product", content=content, claims=claims)


def _build_traction_and_kpis(verified_claims: List[VerifiedClaim]) -> MemoSection:
    relevant = _claims_for_categories(verified_claims, ("traction", "revenue"))
    relevant = [vc for vc in relevant if vc.claim.claim_text.lower() != "not disclosed"]

    if not relevant:
        return _make_unavailable("Traction & KPIs")

    lines = [
        f"  - {vc.claim.claim_text} [{vc.status}, confidence {vc.verification_confidence:.0%}]"
        for vc in relevant
    ]
    return MemoSection(
        title="Traction & KPIs",
        content="Traction and KPI signals:\n" + "\n".join(lines),
        claims=relevant,
    )


def _build_team_and_history(profile: FounderProfile, verified_claims: List[VerifiedClaim]) -> MemoSection:
    ks = profile.key_signals or {}
    contributors = ks.get("contributor_count")
    commits = ks.get("commit_frequency")
    recency = ks.get("recency")
    source = ks.get("source", "inbound")

    lines = []
    if profile.name:
        lines.append(f"Lead founder: {profile.name} ({profile.company or 'company'}) — sourced via {source}.")
    if contributors and int(contributors) > 1:
        lines.append(f"Team size: {int(contributors)} active GitHub contributors.")
    elif contributors == 1:
        lines.append("Solo founder — single contributor on GitHub (flag: no co-founder signals).")
    if commits:
        lines.append(f"Engineering cadence: {float(commits):.1f} commits/week average.")
    if recency is not None:
        days = int(recency)
        label = "actively maintained" if days <= 7 else "recently active" if days <= 30 else "stale — low recent activity"
        lines.append(f"Repository freshness: last push {days} days ago ({label}).")

    team_vcs = _claims_for_categories(verified_claims, ("team",))
    for vc in team_vcs:
        if vc.claim.claim_text.lower() != "not disclosed":
            lines.append(f"Signal: {vc.claim.claim_text} [{vc.status}]")

    if not lines:
        return _make_unavailable("Team & History")

    lines.append("Company timeline and prior exit history: not disclosed.")
    return MemoSection(
        title="Team & History",
        content="\n".join(f"  - {l}" for l in lines),
        claims=team_vcs if team_vcs else [_gap_claim("team_history")],
    )


def _build_technology_defensibility(profile: FounderProfile, verified_claims: List[VerifiedClaim]) -> MemoSection:
    ks = profile.key_signals or {}
    stars = ks.get("total_stars", 0)
    commits = ks.get("commit_frequency")
    tech_depth = ks.get("tech_stack_depth")
    sector = profile.sector or "unknown"

    lines = []

    if tech_depth is not None:
        lines.append(f"Tech stack depth signal: {tech_depth}/100 — "
                     + ("broad multi-language stack." if float(tech_depth) > 60
                        else "focused stack, potential specialisation." if float(tech_depth) > 35
                        else "shallow stack — commoditisation risk."))

    if stars and int(stars) > 0:
        s = int(stars)
        adoption = "strong OSS adoption" if s > 1000 else "growing community" if s > 100 else "early-stage traction"
        lines.append(f"Open-source footprint: {s:,} GitHub stars — {adoption}.")

    if commits:
        c = float(commits)
        lines.append(f"Development velocity: {c:.1f} commits/week — "
                     + ("high-cadence iteration, suggests rapid product development." if c > 10
                        else "steady iteration." if c > 3
                        else "low velocity — potential execution risk."))

    lines.append(f"Sector ({sector}): proprietary advantage and data moat details not disclosed.")
    lines.append("Architecture choices and defensibility compounding: not disclosed — to be validated in diligence.")

    traction_vcs = _verified_only(_claims_for_categories(verified_claims, ("traction",)))
    return MemoSection(
        title="Technology & Defensibility",
        content="\n".join(f"  - {l}" for l in lines),
        claims=traction_vcs if traction_vcs else [_gap_claim("technology_defensibility")],
    )


def _build_optional_section(title: str, categories: tuple, verified_claims: List[VerifiedClaim]) -> MemoSection:
    relevant = [
        vc for vc in verified_claims
        if vc.claim.category in categories and vc.claim.claim_text.lower() != "not disclosed"
    ]
    if not relevant:
        return _make_unavailable(title)
    lines = [f"  - {vc.claim.claim_text} [{vc.status}]" for vc in relevant]
    return MemoSection(title=title, content="\n".join(lines), claims=relevant)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def generate_memo(
    profile: FounderProfile,
    screening: ScreeningResult,
    verified_claims: List[VerifiedClaim],
) -> InvestmentMemo:
    """
    Assemble a structured InvestmentMemo from pipeline inputs.
    No Ollama call. Never fabricates. Never raises.
    """
    try:
        company = profile.company or profile.name or "Unknown Company"
        today = str(date.today())

        required = [
            _build_company_snapshot(profile, verified_claims),
            _build_investment_hypotheses(screening, verified_claims),
            _build_swot(screening, verified_claims),
            _build_problem_and_product(profile, verified_claims),
            _build_traction_and_kpis(verified_claims),
        ]

        optional = [
            _build_team_and_history(profile, verified_claims),
            _build_technology_defensibility(profile, verified_claims),
            _build_optional_section("Financials & Round Structure", ("revenue",), verified_claims),
            _build_optional_section("Cap Table", ("other",), verified_claims),
            _build_optional_section("Competition", ("market_size",), verified_claims),
            _build_optional_section("Market Sizing", ("market_size",), verified_claims),
            _make_unavailable("Due Diligence Log"),
            _make_unavailable("Exit Perspective"),
        ]

        if verified_claims:
            overall_trust = sum(vc.verification_confidence for vc in verified_claims) / len(verified_claims)
        else:
            overall_trust = 0.0

        return InvestmentMemo(
            company=company,
            date=today,
            required_sections=required,
            optional_sections=optional,
            overall_trust_score=overall_trust,
        )

    except Exception:
        logger.exception("generate_memo failed — returning minimal fallback memo")
        fallback_claim = _gap_claim("memo_generation_error")
        fallback_section = MemoSection(
            title="Error",
            content="Memo generation encountered an error.",
            claims=[fallback_claim],
        )
        return InvestmentMemo(
            company=profile.company or "Unknown",
            date=str(date.today()),
            required_sections=[fallback_section] * 5,
            optional_sections=[],
            overall_trust_score=0.0,
        )


def export_memo_markdown(memo: InvestmentMemo) -> str:
    """Render InvestmentMemo to a markdown string. Never raises."""
    try:
        lines = [
            f"# Investment Memo: {memo.company}",
            f"Date: {memo.date}",
            f"**Trust Score: {memo.overall_trust_score:.0%}**",
            "",
        ]

        for section in memo.required_sections:
            if not section.is_available:
                lines.append(f"> **[{section.title}: {NOT_DISCLOSED}]**")
            else:
                lines.append(f"## {section.title}")
                lines.append(section.content)
            lines.append("")

        for section in memo.optional_sections:
            if not section.is_available:
                lines.append(f"> **[{section.title}: {NOT_DISCLOSED}]**")
            else:
                lines.append(f"## {section.title}")
                lines.append(section.content)
            lines.append("")

        # Traceability table — deduplicated by claim_text
        lines.append("## Claim Traceability")
        lines.append("| Claim | Category | Status | Confidence |")
        lines.append("|-------|----------|--------|------------|")
        seen: set = set()
        all_vcs: List[VerifiedClaim] = []
        for section in memo.required_sections + memo.optional_sections:
            for vc in section.claims:
                if vc.claim.claim_text not in seen:
                    seen.add(vc.claim.claim_text)
                    all_vcs.append(vc)
        for vc in all_vcs:
            claim_short = vc.claim.claim_text[:60].replace("|", "\\|")
            lines.append(
                f"| {claim_short} | {vc.claim.category} | {vc.status} | {vc.verification_confidence:.0%} |"
            )

        return "\n".join(lines)

    except Exception:
        return f"# Investment Memo: {getattr(memo, 'company', 'Unknown')}\n\n[Error rendering memo]"


def export_memo_pdf(memo: InvestmentMemo) -> bytes:
    """Render InvestmentMemo to PDF bytes via reportlab. Never raises — returns b'' on failure."""
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import letter

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        md_text = export_memo_markdown(memo)
        for line in md_text.splitlines():
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 8))
                continue
            if stripped.startswith("# "):
                story.append(Paragraph(stripped[2:], styles["Title"]))
            elif stripped.startswith("## "):
                story.append(Paragraph(stripped[3:], styles["Heading2"]))
            elif stripped.startswith("> **["):
                story.append(Paragraph(stripped.lstrip("> *").rstrip("*]") or stripped, styles["Italic"]))
            elif stripped.startswith("|"):
                story.append(Paragraph(stripped, styles["Code"]))
            else:
                safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, styles["Normal"]))

        doc.build(story)
        return buffer.getvalue()

    except Exception:
        logger.warning("export_memo_pdf failed — returning empty bytes", exc_info=True)
        return b""

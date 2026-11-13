"""
decision_gate.py — Spark Cockpit FNOL Claims Triage Agent
==========================================================
Deterministic Python routing engine.  The LLM never touches this file —
all tier assignments and Cockpit field population are pure Python logic
evaluated top-down (Tier 3 first, Tier 1 last).

Outputs:
  • final_tier            — "Tier 1" | "Tier 2" | "Tier 3"
  • claim_status          — ClaimStatusEnum value
  • action_type           — ActionTypeEnum value
  • priority              — "High priority" | "Normal"
  • headline_summary      — one-liner shown in the claim list row
  • what_spark_did        — paragraph shown in the expanded detail panel
  • recommendation_title  — bold headline in the Recommendation card
  • confidence_score      — int 0-100
  • rationale_bullets     — list of bullet strings for the WHY section
  • referenced_documents  — list of ReferencedDoc for the REFERENCED DOCUMENTS section
  • data_tags             — list of data-source tag strings
  • current_stage         — set to STAGE_5_DECISION on completion
  • stages_completed      — appended with all stages up to STAGE_5_DECISION
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from config import (
    FAST_TRACK_LIMIT_INR,
    MIN_CONFIDENCE_THRESHOLD,
    STAGE_1_INTAKE,
    STAGE_2_COVERAGE,
    STAGE_3_VISION,
    STAGE_4_FRAUD,
    STAGE_5_DECISION,
    TOTAL_LOSS_RATIO,
)
from schemas import (
    ActionTypeEnum,
    ClaimRecord,
    ClaimStatusEnum,
    CoverageResult,
    FraudConsistencyReport,
    HandledByEnum,
    ReferencedDoc,
    StatementFacts,
    TraceEntry,
    VisionReport,
)

# Full ordered pipeline — used to populate stages_completed
_ALL_STAGES = [
    STAGE_1_INTAKE,
    STAGE_2_COVERAGE,
    STAGE_3_VISION,
    STAGE_4_FRAUD,
    STAGE_5_DECISION,
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_inr(amount: float) -> str:
    """Format a float as a compact Indian Rupee string, e.g. ₹35,000."""
    return f"₹{amount:,.0f}"


def _build_referenced_docs(claim: ClaimRecord) -> List[ReferencedDoc]:
    """
    Build the three canonical referenced documents shown in the UI detail panel.
    Mirrors the reference screenshots exactly:
      FNOL_intake_{id}.pdf — p. 1, loss narrative
      Policy_schedule_{policy_id}.pdf — Cover section, p. 4
      Vision_assessment_{id}.pdf — Findings, p. 2
    """
    cid = claim.claim_id
    pid = claim.policy_id
    return [
        ReferencedDoc(
            doc_name=f"FNOL_intake_{cid}.pdf",
            section_ref="p. 1, loss narrative",
            summary="Loss description and reported circumstances used for triage.",
        ),
        ReferencedDoc(
            doc_name=f"Policy_schedule_{pid}.pdf",
            section_ref="Cover section, p. 4",
            summary="Cover, limits and deductible confirmed in force on the loss date.",
        ),
        ReferencedDoc(
            doc_name=f"Vision_assessment_{cid}.pdf",
            section_ref="Findings, p. 2",
            summary="Zone-by-zone photographic damage assessment supporting the outcome.",
        ),
    ]


def _build_data_tags(
    has_vision: bool,
    has_policy: bool,
    has_history: bool,
    has_weather: bool,
    has_fraud: bool,
) -> List[str]:
    tags = []
    if has_vision:
        tags.append("Vision Zone Checklist")
    if has_policy:
        tags.append("Policy Schedule DB2")
    if has_history:
        tags.append("Policy Loss History")
    if has_weather:
        tags.append("Open-Meteo Weather")
    if has_fraud:
        tags.append("Fraud Screening Result")
    return tags


def _trace(
    stage: str, agent: str, purpose: str, result: str
) -> TraceEntry:
    return TraceEntry(
        timestamp=_now_iso(),
        stage=stage,
        agent_or_tool=agent,
        purpose=purpose,
        result_summary=result,
    )


# ===========================================================================
# Main entry point
# ===========================================================================

def run_decision_gate(claim: ClaimRecord) -> ClaimRecord:
    """
    Evaluate all structured pipeline outputs and populate every Spark Cockpit
    UI field on the ClaimRecord.  Returns the fully-updated ClaimRecord.

    Evaluation order (top-down, first match wins):
      Case 1: Tier 3 — High fraud risk OR unresolved contradiction
      Case 2: Coverage Gate Failed — policy not_covered
      Case 3: Missing / Low-Confidence Evidence — no photos / unusable / low confidence
      Case 4: Tier 2 — Moderate/Total Loss, high reserve, injuries, third-party
      Case 5: Tier 1 — Fast-Track (all clear)
    """

    # --- Collect inputs (with safe defaults if agents haven't populated them) ---
    vision: VisionReport = claim.vision_report or VisionReport(
        findings=[], overall_severity="Unknown", estimated_repair_cost_inr=0.0,
        overall_confidence=0, unusable_photos=True, notes="No vision report available.",
    )
    coverage: CoverageResult = claim.coverage_result or CoverageResult(
        policy_id=claim.policy_id, status="needs_review",
    )
    fraud: FraudConsistencyReport = claim.fraud_report or FraudConsistencyReport(
        risk_level="Low", signals=[], contradictions=[], unresolved_contradiction=False,
        weather_verification="unavailable",
    )
    facts: StatementFacts = claim.statement_facts or StatementFacts(
        claimed_zones=[], incident_date=claim.incident_date,
        incident_time=claim.incident_time, location=claim.location,
        narrative_summary=claim.raw_statement[:300],
        injuries_reported=claim.injuries, third_party_involved=claim.third_party,
        police_report_filed=claim.police_report,
    )

    cost: float = vision.estimated_repair_cost_inr
    severity: str = vision.overall_severity
    confidence: int = vision.overall_confidence
    no_photos: bool = not claim.photo_paths
    unusable: bool = vision.unusable_photos
    net_payable: float = coverage.net_payable_estimate_inr

    # Total Loss upgrade (deterministic, mirrors tools.py logic as a safety net)
    if (
        coverage.status == "covered"
        and coverage.idv_inr > 0
        and cost >= TOTAL_LOSS_RATIO * coverage.idv_inr
    ):
        severity = "Total Loss"

    has_weather = "unavailable" not in fraud.weather_verification.lower()
    prior_claims_flagged = any(
        s.signal_name == "Prior Claim Frequency" and s.triggered
        for s in fraud.signals
    )

    data_tags = _build_data_tags(
        has_vision=bool(vision.findings),
        has_policy=coverage.policy_id != "",
        has_history=prior_claims_flagged,
        has_weather=has_weather,
        has_fraud=bool(fraud.signals),
    )

    # We'll accumulate trace entries for the decision gate stage
    gate_traces: List[TraceEntry] = []

    # --- Determine final tier ---
    final_tier: str
    claim_status: ClaimStatusEnum
    action_type: ActionTypeEnum
    priority: str
    headline_summary: str
    what_spark_did: str
    recommendation_title: str
    rationale_bullets: List[str]
    score: int

    # ===========================================================
    # CASE 1 — Tier 3: Fraud / SIU Escalation
    # ===========================================================
    if fraud.risk_level == "High" or fraud.unresolved_contradiction:
        final_tier = "Tier 3"
        claim_status = ClaimStatusEnum.STUCK
        action_type = ActionTypeEnum.ESCALATION
        priority = "High priority"
        score = max(0, confidence - 20)  # penalise confidence

        if fraud.unresolved_contradiction:
            headline_summary = (
                f"Unresolved damage zone contradiction after "
                f"{claim.loop_count} verification loop(s) — SIU review required"
            )
            recommendation_title = "Refer to Special Investigations Unit"
            what_spark_did = (
                f"Spark completed {claim.loop_count} verification loop(s) requesting "
                "additional photographic evidence. The discrepancy between the claimed "
                "damage zones and the zones observed in all submitted photos could not "
                "be reconciled. The claim has been escalated per protocol — no auto-denial "
                "has been issued."
            )
            rationale_bullets = [
                f"Claimed zones: {', '.join(facts.claimed_zones) or 'not specified'}",
                f"Observed damaged zones: "
                + (
                    ", ".join(
                        f.zone for f in vision.findings if f.status == "damaged"
                    ) or "none"
                ),
                "Contradiction persisted through all verification loops.",
                "Tier 3 protocol: unresolved contradictions escalate to SIU — not an auto-denial.",
            ]
        else:
            triggered_names = [s.signal_name for s in fraud.signals if s.triggered]
            headline_summary = (
                f"High fraud risk — {', '.join(triggered_names)} "
                "— SIU review required"
            )
            recommendation_title = "Refer to Special Investigations Unit"
            what_spark_did = (
                "Spark completed all five pipeline stages. Fraud & Consistency analysis "
                "returned a High risk rating based on multiple weighted signals. "
                "No auto-denial has been issued — the evidence is forwarded to the "
                "Special Investigations Unit for human review."
            )
            rationale_bullets = [
                f"{s.signal_name} ({s.weight}): {s.reason}"
                for s in fraud.signals if s.triggered
            ] or ["High fraud risk composite score triggered by multiple signals."]

        gate_traces.append(_trace(
            STAGE_5_DECISION, "Decision Gate",
            "Tier assignment — fraud/contradiction",
            f"Tier 3 assigned. Risk: {fraud.risk_level}. "
            f"Unresolved: {fraud.unresolved_contradiction}.",
        ))

    # ===========================================================
    # CASE 2 — Coverage Gate Failed (not_covered)
    # ===========================================================
    elif coverage.status == "not_covered":
        final_tier = "Tier 2"
        claim_status = ClaimStatusEnum.STUCK
        action_type = ActionTypeEnum.ESCALATION
        priority = "High priority"
        score = 0  # no payable amount → confidence in coverage decision is 100% but payout is 0

        citations = "; ".join(coverage.clause_citations) or "Policy terms"
        headline_summary = (
            "Loss date / policy coverage gate failed — "
            "human sign-off required before rejection"
        )
        recommendation_title = "Coverage Gate Failed — Adjuster Sign-Off Required"
        what_spark_did = (
            "Spark completed the coverage check. The claim cannot be auto-processed "
            f"because: {coverage.explanation} "
            "No rejection has been issued — per protocol, coverage denials require "
            "a named adjuster sign-off."
        )
        rationale_bullets = [
            f"Policy active on date: {coverage.policy_active_on_date}",
            f"Vehicle matched: {coverage.vehicle_matched}",
            f"Coverage type: {coverage.coverage_type}",
            f"Clause citation(s): {citations}",
            "System rule: auto-rejection is prohibited — human sign-off required.",
        ]

        gate_traces.append(_trace(
            STAGE_5_DECISION, "Decision Gate",
            "Tier assignment — coverage gate",
            f"Tier 2 (STUCK). Coverage status: {coverage.status}. "
            f"Clauses: {citations}.",
        ))

    # ===========================================================
    # CASE 3 — Missing / Low-Confidence Evidence
    # ===========================================================
    elif no_photos or unusable or confidence < MIN_CONFIDENCE_THRESHOLD:
        final_tier = "Tier 2"
        claim_status = ClaimStatusEnum.NEEDS_ATTENTION
        action_type = ActionTypeEnum.QUESTION
        priority = "High priority"
        score = confidence

        if no_photos:
            reason_detail = "No photos were submitted with this claim."
        elif unusable:
            reason_detail = "All submitted photos are too blurry or dark to assess."
        else:
            reason_detail = (
                f"Vision confidence ({confidence}%) is below the "
                f"{MIN_CONFIDENCE_THRESHOLD}% automation threshold."
            )

        headline_summary = (
            f"Spark has a question — {reason_detail.lower().rstrip('.')} — "
            "clearer photos required"
        )
        recommendation_title = "Additional Photo Evidence Required"
        what_spark_did = (
            "Spark attempted vision analysis but could not reach the minimum confidence "
            f"threshold. {reason_detail} The claim cannot be auto-processed until "
            "clear photographic evidence is available."
        )
        rationale_bullets = [
            reason_detail,
            f"Vision overall confidence: {confidence}% "
            f"(minimum required: {MIN_CONFIDENCE_THRESHOLD}%)",
            "Automation halted pending additional evidence — no decision issued.",
        ]

        gate_traces.append(_trace(
            STAGE_5_DECISION, "Decision Gate",
            "Tier assignment — missing/low-confidence evidence",
            f"Tier 2 (NEEDS ATTENTION / QUESTION). No photos: {no_photos}. "
            f"Unusable: {unusable}. Confidence: {confidence}%.",
        ))

    # ===========================================================
    # CASE 4 — Tier 2: Desk Adjuster (Heavy Loss / High Reserve / Unverified Policy)
    # ===========================================================
    elif (
        coverage.status == "needs_review"
        or severity in ("Moderate", "Total Loss")
        or cost > FAST_TRACK_LIMIT_INR
        or claim.injuries
        or claim.third_party
    ):
        final_tier = "Tier 2"
        claim_status = ClaimStatusEnum.NEEDS_ATTENTION
        priority = "High priority"
        score = confidence

        # REQUEST if reserve exceeds ceiling or policy needs review; RECOMMENDATION if it's a human-required step
        if coverage.status == "needs_review":
            action_type = ActionTypeEnum.REQUEST
            headline_summary = (
                f"Policy schedule unverified ({coverage.coverage_type}) — "
                "desk adjuster verification required"
            )
            recommendation_title = "Manual Policy Schedule Verification Required"
        elif cost > FAST_TRACK_LIMIT_INR:
            action_type = ActionTypeEnum.REQUEST
            headline_summary = (
                f"Reserve {_fmt_inr(cost)} exceeds {_fmt_inr(FAST_TRACK_LIMIT_INR)} "
                "fast-track ceiling — mandatory human sign-off required"
            )
            recommendation_title = (
                f"Human Sign-Off Required — Reserve {_fmt_inr(cost)}"
            )
        elif severity == "Total Loss":
            action_type = ActionTypeEnum.RECOMMENDATION
            headline_summary = (
                f"Total Loss assessment — estimated repair {_fmt_inr(cost)} "
                f"≥ {int(TOTAL_LOSS_RATIO*100)}% of IDV {_fmt_inr(coverage.idv_inr)} "
                "— desk adjuster review required"
            )
            recommendation_title = f"Total Loss Assessment — {_fmt_inr(net_payable)} Net Payable"
        elif claim.injuries or claim.third_party:
            action_type = ActionTypeEnum.RECOMMENDATION
            flags = []
            if claim.injuries:
                flags.append("bodily injury reported")
            if claim.third_party:
                flags.append("third-party involved")
            headline_summary = (
                f"Claim involves {' and '.join(flags)} — desk adjuster review required"
            )
            recommendation_title = "Adjuster Review Required — Injury / Third-Party Involvement"
        else:
            action_type = ActionTypeEnum.RECOMMENDATION
            headline_summary = (
                f"Moderate damage — estimated repair {_fmt_inr(cost)} "
                "— desk adjuster review required"
            )
            recommendation_title = f"Desk Adjuster Review — {_fmt_inr(net_payable)} Net Payable"

        what_spark_did = (
            "Spark completed all five pipeline stages: statement parsing, policy coverage "
            "verification, multimodal damage assessment, and fraud & consistency checks. "
            f"Damage severity is '{severity}' with an estimated repair cost of "
            f"{_fmt_inr(cost)}. The claim exceeds the fast-track automation threshold "
            "and has been queued for desk adjuster review."
        )
        rationale_bullets = _build_tier2_bullets(
            severity, cost, net_payable, coverage, claim, fraud, vision
        )

        gate_traces.append(_trace(
            STAGE_5_DECISION, "Decision Gate",
            "Tier assignment — Tier 2 heavy loss",
            f"Tier 2. Severity: {severity}. Cost: {_fmt_inr(cost)}. "
            f"Injuries: {claim.injuries}. Third-party: {claim.third_party}.",
        ))

    # ===========================================================
    # CASE 5 — Tier 1: Fast-Track Auto-Approve
    # ===========================================================
    else:
        final_tier = "Tier 1"
        claim_status = ClaimStatusEnum.NEEDS_ATTENTION  # awaiting 1-click Execute
        action_type = ActionTypeEnum.RECOMMENDATION
        priority = "Normal"
        score = confidence

        headline_summary = (
            f"Settlement offer ready (Tier 1 Fast-Track) — "
            f"approve prepared outcome for {_fmt_inr(net_payable)}"
        )
        recommendation_title = (
            f"Approve the prepared outcome for {_fmt_inr(net_payable)}"
        )
        what_spark_did = (
            "Spark completed all five pipeline stages. The claim satisfies every "
            "fast-track criterion: policy is active, coverage is confirmed, damage is "
            f"minor ({_fmt_inr(cost)}), no injuries or third-party involvement, "
            f"vision confidence is {confidence}%, and fraud risk is Low. "
            "A settlement offer has been prepared for one-click approval."
        )
        rationale_bullets = [
            "The analysis is complete and no data is missing.",
            f"Coverage confirmed — policy active, vehicle matched, own damage covered.",
            f"Damage severity: {severity} — estimated repair {_fmt_inr(cost)} "
            f"≤ fast-track ceiling {_fmt_inr(FAST_TRACK_LIMIT_INR)}.",
            f"Vision confidence: {confidence}% ≥ {MIN_CONFIDENCE_THRESHOLD}% threshold.",
            f"Fraud & Consistency risk: {fraud.risk_level} — no triggered high-weight signals.",
            f"Net payable estimate after deductible: {_fmt_inr(net_payable)}.",
        ]

        gate_traces.append(_trace(
            STAGE_5_DECISION, "Decision Gate",
            "Tier assignment — Tier 1 fast-track",
            f"Tier 1. Cost: {_fmt_inr(cost)}. Confidence: {confidence}%. "
            f"Risk: {fraud.risk_level}.",
        ))

    # ===========================================================
    # Populate all fields on the ClaimRecord
    # ===========================================================
    claim.final_tier = final_tier
    claim.claim_status = claim_status
    claim.action_type = action_type
    claim.priority = priority
    claim.headline_summary = headline_summary
    claim.what_spark_did = what_spark_did
    claim.recommendation_title = recommendation_title
    claim.confidence_score = score
    claim.rationale_bullets = rationale_bullets
    claim.referenced_documents = _build_referenced_docs(claim)
    claim.data_tags = data_tags
    claim.current_stage = STAGE_5_DECISION
    claim.stages_completed = _ALL_STAGES[:]  # mark all stages complete

    # Append decision gate trace entries
    claim.agent_trace.extend(gate_traces)

    return claim


# ===========================================================================
# Helpers
# ===========================================================================

def _build_tier2_bullets(
    severity: str,
    cost: float,
    net_payable: float,
    coverage: CoverageResult,
    claim: ClaimRecord,
    fraud: FraudConsistencyReport,
    vision: VisionReport,
) -> List[str]:
    """Build the rationale bullet list for a Tier 2 (desk adjuster) claim."""
    bullets = []

    bullets.append(
        f"Damage severity: {severity} — estimated repair {_fmt_inr(cost)}."
    )

    if cost > FAST_TRACK_LIMIT_INR:
        bullets.append(
            f"Reserve {_fmt_inr(cost)} exceeds fast-track ceiling "
            f"{_fmt_inr(FAST_TRACK_LIMIT_INR)} — mandatory human sign-off required."
        )

    bullets.append(
        f"Policy coverage: {coverage.status} — {coverage.coverage_type}. "
        f"IDV: {_fmt_inr(coverage.idv_inr)}. "
        f"Deductible: {_fmt_inr(coverage.deductible_inr)}."
    )

    if net_payable > 0:
        bullets.append(f"Net payable estimate after deductible: {_fmt_inr(net_payable)}.")

    if claim.injuries:
        bullets.append("Bodily injury reported — liability assessment required before settlement.")

    if claim.third_party:
        bullets.append(
            "Third-party involvement reported — third-party liability must be assessed."
        )

    # Fraud signals
    triggered = [s for s in fraud.signals if s.triggered]
    if triggered:
        for sig in triggered:
            bullets.append(f"Risk signal — {sig.signal_name} ({sig.weight}): {sig.reason}")
    else:
        bullets.append(f"Fraud & Consistency risk: {fraud.risk_level} — no high-weight signals triggered.")

    # Vision zones
    damaged_zones = [f.zone for f in vision.findings if f.status == "damaged"]
    if damaged_zones:
        bullets.append(f"Damaged zones identified: {', '.join(damaged_zones)}.")

    return bullets


# ===========================================================================
# Convenience: apply decision gate directly to a ClaimRecord by claim_id
# ===========================================================

def apply_decision_gate_to_claim(claim: ClaimRecord) -> ClaimRecord:
    """
    Thin wrapper: run the decision gate and return the updated ClaimRecord.
    The caller is responsible for persisting the result via state_manager.update_claim().
    """
    return run_decision_gate(claim)

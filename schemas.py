"""
schemas.py — Spark Cockpit FNOL Claims Triage Agent
Pydantic v2 models for every structured artefact produced by the pipeline.
These models are the single source of truth for db1_claims.json persistence
and for all inter-agent hand-offs.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ===========================================================================
# Enumerations
# ===========================================================================

class ClaimStatusEnum(str, Enum):
    IN_PROGRESS    = "IN PROGRESS"
    NEEDS_ATTENTION = "NEEDS ATTENTION"
    STUCK          = "STUCK"
    AUTOMATION_OFF = "AUTOMATION OFF"
    SETTLED        = "SETTLED"
    DISCARDED      = "DISCARDED"


class ActionTypeEnum(str, Enum):
    RECOMMENDATION = "RECOMMENDATION"
    REQUEST        = "REQUEST"
    QUESTION       = "QUESTION"
    ESCALATION     = "ESCALATION"


class HandledByEnum(str, Enum):
    SPARK  = "Spark"
    MANUAL = "Manual"


# ===========================================================================
# Vision Agent models
# ===========================================================================

class ZoneFinding(BaseModel):
    """Per-zone damage finding from the Vision Agent."""
    zone: str = Field(
        ...,
        description="Vehicle zone assessed: front | rear | left | right | corners | roof_windshield"
    )
    status: str = Field(
        ...,
        description="damaged | not_damaged | not_visible"
    )
    severity: str = Field(
        default="None",
        description="None | Minor | Moderate | Severe"
    )
    description: str = Field(default="", description="Free-text description of the finding.")
    confidence: int = Field(
        default=0,
        ge=0, le=100,
        description="Vision confidence score for this zone (0–100)."
    )
    photo_ref: str = Field(
        default="",
        description="Reference to the photo filename that produced this finding."
    )


class VisionReport(BaseModel):
    """Aggregated output from the Vision Agent after analysing all submitted photos."""
    findings: List[ZoneFinding] = Field(default_factory=list)
    overall_severity: str = Field(
        default="Unknown",
        description="Minor | Moderate | Total Loss | Unknown"
    )
    estimated_repair_cost_inr: float = Field(
        default=0.0,
        description="Estimated repair cost in INR, derived from zone findings + repair cost table."
    )
    overall_confidence: int = Field(
        default=0,
        ge=0, le=100,
        description="Aggregate confidence across all zone findings."
    )
    unusable_photos: bool = Field(
        default=False,
        description="True if all submitted photos are too blurry / dark to assess."
    )
    notes: str = Field(default="", description="Additional notes from the Vision Agent.")


# ===========================================================================
# Statement parsing model
# ===========================================================================

class StatementFacts(BaseModel):
    """Structured facts extracted by the Supervisor from the claimant's raw statement."""
    claimed_zones: List[str] = Field(
        default_factory=list,
        description="Vehicle zones mentioned in the claimant's statement."
    )
    incident_date: str = Field(default="", description="ISO-8601 date string of the incident.")
    incident_time: str = Field(default="", description="HH:MM time string of the incident.")
    location: str = Field(default="", description="Location of the incident.")
    narrative_summary: str = Field(
        default="",
        description="One-paragraph factual summary of the claimant's account."
    )
    injuries_reported: bool = Field(default=False)
    third_party_involved: bool = Field(default=False)
    police_report_filed: bool = Field(default=False)
    weather_claimed: str = Field(
        default="",
        description="Weather conditions as described by the claimant."
    )


# ===========================================================================
# Policy / Coverage models
# ===========================================================================

class CoverageResult(BaseModel):
    """Output from the Policy Agent's coverage check."""
    policy_id: str = Field(default="")
    status: str = Field(
        default="needs_review",
        description="covered | not_covered | needs_review"
    )
    policy_active_on_date: bool = Field(default=False)
    vehicle_matched: bool = Field(default=False)
    coverage_type: str = Field(
        default="",
        description="Comprehensive | Third_Party_Only | Commercial | etc."
    )
    idv_inr: float = Field(default=0.0, description="Insured Declared Value in INR.")
    deductible_inr: float = Field(default=0.0, description="Policy deductible in INR.")
    limit_inr: float = Field(default=0.0, description="Per-claim coverage limit in INR.")
    net_payable_estimate_inr: float = Field(
        default=0.0,
        description="Estimated net payable after deductible."
    )
    clause_citations: List[str] = Field(
        default_factory=list,
        description="Policy clause IDs or section references cited in the decision."
    )
    explanation: str = Field(
        default="",
        description="Human-readable explanation of the coverage decision."
    )


# ===========================================================================
# Fraud & Consistency models
# ===========================================================================

class RiskSignal(BaseModel):
    """A single weighted fraud / risk indicator."""
    signal_name: str
    weight: str = Field(description="Low | Medium | High")
    triggered: bool = Field(default=False)
    reason: str = Field(default="")


class FraudConsistencyReport(BaseModel):
    """Aggregated output from the Fraud & Consistency Agent."""
    risk_level: str = Field(
        default="Low",
        description="Low | Medium | High"
    )
    signals: List[RiskSignal] = Field(default_factory=list)
    contradictions: List[str] = Field(
        default_factory=list,
        description="Specific contradictions found between claimed facts and observed evidence."
    )
    unresolved_contradiction: bool = Field(
        default=False,
        description="True if at least one contradiction remained unresolved after MAX_CONTRADICTION_LOOPS."
    )
    weather_verification: str = Field(
        default="unavailable",
        description="Result of Open-Meteo weather cross-check: matches | mismatch | unavailable"
    )


# ===========================================================================
# Audit / traceability models
# ===========================================================================

class ReferencedDoc(BaseModel):
    """A document or data source cited in the final rationale."""
    doc_name: str
    section_ref: str = Field(default="")
    summary: str = Field(default="")


class TraceEntry(BaseModel):
    """A single step in the agent execution trace (audit log)."""
    timestamp: str = Field(description="ISO-8601 datetime string.")
    stage: str = Field(description="Pipeline stage constant from config.py.")
    agent_or_tool: str = Field(description="Name of the agent or tool that produced this entry.")
    purpose: str = Field(description="Why this step was taken.")
    result_summary: str = Field(description="Brief summary of what the step produced.")


class ChatMessage(BaseModel):
    """A single message in the Adjuster ↔ Spark chat thread."""
    sender: str = Field(description="Adjuster | Spark")
    timestamp: str = Field(description="ISO-8601 datetime string.")
    message: str


# ===========================================================================
# Top-level Claim Record
# ===========================================================================

class ClaimRecord(BaseModel):
    """
    The canonical record for a single FNOL claim.
    Persisted as one element in the db1_claims.json `claims` array.
    """

    # --- Identity ---
    claim_id: str = Field(
        ...,
        description="Unique claim identifier, e.g. CLM-26-00014."
    )
    created_at: str = Field(
        ...,
        description="ISO-8601 datetime when the claim was first submitted."
    )

    # --- Intake fields ---
    policy_id: str
    policyholder_name: str = Field(default="")
    vehicle_reg: str = Field(default="", description="Vehicle registration number.")
    line_of_business: str = Field(default="Personal Auto")

    incident_date: str = Field(default="")
    incident_time: str = Field(default="")
    location: str = Field(default="")
    raw_statement: str = Field(default="", description="Verbatim claimant statement.")
    photo_paths: List[str] = Field(
        default_factory=list,
        description="Paths to uploaded photos, relative to the project root."
    )

    injuries: bool = Field(default=False)
    third_party: bool = Field(default=False)
    police_report: bool = Field(default=False)

    # --- Pipeline state ---
    claim_status: ClaimStatusEnum = Field(default=ClaimStatusEnum.IN_PROGRESS)
    current_stage: str = Field(default="1 INTAKE & TRIAGE")
    stages_completed: List[str] = Field(default_factory=list)

    priority: str = Field(
        default="Normal",
        description="High priority | Normal"
    )
    action_type: ActionTypeEnum = Field(default=ActionTypeEnum.RECOMMENDATION)
    handled_by: HandledByEnum = Field(default=HandledByEnum.SPARK)

    loop_count: int = Field(default=0, description="Number of contradiction-resolution loops run.")
    returned_to_user_prompt: Optional[str] = Field(
        default=None,
        description="Populated when the Adjuster clicks 'Return to User'; contains the prompt sent."
    )

    # --- Structured agent outputs ---
    statement_facts: Optional[StatementFacts] = None
    vision_report: Optional[VisionReport] = None
    coverage_result: Optional[CoverageResult] = None
    fraud_report: Optional[FraudConsistencyReport] = None

    # --- Decision Gate output ---
    final_tier: Optional[str] = Field(
        default=None,
        description="Tier 1 | Tier 2 | Tier 3"
    )

    # --- Cockpit display fields ---
    headline_summary: str = Field(
        default="",
        description="One-line summary shown in the Cockpit claim list row."
    )
    what_spark_did: str = Field(
        default="",
        description="Short paragraph describing what Spark has completed on this claim."
    )
    recommendation_title: str = Field(
        default="",
        description="Bold headline for the Recommendation card."
    )
    confidence_score: int = Field(
        default=0,
        ge=0, le=100,
        description="Overall pipeline confidence score (0–100)."
    )
    rationale_bullets: List[str] = Field(
        default_factory=list,
        description="Bullet-point reasons supporting the recommendation."
    )
    referenced_documents: List[ReferencedDoc] = Field(
        default_factory=list,
        description="Documents / data sources cited in the rationale."
    )
    data_tags: List[str] = Field(
        default_factory=list,
        description=(
            "Labels for data sources consulted, e.g. "
            "['Vision Zone Checklist', 'Policy Schedule DB2', "
            "'Policy Loss History', 'Open-Meteo Weather', 'Fraud Screening Result']"
        )
    )

    # --- Audit trail ---
    agent_trace: List[TraceEntry] = Field(default_factory=list)
    chat_history: List[ChatMessage] = Field(default_factory=list)


# ===========================================================================
# Top-level DB wrapper
# ===========================================================================

class ClaimsDB(BaseModel):
    """Root object for db1_claims.json."""
    claims: List[ClaimRecord] = Field(default_factory=list)
    engine_paused: bool = Field(
        default=False,
        description="Global kill-switch: when True the pipeline stops accepting new processing jobs."
    )

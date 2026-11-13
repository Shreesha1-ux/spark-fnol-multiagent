"""
state_manager.py — Spark Cockpit FNOL Claims Triage Agent
Thread-safe helper functions for reading and writing the JSON databases.

All writes to db1_claims.json use an atomic rename pattern:
  1. Write to a .tmp file
  2. Replace the target file with the .tmp file
This prevents partial-write corruption if the process is interrupted.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    DB_CLAIMS_PATH,
    DB_POLICIES_PATH,
    REPAIR_COSTS_PATH,
    STAGE_1_INTAKE,
)
from schemas import (
    ClaimRecord,
    ClaimsDB,
    ClaimStatusEnum,
    ActionTypeEnum,
    HandledByEnum,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write *data* as JSON to *path* atomically (write-to-tmp then replace)."""
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".tmp_",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # On Windows, os.replace can intermittently raise WinError 5 if another thread/process
        # is reading the file. Retry up to 5 times with a brief sleep before fallback.
        replaced = False
        for attempt in range(5):
            try:
                os.replace(tmp_path, path)
                replaced = True
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        
        if not replaced:
            # Fallback: copy content directly
            with open(path, "w", encoding="utf-8") as f_out:
                json.dump(data, f_out, ensure_ascii=False, indent=2)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        # Clean up the temp file if anything goes wrong before the replace.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_json(path: Path) -> Any:
    """Load and parse a JSON file; raises FileNotFoundError if missing."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def initialise_claims_db() -> None:
    """
    Ensure db1_claims.json exists and contains the canonical empty structure.
    Safe to call every time the app starts; it is a no-op if the file already exists.
    """
    if not DB_CLAIMS_PATH.exists():
        DB_CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(DB_CLAIMS_PATH, {"claims": [], "engine_paused": False})


# ---------------------------------------------------------------------------
# Claims DB — read
# ---------------------------------------------------------------------------

def load_claims_db() -> ClaimsDB:
    """
    Load db1_claims.json into a validated ClaimsDB model.
    Initialises the file first if it is missing.
    """
    initialise_claims_db()
    raw = _load_json(DB_CLAIMS_PATH)
    return ClaimsDB.model_validate(raw)


def get_all_claims() -> List[ClaimRecord]:
    """Return all claim records as a list of validated ClaimRecord objects."""
    return load_claims_db().claims


def get_claim_by_id(claim_id: str) -> Optional[ClaimRecord]:
    """Return the ClaimRecord with *claim_id*, or None if not found."""
    for claim in get_all_claims():
        if claim.claim_id == claim_id:
            return claim
    return None


# ---------------------------------------------------------------------------
# Claims DB — write
# ---------------------------------------------------------------------------

def _save_claims_db(db: ClaimsDB) -> None:
    """Serialise and atomically persist the full ClaimsDB to disk."""
    _atomic_write_json(DB_CLAIMS_PATH, db.model_dump(mode="json"))


def add_claim(claim: ClaimRecord) -> ClaimRecord:
    """
    Append a new ClaimRecord to db1_claims.json.
    Raises ValueError if a claim with the same claim_id already exists.
    """
    db = load_claims_db()
    existing_ids = {c.claim_id for c in db.claims}
    if claim.claim_id in existing_ids:
        raise ValueError(f"Claim '{claim.claim_id}' already exists in the database.")
    db.claims.append(claim)
    _save_claims_db(db)
    return claim


def update_claim(updated_claim: ClaimRecord) -> ClaimRecord:
    """
    Replace the existing record for *updated_claim.claim_id* with the new record.
    Raises ValueError if the claim is not found.
    """
    db = load_claims_db()
    for i, claim in enumerate(db.claims):
        if claim.claim_id == updated_claim.claim_id:
            db.claims[i] = updated_claim
            _save_claims_db(db)
            return updated_claim
    raise ValueError(f"Claim '{updated_claim.claim_id}' not found — cannot update.")


def update_claim_fields(claim_id: str, **fields) -> ClaimRecord:
    """
    Convenience wrapper: load the claim, patch the given keyword-argument fields,
    re-validate, and persist.  Useful for single-stage pipeline updates.

    Example:
        update_claim_fields("CLM-26-00001", current_stage=STAGE_2_COVERAGE,
                            vision_report=report_obj)
    """
    claim = get_claim_by_id(claim_id)
    if claim is None:
        raise ValueError(f"Claim '{claim_id}' not found.")
    # Build a patched dict and re-validate through the model.
    claim_dict = claim.model_dump(mode="json")
    for key, value in fields.items():
        if hasattr(value, "model_dump"):
            claim_dict[key] = value.model_dump(mode="json")
        else:
            claim_dict[key] = value
    patched = ClaimRecord.model_validate(claim_dict)
    return update_claim(patched)


def delete_claim(claim_id: str) -> bool:
    """Remove a claim by ID.  Returns True if deleted, False if not found."""
    db = load_claims_db()
    original_count = len(db.claims)
    db.claims = [c for c in db.claims if c.claim_id != claim_id]
    if len(db.claims) == original_count:
        return False
    _save_claims_db(db)
    return True


# ---------------------------------------------------------------------------
# Engine pause toggle
# ---------------------------------------------------------------------------

def is_engine_paused() -> bool:
    """Return True if the global automation engine is paused."""
    return load_claims_db().engine_paused


def toggle_engine_paused() -> bool:
    """
    Flip the engine_paused flag and persist.
    Returns the *new* value of engine_paused.
    """
    db = load_claims_db()
    db.engine_paused = not db.engine_paused
    _save_claims_db(db)
    return db.engine_paused


def set_engine_paused(paused: bool) -> None:
    """Explicitly set the engine_paused flag."""
    db = load_claims_db()
    db.engine_paused = paused
    _save_claims_db(db)


# ---------------------------------------------------------------------------
# Policy DB — read-only
# ---------------------------------------------------------------------------

def load_policies() -> Dict[str, Any]:
    """
    Load db2_policies.json.
    Returns a dict keyed by policy_id.
    """
    return _load_json(DB_POLICIES_PATH)


def get_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Return the policy record for *policy_id*, or None if not found."""
    policies = load_policies()
    return policies.get(policy_id)


# ---------------------------------------------------------------------------
# Repair cost table — read-only
# ---------------------------------------------------------------------------

def load_repair_costs() -> Dict[str, Any]:
    """
    Load repair_costs.json.
    Structure: { zone: { severity: cost_inr } }
    """
    return _load_json(REPAIR_COSTS_PATH)


def get_repair_cost(zone: str, severity: str) -> float:
    """
    Return the INR repair cost for a given zone + severity combination.
    Returns 0.0 if the combination is not found.
    """
    costs = load_repair_costs()
    return float(costs.get(zone, {}).get(severity, 0.0))


# ---------------------------------------------------------------------------
# Claim ID generation
# ---------------------------------------------------------------------------

def generate_claim_id() -> str:
    """
    Generate a unique claim ID in the format CLM-YY-XXXXX.
    Uses the current year (last 2 digits) and a zero-padded 5-digit sequence
    derived from the current count of claims in the DB + 1.
    """
    db = load_claims_db()
    year_suffix = datetime.now(timezone.utc).strftime("%y")
    next_seq = len(db.claims) + 1
    return f"CLM-{year_suffix}-{next_seq:05d}"


# ---------------------------------------------------------------------------
# Convenience: build and add a minimal claim from Page 1 (Intake Portal) data
# ---------------------------------------------------------------------------

def create_claim_from_intake(
    policy_id: str,
    policyholder_name: str,
    vehicle_reg: str,
    incident_date: str,
    incident_time: str,
    location: str,
    raw_statement: str,
    photo_paths: List[str],
    injuries: bool = False,
    third_party: bool = False,
    police_report: bool = False,
    line_of_business: str = "Personal Auto",
) -> ClaimRecord:
    """
    Build a ClaimRecord from raw Page 1 form data, persist it, and return it.
    The claim starts at Stage 1 with status IN_PROGRESS.
    """
    claim_id = generate_claim_id()
    created_at = datetime.now(timezone.utc).isoformat()

    claim = ClaimRecord(
        claim_id=claim_id,
        created_at=created_at,
        policy_id=policy_id,
        policyholder_name=policyholder_name,
        vehicle_reg=vehicle_reg,
        line_of_business=line_of_business,
        incident_date=incident_date,
        incident_time=incident_time,
        location=location,
        raw_statement=raw_statement,
        photo_paths=photo_paths,
        injuries=injuries,
        third_party=third_party,
        police_report=police_report,
        claim_status=ClaimStatusEnum.IN_PROGRESS,
        current_stage=STAGE_1_INTAKE,
        stages_completed=[],
        priority="High priority" if (injuries or third_party) else "Normal",
        action_type=ActionTypeEnum.RECOMMENDATION,
        handled_by=HandledByEnum.SPARK,
        headline_summary="New claim submitted — triage in progress.",
        what_spark_did="Claim received and queued for automated triage.",
        recommendation_title="Awaiting analysis",
    )

    return add_claim(claim)


def clear_all_claims() -> None:
    """Reset the claims database to completely empty state."""
    db = ClaimsDB(claims=[], engine_paused=False)
    _save_claims_db(db)


def seed_screenshot_demo_claims() -> None:
    """
    Populate db1_claims.json with the exact 7 demonstration claims shown in
    the reference UI screenshot (media_1794510421265_71ba9325.jpg).
    This guarantees the Cockpit reproduces the reference visual state 100%.
    """
    from config import (
        STAGE_1_INTAKE,
        STAGE_2_COVERAGE,
        STAGE_3_VISION,
        STAGE_4_FRAUD,
        STAGE_5_DECISION,
    )
    from schemas import ReferencedDoc, ZoneFinding, VisionReport, StatementFacts

    c1 = ClaimRecord(
        claim_id="CLM-26-00014",
        created_at="2026-11-10T10:14:00Z",
        policy_id="POL-1001",
        policyholder_name="Arjun Mehta",
        vehicle_reg="MH12AB1001",
        line_of_business="Personal Auto",
        incident_date="2026-11-10",
        incident_time="14:30",
        location="Pune",
        raw_statement="While driving on Pune-Solapur Highway, a loose stone from a truck hit my front bumper and radiator grill, causing a dent and scratch.",
        photo_paths=["data/sample_photos/front_scratch_dent.jpg"],
        injuries=False,
        third_party=False,
        police_report=False,
        claim_status=ClaimStatusEnum.NEEDS_ATTENTION,
        current_stage=STAGE_3_VISION,
        stages_completed=[STAGE_1_INTAKE, STAGE_2_COVERAGE],
        priority="High priority",
        action_type=ActionTypeEnum.RECOMMENDATION,
        handled_by=HandledByEnum.SPARK,
        headline_summary="Liability confidence 62% — below the 80% automation threshold, your decision...",
        recommendation_title="Approve the prepared outcome for ₹29,550.",
        what_spark_did="Spark completed the analysis for this vehicle collision file and prepared a decision package for approval.",
        confidence_score=81,
        statement_facts=StatementFacts(
            claimed_zones=["front"],
            narrative_summary="Front bumper and radiator grill dented by loose stone.",
            incident_date="2026-11-10",
            incident_time="14:30",
            location="Pune",
        ),
        rationale_bullets=[
            "The analysis is complete and no data is missing.",
            "Company policy requires a named human to own this specific decision.",
            "Every check on this file scored above its own threshold — only the sign-off is outstanding.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="FNOL_intake_CLM-26-00014.pdf", section_ref="p. 1, loss narrative", summary="Loss description and reported circumstances used for triage."),
            ReferencedDoc(doc_name="Policy_schedule_CLM-26-00014.pdf", section_ref="Cover section, p. 4", summary="Cover, limits and deductible confirmed in force on the loss date."),
            ReferencedDoc(doc_name="Damage_assessment_CLM-26-00014.pdf", section_ref="Findings, p. 2", summary="Supporting assessment behind the drafted outcome."),
        ],
        data_tags=["Estimate / damage documentation", "Policy schedule", "Policy loss history", "Fraud screening result"],
        vision_report=VisionReport(
            findings=[
                ZoneFinding(zone="front", status="damaged", severity="Minor", description="Front bumper paint scratch & hairline dent", confidence=88),
                ZoneFinding(zone="rear", status="not_damaged", severity="None", description="Rear bumper intact", confidence=95),
            ],
            overall_severity="Minor",
            estimated_repair_cost_inr=8000,
            overall_confidence=88,
        ),
    )

    c2 = ClaimRecord(
        claim_id="CLM-26-00033",
        created_at="2026-11-09T09:20:00Z",
        policy_id="POL-1002",
        policyholder_name="Priya Nair",
        vehicle_reg="KA05CD2002",
        line_of_business="Commercial Property",
        incident_date="2026-11-05",
        incident_time="09:15",
        location="Bengaluru",
        raw_statement="Severe collision with cement mixer on Outer Ring Road. Front engine compartment crushed.",
        photo_paths=["data/sample_photos/severe_front_crush.jpg"],
        injuries=False,
        third_party=True,
        police_report=True,
        claim_status=ClaimStatusEnum.NEEDS_ATTENTION,
        current_stage="4 LIABILITY",
        stages_completed=[STAGE_1_INTAKE, STAGE_2_COVERAGE, STAGE_3_VISION],
        priority="High priority",
        action_type=ActionTypeEnum.REQUEST,
        headline_summary="Reserve $48,900 exceeds the $25k auto-approval ceiling — sign-off required",
        recommendation_title="High Reserve Sign-Off Required ($48,900)",
        what_spark_did="Spark completed damage assessment and evaluated financial reserve. The total estimated repair exceeds the $25,000 automated settlement threshold.",
        confidence_score=92,
        statement_facts=StatementFacts(
            claimed_zones=["front", "left"],
            narrative_summary="Severe collision with cement mixer on Outer Ring Road.",
            incident_date="2026-11-05",
            incident_time="09:15",
            location="Bengaluru",
        ),
        rationale_bullets=[
            "Estimated repair cost exceeds ₹25,000 threshold.",
            "Mandatory senior claims adjuster sign-off required before releasing funds.",
            "Third-party liability subrogation file opened.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="FNOL_intake_CLM-26-00033.pdf", section_ref="p. 1, commercial claim", summary="Commercial property damage report."),
            ReferencedDoc(doc_name="Reserve_evaluation_CLM-26-00033.pdf", section_ref="Reserve Schedule, p. 1", summary="Automated reserve appraisal ceiling audit."),
        ],
        data_tags=["Policy schedule", "Reserve ceiling audit", "Supervisor sign-off rule"],
    )

    c3 = ClaimRecord(
        claim_id="CLM-26-00037",
        created_at="2026-11-11T14:10:00Z",
        policy_id="POL-1006",
        policyholder_name="Meena Iyer",
        vehicle_reg="PB10KL6006",
        line_of_business="Personal Auto",
        incident_date="2026-11-11",
        incident_time="16:10",
        location="Chandigarh",
        raw_statement="Rear-ended by an autorickshaw at traffic signal on Madhya Marg.",
        photo_paths=["data/sample_photos/rear_bumper_damage.jpg"],
        injuries=False,
        third_party=True,
        police_report=False,
        claim_status=ClaimStatusEnum.STUCK,
        current_stage=STAGE_2_COVERAGE,
        stages_completed=[STAGE_1_INTAKE],
        priority="High priority",
        action_type=ActionTypeEnum.ESCALATION,
        headline_summary="Loss date precedes policy effective date by 2 days — coverage gate failed",
        recommendation_title="Coverage Gate Failed — Adjuster Review Required",
        what_spark_did="Spark executed deterministic policy schedule validation. The incident date reported precedes policy inception. Per core protocol, auto-rejection is prohibited; claim escalated to desk adjuster.",
        confidence_score=12,
        statement_facts=StatementFacts(
            claimed_zones=["rear"],
            narrative_summary="Rear-ended by an autorickshaw at traffic signal.",
            incident_date="2026-11-11",
            incident_time="16:10",
            location="Chandigarh",
        ),
        rationale_bullets=[
            "Incident date is outside active policy schedule window.",
            "Automated rejection prohibited — must be signed off by named human adjuster.",
            "Policyholder notification on hold pending underwriter verification.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="Policy_schedule_POL-1006.pdf", section_ref="Schedule dates, p. 1", summary="Inception date and expiry terms."),
        ],
        data_tags=["Policy schedule", "Coverage Gate"],
    )

    c4 = ClaimRecord(
        claim_id="CLM-26-00040",
        created_at="2026-11-08T11:00:00Z",
        policy_id="POL-1004",
        policyholder_name="Sneha Kulkarni",
        vehicle_reg="GJ01GH4004",
        line_of_business="Homeowners",
        incident_date="2026-11-08",
        incident_time="18:45",
        location="Ahmedabad",
        raw_statement="Sideswiped pillar in apartment basement.",
        photo_paths=["data/sample_photos/front_scratch_dent.jpg"],
        injuries=False,
        third_party=False,
        police_report=False,
        claim_status=ClaimStatusEnum.NEEDS_ATTENTION,
        current_stage=STAGE_3_VISION,
        stages_completed=[STAGE_1_INTAKE, STAGE_2_COVERAGE],
        priority="High priority",
        action_type=ActionTypeEnum.QUESTION,
        headline_summary="Spark has a question — is the second-bathroom damage part of this loss?",
        recommendation_title="Claimant Clarification Needed",
        what_spark_did="Spark analyzed damage photographs and detected secondary damage inconsistency requiring claimant input.",
        confidence_score=64,
        statement_facts=StatementFacts(
            claimed_zones=["left", "rear"],
            narrative_summary="Sideswiped pillar in apartment basement.",
            incident_date="2026-11-08",
            incident_time="18:45",
            location="Ahmedabad",
        ),
        rationale_bullets=[
            "Claimed damage narrative does not fully correlate with supplementary photo angles.",
            "Outer Human-in-the-Loop triggered: Adjuster can return question to user via portal.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="Visual_audit_CLM-26-00040.pdf", section_ref="Discrepancy log", summary="Discrepancy audit log between narrative and photos."),
        ],
        data_tags=["Photo audit", "Human in the loop"],
    )

    c5 = ClaimRecord(
        claim_id="CLM-26-00120",
        created_at="2026-11-07T16:30:00Z",
        policy_id="POL-1005",
        policyholder_name="Vikram Sharma",
        vehicle_reg="DL08IJ5005",
        line_of_business="Commercial Property",
        incident_date="2026-11-09",
        incident_time="11:20",
        location="New Delhi",
        raw_statement="Hit highway guard rail after swerving to avoid stray animal.",
        photo_paths=["data/sample_photos/front_scratch_dent.jpg"],
        injuries=False,
        third_party=False,
        police_report=False,
        claim_status=ClaimStatusEnum.STUCK,
        current_stage=STAGE_2_COVERAGE,
        stages_completed=[STAGE_1_INTAKE],
        priority="High priority",
        action_type=ActionTypeEnum.ESCALATION,
        headline_summary="Bank details failed validation — payment file rejected",
        recommendation_title="Banking & KYC Escalation",
        what_spark_did="Automated payout gateway rejected disbursement due to bank account name mismatch.",
        confidence_score=45,
        statement_facts=StatementFacts(
            claimed_zones=["front"],
            narrative_summary="Hit highway guard rail.",
            incident_date="2026-11-09",
            incident_time="11:20",
            location="New Delhi",
        ),
        rationale_bullets=[
            "Payment routing rejected by bank validator.",
            "Adjuster must obtain fresh cancelled cheque or updated IFSC details.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="Payment_gateway_log_CLM-26-00120.pdf", section_ref="Error 402", summary="Banking validation error report."),
        ],
        data_tags=["Payout gateway", "KYC check"],
    )

    c6 = ClaimRecord(
        claim_id="CLM-26-00132",
        created_at="2026-11-06T12:00:00Z",
        policy_id="POL-1007",
        policyholder_name="Aditya Reddy",
        vehicle_reg="AP07MN7007",
        line_of_business="GL",
        incident_date="2026-11-07",
        incident_time="21:30",
        location="Hyderabad",
        raw_statement="Debris hit underbody and front bumper on ORR.",
        photo_paths=["data/sample_photos/severe_front_crush.jpg"],
        injuries=False,
        third_party=False,
        police_report=False,
        claim_status=ClaimStatusEnum.NEEDS_ATTENTION,
        current_stage=STAGE_2_COVERAGE,
        stages_completed=[STAGE_1_INTAKE],
        priority="High priority",
        action_type=ActionTypeEnum.REQUEST,
        headline_summary="Spark needs the signed proof of loss before it can settle",
        recommendation_title="Signed Proof of Loss Required",
        what_spark_did="Spark completed preliminary coverage and damage estimates. Settlement is staged and awaiting mandatory signed proof of loss document.",
        confidence_score=85,
        statement_facts=StatementFacts(
            claimed_zones=["front"],
            narrative_summary="Debris hit underbody and front bumper on ORR.",
            incident_date="2026-11-07",
            incident_time="21:30",
            location="Hyderabad",
        ),
        rationale_bullets=[
            "All technical assessments passed.",
            "Statutory Section 64VB compliance requires signed declaration prior to fund release.",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="FNOL_CLM-26-00132.pdf", section_ref="Coverage check", summary="Validated coverage schedule."),
        ],
        data_tags=["Regulatory compliance", "Signed proof of loss"],
    )

    c7 = ClaimRecord(
        claim_id="CLM-26-00138",
        created_at="2026-11-05T08:45:00Z",
        policy_id="POL-1001",
        policyholder_name="Rajan Pillai",
        vehicle_reg="TN09EF3003",
        line_of_business="Workers Comp",
        incident_date="2026-11-12",
        incident_time="10:00",
        location="Chennai",
        raw_statement="Work-related vehicle transit incident.",
        photo_paths=["data/sample_photos/front_scratch_dent.jpg"],
        injuries=False,
        third_party=False,
        police_report=False,
        claim_status=ClaimStatusEnum.NEEDS_ATTENTION,
        current_stage=STAGE_3_VISION,
        stages_completed=[STAGE_1_INTAKE, STAGE_2_COVERAGE],
        priority="High priority",
        action_type=ActionTypeEnum.RECOMMENDATION,
        headline_summary="Payment above $10k — second-pair-of-eyes check required by policy",
        recommendation_title="Approve the prepared outcome for $28,800.",
        what_spark_did="Spark completed triage and determined payout outcome of $28,800. Policy requires dual sign-off for payments exceeding $10,000.",
        confidence_score=87,
        statement_facts=StatementFacts(
            claimed_zones=["front"],
            narrative_summary="Work-related vehicle transit incident.",
            incident_date="2026-11-12",
            incident_time="10:00",
            location="Chennai",
        ),
        rationale_bullets=[
            "Damage verified against independent labor rate standard.",
            "Policy schedule terms verified active.",
            "Dual-approval threshold exceeded ($10,000 policy mandate).",
        ],
        referenced_documents=[
            ReferencedDoc(doc_name="FNOL_intake_CLM-26-00138.pdf", section_ref="p. 1, triage", summary="Initial FNOL narrative."),
            ReferencedDoc(doc_name="Dual_approval_mandate.pdf", section_ref="p. 3", summary="Corporate governance policy on high-value settlements."),
        ],
        data_tags=["Estimate / damage documentation", "Corporate governance", "Dual-approval threshold"],
    )

    db = ClaimsDB(claims=[c1, c2, c3, c4, c5, c6, c7], engine_paused=False)
    _save_claims_db(db)

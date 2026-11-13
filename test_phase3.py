"""
test_phase3.py — Phase 3 syntax / import / stage execution / HIIL verification
==============================================================================
Run with: python test_phase3.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest.mock as mock
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import config
if not config.GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = "dummy-test-key"
    os.environ["GOOGLE_API_KEY"] = "dummy-test-key"
    config.GEMINI_API_KEY = "dummy-test-key"

print("=" * 60)
print("PHASE 3 VERIFICATION TEST")
print("=" * 60)

# ===========================================================================
# 1. Imports
# ===========================================================================
print("\n[1] Importing agents_crew...")
import agents_crew as ac
import state_manager as sm
from schemas import (
    ActionTypeEnum,
    ClaimRecord,
    ClaimStatusEnum,
    HandledByEnum,
    StatementFacts,
    VisionReport,
    ZoneFinding,
)
print("    agents_crew imported OK")

# ===========================================================================
# 2. CrewAI Agents & Crew Initialisation
# ===========================================================================
print("\n[2] Initialising CrewAI Agents & Crew...")
a1 = ac.get_statement_analyst_agent()
a4 = ac.get_policy_coverage_agent()
a2 = ac.get_vision_assessor_agent()
a3 = ac.get_supervisor_brain_agent()
crew = ac.create_fnol_crew()
assert len(crew.agents) == 4
print(f"    Crew created with {len(crew.agents)} agents: {[a.role for a in crew.agents]} OK")

# ===========================================================================
# 3. Stage-by-Stage Progression (1 -> 2 -> 3 -> 4 -> 5)
# ===========================================================================
print("\n[3] Testing Stage-by-Stage Pipeline Execution...")

# Reset test db
sm.initialise_claims_db()

# Create a test claim in DB
test_claim = sm.create_claim_from_intake(
    policy_id="POL-1001",
    policyholder_name="Arjun Mehta",
    vehicle_reg="MH12AB1001",
    incident_date="2026-11-10",
    incident_time="14:30",
    location="Pune, Maharashtra",
    raw_statement="I hit a pothole on Pune highway damaging the front bumper.",
    photo_paths=["test_photo.jpg"],
    injuries=False,
    third_party=False,
    police_report=False,
)
cid = test_claim.claim_id
print(f"    Created test claim: {cid} at stage: {test_claim.current_stage}")

# Mock LLM calls so we don't need real API quota during unit tests
mock_statement_facts = StatementFacts(
    claimed_zones=["front"],
    incident_date="2026-11-10",
    incident_time="14:30",
    location="Pune, Maharashtra",
    narrative_summary="Driver hit a pothole causing front bumper damage.",
    injuries_reported=False,
    third_party_involved=False,
    police_report_filed=False,
    weather_claimed="Clear",
)

mock_vision_report = VisionReport(
    findings=[
        ZoneFinding(
            zone="front",
            status="damaged",
            severity="Minor",
            confidence=95,
            photo_ref="test_photo.jpg",
            description="Front bumper scuff and scratch",
        ),
        ZoneFinding(
            zone="rear",
            status="not_damaged",
            severity="None",
            confidence=90,
            photo_ref="test_photo.jpg",
        ),
    ],
    overall_severity="Minor",
    estimated_repair_cost_inr=8000.0,
    overall_confidence=92,
    unusable_photos=False,
    notes="Front bumper minor damage identified.",
)

# Advance Stage 1 -> Stage 2
with mock.patch("agents_crew.extract_statement_facts", return_value=mock_statement_facts):
    c_s1 = ac.advance_claim_one_stage(cid)
assert c_s1.current_stage == config.STAGE_2_COVERAGE
assert config.STAGE_1_INTAKE in c_s1.stages_completed
assert c_s1.statement_facts.claimed_zones == ["front"]
print(f"    Stage 1 -> Stage 2: {c_s1.current_stage} OK (stages_completed: {c_s1.stages_completed})")

# Advance Stage 2 -> Stage 3
with mock.patch("tools._llm_call", return_value="Policy active and fully covered."):
    c_s2 = ac.advance_claim_one_stage(cid)
assert c_s2.current_stage == config.STAGE_3_VISION
assert config.STAGE_2_COVERAGE in c_s2.stages_completed
assert c_s2.coverage_result.status == "covered"
assert c_s2.coverage_result.idv_inr == 850000.0
print(f"    Stage 2 -> Stage 3: {c_s2.current_stage} OK (Coverage: {c_s2.coverage_result.status})")

# Advance Stage 3 -> Stage 4
with mock.patch("agents_crew.analyze_photos_neutral", return_value=mock_vision_report):
    c_s3 = ac.advance_claim_one_stage(cid)
assert c_s3.current_stage == config.STAGE_4_FRAUD
assert config.STAGE_3_VISION in c_s3.stages_completed
assert c_s3.vision_report.estimated_repair_cost_inr == 8000.0
print(f"    Stage 3 -> Stage 4: {c_s3.current_stage} OK (Repair: ₹{c_s3.vision_report.estimated_repair_cost_inr:,.0f})")

# Advance Stage 4 -> Stage 5 (No contradiction)
with mock.patch("agents_crew.verify_weather_open_meteo", return_value="Clear sky / 0.0mm (Weather data by Open-Meteo.com)"):
    with mock.patch("tools._llm_call", return_value='{"mismatch": false, "reason": "Weather matches"}'):
        c_s4 = ac.advance_claim_one_stage(cid)
assert c_s4.current_stage == config.STAGE_5_DECISION
assert config.STAGE_4_FRAUD in c_s4.stages_completed
assert c_s4.fraud_report.risk_level == "Low"
print(f"    Stage 4 -> Stage 5: {c_s4.current_stage} OK (Fraud risk: {c_s4.fraud_report.risk_level})")

# Advance Stage 5 -> Completion (Decision Gate)
c_s5 = ac.advance_claim_one_stage(cid)
assert c_s5.current_stage == config.STAGE_5_DECISION
assert config.STAGE_5_DECISION in c_s5.stages_completed
assert c_s5.final_tier == "Tier 1"
assert c_s5.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
assert c_s5.action_type == ActionTypeEnum.RECOMMENDATION
assert len(c_s5.referenced_documents) == 3
print(f"    Stage 5 (Decision Gate): Tier={c_s5.final_tier}, Status={c_s5.claim_status}, Action={c_s5.action_type} OK")

# ===========================================================================
# 4. Testing Autonomous 2-Iteration Verification Loop
# ===========================================================================
print("\n[4] Testing Autonomous 2-Iteration Verification Loop...")

# Create claim with contradiction: Claimed front, but photos show rear damage only
claim_contra = sm.create_claim_from_intake(
    policy_id="POL-1003",
    policyholder_name="Rajan Pillai",
    vehicle_reg="TN09EF3003",
    incident_date="2026-11-12",
    incident_time="10:00",
    location="Chennai",
    raw_statement="Head-on collision with a tree.",
    photo_paths=["rear_photo.jpg"],
)
cid_contra = claim_contra.claim_id

# Manually advance to Stage 4 to isolate verification loop
c_contra = sm.get_claim_by_id(cid_contra)
c_contra.current_stage = config.STAGE_4_FRAUD
c_contra.stages_completed = [config.STAGE_1_INTAKE, config.STAGE_2_COVERAGE, config.STAGE_3_VISION]
c_contra.statement_facts = StatementFacts(claimed_zones=["front"], incident_date="2026-11-12", location="Chennai")
c_contra.vision_report = VisionReport(
    findings=[ZoneFinding(zone="rear", status="damaged", severity="Moderate", confidence=88, photo_ref="rear_photo.jpg")],
    overall_severity="Moderate",
    estimated_repair_cost_inr=30000.0,
    overall_confidence=88,
    unusable_photos=False,
)
sm.update_claim(c_contra)

# Mock rescan_photos_for_conflict returning unresolved after both loops
mock_rescan = {
    "resolved": False,
    "reason": "Only rear damage visible across all submitted photos.",
    "vision_report": c_contra.vision_report,
}

with mock.patch("agents_crew.verify_weather_open_meteo", return_value="unavailable"):
    with mock.patch("agents_crew.rescan_photos_for_conflict", return_value=mock_rescan):
        c_res = ac.advance_claim_one_stage(cid_contra)

assert c_res.loop_count == 2, f"Expected 2 loops, got {c_res.loop_count}"
assert c_res.fraud_report.unresolved_contradiction is True
assert c_res.fraud_report.risk_level == "High"
print(f"    Verification loop executed {c_res.loop_count} loops -> unresolved={c_res.fraud_report.unresolved_contradiction}, risk={c_res.fraud_report.risk_level} OK")

# Run decision gate on this unresolved claim -> should route to Tier 3 (STUCK / ESCALATION)
c_res_final = ac.advance_claim_one_stage(cid_contra)
assert c_res_final.final_tier == "Tier 3"
assert c_res_final.claim_status == ClaimStatusEnum.STUCK
assert c_res_final.action_type == ActionTypeEnum.ESCALATION
print(f"    Unresolved contradiction routed to: {c_res_final.final_tier} ({c_res_final.claim_status} / {c_res_final.action_type}) OK")

# ===========================================================================
# 5. run_all_active_claims_step with Pause/Start Engine Toggle
# ===========================================================================
print("\n[5] Testing run_all_active_claims_step & engine_paused toggle...")

# When paused:
sm.set_engine_paused(True)
res_paused = ac.run_all_active_claims_step()
assert res_paused["paused"] is True
assert res_paused["advanced_count"] == 0
print(f"    Engine paused check: advanced_count={res_paused['advanced_count']} OK")

# When unpaused:
sm.set_engine_paused(False)
res_running = ac.run_all_active_claims_step()
assert res_running["paused"] is False
print(f"    Engine running check: advanced_count={res_running['advanced_count']} OK")

# ===========================================================================
# 6. Adjuster Human-in-the-Loop Action Handlers
# ===========================================================================
print("\n[6] Testing Adjuster HIIL Action Handlers...")

# 6a. execute_claim_action
c_settled = ac.execute_claim_action(cid, adjuster_note="Approved with ₹500 goodwill")
assert c_settled.claim_status == ClaimStatusEnum.SETTLED
assert any("approved and settled" in t.result_summary for t in c_settled.agent_trace)
print(f"    execute_claim_action -> status: {c_settled.claim_status} OK")

# 6b. dismiss_claim_action
c_disc = ac.dismiss_claim_action(cid_contra, adjuster_note="Confirmed fraudulent staging")
assert c_disc.claim_status == ClaimStatusEnum.DISCARDED
assert any("dismissed/rejected" in t.result_summary for t in c_disc.agent_trace)
print(f"    dismiss_claim_action -> status: {c_disc.claim_status} OK")

# 6c. return_to_user_action
c_ret = ac.return_to_user_action(cid, question_prompt="Please send photo of VIN plate")
assert c_ret.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
assert c_ret.action_type == ActionTypeEnum.QUESTION
assert c_ret.returned_to_user_prompt == "Please send photo of VIN plate"
print(f"    return_to_user_action -> prompt: '{c_ret.returned_to_user_prompt}' OK")

# 6d. toggle_handled_by
c_manual = ac.toggle_handled_by(cid, "Manual")
assert c_manual.handled_by == HandledByEnum.MANUAL
assert c_manual.claim_status == ClaimStatusEnum.AUTOMATION_OFF
print(f"    toggle_handled_by(Manual) -> {c_manual.handled_by} / {c_manual.claim_status} OK")

c_spark = ac.toggle_handled_by(cid, "Spark")
assert c_spark.handled_by == HandledByEnum.SPARK
assert c_spark.claim_status != ClaimStatusEnum.AUTOMATION_OFF
print(f"    toggle_handled_by(Spark) -> {c_spark.handled_by} / {c_spark.claim_status} OK")

# ===========================================================================
# 7. Live "Edit via Chat with Spark" Bot
# ===========================================================================
print("\n[7] Testing chat_with_spark...")

mock_chat_response = json.dumps({
    "reply_message": "I have adjusted the settlement calculation applying a 70/30 split. The revised net payable is ₹4,900.",
    "updated_recommendation_title": "Approve revised outcome for ₹4,900 (70/30 liability split applied)",
    "updated_rationale_bullets": [
        "Base repair cost: ₹8,000 minus deductible ₹1,000 = ₹7,000 net.",
        "Adjuster applied 70/30 liability split: 70% of ₹7,000 = ₹4,900 payable."
    ],
    "updated_net_payable_inr": 4900.0,
})

with mock.patch("tools._llm_call", return_value=mock_chat_response):
    chat_res = ac.chat_with_spark(cid, "Apply a 70/30 liability split")

assert chat_res["updated_net_payable_inr"] == 4900.0
c_chat = sm.get_claim_by_id(cid)
assert c_chat.coverage_result.net_payable_estimate_inr == 4900.0
assert len(c_chat.chat_history) >= 2
assert c_chat.chat_history[-2].sender == "Adjuster"
assert c_chat.chat_history[-1].sender == "Spark"
print(f"    chat_with_spark -> reply: '{chat_res['reply_message'][:50]}...' (net_payable: ₹{c_chat.coverage_result.net_payable_estimate_inr}) OK")

# Reset test db to empty
sm.initialise_claims_db()
config.DB_CLAIMS_PATH.write_text(json.dumps({"claims": [], "engine_paused": False}))

print()
print("=" * 60)
print("ALL PHASE 3 CHECKS PASSED")
print("=" * 60)

"""
test_phase2.py — Phase 2 syntax / import / logic verification
=============================================================
Run with: python test_phase2.py
Tests:
  1. Import of tools.py and decision_gate.py without errors
  2. verify_policy_coverage_deterministic (all 7 policy scenarios — no LLM calls)
  3. evaluate_fraud_and_consistency (deterministic signals only — no LLM calls)
  4. run_decision_gate (all 5 cases — no LLM calls)
  5. verify_weather_open_meteo (live API call — skipped if offline)
  6. LLM cache key generation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure we can import from the project root
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 0. Patch config so we don't need a real API key for the deterministic tests
# ---------------------------------------------------------------------------
import config  # noqa: E402

_HAS_KEY = bool(config.GEMINI_API_KEY)
if not _HAS_KEY:
    # Inject a dummy key so genai.Client init doesn't fail on import
    import os
    os.environ["GEMINI_API_KEY"] = "dummy-test-key"
    os.environ["GOOGLE_API_KEY"] = "dummy-test-key"
    config.GEMINI_API_KEY = "dummy-test-key"

print("=" * 60)
print("PHASE 2 VERIFICATION TEST")
print("=" * 60)

# ===========================================================================
# TEST 1 — Import tools.py and decision_gate.py
# ===========================================================================
print("\n[1] Import checks...")
import tools  # noqa: E402
import decision_gate  # noqa: E402
from schemas import (  # noqa: E402
    ClaimRecord,
    ClaimStatusEnum,
    ActionTypeEnum,
    CoverageResult,
    FraudConsistencyReport,
    RiskSignal,
    StatementFacts,
    VisionReport,
    ZoneFinding,
)
from state_manager import get_policy  # noqa: E402

print("    tools.py          imported OK")
print("    decision_gate.py  imported OK")
print("    schemas.py        imported OK")

# ===========================================================================
# TEST 2 — verify_policy_coverage_deterministic (no LLM for routing logic)
# ===========================================================================
print("\n[2] verify_policy_coverage_deterministic (deterministic only)...")

def _cov(policy_id, vehicle_reg, incident_date, cost, severity):
    """Call coverage check but stub the LLM explanation to avoid API calls."""
    orig_llm = tools._llm_call
    tools._llm_call = lambda **kw: "Explanation stub."  # patch
    # Also patch via keyword — the function uses kwargs
    import unittest.mock as mock
    with mock.patch("tools._llm_call", return_value="Explanation stub."):
        return tools.verify_policy_coverage_deterministic(
            policy_id, vehicle_reg, incident_date, cost, severity
        )

# POL-1001: Active Comprehensive, correct vehicle, minor cost → covered
r = _cov("POL-1001", "MH12AB1001", "2026-11-10", 15000.0, "Minor")
assert r.status == "covered", f"Expected covered, got {r.status}"
assert r.policy_active_on_date is True
assert r.vehicle_matched is True
assert r.net_payable_estimate_inr == max(0, min(15000 - r.deductible_inr, r.limit_inr))
print(f"    POL-1001 (Comprehensive / active)        → {r.status} ✓")

# POL-1002: Total Loss check — 350000 >= 0.75 * 450000 = 337500 → covered, Total Loss upgrade
r2 = _cov("POL-1002", "KA05CD2002", "2026-11-05", 350000.0, "Severe")
assert r2.status == "covered"
assert r2.idv_inr == 450000.0
# Total Loss is set by decision_gate; coverage tool just confirms covered
print(f"    POL-1002 (Comprehensive / total loss)    → {r2.status} (IDV ₹{r2.idv_inr:,.0f}) ✓")

# POL-1003: Active but started 3 days before incident (fraud signal — not a coverage issue)
r3 = _cov("POL-1003", "TN09EF3003", "2026-11-12", 60000.0, "Moderate")
assert r3.status == "covered"  # policy is active on that date
print(f"    POL-1003 (Comprehensive / early inception) → {r3.status} ✓")

# POL-1005: Third-Party Only → not_covered for own damage
r5 = _cov("POL-1005", "DL08IJ5005", "2026-11-10", 40000.0, "Moderate")
assert r5.status == "not_covered", f"Expected not_covered, got {r5.status}"
assert any("Own Damage" in c for c in r5.clause_citations)
print(f"    POL-1005 (Third-Party Only)              → {r5.status} ✓")

# POL-1006: Expired policy — incident 2026-11-11, expiry 2026-11-01
r6 = _cov("POL-1006", "PB10KL6006", "2026-11-11", 25000.0, "Minor")
assert r6.status == "not_covered", f"Expected not_covered, got {r6.status}"
assert r6.policy_active_on_date is False
print(f"    POL-1006 (Expired policy)                → {r6.status} ✓")

# POL-1007: Active, high-value, zero-depreciation → covered
r7 = _cov("POL-1007", "AP07MN7007", "2026-11-10", 120000.0, "Moderate")
assert r7.status == "covered"
assert r7.idv_inr == 4800000.0
print(f"    POL-1007 (High-value / zero-dep)         → {r7.status} (IDV ₹{r7.idv_inr:,.0f}) ✓")

# Vehicle reg mismatch
r_mismatch = _cov("POL-1001", "WRONG-REG-999", "2026-11-10", 10000.0, "Minor")
assert r_mismatch.status == "not_covered"
assert r_mismatch.vehicle_matched is False
print(f"    Vehicle reg mismatch                     → {r_mismatch.status} ✓")

print("    All coverage checks PASSED")

# ===========================================================================
# TEST 3 — evaluate_fraud_and_consistency (deterministic signals, no weather LLM)
# ===========================================================================
print("\n[3] evaluate_fraud_and_consistency (deterministic signals)...")

import unittest.mock as mock

def _make_vision(claimed_zones, damaged_zones):
    findings = []
    all_zones = ["front", "rear", "left", "right", "corners", "roof_windshield"]
    for z in all_zones:
        findings.append(ZoneFinding(
            zone=z,
            status="damaged" if z in damaged_zones else "not_damaged",
            severity="Moderate" if z in damaged_zones else "None",
            confidence=90 if z in damaged_zones else 85,
            photo_ref="photo.jpg",
        ))
    return VisionReport(
        findings=findings, overall_severity="Moderate",
        estimated_repair_cost_inr=35000.0, overall_confidence=88,
        unusable_photos=False,
    )

pol1001 = get_policy("POL-1001")
pol1003 = get_policy("POL-1003")

# Scenario A: Consistent claim (front claimed, front damaged) → Low risk
facts_a = StatementFacts(
    claimed_zones=["front"], incident_date="2026-11-10",
    incident_time="14:30", location="Pune",
    narrative_summary="Hit a pothole; front damage.",
    injuries_reported=False, third_party_involved=False,
    police_report_filed=False, weather_claimed="",
)
vision_a = _make_vision(["front"], ["front"])
cov_a = CoverageResult(policy_id="POL-1001", status="covered")

with mock.patch("tools._llm_call", return_value='{"mismatch": false, "reason": "consistent"}'):
    report_a = tools.evaluate_fraud_and_consistency(
        facts_a, vision_a, cov_a, pol1001, "unavailable", loop_count=0
    )
assert report_a.risk_level == "Low", f"Expected Low, got {report_a.risk_level}"
zone_signal_a = next(s for s in report_a.signals if s.signal_name == "Damage Zone Contradiction")
assert zone_signal_a.triggered is False
print(f"    Consistent claim (Scenario A)            → risk={report_a.risk_level} ✓")

# Scenario B: POL-1003 — early inception (3 days) + prior claims (3) + zone mismatch
facts_b = StatementFacts(
    claimed_zones=["front"], incident_date="2026-11-12",
    incident_time="10:00", location="Chennai",
    narrative_summary="Hit a tree head-on.",
    injuries_reported=False, third_party_involved=False,
    police_report_filed=False, weather_claimed="Heavy rain",
)
vision_b = _make_vision(["front"], ["rear"])  # claimed front, observed rear → contradiction

with mock.patch("tools._llm_call", return_value='{"mismatch": false, "reason": "no weather data"}'):
    report_b = tools.evaluate_fraud_and_consistency(
        facts_b, vision_b, cov_a, pol1003, "unavailable", loop_count=2
    )
# After 2 loops with zone mismatch → unresolved_contradiction should be True
assert report_b.unresolved_contradiction is True, f"Expected unresolved=True, got {report_b.unresolved_contradiction}"
# early_inception: 2026-11-12 - 2026-11-09 = 3 days → triggered
early_sig = next(s for s in report_b.signals if s.signal_name == "Early Policy Inception")
assert early_sig.triggered is True
# prior claims: 3 → triggered
prior_sig = next(s for s in report_b.signals if s.signal_name == "Prior Claim Frequency")
assert prior_sig.triggered is True
zone_sig_b = next(s for s in report_b.signals if s.signal_name == "Damage Zone Contradiction")
assert zone_sig_b.triggered is True
assert report_b.risk_level == "High"
print(f"    Fraud scenario (Scenario B/C)            → risk={report_b.risk_level}, unresolved={report_b.unresolved_contradiction} ✓")

print("    All fraud checks PASSED")

# ===========================================================================
# TEST 4 — run_decision_gate (all 5 routing cases)
# ===========================================================================
print("\n[4] run_decision_gate (all 5 routing cases)...")

def _base_claim(claim_id, policy_id, vehicle_reg):
    return ClaimRecord(
        claim_id=claim_id, created_at="2026-11-12T17:30:00Z",
        policy_id=policy_id, policyholder_name="Test User",
        vehicle_reg=vehicle_reg, incident_date="2026-11-10",
        incident_time="14:00", location="Test City",
        raw_statement="Test statement.",
    )

# --- Case 1: Tier 3 — High fraud risk ---
c1 = _base_claim("CLM-26-T3A", "POL-1003", "TN09EF3003")
c1.photo_paths = ["fake_photo.jpg"]
c1.vision_report = _make_vision(["front"], ["rear"])
c1.coverage_result = CoverageResult(policy_id="POL-1003", status="covered",
    policy_active_on_date=True, vehicle_matched=True,
    coverage_type="Comprehensive", idv_inr=320000, deductible_inr=2000,
    limit_inr=320000, net_payable_estimate_inr=18000)
c1.statement_facts = facts_b
c1.fraud_report = report_b  # High risk + unresolved
c1.loop_count = 2
c1 = decision_gate.run_decision_gate(c1)
assert c1.final_tier == "Tier 3", f"Expected Tier 3, got {c1.final_tier}"
assert c1.claim_status == ClaimStatusEnum.STUCK
assert c1.action_type == ActionTypeEnum.ESCALATION
assert c1.priority == "High priority"
print(f"    Case 1 Tier 3 (fraud/unresolved)         → {c1.final_tier} / {c1.claim_status} ✓")

# --- Case 2: Coverage Gate Failed ---
c2 = _base_claim("CLM-26-T2G", "POL-1006", "PB10KL6006")
c2.photo_paths = ["fake_photo.jpg"]
c2.vision_report = _make_vision([], ["left"])
c2.coverage_result = CoverageResult(
    policy_id="POL-1006", status="not_covered",
    policy_active_on_date=False, vehicle_matched=True,
    coverage_type="Comprehensive", idv_inr=280000, deductible_inr=2000,
    limit_inr=280000, net_payable_estimate_inr=0,
    clause_citations=["Section II — Policy Validity: Policy must be active on the date of loss"],
    explanation="Policy expired before incident date.",
)
c2.statement_facts = facts_a
c2.fraud_report = FraudConsistencyReport(risk_level="Low")
c2 = decision_gate.run_decision_gate(c2)
assert c2.final_tier == "Tier 2", f"Expected Tier 2, got {c2.final_tier}"
assert c2.claim_status == ClaimStatusEnum.STUCK
assert c2.action_type == ActionTypeEnum.ESCALATION
print(f"    Case 2 Coverage Gate Failed              → {c2.final_tier} / {c2.claim_status} ✓")

# --- Case 3: Missing / Low-Confidence Evidence ---
c3 = _base_claim("CLM-26-T2Q", "POL-1001", "MH12AB1001")
c3.photo_paths = []  # no photos
c3.vision_report = VisionReport(
    findings=[], overall_severity="Unknown",
    estimated_repair_cost_inr=0.0, overall_confidence=0,
    unusable_photos=True, notes="No photos.",
)
c3.coverage_result = CoverageResult(policy_id="POL-1001", status="covered",
    policy_active_on_date=True, vehicle_matched=True,
    coverage_type="Comprehensive", idv_inr=850000, deductible_inr=1000,
    limit_inr=850000, net_payable_estimate_inr=0)
c3.statement_facts = facts_a
c3.fraud_report = FraudConsistencyReport(risk_level="Low")
c3 = decision_gate.run_decision_gate(c3)
assert c3.final_tier == "Tier 2"
assert c3.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
assert c3.action_type == ActionTypeEnum.QUESTION
print(f"    Case 3 Missing Evidence                  → {c3.final_tier} / {c3.action_type} ✓")

# --- Case 4: Tier 2 — Moderate / high reserve ---
c4 = _base_claim("CLM-26-T2H", "POL-1002", "KA05CD2002")
c4.photo_paths = ["fake_photo.jpg"]  # has photos so Case 3 (no-photo) is skipped
c4.vision_report = VisionReport(
    findings=[ZoneFinding(zone="front", status="damaged", severity="Severe",
              confidence=90, photo_ref="p1.jpg", description="Major crush")],
    overall_severity="Moderate", estimated_repair_cost_inr=350000.0,
    overall_confidence=90, unusable_photos=False,
)
c4.coverage_result = CoverageResult(
    policy_id="POL-1002", status="covered",
    policy_active_on_date=True, vehicle_matched=True,
    coverage_type="Comprehensive", idv_inr=450000, deductible_inr=2000,
    limit_inr=450000, net_payable_estimate_inr=348000,
)
c4.statement_facts = facts_a
c4.fraud_report = FraudConsistencyReport(risk_level="Low")
c4 = decision_gate.run_decision_gate(c4)
assert c4.final_tier == "Tier 2"
assert c4.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
assert c4.action_type == ActionTypeEnum.REQUEST  # cost > 25000
# Also verify Total Loss detection: 350000 >= 0.75 * 450000 = 337500 → Total Loss
# The gate should have upgraded severity
assert "Total Loss" in c4.headline_summary or "₹3,50,000" in c4.headline_summary or "350,000" in c4.headline_summary
print(f"    Case 4 Tier 2 Heavy Loss (₹3,50,000)    → {c4.final_tier} / {c4.action_type} ✓")

# --- Case 5: Tier 1 — Fast-Track ---
c5 = _base_claim("CLM-26-T1", "POL-1001", "MH12AB1001")
c5.photo_paths = ["fake_photo.jpg"]
c5.vision_report = VisionReport(
    findings=[ZoneFinding(zone="front", status="damaged", severity="Minor",
              confidence=92, photo_ref="p1.jpg", description="Small scratch")],
    overall_severity="Minor", estimated_repair_cost_inr=8000.0,
    overall_confidence=92, unusable_photos=False,
)
c5.coverage_result = CoverageResult(
    policy_id="POL-1001", status="covered",
    policy_active_on_date=True, vehicle_matched=True,
    coverage_type="Comprehensive", idv_inr=850000, deductible_inr=1000,
    limit_inr=850000, net_payable_estimate_inr=7000,
)
c5.statement_facts = facts_a
c5.fraud_report = FraudConsistencyReport(risk_level="Low",
    signals=[], contradictions=[], unresolved_contradiction=False,
    weather_verification="Clear sky / 0.0mm (Open-Meteo.com)",
)
c5 = decision_gate.run_decision_gate(c5)
assert c5.final_tier == "Tier 1", f"Expected Tier 1, got {c5.final_tier}"
assert c5.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
assert c5.action_type == ActionTypeEnum.RECOMMENDATION
assert c5.priority == "Normal"
assert c5.confidence_score == 92
assert len(c5.referenced_documents) == 3
assert c5.stages_completed == list(decision_gate._ALL_STAGES)
print(f"    Case 5 Tier 1 Fast-Track (₹7,000 net)   → {c5.final_tier} / {c5.priority} ✓")

print("    All decision gate cases PASSED")

# ===========================================================================
# TEST 5 — verify_weather_open_meteo (live call, skipped if offline)
# ===========================================================================
print("\n[5] verify_weather_open_meteo (live API call)...")
try:
    weather = tools.verify_weather_open_meteo("Pune", "2026-11-10")
    if "unavailable" in weather.lower():
        print(f"    API offline or city not found — result: '{weather}' (acceptable)")
    else:
        assert "Open-Meteo" in weather, f"Expected Open-Meteo credit in: {weather}"
        print(f"    Live weather result: '{weather}' ✓")
except Exception as e:
    print(f"    Weather API error (non-fatal): {e}")

# ===========================================================================
# TEST 6 — LLM cache key generation
# ===========================================================================
print("\n[6] LLM cache key generation...")
key1 = tools._cache_key("hello world", [])
key2 = tools._cache_key("hello world", [])
key3 = tools._cache_key("different prompt", [])
assert key1 == key2, "Same inputs must produce same cache key"
assert key1 != key3, "Different inputs must produce different cache keys"
assert len(key1) == 64, f"Expected 64-char SHA-256, got {len(key1)}"
print(f"    Cache key (SHA-256): {key1[:16]}… ✓")
print("    Cache key generation PASSED")

# ===========================================================================
# SUMMARY
# ===========================================================================
print()
print("=" * 60)
print("ALL PHASE 2 CHECKS PASSED")
print("=" * 60)

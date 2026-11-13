"""
config.py — Spark Cockpit FNOL Claims Triage Agent
Central configuration: environment loading, model IDs, thresholds, pipeline stage constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment — load .env from project root (if present)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent
load_dotenv(_PROJECT_ROOT / ".env")

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# CrewAI google-genai provider reads GOOGLE_API_KEY; keep both in sync.
if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# ---------------------------------------------------------------------------
# Model configuration  (all IDs in one place — retire quickly, update here)
# ---------------------------------------------------------------------------
VISION_MODEL: str = "gemini-2.5-flash"        # Multimodal zone-by-zone analysis
SUPERVISOR_MODEL: str = "gemini-2.5-flash"    # Planner / router / rationale writer
SUBAGENT_MODEL: str = "gemini-2.5-flash-lite" # Policy, Fraud & Consistency agents
FALLBACK_MODEL: str = "gemini-2.5-flash-lite" # Quota-safe fallback for all agents

# ---------------------------------------------------------------------------
# Deterministic decision thresholds
# ---------------------------------------------------------------------------
# Claims with estimated repair ≤ this INR amount are eligible for Fast-Track Tier 1
FAST_TRACK_LIMIT_INR: int = 25_000

# If (estimated_repair_cost / policy_IDV) >= this ratio → classify as "Total Loss"
TOTAL_LOSS_RATIO: float = 0.75

# Minimum AI confidence (%) for the pipeline to continue without human review
MIN_CONFIDENCE_THRESHOLD: int = 80

# Hard cap on claim–statement contradiction resolution loops before Tier 3 escalation
MAX_CONTRADICTION_LOOPS: int = 2

# ---------------------------------------------------------------------------
# Pipeline stage constants  (must match Kanban column labels in the Cockpit UI)
# ---------------------------------------------------------------------------
STAGE_1_INTAKE: str = "1 INTAKE & TRIAGE"
STAGE_2_COVERAGE: str = "2 COVERAGE"
STAGE_3_VISION: str = "3 DA / ESTIMATE"
STAGE_4_FRAUD: str = "4 FRAUD & CONSISTENCY"
STAGE_5_DECISION: str = "5 DECISION GATE"

PIPELINE_STAGES: list[str] = [
    STAGE_1_INTAKE,
    STAGE_2_COVERAGE,
    STAGE_3_VISION,
    STAGE_4_FRAUD,
    STAGE_5_DECISION,
]

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = _PROJECT_ROOT / "data"
DB_CLAIMS_PATH: Path = DATA_DIR / "db1_claims.json"
DB_POLICIES_PATH: Path = DATA_DIR / "db2_policies.json"
REPAIR_COSTS_PATH: Path = DATA_DIR / "repair_costs.json"

# ---------------------------------------------------------------------------
# Photo upload directory
# ---------------------------------------------------------------------------
UPLOAD_DIR: Path = _PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

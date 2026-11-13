"""
server.py — Spark Cockpit FastAPI backend bridge
Wraps state_manager.py and agents_crew.py with REST endpoints and serves the static frontend.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Ensure required directories exist before importing backend modules
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Backend imports
# ---------------------------------------------------------------------------
import config
import state_manager as sm
import agents_crew as ac
from schemas import (
    ClaimRecord,
    ClaimStatusEnum,
    ActionTypeEnum,
    HandledByEnum,
)
from config import (
    STAGE_1_INTAKE,
    STAGE_2_COVERAGE,
    STAGE_3_VISION,
    STAGE_4_FRAUD,
    STAGE_5_DECISION,
    PIPELINE_STAGES,
)

sm.initialise_claims_db()

app = FastAPI(title="Spark Cockpit API", version="1.0.0")

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ===========================================================================
# HELPERS
# ===========================================================================

def _claim_to_dict(c: ClaimRecord) -> Dict[str, Any]:
    """Serialize a ClaimRecord to a plain dict (for JSON responses)."""
    d = c.model_dump(mode="json")
    web_paths = []
    for p in d.get("photo_paths", []):
        p_obj = Path(p)
        if str(p).startswith("/uploads") or str(p).startswith("/static"):
            web_paths.append(p)
            continue
        norm = str(p).replace("\\", "/")
        if "data/uploads/" in norm:
            after = norm.split("data/uploads/", 1)[1]
            web_paths.append(f"/uploads/{after}")
        elif "uploads/" in norm:
            after = norm.split("uploads/", 1)[1]
            web_paths.append(f"/uploads/{after}")
        else:
            fname = p_obj.name
            web_paths.append(f"/static/sample_photos/{fname}")
    d["photo_paths"] = web_paths
    return d


def _compute_stage_counts(claims: List[ClaimRecord]) -> Dict[str, Any]:
    result = {}
    for stage in PIPELINE_STAGES:
        in_stage = [
            c for c in claims
            if c.current_stage == stage
            and c.claim_status not in (
                ClaimStatusEnum.SETTLED,
                ClaimStatusEnum.DISCARDED,
                ClaimStatusEnum.AUTOMATION_OFF,
            )
        ]
        red = sum(
            1 for c in in_stage
            if c.claim_status == ClaimStatusEnum.STUCK
            or c.action_type == ActionTypeEnum.ESCALATION
        )
        amber = sum(
            1 for c in in_stage
            if c.claim_status == ClaimStatusEnum.NEEDS_ATTENTION
            or c.priority == "High priority"
        )
        green = max(0, len(in_stage) - red - amber)
        result[stage] = {
            "open_count": len(in_stage),
            "red_count": red,
            "amber_count": amber,
            "green_count": green,
        }
    return result


def _compute_hud_counts(claims: List[ClaimRecord]) -> Dict[str, Any]:
    counts: Dict[str, int] = {
        "IN PROGRESS": 0,
        "NEEDS ATTENTION": 0,
        "STUCK": 0,
        "AUTOMATION OFF": 0,
        "SETTLED": 0,
        "DISCARDED": 0,
    }
    for c in claims:
        status_str = c.claim_status.value if hasattr(c.claim_status, "value") else str(c.claim_status)
        if status_str in counts:
            counts[status_str] += 1
    counts["total"] = len(claims)
    return counts


# ===========================================================================
# ROUTES — Static SPA entry point
# ===========================================================================

@app.get("/")
def serve_index():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="index.html not found in static/")
    return FileResponse(str(index))


# ===========================================================================
# GET /api/state
# ===========================================================================

@app.get("/api/state")
def get_state():
    db = sm.load_claims_db()
    claims = db.claims
    policies = sm.load_policies()

    sorted_claims = sorted(
        claims,
        key=lambda c: c.created_at,
        reverse=True,
    )

    return JSONResponse({
        "engine_paused": db.engine_paused,
        "claims": [_claim_to_dict(c) for c in sorted_claims],
        "policies": policies,
        "hud_counts": _compute_hud_counts(claims),
        "stage_counts": _compute_stage_counts(claims),
    })


# ===========================================================================
# POST /api/claims/create — Single FNOL Submission
# ===========================================================================

@app.post("/api/claims/create")
async def create_claim(
    policy_id: str = Form(""),
    policyholder_name: str = Form(""),
    vehicle_reg: str = Form(""),
    vehicle_name: str = Form(""),
    incident_date: str = Form(""),
    incident_time: str = Form(""),
    location: str = Form(""),
    raw_statement: str = Form(""),
    injuries: str = Form("false"),
    third_party: str = Form("false"),
    police_report: str = Form("false"),
    run_immediately: str = Form("false"),
    photo_path: str = Form(""),
    photos: List[UploadFile] = File(default=[]),
):
    def _bool(v: str) -> bool:
        return str(v).lower() in ("1", "true", "yes", "on")

    from datetime import datetime, timezone
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_time_str = datetime.now(timezone.utc).strftime("%H:%M")

    clean_pid = policy_id.strip() or "POL-UNVERIFIED"
    clean_holder = policyholder_name.strip() or "Claimant (Unassigned)"
    vname = vehicle_name.strip()
    vreg = vehicle_reg.strip()
    if vname and vreg:
        clean_vreg = f"{vreg} ({vname})"
    elif vname:
        clean_vreg = vname
    elif vreg:
        clean_vreg = vreg
    else:
        clean_vreg = "UNREGISTERED"

    clean_date = incident_date.strip() or today_str
    clean_time = incident_time.strip() or now_time_str
    clean_loc = location.strip() or "Location Unspecified"

    claim = sm.create_claim_from_intake(
        policy_id=clean_pid,
        policyholder_name=clean_holder,
        vehicle_reg=clean_vreg,
        incident_date=clean_date,
        incident_time=clean_time,
        location=clean_loc,
        raw_statement=raw_statement.strip(),
        photo_paths=[],
        injuries=_bool(injuries),
        third_party=_bool(third_party),
        police_report=_bool(police_report),
    )

    saved_paths: List[str] = []
    if photos:
        claim_upload_dir = UPLOADS_DIR / claim.claim_id
        claim_upload_dir.mkdir(parents=True, exist_ok=True)
        for photo in photos:
            if not photo.filename:
                continue
            dest = claim_upload_dir / photo.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(photo.file, f)
            saved_paths.append(str(dest).replace("\\", "/"))

    # If no files uploaded, link preset accident image (only if photo_path provided)
    if not saved_paths and photo_path:
        candidate = photo_path
        if candidate:
            fname = Path(candidate).name
            src1 = BASE_DIR / "data" / "sample_photos" / fname
            src2 = STATIC_DIR / "sample_photos" / fname
            src = src1 if src1.exists() else (src2 if src2.exists() else None)
            if src and src.exists():
                claim_upload_dir = UPLOADS_DIR / claim.claim_id
                claim_upload_dir.mkdir(parents=True, exist_ok=True)
                dest = claim_upload_dir / fname
                shutil.copyfile(src, dest)
                saved_paths.append(str(dest).replace("\\", "/"))
            else:
                saved_paths.append(candidate)

    if saved_paths:
        claim.photo_paths = saved_paths
        sm.update_claim(claim)

    if _bool(run_immediately):
        try:
            claim = ac.run_claim_to_completion(claim.claim_id)
        except Exception as e:
            claim = sm.get_claim_by_id(claim.claim_id) or claim
            claim.headline_summary = f"Pipeline error: {e}"
            sm.update_claim(claim)

    return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})


# ===========================================================================
# POST /api/claims/batch-create — Feed selected test sets (1 to 7) to Cockpit
# ===========================================================================

class BatchCreateBody(BaseModel):
    policy_ids: List[str]
    run_immediately: bool = False


@app.post("/api/claims/batch-create")
def batch_create_claims(body: BatchCreateBody):
    policies = sm.load_policies()
    created_claims = []

    PRESETS_LOOKUP = {
        "POL-1001": {
            "date": "2026-11-10", "time": "14:30", "location": "Pune",
            "statement": "While driving on Pune-Solapur Highway, a loose stone from a truck hit my front bumper and radiator grill, causing a dent and scratch. No other vehicles were involved.",
            "photo": "pol_1001_damage.jpg"
        },
        "POL-1002": {
            "date": "2026-11-05", "time": "09:15", "location": "Bengaluru",
            "statement": "Severe collision on Outer Ring Road. An oncoming cement mixer rammed into the front and left side of my vehicle at high speed. The front engine compartment is completely crushed, suspension broken, and airbags deployed.",
            "photo": "pol_1002_damage.jpg"
        },
        "POL-1003": {
            "date": "2026-11-12", "time": "10:00", "location": "Chennai",
            "statement": "I was driving through a heavy rainstorm when my car skidded and crashed head-on directly into a banyan tree, crushing the entire front hood and radiator.",
            "photo": "pol_1003_damage.jpg"
        },
        "POL-1004": {
            "date": "2026-11-08", "time": "18:45", "location": "Ahmedabad",
            "statement": "Sideswiped a concrete pillar while turning into my apartment basement parking lot, scratching the left doors and rear-left quarter panel.",
            "photo": "pol_1004_damage.jpg"
        },
        "POL-1005": {
            "date": "2026-11-09", "time": "11:20", "location": "New Delhi",
            "statement": "Hit a highway guard rail after swerving to avoid a stray animal, damaging the front bumper, left fender, and headlights.",
            "photo": "pol_1005_damage.jpg"
        },
        "POL-1006": {
            "date": "2026-11-11", "time": "16:10", "location": "Chandigarh",
            "statement": "Rear-ended by an autorickshaw at a traffic signal on Madhya Marg, cracking the rear bumper and tailgate.",
            "photo": "pol_1006_damage.jpg"
        },
        "POL-1007": {
            "date": "2026-11-07", "time": "21:30", "location": "Hyderabad",
            "statement": "Hit road construction debris on the Outer Ring Road. Underbody and front bumper damaged, front alloy wheel cracked.",
            "photo": "pol_1007_damage.jpg"
        },
    }

    for pid in body.policy_ids:
        p = policies.get(pid, {})
        preset = PRESETS_LOOKUP.get(pid, {})

        claim = sm.create_claim_from_intake(
            policy_id=pid,
            policyholder_name=p.get("policyholder_name", "Applicant"),
            vehicle_reg=p.get("vehicle_reg", ""),
            incident_date=preset.get("date", "2026-11-10"),
            incident_time=preset.get("time", "14:30"),
            location=preset.get("location", "Pune"),
            raw_statement=preset.get("statement", "Vehicle damage incident reported."),
            photo_paths=[],
            injuries=False,
            third_party=False,
            police_report=False,
        )

        photo_filename = preset.get("photo", f"{pid.lower().replace('-', '_')}_damage.jpg")
        src1 = BASE_DIR / "data" / "sample_photos" / photo_filename
        src2 = STATIC_DIR / "sample_photos" / photo_filename
        src = src1 if src1.exists() else (src2 if src2.exists() else None)
        if src and src.exists():
            claim_upload_dir = UPLOADS_DIR / claim.claim_id
            claim_upload_dir.mkdir(parents=True, exist_ok=True)
            dest = claim_upload_dir / photo_filename
            shutil.copyfile(src, dest)
            claim.photo_paths = [str(dest).replace("\\", "/")]
            sm.update_claim(claim)

        if body.run_immediately:
            try:
                claim = ac.run_claim_to_completion(claim.claim_id)
            except Exception as e:
                claim = sm.get_claim_by_id(claim.claim_id) or claim
                claim.headline_summary = f"Pipeline error: {e}"
                sm.update_claim(claim)

        created_claims.append(_claim_to_dict(claim))

    db = sm.load_claims_db()
    return JSONResponse({
        "ok": True,
        "count": len(created_claims),
        "created_claims": created_claims,
        "hud_counts": _compute_hud_counts(db.claims),
        "stage_counts": _compute_stage_counts(db.claims),
    })


# ===========================================================================
# POST /api/engine/toggle
# ===========================================================================

@app.post("/api/engine/toggle")
def toggle_engine():
    new_state = sm.toggle_engine_paused()
    return JSONResponse({"engine_paused": new_state})


# ===========================================================================
# POST /api/engine/step
# ===========================================================================

@app.post("/api/engine/step")
def engine_step():
    result = ac.run_all_active_claims_step()
    db = sm.load_claims_db()
    return JSONResponse({
        **result,
        "hud_counts": _compute_hud_counts(db.claims),
        "stage_counts": _compute_stage_counts(db.claims),
    })


# ===========================================================================
# POST /api/engine/run-all
# ===========================================================================

@app.post("/api/engine/run-all")
def engine_run_all():
    total_advanced = 0
    for _ in range(6):
        result = ac.run_all_active_claims_step()
        total_advanced += result.get("advanced_count", 0)
        if result.get("advanced_count", 0) == 0:
            break
    db = sm.load_claims_db()
    return JSONResponse({
        "ok": True,
        "total_advanced": total_advanced,
        "hud_counts": _compute_hud_counts(db.claims),
        "stage_counts": _compute_stage_counts(db.claims),
    })


# ===========================================================================
# POST /api/claims/{claim_id}/execute
# ===========================================================================

class NoteBody(BaseModel):
    note: str = ""


@app.post("/api/claims/{claim_id}/execute")
def execute_claim(claim_id: str, body: NoteBody = NoteBody()):
    try:
        claim = ac.execute_claim_action(claim_id, adjuster_note=body.note)
        return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# POST /api/claims/{claim_id}/dismiss
# ===========================================================================

@app.post("/api/claims/{claim_id}/dismiss")
def dismiss_claim(claim_id: str, body: NoteBody = NoteBody()):
    try:
        claim = ac.dismiss_claim_action(claim_id, adjuster_note=body.note)
        return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# POST /api/claims/{claim_id}/restore
# ===========================================================================

@app.post("/api/claims/{claim_id}/restore")
def restore_claim(claim_id: str):
    claim = sm.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    if claim.current_stage == "5 DECISION GATE":
        claim.claim_status = ClaimStatusEnum.NEEDS_ATTENTION
    else:
        claim.claim_status = ClaimStatusEnum.IN_PROGRESS
    sm.update_claim(claim)
    return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})


# ===========================================================================
# DELETE /api/claims/{claim_id}
# ===========================================================================

@app.delete("/api/claims/{claim_id}")
def delete_claim(claim_id: str):
    success = sm.delete_claim(claim_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    return JSONResponse({"ok": True, "message": f"Claim '{claim_id}' deleted."})


# ===========================================================================
# POST /api/claims/{claim_id}/return-to-user
# ===========================================================================

class ReturnToUserBody(BaseModel):
    question_prompt: str


@app.post("/api/claims/{claim_id}/return-to-user")
def return_to_user(claim_id: str, body: ReturnToUserBody):
    try:
        claim = ac.return_to_user_action(claim_id, body.question_prompt)
        return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# POST /api/claims/{claim_id}/resubmit
# ===========================================================================

@app.post("/api/claims/{claim_id}/resubmit")
async def resubmit_claim(
    claim_id: str,
    clarification: str = Form(""),
    photos: List[UploadFile] = File(default=[]),
):
    claim = sm.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")

    if photos:
        claim_upload_dir = UPLOADS_DIR / claim_id
        claim_upload_dir.mkdir(parents=True, exist_ok=True)
        for photo in photos:
            if not photo.filename:
                continue
            dest = claim_upload_dir / photo.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(photo.file, f)
            claim.photo_paths.append(str(dest).replace("\\", "/"))

    if clarification:
        claim.raw_statement += f"\n[Claimant Clarification]: {clarification}"

    claim.current_stage = STAGE_3_VISION
    claim.claim_status = ClaimStatusEnum.IN_PROGRESS
    claim.returned_to_user_prompt = None
    claim.headline_summary = "Claimant provided clarification — re-evaluating damage & consistency."

    from datetime import datetime, timezone
    from schemas import TraceEntry
    claim.agent_trace.append(TraceEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        stage=STAGE_3_VISION,
        agent_or_tool="Claimant Intake Portal",
        purpose="Claimant Clarification Resubmission",
        result_summary="Clarification added. Re-running from Vision stage.",
    ))
    sm.update_claim(claim)

    try:
        claim = ac.run_claim_to_completion(claim_id)
    except Exception as e:
        claim = sm.get_claim_by_id(claim_id) or claim
        claim.headline_summary = f"Re-triage error: {e}"
        sm.update_claim(claim)

    return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})


# ===========================================================================
# POST /api/claims/{claim_id}/handled-by
# ===========================================================================

class HandledByBody(BaseModel):
    handled_by: str


@app.post("/api/claims/{claim_id}/handled-by")
def set_handled_by(claim_id: str, body: HandledByBody):
    try:
        claim = ac.toggle_handled_by(claim_id, mode=body.handled_by)
        return JSONResponse({"ok": True, "claim": _claim_to_dict(claim)})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# POST /api/claims/{claim_id}/chat
# ===========================================================================

class ChatBody(BaseModel):
    message: str


@app.post("/api/claims/{claim_id}/chat")
def spark_chat(claim_id: str, body: ChatBody):
    try:
        result = ac.chat_with_spark(claim_id, body.message)
        claim = sm.get_claim_by_id(claim_id)
        return JSONResponse({
            "ok": True,
            "result": result,
            "claim": _claim_to_dict(claim) if claim else {},
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# POST /api/claims/seed-demo
# ===========================================================================

@app.post("/api/claims/seed-demo")
def seed_demo():
    sm.clear_all_claims()
    sm.seed_screenshot_demo_claims()
    db = sm.load_claims_db()
    return JSONResponse({
        "ok": True,
        "seeded_count": len(db.claims),
        "hud_counts": _compute_hud_counts(db.claims),
    })


# ===========================================================================
# POST /api/claims/clear
# ===========================================================================

@app.post("/api/claims/clear")
def clear_claims():
    sm.clear_all_claims()
    return JSONResponse({"ok": True, "message": "All claims cleared."})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

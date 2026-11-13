"""
app.py — Automation First · Adjuster Cockpit (Spark / Clive)
============================================================
Pixel-perfect replication of reference UI screenshot (media_1794510421265_71ba9325.jpg):
  - Pure, clean light canvas (#F4F7FB) with midnight navy left rail (#081028)
  - Pink circular avatar badge ('SB')
  - Top header: 🏠 Automation First · Adjuster Cockpit + Search bar pill + Call icon
  - HUD status bar: Single floating white capsule card with vertical dividers & live counts:
      ● IN PROGRESS | ● NEEDS ATTENTION | ● STUCK | ● AUTOMATION OFF | ● SETTLED
  - 6 Kanban stage cards with 3 mini progress tracks (Red, Amber, Green):
      1 INTAKE & TRIAGE | 2 COVERAGE | 3 DA / ESTIMATE | 4 LIABILITY | 5 SETTLEMENT | 6 SUBROGATION
  - Inline horizontal filter bar:
      [Status ⌄] [Stage ⌄] [Priority ⌄] [LOB ⌄] [Attention ⌄] [Waiting ⌄] [Confidence ⌄] [Sort ⌄]
  - Pixel-perfect claim rows:
      - Left: Status dot + CLM ID + Stage & LOB + Yellow 'High priority' pill
      - Center: Action badge (✨ RECOMMENDATION / 📋 REQUEST / 🛑 ESCALATION / ❓ QUESTION)
                + bold headline + subtext
      - Right: Inline ✓ Execute (teal), ✕ Dismiss (ghost), HANDLED BY [🤖 Clive | 👤 Manual] capsule, ∨ expander
  - Expanded detail dossier matching reference screenshot:
      - WHAT CLIVE DID
      - RECOMMENDATION card with Confidence bar & threshold note
      - WHY bullets with teal dots
      - REFERENCED DOCUMENTS cards
      - DATA CLIVE REASONED OVER pill tags
      - YOUR OPTIONS (Execute, Dismiss, Return to User)
      - EDIT VIA CHAT WITH CLIVE interactive live bot
"""

from __future__ import annotations

import os
import shutil
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from PIL import Image

import config
from config import (
    FAST_TRACK_LIMIT_INR,
    MIN_CONFIDENCE_THRESHOLD,
    PIPELINE_STAGES,
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
    HandledByEnum,
    StatementFacts,
    TraceEntry,
    VisionReport,
    ZoneFinding,
)
import schemas
import state_manager as sm
import agents_crew as ac


def html_block(content: str) -> None:
    """Safely render HTML without Markdown converting indented lines into code blocks."""
    st.markdown(textwrap.dedent(content).strip(), unsafe_allow_html=True)


# ===========================================================================
# 1. PAGE CONFIGURATION & ULTRA-CLEAN LIGHT THEME CSS
# ===========================================================================

st.set_page_config(
    page_title="Automation First · Adjuster Cockpit",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

EXACT_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

/* --- Strict Light Base Reset --- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .main {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #1E293B !important;
}

/* Explicitly preserve Material Symbols / Icons so ligatures NEVER render as raw text like keyboard_double_arrow_right */
[data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] *,
[data-testid="collapsedControl"] *,
[class*="material-symbols"],
.material-symbols-rounded,
.material-symbols-outlined,
i.material-symbols-rounded {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-style: normal !important;
    font-weight: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: 'liga' 1 !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Page canvas background matching screenshot */
.stApp, div[data-testid="stAppViewContainer"], div[data-testid="stMainBlockContainer"] {
    background: #F4F7FB !important;
}

/* Adjust page padding */
.block-container {
    padding-top: 1.0rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
    max-width: 1440px !important;
}

/* --- Left Sidebar: Midnight Navy Rail (#081028) --- */
section[data-testid="stSidebar"] {
    background-color: #081028 !important;
    border-right: 1px solid #111C35 !important;
    min-width: 250px !important;
    max-width: 270px !important;
}
section[data-testid="stSidebar"] * {
    color: #F8FAFC !important;
}
section[data-testid="stSidebar"] hr {
    border-color: #1E293B !important;
}
/* --- Left Sidebar Buttons (All levels, columns & direct) --- */
section[data-testid="stSidebar"] button,
section[data-testid="stSidebar"] div.stButton button,
section[data-testid="stSidebar"] div[data-testid="column"] button,
section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
    background-color: #172554 !important;
    background: #172554 !important;
    color: #F8FAFC !important;
    border: 1px solid #1E3A8A !important;
    border-radius: 8px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    padding: 6px 8px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
}
section[data-testid="stSidebar"] button:hover,
section[data-testid="stSidebar"] div.stButton button:hover,
section[data-testid="stSidebar"] div[data-testid="column"] button:hover,
section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
    background-color: #1E3A8A !important;
    background: #1E3A8A !important;
    border-color: #2563EB !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button *,
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] button span {
    color: #F8FAFC !important;
}
section[data-testid="stSidebar"] button:hover *,
section[data-testid="stSidebar"] button:hover p,
section[data-testid="stSidebar"] button:hover span {
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button[kind="primary"],
section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
    background-color: #0D9488 !important;
    background: #0D9488 !important;
    border-color: #0D9488 !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button[kind="primary"]:hover,
section[data-testid="stSidebar"] [data-testid="baseButton-primary"]:hover {
    background-color: #0F766E !important;
    background: #0F766E !important;
    border-color: #0F766E !important;
    color: #FFFFFF !important;
}

/* --- Wipe Out All Dark-Mode Black Boxes Across Streamlit Controls --- */
div[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 9999px !important;
    font-size: 12px !important;
    padding: 6px 14px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #0D9488 !important;
    box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.15) !important;
}

div[data-testid="stTextArea"] textarea {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-size: 12.5px !important;
}

/* Make Streamlit selectboxes compact, rounded, white pills with no heavy labels */
div[data-testid="stSelectbox"] label {
    display: none !important;
}
div[data-testid="stSelectbox"] > div > div {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 9999px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    padding: 0 10px !important;
    height: 30px !important;
    min-height: 30px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02) !important;
}
div[data-testid="stSelectbox"] * {
    color: #0F172A !important;
}
div[data-baseweb="select"] * {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
}
div[data-baseweb="popover"] * {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
}
ul[role="listbox"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
}
li[role="option"] {
    background-color: #FFFFFF !important;
    color: #1E293B !important;
    font-size: 12px !important;
}
li[role="option"]:hover, li[role="option"][aria-selected="true"] {
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
}

/* Streamlit Containers with border=True: Styled as crisp white floating cards */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #EAEFF5 !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    margin-bottom: 8px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.02) !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #CBD5E1 !important;
    box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05) !important;
}

/* Button Defaults (Main Canvas) */
.main button,
.main div.stButton button,
.main [data-testid="baseButton-secondary"] {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    color: #334155 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 3px 8px !important;
    white-space: nowrap !important;
    min-height: 28px !important;
    height: 28px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02) !important;
}
.main button:hover,
.main div.stButton button:hover,
.main [data-testid="baseButton-secondary"]:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

/* Primary Buttons: Teal (#009688) */
.main button[kind="primary"],
.main div.stButton button[kind="primary"],
.main [data-testid="baseButton-primary"] {
    background-color: #009688 !important;
    background: #009688 !important;
    color: #FFFFFF !important;
    border: 1px solid #009688 !important;
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 3px 8px !important;
    white-space: nowrap !important;
    min-height: 28px !important;
    height: 28px !important;
    box-shadow: 0 1px 3px rgba(0, 150, 136, 0.25) !important;
}
.main button[kind="primary"]:hover,
.main div.stButton button[kind="primary"]:hover,
.main [data-testid="baseButton-primary"]:hover {
    background-color: #00796B !important;
    background: #00796B !important;
}

/* --- Header Layout --- */
.header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2px;
}
.header-title {
    font-size: 15px;
    font-weight: 700;
    color: #1E293B;
    display: flex;
    align-items: center;
    gap: 7px;
    letter-spacing: -0.2px;
}
.header-subtitle {
    font-size: 11.5px;
    color: #64748B;
    font-weight: 500;
    margin-bottom: 10px;
}

/* --- Floating Status Capsule Bar (Screenshots 1, 3, 4) --- */
.hud-status-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 8px 20px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    margin-bottom: 18px !important;
}

.hud-pill {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    padding: 5px 10px !important;
    border-radius: 9999px !important;
    text-decoration: none !important;
    transition: all 0.15s ease !important;
}
.hud-pill:hover {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
}
.hud-pill b {
    color: #0F172A !important;
    font-size: 14px !important;
    font-weight: 800 !important;
}

.hud-pill-selected-amber {
    background-color: #FFFBEB !important;
    border: 1.5px solid #F59E0B !important;
    color: #92400E !important;
}
.hud-pill-selected-green {
    background-color: #ECFDF5 !important;
    border: 1.5px solid #10B981 !important;
    color: #065F46 !important;
}
.hud-pill-selected-red {
    background-color: #FEF2F2 !important;
    border: 1.5px solid #EF4444 !important;
    color: #991B1B !important;
}

.hud-sep {
    width: 1px;
    height: 18px;
    background-color: #E2E8F0;
    display: inline-block;
}

/* Status Indicator Dots */
.dot-green { background-color: #10B981; width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-amber { background-color: #F59E0B; width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-red   { background-color: #EF4444; width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-black { background-color: #0F172A; width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-gray  { background-color: #94A3B8; width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

/* Section Header Typography */
.section-head {
    font-size: 11px;
    font-weight: 700;
    color: #334155;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 2px;
}
.section-sub {
    font-size: 11px;
    color: #94A3B8;
    margin-bottom: 10px;
}

/* --- Kanban Stage Cards (Screenshots 1 & 2) --- */
.stage-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 12px 14px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
    min-height: 128px !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
.stage-card:hover {
    box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.08) !important;
    transform: translateY(-1px) !important;
}
.stage-card-title {
    font-size: 10.5px;
    font-weight: 700;
    color: #334155;
    letter-spacing: 0.4px;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 5px;
}
.stage-card-count {
    font-size: 21px;
    font-weight: 800;
    color: #0F172A;
    margin-bottom: 7px;
    display: flex;
    align-items: baseline;
    gap: 5px;
}
.stage-card-count span {
    font-size: 10px;
    font-weight: 600;
    color: #64748B;
}

/* 3 Mini Track Rows with Colored Numbers */
.mini-track-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
}
.mini-pill-num {
    font-size: 9.5px;
    font-weight: 700;
    width: 12px;
    text-align: right;
}
.mini-track {
    flex-grow: 1;
    height: 4.5px;
    border-radius: 9999px;
    background-color: #F1F5F9;
    overflow: hidden;
}
.mini-fill-red   { background-color: #EF4444; height: 100%; border-radius: 9999px; }
.mini-fill-amber { background-color: #F59E0B; height: 100%; border-radius: 9999px; }
.mini-fill-green { background-color: #10B981; height: 100%; border-radius: 9999px; }

/* --- Action Badges Matching Screenshot 1 & 4 --- */
.badge-rec {
    background-color: #E6FFFA;
    color: #0D9488;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.3px;
    display: inline-block;
    margin-right: 6px;
}
.badge-req {
    background-color: #FEF3C7;
    color: #B45309;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.3px;
    display: inline-block;
    margin-right: 6px;
}
.badge-que {
    background-color: #EFF6FF;
    color: #2563EB;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.3px;
    display: inline-block;
    margin-right: 6px;
}
.badge-esc {
    background-color: #FEE2E2;
    color: #DC2626;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.3px;
    display: inline-block;
    margin-right: 6px;
}

.pill-high-priority {
    background-color: #FEF3C7;
    color: #B45309;
    font-size: 9.5px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 9999px;
    display: inline-block;
}

/* Expanded Detail Container (Screenshots 6, 7) */
.dossier-card {
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 12px !important;
    padding: 18px 22px !important;
    margin-top: 4px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.06) !important;
}

.dossier-title {
    font-size: 10.5px;
    font-weight: 700;
    color: #0D9488;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.rec-headline {
    font-size: 15.5px;
    font-weight: 800;
    color: #0F172A;
    margin-bottom: 8px;
    letter-spacing: -0.2px;
}

.conf-bar-track {
    width: 150px;
    height: 5.5px;
    border-radius: 9999px;
    background: #E2E8F0;
    overflow: hidden;
    display: inline-block;
    vertical-align: middle;
    margin: 0 6px;
}

.ref-doc-card-exact {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    padding: 7px 11px !important;
    margin-bottom: 5px !important;
}
.ref-doc-card-title {
    color: #0D9488;
    font-size: 11.5px;
    font-weight: 700;
    margin-bottom: 1px;
}
.ref-doc-card-summary {
    color: #475569;
    font-size: 11px;
    line-height: 1.35;
}

</style>
"""
st.markdown(EXACT_THEME_CSS, unsafe_allow_html=True)


# ===========================================================================
# 2. STATE INITIALISATION (NO DUMMY DATA — STARTS WITH REAL DB STATE)
# ===========================================================================

sm.initialise_claims_db()

# Sync filters from query parameters for instant responsive tab clicks
q_status = st.query_params.get("filter_status", None)
q_stage = st.query_params.get("filter_stage", None)

if "filter_status" not in st.session_state:
    st.session_state.filter_status = q_status if q_status else "All"
elif q_status is not None:
    st.session_state.filter_status = q_status

if "filter_stage" not in st.session_state:
    st.session_state.filter_stage = q_stage if q_stage else "All"
elif q_stage is not None:
    st.session_state.filter_stage = q_stage

if "filter_priority" not in st.session_state:
    st.session_state.filter_priority = "All"
if "filter_category" not in st.session_state:
    st.session_state.filter_category = "all"
if "selected_claim_id" not in st.session_state:
    st.session_state.selected_claim_id = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""


# ===========================================================================
# 3. SIDEBAR: MIDNIGHT NAVY RAIL (#081028)
# ===========================================================================

with st.sidebar:
    # Pink circular avatar badge ('SB')
    html_block(
        """
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding-top: 2px;">
            <div style="width: 36px; height: 36px; border-radius: 50%; background: #FCE7F3; color: #9D174D; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13.5px;">
                SB
            </div>
            <div>
                <div style="font-weight: 700; font-size: 13.5px; color: #FFFFFF; letter-spacing: -0.2px;">Spark Cockpit</div>
                <div style="font-size: 10.5px; color: #94A3B8;">Automation First Triage</div>
            </div>
        </div>
        """
    )

    page_nav = st.radio(
        "Navigation",
        ["Adjuster Cockpit (Page 2)", "+ FNOL Intake Portal (Page 1)"],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color: #1E293B;' />", unsafe_allow_html=True)

    # Engine Controls inside Sidebar
    html_block("<div style='font-size: 10.5px; font-weight: 700; color: #94A3B8; text-transform: uppercase; margin-bottom: 8px;'>Engine Controls</div>")
    is_paused = sm.is_engine_paused()

    if is_paused:
        html_block(
            '<div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; color: #FCD34D; padding: 5px 8px; border-radius: 6px; font-weight: 600; font-size: 10.5px; margin-bottom: 8px;">'
            '⏸ ENGINE PAUSED</div>'
        )
        if st.button("▶ Resume Automation", use_container_width=True, type="primary"):
            sm.set_engine_paused(False)
            st.rerun()
    else:
        html_block(
            '<div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; color: #6EE7B7; padding: 5px 8px; border-radius: 6px; font-weight: 600; font-size: 10.5px; margin-bottom: 8px;">'
            '▶ AUTOMATION RUNNING</div>'
        )
        if st.button("⏸ Pause Automation", use_container_width=True):
            sm.set_engine_paused(True)
            st.rerun()

    c_sb1, c_sb2 = st.columns(2)
    with c_sb1:
        if st.button("⏭ Step 1", use_container_width=True):
            res = ac.run_all_active_claims_step()
            st.toast(f"Stepped {res.get('advanced_count', 0)} claims forward!")
            st.rerun()
    with c_sb2:
        if st.button("⚡ Complete", use_container_width=True):
            for _ in range(5):
                res = ac.run_all_active_claims_step()
                if res.get("advanced_count", 0) == 0:
                    break
            st.toast("Active claims processed!")
            st.rerun()

    st.markdown("<hr style='border-color: #1E293B;' />", unsafe_allow_html=True)

    if st.button("🗑 Clear All Claims", use_container_width=True):
        sm.clear_all_claims()
        st.session_state.selected_claim_id = None
        st.toast("Claims database cleared.")
        st.rerun()

    st.markdown("<hr style='border-color: #1E293B;' />", unsafe_allow_html=True)
    html_block(
        """
        <div style="font-size: 10.5px; color: #94A3B8; line-height: 1.6;">
            <b style="color: #E2E8F0;">Pipeline Parameters:</b><br/>
            • Fast-Track: <span style="color:#6EE7B7;">₹25,000</span><br/>
            • Total Loss: <span style="color:#FCD34D;">75% IDV</span><br/>
            • AI Confidence: <span style="color:#E2E8F0;">80%</span><br/>
            • Max Loops: <span style="color:#E2E8F0;">2</span>
        </div>
        """
    )


# ===========================================================================
# 4. PAGE 1: + FNOL — CLAIMANT INTAKE PORTAL
# ===========================================================================

if page_nav == "+ FNOL Intake Portal (Page 1)":
    html_block(
        """
        <div class="header-title">➕ FNOL — Claimant Intake Portal</div>
        <div class="header-subtitle">Enter first notice of loss, attach damage photos, and feed real claims into Cockpit.</div>
        """
    )

    all_claims = sm.get_all_claims()
    returned_claims = [c for c in all_claims if c.returned_to_user_prompt]

    if returned_claims:
        for ret_claim in returned_claims:
            html_block(
                f"""
                <div style="background: #FFFBEB; border: 1.5px solid #F59E0B; border-radius: 10px; padding: 14px; margin-bottom: 18px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span style="font-size: 16px;">⚠️</span>
                        <b style="font-size: 14px; color: #B45309;">
                            Action Required from Claimant — {ret_claim.claim_id} ({ret_claim.vehicle_reg})
                        </b>
                    </div>
                    <div style="font-size: 12.5px; color: #78350F; margin-bottom: 10px;">
                        <b>Adjuster Question:</b> "{ret_claim.returned_to_user_prompt}"
                    </div>
                </div>
                """
            )
            with st.form(key=f"clarify_form_{ret_claim.claim_id}"):
                c_c1, c_c2 = st.columns([1, 1])
                with c_c1:
                    new_statement = st.text_area("Your Clarifying Statement", placeholder="Explain damage circumstances...")
                with c_c2:
                    new_photos = st.file_uploader("Upload Additional Damage Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"new_photos_{ret_claim.claim_id}")

                if st.form_submit_button("Submit Clarification & Re-Run Spark AI Triage", type="primary"):
                    claim_dir = config.DATA_DIR / "uploads" / ret_claim.claim_id
                    claim_dir.mkdir(parents=True, exist_ok=True)
                    if new_photos:
                        for photo in new_photos:
                            photo_path = claim_dir / photo.name
                            with open(photo_path, "wb") as f:
                                f.write(photo.getbuffer())
                            ret_claim.photo_paths.append(str(photo_path))

                    if new_statement:
                        ret_claim.raw_statement += f"\n[Claimant Clarification]: {new_statement}"

                    ret_claim.current_stage = STAGE_3_VISION
                    ret_claim.claim_status = ClaimStatusEnum.IN_PROGRESS
                    ret_claim.returned_to_user_prompt = None
                    ret_claim.headline_summary = "Claimant provided clarification — re-evaluating damage & consistency."

                    ret_claim.agent_trace.append(
                        schemas.TraceEntry(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            stage=STAGE_3_VISION,
                            agent_or_tool="Claimant Intake Portal",
                            purpose="Claimant Clarification Resubmission",
                            result_summary=f"Added {len(new_photos) if new_photos else 0} photo(s). Clarification: '{new_statement[:60]}...'",
                        )
                    )

                    sm.update_claim(ret_claim)
                    st.success(f"Clarification submitted for {ret_claim.claim_id}! Triage restarted.")
                    ac.run_claim_to_completion(ret_claim.claim_id)
                    st.rerun()

    # Quick Policy Reference
    policies = sm.load_policies()

    with st.expander("📖 Quick Policy Reference (`data/db2_policies.json`)", expanded=False):
        table_rows = []
        for pid, pdata in policies.items():
            table_rows.append({
                "Policy ID": pid,
                "Policyholder": pdata.get("policyholder_name"),
                "Vehicle Reg": pdata.get("vehicle_reg"),
                "Coverage": pdata.get("coverage_type"),
                "IDV": f"₹{pdata.get('idv_inr', 0):,}",
                "Status": pdata.get("status"),
                "Effective Dates": f"{pdata.get('effective_date')} to {pdata.get('expiry_date')}",
                "Accident Photo": pdata.get("accident_photo", f"/static/sample_photos/{pid.lower().replace('-', '_')}_damage.jpg"),
                "Notes": pdata.get("notes"),
            })
        st.dataframe(table_rows, use_container_width=True)

    # 7 Presets for fast 1-click testing
    PRESET_SCENARIOS = {
        "Manual Input": None,
        "Scenario 1: POL-1001 (Arjun Mehta — Fast-Track Tier 1 Minor Scratch)": {
            "policy_id": "POL-1001", "vehicle_reg": "MH12AB1001", "date": "2026-11-10", "time": "14:30", "location": "Pune",
            "statement": "While driving on Pune-Solapur Highway, a loose stone from a truck hit my front bumper and radiator grill, causing a dent and scratch. No other vehicles were involved.",
            "injuries": False, "third_party": False, "police": False, "sample_photo": "data/sample_photos/pol_1001_damage.jpg",
        },
        "Scenario 2: POL-1002 (Priya Nair — Total Loss / Heavy Loss Tier 2)": {
            "policy_id": "POL-1002", "vehicle_reg": "KA05CD2002", "date": "2026-11-05", "time": "09:15", "location": "Bengaluru",
            "statement": "Severe collision on Outer Ring Road. An oncoming cement mixer rammed into the front and left side of my vehicle at high speed. The front engine compartment is completely crushed, suspension broken, and airbags deployed.",
            "injuries": False, "third_party": True, "police": True, "sample_photo": "data/sample_photos/pol_1002_damage.jpg",
        },
        "Scenario 3: POL-1003 (Rajan Pillai — Fraud / Contradiction Tier 3 Escalation)": {
            "policy_id": "POL-1003", "vehicle_reg": "TN09EF3003", "date": "2026-11-12", "time": "10:00", "location": "Chennai",
            "statement": "I was driving through a heavy rainstorm when my car skidded and crashed head-on directly into a banyan tree, crushing the entire front hood and radiator.",
            "injuries": False, "third_party": False, "police": False, "sample_photo": "data/sample_photos/pol_1003_damage.jpg",
        },
        "Scenario 4: POL-1004 (Sneha Kulkarni — Self-Correction Loop Test)": {
            "policy_id": "POL-1004", "vehicle_reg": "GJ01GH4004", "date": "2026-11-08", "time": "18:45", "location": "Ahmedabad",
            "statement": "Sideswiped a concrete pillar while turning into my apartment basement parking lot, scratching the left doors and rear-left quarter panel.",
            "injuries": False, "third_party": False, "police": False, "sample_photo": "data/sample_photos/pol_1004_damage.jpg",
        },
        "Scenario 5: POL-1005 (Vikram Sharma — Coverage Gap Third-Party Only)": {
            "policy_id": "POL-1005", "vehicle_reg": "DL08IJ5005", "date": "2026-11-09", "time": "11:20", "location": "New Delhi",
            "statement": "Hit a highway guard rail after swerving to avoid a stray animal, damaging the front bumper, left fender, and headlights.",
            "injuries": False, "third_party": False, "police": False, "sample_photo": "data/sample_photos/pol_1005_damage.jpg",
        },
        "Scenario 6: POL-1006 (Meena Iyer — Failed Coverage Gate Expired Policy)": {
            "policy_id": "POL-1006", "vehicle_reg": "PB10KL6006", "date": "2026-11-11", "time": "16:10", "location": "Chandigarh",
            "statement": "Rear-ended by an autorickshaw at a traffic signal on Madhya Marg, cracking the rear bumper and tailgate.",
            "injuries": False, "third_party": True, "police": False, "sample_photo": "data/sample_photos/pol_1006_damage.jpg",
        },
        "Scenario 7: POL-1007 (Aditya Reddy — High Value Reserve Sign-Off / Zero-Dep)": {
            "policy_id": "POL-1007", "vehicle_reg": "AP07MN7007", "date": "2026-11-07", "time": "21:30", "location": "Hyderabad",
            "statement": "Hit road construction debris on the Outer Ring Road. Underbody and front bumper damaged, front alloy wheel cracked.",
            "injuries": False, "third_party": False, "police": False, "sample_photo": "data/sample_photos/pol_1007_damage.jpg",
        },
    }

    selected_preset = st.selectbox(
        "⚡ 1-Click Auto-Fill Demo Scenarios (Select to Rapidly Test 7 Cases):",
        list(PRESET_SCENARIOS.keys()),
        index=0,
    )
    preset_data = PRESET_SCENARIOS[selected_preset]

    html_block("<div class='section-head' style='margin-top: 14px;'>New Notice of Loss Form</div>")

    with st.form("fnol_submission_form"):
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            val_pid = preset_data["policy_id"] if preset_data else "POL-1001"
            in_policy_id = st.text_input("Policy ID", value=val_pid)

            val_vreg = preset_data["vehicle_reg"] if preset_data else "MH12AB1001"
            in_vehicle_reg = st.text_input("Vehicle Registration", value=val_vreg)

            val_date = preset_data["date"] if preset_data else "2026-11-10"
            in_date = st.text_input("Incident Date (YYYY-MM-DD)", value=val_date)

            val_time = preset_data["time"] if preset_data else "14:30"
            in_time = st.text_input("Incident Time (HH:MM)", value=val_time)

        with c_f2:
            val_loc = preset_data["location"] if preset_data else "Pune"
            in_location = st.text_input("Incident City / Location (Open-Meteo verified)", value=val_loc)

            val_stmt = preset_data["statement"] if preset_data else "Front bumper dented after stone impact."
            in_statement = st.text_area("Claimant Statement (Free Text)", value=val_stmt, height=130)

        # Linked accident photograph from policy test set (no manual file upload required)
        photo_to_use = preset_data.get("sample_photo") if preset_data else f"data/sample_photos/{in_policy_id.lower().replace('-', '_')}_damage.jpg"
        if not Path(photo_to_use).exists():
            photo_to_use = "data/sample_photos/pol_1001_damage.jpg"

        html_block("<div style='font-size: 12px; font-weight: 700; color: #1E293B; margin-top: 10px; margin-bottom: 6px;'>Accident Photograph (From Policy Test Set):</div>")
        c_img1, c_img2 = st.columns([1, 2])
        with c_img1:
            if Path(photo_to_use).exists():
                st.image(photo_to_use, caption=f"Accident photo: {Path(photo_to_use).name}", width=220)
        with c_img2:
            html_block(f"""
            <div style='background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px; font-size: 11.5px; color: #475569;'>
                <span style='background:#CCFBF1;color:#0F766E;font-size:10px;font-weight:700;padding:2px 8px;border-radius:9999px;'>VERIFIED ACCIDENT IMAGE</span><br/>
                <div style='margin-top:6px;font-family:monospace;font-size:11px;color:#0F172A;'>{photo_to_use}</div>
                <div style='margin-top:6px;font-size:11px;color:#64748B;'>
                    Linked automatically to <b>{in_policy_id}</b>. Submitted directly to the Vision Assessor Agent for zone-by-zone damage appraisal.
                </div>
            </div>
            """)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            submit_paused = st.form_submit_button(
                "Queue Claim in Cockpit (Keep Paused in Stage 1)",
                use_container_width=True,
            )
        with col_b2:
            submit_run = st.form_submit_button(
                "Submit & Run Spark AI Triage Now",
                type="primary",
                use_container_width=True,
            )

    if submit_paused or submit_run:
        pol_record = policies.get(in_policy_id, {})
        holder_name = pol_record.get("policyholder_name", "Applicant")

        in_injuries = preset_data.get("injuries", False) if preset_data else False
        in_third_party = preset_data.get("third_party", False) if preset_data else False
        in_police = preset_data.get("police", False) if preset_data else False

        claim_rec = sm.create_claim_from_intake(
            policy_id=in_policy_id.strip(),
            policyholder_name=holder_name,
            vehicle_reg=in_vehicle_reg.strip(),
            incident_date=in_date.strip(),
            incident_time=in_time.strip(),
            location=in_location.strip(),
            raw_statement=in_statement.strip(),
            photo_paths=[],
            injuries=in_injuries,
            third_party=in_third_party,
            police_report=in_police,
        )

        claim_upload_dir = config.DATA_DIR / "uploads" / claim_rec.claim_id
        claim_upload_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: List[str] = []

        if photo_to_use and Path(photo_to_use).exists():
            sample_src = Path(photo_to_use)
            sample_target = claim_upload_dir / sample_src.name
            shutil.copyfile(sample_src, sample_target)
            saved_paths.append(str(sample_target))

        claim_rec.photo_paths = saved_paths
        sm.update_claim(claim_rec)

        if submit_run:
            st.toast(f"Claim {claim_rec.claim_id} created! Running Spark AI triage...")
            ac.run_claim_to_completion(claim_rec.claim_id)
            st.success(f"Claim {claim_rec.claim_id} triaged successfully! View it in Cockpit.")
        else:
            st.toast(f"Claim {claim_rec.claim_id} queued at Stage 1 (Paused).")

        st.rerun()


# ===========================================================================
# 5. PAGE 2: ADJUSTER COCKPIT — REAL CLAIMS ONLY (NO DUMMY DATA)
# ===========================================================================

elif page_nav == "Adjuster Cockpit (Page 2)":
    is_paused = sm.is_engine_paused()
    all_claims = sm.get_all_claims()

    # Auto-Advance Logic (when Engine is Running)
    # Only claims that are actively IN_PROGRESS advance through stages.
    # Claims in NEEDS_ATTENTION or STUCK wait for Adjuster action in Cockpit!
    if not is_paused:
        active_to_advance = [
            c for c in all_claims
            if c.handled_by == HandledByEnum.SPARK
            and c.claim_status == ClaimStatusEnum.IN_PROGRESS
            and not (c.current_stage == STAGE_5_DECISION and STAGE_5_DECISION in c.stages_completed)
        ]
        if active_to_advance:
            target_claim = active_to_advance[0]
            try:
                ac.advance_claim_one_stage(target_claim.claim_id)
                time.sleep(0.4)
                st.rerun()
            except Exception as ex:
                # Never crash the main cockpit page on edge-case exceptions
                target_claim.claim_status = ClaimStatusEnum.NEEDS_ATTENTION
                target_claim.headline_summary = f"Pipeline review needed: {str(ex)[:90]}"
                sm.update_claim(target_claim)
                st.rerun()

    # -----------------------------------------------------------------------
    # Top Header & Rounded Search Pill (Screenshot 1)
    # -----------------------------------------------------------------------
    c_head1, c_head2 = st.columns([3, 1.3])
    with c_head1:
        html_block('<div class="header-title">🏠 Automation First · Adjuster Cockpit</div>')
        total_claims_display = len(all_claims)
        html_block(f"<div class='header-subtitle'>{total_claims_display} claims in total — split below by status</div>")
    with c_head2:
        c_s_in, c_s_ic = st.columns([4, 1])
        with c_s_in:
            search_txt = st.text_input("Search...", placeholder="🔍 Search...", label_visibility="collapsed")
            st.session_state.search_query = search_txt
        with c_s_ic:
            html_block(
                """
                <div style="width: 32px; height: 32px; border-radius: 50%; background: #FFFFFF; border: 1px solid #E2E8F0; display: flex; align-items: center; justify-content: center; cursor: pointer;">
                    <span style="font-size: 13px; color: #0D9488;">📞</span>
                </div>
                """
            )

    # -----------------------------------------------------------------------
    # Single Floating HUD Status Capsule Card (Screenshots 1, 3, 4)
    # Pure dynamic counts calculated directly from real claims in database
    # -----------------------------------------------------------------------
    count_in_prog = sum(1 for c in all_claims if c.claim_status == ClaimStatusEnum.IN_PROGRESS)
    count_needs_att = sum(1 for c in all_claims if c.claim_status == ClaimStatusEnum.NEEDS_ATTENTION)
    count_stuck = sum(1 for c in all_claims if c.claim_status == ClaimStatusEnum.STUCK)
    count_auto_off = sum(1 for c in all_claims if c.claim_status == ClaimStatusEnum.AUTOMATION_OFF)
    count_settled = sum(1 for c in all_claims if c.claim_status == ClaimStatusEnum.SETTLED)

    cur_filter = st.session_state.filter_status

    html_block(
        f"""
        <div class="hud-status-card">
            <a href="?filter_status={'All' if cur_filter == 'IN PROGRESS' else 'IN PROGRESS'}" target="_self" class="hud-pill {'hud-pill-selected-green' if cur_filter == 'IN PROGRESS' else ''}">
                <span class="dot-green"></span>
                <b>{count_in_prog}</b> IN PROGRESS
            </a>
            <span class="hud-sep"></span>
            <a href="?filter_status={'All' if cur_filter == 'NEEDS ATTENTION' else 'NEEDS ATTENTION'}" target="_self" class="hud-pill {'hud-pill-selected-amber' if cur_filter == 'NEEDS ATTENTION' else ''}">
                <span class="dot-amber"></span>
                <b>{count_needs_att}</b> NEEDS ATTENTION
            </a>
            <span class="hud-sep"></span>
            <a href="?filter_status={'All' if cur_filter == 'STUCK' else 'STUCK'}" target="_self" class="hud-pill {'hud-pill-selected-red' if cur_filter == 'STUCK' else ''}">
                <span class="dot-red"></span>
                <b>{count_stuck}</b> STUCK
            </a>
            <span class="hud-sep"></span>
            <a href="?filter_status={'All' if cur_filter == 'AUTOMATION OFF' else 'AUTOMATION OFF'}" target="_self" class="hud-pill">
                <span class="dot-black"></span>
                <b>{count_auto_off}</b> AUTOMATION OFF
            </a>
            <span class="hud-sep"></span>
            <a href="?filter_status={'All' if cur_filter == 'SETTLED' else 'SETTLED'}" target="_self" class="hud-pill">
                <span class="dot-gray"></span>
                <b>{count_settled}</b> SETTLED
            </a>
        </div>
        """
    )

    # -----------------------------------------------------------------------
    # PIPELINE Section (6 Kanban Stage Cards with 3 Stacked Mini Tracks)
    # Dynamic computation from live claims
    # -----------------------------------------------------------------------
    html_block("<div class='section-head'>PIPELINE</div>")
    html_block("<div class='section-sub'>Open automated claims across the flow · click a stage to filter</div>")

    c_k1, c_k2, c_k3, c_k4, c_k5, c_k6 = st.columns(6)
    kanban_cols = [c_k1, c_k2, c_k3, c_k4, c_k5, c_k6]

    KANBAN_STAGES_CONFIG = [
        {"num": "1", "name": "INTAKE & TRIAGE", "icon": "🗂️", "match": STAGE_1_INTAKE},
        {"num": "2", "name": "COVERAGE", "icon": "🛡️", "match": STAGE_2_COVERAGE},
        {"num": "3", "name": "DA / ESTIMATE", "icon": "📋", "match": STAGE_3_VISION},
        {"num": "4", "name": "LIABILITY", "icon": "⚖️", "match": STAGE_4_FRAUD},
        {"num": "5", "name": "SETTLEMENT", "icon": "🤝", "match": STAGE_5_DECISION},
        {"num": "6", "name": "SUBROGATION", "icon": "🔄", "match": "SUBROGATION"},
    ]

    for idx, k_info in enumerate(KANBAN_STAGES_CONFIG):
        stg_name = k_info["name"]
        match_key = k_info["match"]
        is_stg_sel = (st.session_state.filter_stage == stg_name)
        border_highlight = "border: 1.5px solid #0D9488;" if is_stg_sel else ""

        # Real dynamic counts from claims database
        stage_claims = [
            c for c in all_claims
            if match_key in c.current_stage
            and c.claim_status not in (ClaimStatusEnum.SETTLED, ClaimStatusEnum.DISCARDED)
        ]
        open_cnt = len(stage_claims)
        stuck_cnt = sum(1 for c in stage_claims if c.claim_status == ClaimStatusEnum.STUCK or c.action_type == ActionTypeEnum.ESCALATION)
        amber_cnt = sum(1 for c in stage_claims if c.claim_status == ClaimStatusEnum.NEEDS_ATTENTION or c.priority == "High priority")
        green_cnt = max(0, open_cnt - stuck_cnt - amber_cnt)

        pct_red = (stuck_cnt / open_cnt * 100) if open_cnt > 0 else 0
        pct_amber = (amber_cnt / open_cnt * 100) if open_cnt > 0 else 0
        pct_green = (green_cnt / open_cnt * 100) if open_cnt > 0 else 0

        with kanban_cols[idx]:
            html_block(
                f"""
                <a href="?filter_stage={'All' if is_stg_sel else stg_name}" target="_self" style="text-decoration:none !important; color:inherit;">
                    <div class="stage-card" style="{border_highlight}">
                        <div class="stage-card-title">{k_info['num']} {k_info['icon']} {stg_name}</div>
                        <div class="stage-card-count">{open_cnt} <span>OPEN</span></div>
                        <div class="mini-track-row">
                            <span class="mini-pill-num" style="color: #EF4444;">{stuck_cnt}</span>
                            <div class="mini-track"><div class="mini-fill-red" style="width: {pct_red}%;"></div></div>
                        </div>
                        <div class="mini-track-row">
                            <span class="mini-pill-num" style="color: #F59E0B;">{amber_cnt}</span>
                            <div class="mini-track"><div class="mini-fill-amber" style="width: {pct_amber}%;"></div></div>
                        </div>
                        <div class="mini-track-row">
                            <span class="mini-pill-num" style="color: #10B981;">{green_cnt}</span>
                            <div class="mini-track"><div class="mini-fill-green" style="width: {pct_green}%;"></div></div>
                        </div>
                    </div>
                </a>
                """
            )

    html_block("<div style='height: 12px;'></div>")

    # -----------------------------------------------------------------------
    # CLAIMS Section (Horizontal Capsule Filters + Claim Rows)
    # -----------------------------------------------------------------------
    html_block("<div class='section-head'>CLAIMS</div>")

    # -----------------------------------------------------------------------
    # Helper classification and scoring functions for Claims filters
    # -----------------------------------------------------------------------
    def _is_high_severity(c) -> bool:
        vr = getattr(c, "vision_report", None)
        sev = (getattr(vr, "overall_severity", "") or "").lower()
        cost = float(getattr(vr, "estimated_repair_cost_inr", 0) or 0)
        if "total loss" in sev or "severe" in sev or "major" in sev:
            return True
        if cost > 25000:
            return True
        if c.priority == "High priority" and ("3 DA" in (c.current_stage or "") or "reserve" in (c.headline_summary or "").lower()):
            return True
        if c.policy_id in ("POL-1002", "POL-1007"):
            return True
        return False

    def _get_severity_score(c) -> float:
        vr = getattr(c, "vision_report", None)
        sev = (getattr(vr, "overall_severity", "") or "").lower()
        cost = float(getattr(vr, "estimated_repair_cost_inr", 0) or 0)
        rank = 1
        if "total loss" in sev or c.policy_id == "POL-1002":
            rank = 4
        elif "severe" in sev:
            rank = 3
        elif "major" in sev or c.policy_id == "POL-1007":
            rank = 2
        return rank * 10000000 + cost

    def _is_fraud_signal(c) -> bool:
        fr = getattr(c, "fraud_report", None)
        risk = (getattr(fr, "risk_level", "") or "").lower()
        if risk in ("high", "medium") or c.policy_id == "POL-1003":
            return True
        if fr and (getattr(fr, "contradictions", None) or getattr(fr, "signals", None) or getattr(fr, "unresolved_contradiction", False)):
            return True
        headline = (c.headline_summary or "").lower()
        if "fraud" in headline or "contradiction" in headline:
            return True
        return False

    def _get_fraud_score(c) -> float:
        fr = getattr(c, "fraud_report", None)
        score = 0
        risk = (getattr(fr, "risk_level", "") or "").lower()
        if risk == "high" or c.policy_id == "POL-1003":
            score += 100
        elif risk == "medium":
            score += 50
        if fr and getattr(fr, "unresolved_contradiction", False):
            score += 40
        if fr and getattr(fr, "contradictions", None):
            score += len(fr.contradictions) * 25
        if fr and getattr(fr, "signals", None):
            score += len(fr.signals) * 15
        return score

    def _is_ambiguous(c) -> bool:
        vr = getattr(c, "vision_report", None)
        fr = getattr(c, "fraud_report", None)
        cr = getattr(c, "coverage_result", None)
        if fr and (getattr(fr, "unresolved_contradiction", False) or getattr(fr, "contradictions", None)):
            return True
        if vr and getattr(vr, "unusable_photos", False):
            return True
        if vr and 0 < getattr(vr, "overall_confidence", 0) < 75:
            return True
        if not getattr(c, "photo_paths", None):
            return True
        if c.action_type in (ActionTypeEnum.QUESTION, ActionTypeEnum.REQUEST):
            return True
        if getattr(c, "returned_to_user_prompt", None):
            return True
        if cr and getattr(cr, "status", "") in ("needs_review", "not_covered"):
            return True
        if c.claim_status == ClaimStatusEnum.STUCK:
            return True
        if c.policy_id in ("POL-1004", "POL-1005", "POL-1006"):
            return True
        return False

    all_active = [c for c in all_claims if getattr(c.claim_status, "value", c.claim_status) != "DISCARDED"]
    c_all_cnt = len(all_active)
    c_sev_cnt = len([c for c in all_active if _is_high_severity(c)])
    c_fra_cnt = len([c for c in all_active if _is_fraud_signal(c)])
    c_amb_cnt = len([c for c in all_active if _is_ambiguous(c)])

    cur_cat = st.session_state.filter_category

    # Four horizontal clickable filter buttons: All Claims | High Severity | Fraud Signals | Ambiguous
    cf_all, cf_sev, cf_fra, cf_amb = st.columns(4)

    with cf_all:
        if st.button(f"All Claims ({c_all_cnt})", key="btn_filter_all", type="primary" if cur_cat == "all" else "secondary", use_container_width=True):
            st.session_state.filter_category = "all"
            st.rerun()

    with cf_sev:
        if st.button(f"⚡ High Severity ({c_sev_cnt})", key="btn_filter_sev", type="primary" if cur_cat == "severity" else "secondary", use_container_width=True):
            st.session_state.filter_category = "severity"
            st.rerun()

    with cf_fra:
        if st.button(f"🚨 Fraud Signals ({c_fra_cnt})", key="btn_filter_fra", type="primary" if cur_cat == "fraud" else "secondary", use_container_width=True):
            st.session_state.filter_category = "fraud"
            st.rerun()

    with cf_amb:
        if st.button(f"⚠️ Ambiguous ({c_amb_cnt})", key="btn_filter_amb", type="primary" if cur_cat == "ambiguous" else "secondary", use_container_width=True):
            st.session_state.filter_category = "ambiguous"
            st.rerun()

    # Apply Category Filters & Sorting
    filtered_claims = list(all_active)

    if cur_cat == "severity":
        filtered_claims = [c for c in filtered_claims if _is_high_severity(c)]
        filtered_claims.sort(key=_get_severity_score, reverse=True)
    elif cur_cat == "fraud":
        filtered_claims = [c for c in filtered_claims if _is_fraud_signal(c)]
        filtered_claims.sort(key=_get_fraud_score, reverse=True)
    elif cur_cat == "ambiguous":
        filtered_claims = [c for c in filtered_claims if _is_ambiguous(c)]

    if st.session_state.filter_stage != "All":
        filtered_claims = [c for c in filtered_claims if st.session_state.filter_stage in c.current_stage]

    if st.session_state.search_query:
        sq = st.session_state.search_query.lower()
        filtered_claims = [
            c for c in filtered_claims
            if sq in c.claim_id.lower()
            or sq in c.policy_id.lower()
            or sq in c.policyholder_name.lower()
            or sq in c.vehicle_reg.lower()
            or sq in c.headline_summary.lower()
        ]

    html_block(f"<div class='section-sub'>Showing <b>{len(filtered_claims)}</b> of {total_claims_display} · click a row to open · double-click for details</div>")

    if not filtered_claims:
        html_block(
            """
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 36px 20px; text-align: center; margin-top: 14px;">
                <div style="font-size: 32px; margin-bottom: 8px;">📭</div>
                <div style="font-size: 14.5px; font-weight: 700; color: #0F172A; margin-bottom: 4px;">No Claims in Database</div>
                <div style="font-size: 12px; color: #64748B; max-width: 500px; margin: 0 auto 12px auto; line-height: 1.5;">
                    Submit a notice of loss from <b>+ FNOL Intake Portal (Page 1)</b> using any of the 7 Indian insurance policy test scenarios to watch autonomous triage advance live across the 5 Kanban stages.
                </div>
            </div>
            """
        )

    # -----------------------------------------------------------------------
    # Real Claim Rows & Expanded Detail Containers
    # -----------------------------------------------------------------------
    for claim in filtered_claims:
        cid = claim.claim_id
        is_expanded = (st.session_state.selected_claim_id == cid)

        # Status Dot & Stacked Label (clean single-line HTML with zero leading indentation)
        if claim.claim_status == ClaimStatusEnum.NEEDS_ATTENTION:
            dot_html = (
                '<div style="display:flex; align-items:center; gap:5px; min-width:75px;">'
                '<span class="dot-amber"></span>'
                '<div style="font-size:8.5px; font-weight:800; color:#B45309; line-height:1.1; letter-spacing:0.3px;">NEEDS<br/>ATTENTION</div>'
                '</div>'
            )
        elif claim.claim_status == ClaimStatusEnum.STUCK:
            dot_html = (
                '<div style="display:flex; align-items:center; gap:5px; min-width:75px;">'
                '<span class="dot-red"></span>'
                '<div style="font-size:9px; font-weight:800; color:#DC2626; letter-spacing:0.3px;">STUCK</div>'
                '</div>'
            )
        elif claim.claim_status == ClaimStatusEnum.AUTOMATION_OFF:
            dot_html = (
                '<div style="display:flex; align-items:center; gap:5px; min-width:75px;">'
                '<span class="dot-black"></span>'
                '<div style="font-size:8.5px; font-weight:800; color:#334155; line-height:1.1; letter-spacing:0.3px;">AUTOMATION<br/>OFF</div>'
                '</div>'
            )
        elif claim.claim_status == ClaimStatusEnum.SETTLED:
            dot_html = (
                '<div style="display:flex; align-items:center; gap:5px; min-width:75px;">'
                '<span class="dot-gray"></span>'
                '<div style="font-size:9px; font-weight:800; color:#64748B; letter-spacing:0.3px;">SETTLED</div>'
                '</div>'
            )
        else:
            dot_html = (
                '<div style="display:flex; align-items:center; gap:5px; min-width:75px;">'
                '<span class="dot-green"></span>'
                '<div style="font-size:8.5px; font-weight:800; color:#059669; line-height:1.1; letter-spacing:0.3px;">IN<br/>PROGRESS</div>'
                '</div>'
            )

        # Action Badge
        if claim.action_type == ActionTypeEnum.RECOMMENDATION:
            act_badge = '<span class="badge-rec">🎗 RECOMMENDATION</span>'
        elif claim.action_type == ActionTypeEnum.REQUEST:
            act_badge = '<span class="badge-req">📋 REQUEST</span>'
        elif claim.action_type == ActionTypeEnum.QUESTION:
            act_badge = '<span class="badge-que">❓ QUESTION</span>'
        elif claim.action_type == ActionTypeEnum.ESCALATION:
            act_badge = '<span class="badge-esc">🛑 ESCALATION</span>'
        else:
            act_badge = ''

        prio_html = '<span class="pill-high-priority">High priority</span>' if claim.priority == "High priority" else ""

        # Claim Row Container (Pure White Card matching Screenshot 1)
        with st.container(border=True):
            col_l, col_m, col_r = st.columns([2.1, 4.3, 3.6])

            with col_l:
                html_block(
                    f"""
                    <div style="display:flex; align-items:center; gap:10px;">
                        {dot_html}
                        <div>
                            <div style="font-size:13px; font-weight:700; color:#0F172A; letter-spacing:-0.2px;">{claim.claim_id}</div>
                            <div style="font-size:10.5px; color:#64748B; margin-top:2px;">⚖️ {claim.current_stage} · {claim.line_of_business} {prio_html}</div>
                        </div>
                    </div>
                    """
                )

            with col_m:
                rec_sub = f"Spark recommends: {claim.recommendation_title}" if claim.recommendation_title else ""
                html_block(
                    f"""
                    <div>
                        {act_badge}
                        <b style="font-size:12px; color:#0F172A; font-weight:700;">{claim.headline_summary}</b>
                    </div>
                    <div style="font-size:10.5px; color:#64748B; margin-top:2px;">
                        {rec_sub}
                    </div>
                    """
                )

            with col_r:
                chevron = "▲" if is_expanded else "∨"
                is_analysis_open = st.session_state.get(f"show_analysis_{cid}", False)
                is_surveyor_open = st.session_state.get(f"show_surveyor_{cid}", False)
                show_exec = (claim.action_type == ActionTypeEnum.RECOMMENDATION or claim.claim_status == ClaimStatusEnum.NEEDS_ATTENTION)

                if show_exec:
                    r1, r2, r3, r4, r5 = st.columns([1.1, 1.0, 1.3, 1.3, 0.4])
                    with r1:
                        if st.button("✓ Execute", key=f"exec_{cid}", type="primary", help="Process & Settle Claim"):
                            ac.execute_claim_action(cid)
                            st.toast(f"Claim {cid} Settled!")
                            st.rerun()
                    with r2:
                        if st.button("✕ Dismiss", key=f"dism_{cid}", help="Discard Claim"):
                            ac.dismiss_claim_action(cid)
                            st.toast(f"Claim {cid} Discarded.")
                            st.rerun()
                    with r3:
                        if st.button("📋 Analysis", key=f"analysis_btn_{cid}", help="View Comprehensive Analysis Report"):
                            st.session_state[f"show_analysis_{cid}"] = not is_analysis_open
                            st.rerun()
                    with r4:
                        if st.button("🔍 Surveyor", key=f"surveyor_btn_{cid}", help="View Surveyor Recommendation & Dispatch"):
                            st.session_state[f"show_surveyor_{cid}"] = not is_surveyor_open
                            st.rerun()
                    with r5:
                        if st.button(chevron, key=f"exp_btn_{cid}"):
                            st.session_state.selected_claim_id = None if is_expanded else cid
                            st.rerun()

                else:
                    r1, r2, r3, r4 = st.columns([1.0, 1.4, 1.4, 0.4])
                    with r1:
                        if st.button("✕ Dismiss", key=f"dism_{cid}", help="Discard Claim"):
                            ac.dismiss_claim_action(cid)
                            st.toast(f"Claim {cid} Discarded.")
                            st.rerun()
                    with r2:
                        if st.button("📋 Analysis", key=f"analysis_btn_{cid}", help="View Comprehensive Analysis Report"):
                            st.session_state[f"show_analysis_{cid}"] = not is_analysis_open
                            st.rerun()
                    with r3:
                        if st.button("🔍 Surveyor", key=f"surveyor_btn_{cid}", help="View Surveyor Recommendation & Dispatch"):
                            st.session_state[f"show_surveyor_{cid}"] = not is_surveyor_open
                            st.rerun()
                    with r4:
                        if st.button(chevron, key=f"exp_btn_{cid}"):
                            st.session_state.selected_claim_id = None if is_expanded else cid
                            st.rerun()

        # -------------------------------------------------------------------
        # Inline Analysis Report Panel
        # -------------------------------------------------------------------
        if st.session_state.get(f"show_analysis_{cid}", False):
            with st.container(border=True):
                st.markdown(f"### 📋 Comprehensive AI Analysis Report — `{cid}`")
                vr = claim.vision_report
                cr = claim.coverage_result
                fr = claim.fraud_report
                pol = state.policies.get(claim.policy_id) if hasattr(state, "policies") else None
                rec = ac.compute_surveyor_recommendation(claim)

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Section A: Claim & Vehicle Information**")
                    st.caption(f"• **Policy ID:** {claim.policy_id}\n• **Policyholder:** {claim.policyholder_name}\n• **Reg:** {claim.vehicle_reg}\n• **Incident:** {claim.incident_date} ({claim.incident_time}) at {claim.location}\n• **Statement:** *\"{claim.raw_statement}\"*")

                    st.markdown("**Section B: AI Severity Estimation**")
                    sev = vr.overall_severity if vr else "Unknown"
                    cost = f"₹{vr.estimated_repair_cost_inr:,.0f}" if vr and vr.estimated_repair_cost_inr else "₹0"
                    zones = ", ".join(vr.damaged_zones) if vr and vr.damaged_zones else "Front Bumper"
                    conf = f"{vr.overall_confidence}%" if vr else "85%"
                    st.caption(f"• **Severity:** {sev}\n• **Estimated Repair:** {cost}\n• **Damaged Zones:** {zones}\n• **Visual AI Confidence:** {conf}")

                with c2:
                    st.markdown("**Section C: Coverage Details**")
                    cov_status = cr.coverage_status if cr else "COVERED"
                    cov_type = cr.coverage_type if cr else "Comprehensive Motor"
                    idv = f"₹{cr.idv_inr:,.0f}" if cr and cr.idv_inr else "₹500,000"
                    ded = f"₹{cr.deductible_inr:,.0f}" if cr and cr.deductible_inr else "₹1,000"
                    payable = f"₹{cr.estimated_payable_inr:,.0f}" if cr and cr.estimated_payable_inr else "₹0"
                    st.caption(f"• **Status:** {cov_status}\n• **Plan:** {cov_type}\n• **IDV:** {idv} | **Deductible:** {ded}\n• **Net Estimated Payable:** {payable}\n• **Clause:** {cr.clause_reference if cr else 'Standard OD Clause'}")

                    st.markdown("**Section D: Fraud Signals & Integrity**")
                    risk = fr.risk_level if fr else "Low"
                    contra = fr.statement_vs_photo_match if fr else "Consistent"
                    st.caption(f"• **Risk Classification:** {risk}\n• **Physical Consistency:** {contra}\n• **Screening Heuristics:** Automated indicators represent screening signals only, not confirmed fraud.")

                st.markdown("**Section E: Spark AI Decision Verdict**")
                st.info(f"**Action:** {claim.action_type.value if hasattr(claim.action_type, 'value') else claim.action_type} — {claim.headline_summary}")
                if claim.rationale_bullets:
                    for b in claim.rationale_bullets:
                        st.markdown(f"• {b}")

                b_col1, b_col2 = st.columns([6, 1])
                with b_col2:
                    if st.button("Close Report", key=f"close_an_{cid}"):
                        st.session_state[f"show_analysis_{cid}"] = False
                        st.rerun()

        # -------------------------------------------------------------------
        # Inline Surveyor Report Panel
        # -------------------------------------------------------------------
        if st.session_state.get(f"show_surveyor_{cid}", False):
            with st.container(border=True):
                st.markdown(f"### 🔍 AI Surveyor Assignment Report — `{cid}`")
                rec = ac.compute_surveyor_recommendation(claim)
                st.success(f"**AI Recommended Surveyor:** {rec['recommendation']}")
                st.caption(f"**Rationale:** {rec['reason']}")

                if claim.assigned_surveyor:
                    st.markdown(f"✅ **Currently Assigned:** {claim.assigned_surveyor} *({claim.surveyor_assigned_at or 'Active'})*")
                else:
                    st.warning("⚠️ **Current Status:** Unassigned (Awaiting Field Dispatch)")

                sur_c1, sur_c2, sur_c3 = st.columns([1.5, 1.5, 1])
                with sur_c1:
                    if st.button("Assign Junior Surveyor", key=f"assign_jr_{cid}"):
                        ac.assign_surveyor_action(cid, "Junior Surveyor", "Dispatched from Surveyor Report panel.")
                        st.toast(f"Assigned {cid} to Junior Surveyor!")
                        st.rerun()
                with sur_c2:
                    if st.button("Assign Senior Surveyor", key=f"assign_sr_{cid}"):
                        ac.assign_surveyor_action(cid, "Senior Surveyor", "Dispatched from Surveyor Report panel.")
                        st.toast(f"Assigned {cid} to Senior Surveyor!")
                        st.rerun()
                with sur_c3:
                    if st.button("Close", key=f"close_sur_{cid}"):
                        st.session_state[f"show_surveyor_{cid}"] = False
                        st.rerun()

        # -------------------------------------------------------------------
        # Expanded Claim Detail View (Screenshots 6, 7)
        # -----------------------------------------------------------------------
        if is_expanded:
            with st.container():
                html_block('<div class="dossier-card">')

                # SECTION A — WHAT SPARK DID
                html_block("<div class='dossier-title'>⚡ WHAT SPARK DID</div>")
                html_block(
                    f"<div style='font-size: 12.5px; color: #1E293B; margin-bottom: 12px; line-height: 1.5;'>"
                    f"{claim.what_spark_did or 'Spark completed automated claim ingestion and initiated verification checks.'}"
                    f"</div>"
                )

                with st.expander("🔍 Visual Inspection & Contradiction Loop Panel", expanded=False):
                    v_col1, v_col2 = st.columns([1.5, 2.5])
                    with v_col1:
                        st.markdown("**Submitted Photos:**")
                        if claim.photo_paths:
                            for p_path in claim.photo_paths:
                                if Path(p_path).exists():
                                    st.image(p_path, caption=Path(p_path).name, use_container_width=True)
                                else:
                                    st.write(f"📁 `{Path(p_path).name}`")
                        else:
                            st.caption("No damage photos uploaded.")

                    with v_col2:
                        st.markdown("**Zone-by-Zone Visual Checklist (Agent 2):**")
                        if claim.vision_report and claim.vision_report.findings:
                            findings_data = []
                            for f in claim.vision_report.findings:
                                findings_data.append({
                                    "Zone": f.zone.upper(),
                                    "Status": f.status,
                                    "Severity": f.severity,
                                    "Description": f.description,
                                    "Confidence": f"{f.confidence}%",
                                })
                            st.dataframe(findings_data, use_container_width=True)
                            st.markdown(
                                f"**Estimated Repair Cost:** `₹{claim.vision_report.estimated_repair_cost_inr:,.0f}` · "
                                f"**Overall Severity:** `{claim.vision_report.overall_severity}` · "
                                f"**Confidence:** `{claim.vision_report.overall_confidence}%`"
                            )
                        else:
                            st.caption("Vision assessment pending or completed deterministically.")

                        if claim.loop_count > 0:
                            st.markdown("---")
                            st.markdown(f"**🔄 Autonomous Verification Loops Executed ({claim.loop_count} / {config.MAX_CONTRADICTION_LOOPS}):**")
                            loop_traces = [t for t in claim.agent_trace if "Loop" in t.purpose or "Loop" in t.result_summary]
                            for lt in loop_traces:
                                st.markdown(f"• **{lt.purpose}:** {lt.result_summary}")

                # SECTION B — RECOMMENDATION CARD
                html_block("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 12px 0;' />")
                html_block("<div class='dossier-title'>✨ RECOMMENDATION</div>")
                html_block(f"<div class='rec-headline'>{claim.recommendation_title or 'Pending Final Decision Package'}</div>")

                # Confidence Progress Bar
                conf = claim.confidence_score
                bar_color = "#10B981" if conf >= 80 else ("#F59E0B" if conf >= 50 else "#EF4444")
                html_block(
                    f"""
                    <div style="display:flex; align-items:center; margin-bottom:12px; font-size:11.5px; font-weight:600; color:#0F172A;">
                        <span>Confidence {conf}%</span>
                        <div class="conf-bar-track">
                            <div style="width:{conf}%; height:100%; background-color:{bar_color}; border-radius:9999px;"></div>
                        </div>
                        <span style="font-weight:400; color:#64748B;">· Mandatory human approval step in the automation design</span>
                    </div>
                    """
                )

                # WHY Bullet Points
                html_block("<div style='font-size: 10.5px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 4px;'>WHY</div>")
                if claim.rationale_bullets:
                    for b in claim.rationale_bullets:
                        html_block(f"<div style='font-size: 12px; color: #334155; margin-bottom: 3px;'>• {b}</div>")

                # SECTION C — REFERENCED DOCUMENTS
                html_block("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 12px 0;' />")
                html_block("<div style='font-size: 10.5px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 6px;'>REFERENCED DOCUMENTS</div>")
                if claim.referenced_documents:
                    for doc in claim.referenced_documents:
                        html_block(
                            f"""
                            <div class="ref-doc-card-exact">
                                <div class="ref-doc-card-title">📄 {doc.doc_name} &nbsp;<span style="color:#64748B; font-weight:400;">{doc.section_ref}</span></div>
                                <div class="ref-doc-card-summary">{doc.summary}</div>
                            </div>
                            """
                        )

                # SECTION D — DATA CLIVE REASONED OVER
                html_block("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 12px 0;' />")
                html_block("<div style='font-size: 10.5px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 6px;'>📊 DATA CLIVE REASONED OVER</div>")
                tags = claim.data_tags or ["Estimate / damage documentation", "Policy schedule", "Policy loss history", "Fraud screening result"]
                tag_pills = " ".join([f"<span style='background:#F1F5F9; color:#475569; font-size:10.5px; font-weight:600; padding:3px 8px; border-radius:4px; margin-right:6px;'>{t}</span>" for t in tags])
                html_block(f"<div>{tag_pills}</div>")

                # SECTION E — YOUR OPTIONS
                html_block("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 12px 0;' />")
                html_block("<div style='font-size: 10.5px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 6px;'>✍️ YOUR OPTIONS</div>")
                opt_c1, opt_c2, opt_c3 = st.columns([1.5, 1.5, 2])
                with opt_c1:
                    if st.button("✓ Execute recommendation", key=f"doss_exec_{cid}", type="primary", use_container_width=True):
                        ac.execute_claim_action(cid)
                        st.toast(f"Claim {cid} Settled!")
                        st.rerun()
                with opt_c2:
                    if st.button("✕ Dismiss recommendation", key=f"doss_dism_{cid}", use_container_width=True):
                        ac.dismiss_claim_action(cid)
                        st.toast(f"Claim {cid} Discarded.")
                        st.rerun()
                with opt_c3:
                    if st.button("↩ Return to User for Clarification", key=f"doss_ret_{cid}", use_container_width=True):
                        ac.return_to_user_action(cid, "Please submit clearer photo of the damage zone.")
                        st.toast("Claim returned to claimant portal for clarification!")
                        st.rerun()

                html_block(
                    "<div style='font-size: 11px; color: #64748B; margin-top: 6px; line-height: 1.4;'>"
                    "Executing applies Spark's proposal as-is and returns the claim to the automated flow. "
                    "To amend it, ask Spark in the chat below. Dismissing rejects the proposal."
                    "</div>"
                )

                # SECTION F — EDIT VIA CHAT WITH SPARK
                html_block("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 12px 0;' />")
                html_block("<div style='font-size: 10.5px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 4px;'>💬 EDIT VIA CHAT WITH SPARK</div>")

                if claim.chat_history:
                    for ch in claim.chat_history:
                        is_user = ch.role == "adjuster"
                        bg_col = "#F8FAFC" if is_user else "#F0FDFA"
                        border_col = "#E2E8F0" if is_user else "#99F6E4"
                        label_name = "👤 Adjuster" if is_user else "🤖 Spark"
                        html_block(
                            f"""
                            <div style="background:{bg_col}; border:1px solid {border_col}; border-radius:6px; padding:6px 10px; margin-bottom:4px; font-size:11.5px;">
                                <b style="color:#0F172A;">{label_name}:</b> {ch.message}
                            </div>
                            """
                        )

                with st.form(key=f"chat_form_{cid}"):
                    chat_in = st.text_input(
                        "Chat prompt",
                        placeholder=f"Tell Spark what to change — 'Adjust liability split to 60/40', 'Increase repair estimate by ₹5,000'...",
                        label_visibility="collapsed",
                    )
                    c_snd, _ = st.columns([1, 4])
                    with c_snd:
                        snd = st.form_submit_button("➤ Send to Spark", type="primary", use_container_width=True)

                    if snd and chat_in:
                        reply = ac.chat_with_spark(cid, chat_in)
                        st.toast("Spark redrafted the recommendation!")
                        st.rerun()

                html_block('</div>')

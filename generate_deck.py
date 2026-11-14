"""
generate_deck.py — Generates the 5-slide Aerophilia 2026 Hackathon Presentation
for Spark FNOL (Team Sparklers).
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------------------------------------------------------------------------
# COLOR PALETTE (Professional Modern Tech / Insurance)
# ---------------------------------------------------------------------------
BG_WHITE       = RGBColor(255, 255, 255)
NAVY_HEAD      = RGBColor(15, 23, 42)     # #0F172A Dark Navy
BLUE_ACCENT    = RGBColor(37, 99, 235)    # #2563EB Primary Blue
BLUE_DARK      = RGBColor(30, 58, 138)    # #1E3A8A Darker Blue
SLATE_DARK     = RGBColor(51, 65, 85)     # #334155 Charcoal text
SLATE_MED      = RGBColor(100, 116, 139)  # #64748B Secondary text
SLATE_LIGHT    = RGBColor(248, 250, 252)  # #F8FAFC Card background
SLATE_BORDER   = RGBColor(226, 232, 240)  # #E2E8F0 Subtle border
BLUE_TINT_BG   = RGBColor(239, 246, 255)  # #EFF6FF Blue tinted card
BLUE_TINT_BDR  = RGBColor(191, 219, 254)  # #BFDBFE Blue card border
TEAL_ACCENT    = RGBColor(13, 148, 136)   # #0D9488 Teal
TEAL_TINT_BG   = RGBColor(240, 253, 250)  # #F0FDFA Teal tint card
TEAL_TINT_BDR  = RGBColor(153, 246, 228)  # #99F6E4 Teal border
AMBER_ACCENT   = RGBColor(217, 119, 6)    # #D97706 Amber
AMBER_TINT_BG  = RGBColor(254, 243, 199)  # #FEF3C7 Amber tint card
ROSE_ACCENT    = RGBColor(225, 29, 72)    # #E11D48 Rose / Red
ROSE_TINT_BG   = RGBColor(255, 241, 242)  # #FFF1F2 Rose tint card
PURPLE_ACCENT  = RGBColor(124, 58, 237)   # #7C3AED Purple
PURPLE_TINT_BG = RGBColor(245, 243, 255)  # #F5F3FF Purple tint card

FONT_MAIN = "Arial"

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================
    def set_slide_background(slide, color=BG_WHITE):
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_header(slide, title, subtitle, category_tag="AEROPHILIA 2026"):
        # Category Tag Pill
        tag_box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.8), Inches(0.45), Inches(3.8), Inches(0.32)
        )
        tag_box.fill.solid()
        tag_box.fill.fore_color.rgb = BLUE_TINT_BG
        tag_box.line.color.rgb = BLUE_TINT_BDR
        tag_box.line.width = Pt(1)
        tf_tag = tag_box.text_frame
        tf_tag.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_tag.margin_left = tf_tag.margin_right = tf_tag.margin_top = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = category_tag.upper()
        p_tag.font.name = FONT_MAIN
        p_tag.font.size = Pt(9.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = BLUE_ACCENT
        p_tag.alignment = PP_ALIGN.CENTER

        # Main Title & Subtitle Box
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.82), Inches(11.733), Inches(0.9))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        
        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.name = FONT_MAIN
        p_t.font.size = Pt(26)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY_HEAD

        p_sub = tf.add_paragraph()
        p_sub.text = subtitle
        p_sub.font.name = FONT_MAIN
        p_sub.font.size = Pt(13)
        p_sub.font.color.rgb = SLATE_MED
        p_sub.space_before = Pt(3)

    # =========================================================================
    # SLIDE 1: INTRODUCTION
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide1)

    # Top Hackathon Tag Pill
    top_pill = slide1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(4.166), Inches(0.65), Inches(5.0), Inches(0.45)
    )
    top_pill.fill.solid()
    top_pill.fill.fore_color.rgb = BLUE_TINT_BG
    top_pill.line.color.rgb = BLUE_TINT_BDR
    top_pill.line.width = Pt(1.5)
    tf_top = top_pill.text_frame
    tf_top.vertical_anchor = MSO_ANCHOR.MIDDLE
    p_tp = tf_top.paragraphs[0]
    p_tp.text = "AEROPHILIA 2026  ·  AGENTIC AI HACKATHON"
    p_tp.font.name = FONT_MAIN
    p_tp.font.size = Pt(11)
    p_tp.font.bold = True
    p_tp.font.color.rgb = BLUE_DARK
    p_tp.alignment = PP_ALIGN.CENTER

    # Project Title & Subtitle
    title_box1 = slide1.shapes.add_textbox(Inches(1.0), Inches(1.3), Inches(11.333), Inches(1.5))
    tf1 = title_box1.text_frame
    tf1.word_wrap = True
    p1_title = tf1.paragraphs[0]
    p1_title.text = "SPARK FNOL"
    p1_title.font.name = FONT_MAIN
    p1_title.font.size = Pt(46)
    p1_title.font.bold = True
    p1_title.font.color.rgb = NAVY_HEAD
    p1_title.alignment = PP_ALIGN.CENTER

    p1_sub = tf1.add_paragraph()
    p1_sub.text = "Autonomous Multi-Agent Insurance Claims Triage & Adjuster Cockpit"
    p1_sub.font.name = FONT_MAIN
    p1_sub.font.size = Pt(17)
    p1_sub.font.color.rgb = BLUE_ACCENT
    p1_sub.space_before = Pt(4)
    p1_sub.alignment = PP_ALIGN.CENTER

    # Left Card: Problem Statement & Track
    left_card = slide1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.2), Inches(3.0), Inches(5.2), Inches(3.3)
    )
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = SLATE_LIGHT
    left_card.line.color.rgb = SLATE_BORDER
    left_card.line.width = Pt(1.5)
    tf_lc = left_card.text_frame
    tf_lc.word_wrap = True
    tf_lc.margin_left = tf_lc.margin_right = tf_lc.margin_top = tf_lc.margin_bottom = Inches(0.25)

    p = tf_lc.paragraphs[0]
    p.text = "PROBLEM STATEMENT TRACK"
    p.font.name = FONT_MAIN
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = TEAL_ACCENT

    p = tf_lc.add_paragraph()
    p.text = "Claims Triage Agent (Insurance)"
    p.font.name = FONT_MAIN
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = NAVY_HEAD
    p.space_before = Pt(6)

    bullets_lc = [
        "Autonomous First Notice of Loss (FNOL) processing",
        "Multimodal damage assessment & benchmark repair matrix",
        "Deterministic policy coverage gating (db2_policies.json)",
        "Satellite weather radar check & self-correction re-scan loops",
        "Human-in-the-loop governance & AI surveyor dispatch"
    ]
    for b in bullets_lc:
        p = tf_lc.add_paragraph()
        p.text = f"•  {b}"
        p.font.name = FONT_MAIN
        p.font.size = Pt(11)
        p.font.color.rgb = SLATE_DARK
        p.space_before = Pt(6)

    # Right Card: Team Sparklers & Members
    right_card = slide1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(6.9), Inches(3.0), Inches(5.2), Inches(3.3)
    )
    right_card.fill.solid()
    right_card.fill.fore_color.rgb = BLUE_TINT_BG
    right_card.line.color.rgb = BLUE_TINT_BDR
    right_card.line.width = Pt(1.5)
    tf_rc = right_card.text_frame
    tf_rc.word_wrap = True
    tf_rc.margin_left = tf_rc.margin_right = tf_rc.margin_top = tf_rc.margin_bottom = Inches(0.25)

    p = tf_rc.paragraphs[0]
    p.text = "HACKATHON TEAM"
    p.font.name = FONT_MAIN
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT

    p = tf_rc.add_paragraph()
    p.text = "TEAM SPARKLERS"
    p.font.name = FONT_MAIN
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = NAVY_HEAD
    p.space_before = Pt(6)

    members = [
        ("Shreesha Poojary", "Agentic Orchestration & Full-Stack Engine"),
        ("Bhoomika", "Multimodal Vision & Damage Appraisal"),
        ("Avani", "Policy Verification & Coverage Logic"),
        ("Amarjit Yadav", "Fraud Radar, Open-Meteo & Decision Gates")
    ]
    for name, role in members:
        p = tf_rc.add_paragraph()
        p.text = f"👤  {name}"
        p.font.name = FONT_MAIN
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = NAVY_HEAD
        p.space_before = Pt(6)

        p2 = tf_rc.add_paragraph()
        p2.text = f"     {role}"
        p2.font.name = FONT_MAIN
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = SLATE_MED

    # Footer note
    footer_box = slide1.shapes.add_textbox(Inches(1.0), Inches(6.8), Inches(11.333), Inches(0.4))
    tf_foot = footer_box.text_frame
    p_ft = tf_foot.paragraphs[0]
    p_ft.text = "Powered by Google Gemini 2.5, CrewAI & FastAPI  ·  Live Demonstration & Architecture Deep Dive"
    p_ft.font.name = FONT_MAIN
    p_ft.font.size = Pt(10.5)
    p_ft.font.color.rgb = SLATE_MED
    p_ft.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 2: THE PROBLEM
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide2)
    add_header(
        slide2,
        title="The Problem",
        subtitle="Critical Bottlenecks in Traditional Auto Insurance Claims Triage",
        category_tag="PROBLEM STATEMENT · CLAIMS TRIAGE AGENT"
    )

    # 4 Problem Cards in 2x2 Grid
    problems = [
        (
            "1. Prolonged Intake & Processing Delays",
            "MANUAL BACKLOG",
            ROSE_ACCENT, ROSE_TINT_BG,
            [
                "Manual FNOL data entry and initial reviews typically consume 7–14 days.",
                "Policyholders endure prolonged uncertainty without immediate claim validity feedback.",
                "High-volume peak loss events trigger immediate operational gridlocks."
            ],
            Inches(0.8), Inches(1.9), Inches(5.7), Inches(2.35)
        ),
        (
            "2. Subjective Damage & Cost Appraisal",
            "UNSTANDARDIZED ESTIMATION",
            AMBER_ACCENT, AMBER_TINT_BG,
            [
                "Adjusters visually estimate complex multizone vehicle damage without uniform pricing.",
                "Inconsistent repair estimates create reserve disputes, margin leaks, and delayed payouts.",
                "Zero automated mapping between photographic crush depth and parts/labor benchmarks."
            ],
            Inches(6.83), Inches(1.9), Inches(5.7), Inches(2.35)
        ),
        (
            "3. Contractual Coverage Blind Spots",
            "COMPLEX MANUAL POLICIES",
            BLUE_ACCENT, BLUE_TINT_BG,
            [
                "Policy schedules, inception dates, IDVs, and deductibles are manually cross-checked.",
                "Lapsed policies and Third-Party Only exclusions are identified late, wasting adjuster time.",
                "Contractual exclusions and endorsement riders require tedious clause-by-clause reading."
            ],
            Inches(0.8), Inches(4.5), Inches(5.7), Inches(2.35)
        ),
        (
            "4. Undetected Fraud & Environmental Fabrications",
            "BLIND RISK EXPOSURE",
            PURPLE_ACCENT, PURPLE_TINT_BG,
            [
                "Physical contradictions (e.g. rear-end story vs. front-end damage) slip through high-volume triage.",
                "Zero live verification of claimed weather events (rain, hail, floods) at accident coordinates.",
                "Exaggerated or pre-existing damage is approved due to lack of cross-evidence verification."
            ],
            Inches(6.83), Inches(4.5), Inches(5.7), Inches(2.35)
        )
    ]

    for title, badge, accent_c, bg_c, bullets, left, top, width, height in problems:
        card = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = SLATE_LIGHT
        card.line.color.rgb = SLATE_BORDER
        card.line.width = Pt(1.5)

        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.2)

        # Top Badge
        p = tf.paragraphs[0]
        p.text = badge
        p.font.name = FONT_MAIN
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = accent_c

        # Title
        p_t = tf.add_paragraph()
        p_t.text = title
        p_t.font.name = FONT_MAIN
        p_t.font.size = Pt(14)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY_HEAD
        p_t.space_before = Pt(3)

        # Bullets
        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"•  {b}"
            p_b.font.name = FONT_MAIN
            p_b.font.size = Pt(10)
            p_b.font.color.rgb = SLATE_DARK
            p_b.space_before = Pt(4)

    # =========================================================================
    # SLIDE 3: OUR SOLUTION
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3)
    add_header(
        slide3,
        title="Introducing Spark FNOL",
        subtitle="Autonomous Multi-Agent Claims Triage with Human-in-the-Loop Governance",
        category_tag="OUR SOLUTION · 5 CORE CAPABILITIES"
    )

    # 5 Vertical Pillars
    cols_s3 = [
        (
            "1. Multimodal Intake",
            "STAGE 1 · AGENT 1",
            BLUE_ACCENT,
            "Statement Analyst",
            [
                "Accepts raw free-text statement + real damage photos",
                "Extracts claimed impact zones, date & location",
                "Screens injuries & third-party liability facts"
            ],
            Inches(0.8)
        ),
        (
            "2. Policy Gating",
            "STAGE 2 · AGENT 4",
            TEAL_ACCENT,
            "Coverage Specialist",
            [
                "Validates in-force dates & Own Damage coverage",
                "Queries db2_policies.json deterministically",
                "Cites exact IRDAI contract clauses & limits"
            ],
            Inches(3.22)
        ),
        (
            "3. Vision Appraisal",
            "STAGE 3 · AGENT 2",
            NAVY_HEAD,
            "Vision Assessor",
            [
                "Gemini 2.5 multimodal zone-by-zone damage scan",
                "Appraises bumper, hood, doors, glass & panels",
                "Computes repair costs via repair_costs.json matrix"
            ],
            Inches(5.64)
        ),
        (
            "4. Fraud & Radar",
            "STAGE 4 · AGENT 3",
            ROSE_ACCENT,
            "Supervisor Brain",
            [
                "Queries Open-Meteo satellite weather radar",
                "Cross-checks claimed storm/rain at loss coordinates",
                "2-iteration self-correction loop resolves conflicts"
            ],
            Inches(8.06)
        ),
        (
            "5. Decision & Dispatch",
            "STAGE 5 · AGENTS 5 & 6",
            AMBER_ACCENT,
            "Decision Gate Engine",
            [
                "Tier 1 STP (≤ ₹25k) vs Tier 2 Review vs Tier 3 SIU",
                "100% deterministic pure Python financial math",
                "Recommends Junior vs Senior Surveyor allocation"
            ],
            Inches(10.48)
        )
    ]

    for title, stage_badge, color, agent_name, bullets, left in cols_s3:
        card = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.85), Inches(2.25), Inches(4.95))
        card.fill.solid()
        card.fill.fore_color.rgb = SLATE_LIGHT
        card.line.color.rgb = SLATE_BORDER
        card.line.width = Pt(1.5)

        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.18)

        # Stage Badge
        p = tf.paragraphs[0]
        p.text = stage_badge
        p.font.name = FONT_MAIN
        p.font.size = Pt(8.5)
        p.font.bold = True
        p.font.color.rgb = color

        # Pillar Title
        p_t = tf.add_paragraph()
        p_t.text = title
        p_t.font.name = FONT_MAIN
        p_t.font.size = Pt(13)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY_HEAD
        p_t.space_before = Pt(3)

        # Agent Name
        p_a = tf.add_paragraph()
        p_a.text = agent_name
        p_a.font.name = FONT_MAIN
        p_a.font.size = Pt(10)
        p_a.font.bold = True
        p_a.font.color.rgb = color
        p_a.space_before = Pt(1)

        # Divider line
        p_div = tf.add_paragraph()
        p_div.text = "―" * 15
        p_div.font.name = FONT_MAIN
        p_div.font.size = Pt(8)
        p_div.font.color.rgb = SLATE_BORDER
        p_div.space_before = Pt(2)

        # Bullets
        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.name = FONT_MAIN
            p_b.font.size = Pt(9.5)
            p_b.font.color.rgb = SLATE_DARK
            p_b.space_before = Pt(5)

    # =========================================================================
    # SLIDE 4: ARCHITECTURE & TECH STACK
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4)
    add_header(
        slide4,
        title="How Spark FNOL Works",
        subtitle="Multi-Agent Pipeline, Autonomous Re-Scan Loops & Production Tech Stack",
        category_tag="AGENTIC ARCHITECTURE & TECH STACK"
    )

    # Top Pipeline Bar (Horizontal 5-Stage Step Flow)
    pipe_steps = [
        ("Stage 1", "Intake Parsing", "Statement Analyst", BLUE_ACCENT),
        ("Stage 2", "Contract Gating", "Coverage Specialist", TEAL_ACCENT),
        ("Stage 3", "Vision Appraisal", "Vision Assessor", NAVY_HEAD),
        ("Stage 4", "Radar & Loops", "Supervisor Brain", ROSE_ACCENT),
        ("Stage 5", "Tiers & Dispatch", "Decision Gate", AMBER_ACCENT)
    ]
    step_w = Inches(2.25)
    gap = Inches(0.12)
    start_x = Inches(0.8)

    for i, (stg, name, role, col) in enumerate(pipe_steps):
        bx = start_x + i * (step_w + gap)
        box = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, Inches(1.8), step_w, Inches(1.2))
        box.fill.solid()
        box.fill.fore_color.rgb = SLATE_LIGHT
        box.line.color.rgb = col
        box.line.width = Pt(1.5)

        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.12)

        p = tf.paragraphs[0]
        p.text = f"{stg.upper()}"
        p.font.name = FONT_MAIN
        p.font.size = Pt(8.5)
        p.font.bold = True
        p.font.color.rgb = col

        p2 = tf.add_paragraph()
        p2.text = name
        p2.font.name = FONT_MAIN
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = NAVY_HEAD
        p2.space_before = Pt(1)

        p3 = tf.add_paragraph()
        p3.text = role
        p3.font.name = FONT_MAIN
        p3.font.size = Pt(9)
        p3.font.color.rgb = SLATE_MED
        p3.space_before = Pt(1)

    # Left Bottom Card: WHAT MAKES IT AGENTIC
    left_card4 = slide4.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(3.2), Inches(5.7), Inches(3.7)
    )
    left_card4.fill.solid()
    left_card4.fill.fore_color.rgb = BLUE_TINT_BG
    left_card4.line.color.rgb = BLUE_TINT_BDR
    left_card4.line.width = Pt(1.5)

    tf_l4 = left_card4.text_frame
    tf_l4.word_wrap = True
    tf_l4.margin_left = tf_l4.margin_right = tf_l4.margin_top = tf_l4.margin_bottom = Inches(0.22)

    p = tf_l4.paragraphs[0]
    p.text = "CORE AGENTIC CAPABILITIES (NOT A SIMPLE CHATBOT)"
    p.font.name = FONT_MAIN
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT

    agentic_points = [
        ("Autonomous Tool Calling", "Agents dynamically invoke extract_statement_facts, verify_weather_open_meteo, and rescan_photos_for_conflict without hardcoding."),
        ("Self-Correction Re-Scan Loop", "When statement facts contradict photo physics, Supervisor triggers an autonomous 2-iteration re-scan before escalating."),
        ("Deterministic Financial Guardrails", "Coverage limits, IDV calculations, and Tier 1–3 routing execute in pure Python (decision_gate.py) to prevent LLM hallucinations."),
        ("Supervised Human Governance", "Adjuster Cockpit provides real-time oversight: 1-click execution, claim dismissal, caseload re-balancing, and audit dossiers.")
    ]
    for title, desc in agentic_points:
        p_t = tf_l4.add_paragraph()
        p_t.text = f"•  {title}"
        p_t.font.name = FONT_MAIN
        p_t.font.size = Pt(11)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY_HEAD
        p_t.space_before = Pt(5)

        p_d = tf_l4.add_paragraph()
        p_d.text = f"   {desc}"
        p_d.font.name = FONT_MAIN
        p_d.font.size = Pt(9.5)
        p_d.font.color.rgb = SLATE_DARK
        p_d.space_before = Pt(1)

    # Right Bottom Card: VERIFIED TECH STACK
    right_card4 = slide4.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(6.83), Inches(3.2), Inches(5.7), Inches(3.7)
    )
    right_card4.fill.solid()
    right_card4.fill.fore_color.rgb = SLATE_LIGHT
    right_card4.line.color.rgb = SLATE_BORDER
    right_card4.line.width = Pt(1.5)

    tf_r4 = right_card4.text_frame
    tf_r4.word_wrap = True
    tf_r4.margin_left = tf_r4.margin_right = tf_r4.margin_top = tf_r4.margin_bottom = Inches(0.22)

    p = tf_r4.paragraphs[0]
    p.text = "VERIFIED PRODUCTION TECHNOLOGY STACK"
    p.font.name = FONT_MAIN
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = TEAL_ACCENT

    tech_points = [
        ("AI & Multimodal Vision", "Google Gemini 2.5 Flash, Gemini 2.5 Flash-Lite, CrewAI Agent Framework, Google GenAI SDK"),
        ("Backend Services & Server", "Python 3.13, FastAPI (REST API on port 8000), Uvicorn ASGI Server, Pydantic v2 domain schemas"),
        ("Storage & Persistence", "Atomic file swap architecture, db1_claims.json, db2_policies.json (7 test policies), repair_costs.json"),
        ("External APIs & Interfaces", "Open-Meteo Satellite Weather API, Tailwind CSS/Vanilla JS Single-Page App, Streamlit Cockpit")
    ]
    for category, stack in tech_points:
        p_c = tf_r4.add_paragraph()
        p_c.text = f"⚙️  {category}"
        p_c.font.name = FONT_MAIN
        p_c.font.size = Pt(11)
        p_c.font.bold = True
        p_c.font.color.rgb = NAVY_HEAD
        p_c.space_before = Pt(5)

        p_s = tf_r4.add_paragraph()
        p_s.text = f"    {stack}"
        p_s.font.name = FONT_MAIN
        p_s.font.size = Pt(9.5)
        p_s.font.color.rgb = SLATE_DARK
        p_s.space_before = Pt(1)

    # =========================================================================
    # SLIDE 5: IMPACT & CLOSING
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5)
    add_header(
        slide5,
        title="Why Spark FNOL Matters",
        subtitle="Practical, Measurable Value for Insurers, Adjusters & Policyholders",
        category_tag="BUSINESS VALUE & CONCLUSION"
    )

    # 4 Impact Cards in 2x2 Grid
    impacts = [
        (
            "⚡ Instant Straight-Through Processing (STP)",
            "OPERATIONAL VELOCITY",
            TEAL_ACCENT,
            [
                "Routine, low-cost claims (≤ ₹25,000) with verified coverage qualify for instant payouts.",
                "Dramatically slashes turnaround times from weeks to minutes, clearing adjuster backlogs.",
                "Policyholders receive transparent, immediate digital settlement offers."
            ],
            Inches(0.8), Inches(1.85), Inches(5.7), Inches(1.9)
        ),
        (
            "🎯 Objective, Physics-Grounded Appraisal",
            "FINANCIAL ACCURACY",
            BLUE_ACCENT,
            [
                "Multimodal zone damage appraisal replaces subjective visual guesswork and disputes.",
                "Standard IRDAI benchmark repair tables ensure accurate, auditable reserve allocations.",
                "Confidence metrics and visual evidence logging support full regulatory compliance."
            ],
            Inches(6.83), Inches(1.85), Inches(5.7), Inches(1.9)
        ),
        (
            "🛡️ Proactive Multi-Source Fraud Defense",
            "LOSS RATIO PROTECTION",
            ROSE_ACCENT,
            [
                "Real-time Open-Meteo satellite weather radar validates claimed rain and storm conditions.",
                "Autonomous re-scan loops catch narrative vs. photo contradictions before payouts.",
                "Flags suspicious, lapsed, or high-risk claims directly to Special Investigation Units."
            ],
            Inches(0.8), Inches(3.9), Inches(5.7), Inches(1.9)
        ),
        (
            "🤝 Supervised Human-in-the-Loop Governance",
            "HUMAN EMPOWERMENT",
            PURPLE_ACCENT,
            [
                "Adjusters retain full decision authority with 1-click execution, dismissal, or claim return.",
                "Automated AI surveyor recommendation matches field experts based on loss complexity.",
                "Instant export of 5-section audit dossiers (formatted printable PDF and plain text)."
            ],
            Inches(6.83), Inches(3.9), Inches(5.7), Inches(1.9)
        )
    ]

    for title, badge, accent_c, bullets, left, top, width, height in impacts:
        card = slide5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = SLATE_LIGHT
        card.line.color.rgb = SLATE_BORDER
        card.line.width = Pt(1.5)

        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.18)

        p = tf.paragraphs[0]
        p.text = badge
        p.font.name = FONT_MAIN
        p.font.size = Pt(8.5)
        p.font.bold = True
        p.font.color.rgb = accent_c

        p_t = tf.add_paragraph()
        p_t.text = title
        p_t.font.name = FONT_MAIN
        p_t.font.size = Pt(13)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY_HEAD
        p_t.space_before = Pt(2)

        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.name = FONT_MAIN
            p_b.font.size = Pt(9.5)
            p_b.font.color.rgb = SLATE_DARK
            p_b.space_before = Pt(3)

    # Bottom Closing Banner
    banner = slide5.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(6.0), Inches(11.733), Inches(1.0)
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = NAVY_HEAD
    banner.line.color.rgb = BLUE_ACCENT
    banner.line.width = Pt(2)

    tf_ban = banner.text_frame
    tf_ban.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf_ban.margin_left = tf_ban.margin_right = tf_ban.margin_top = tf_ban.margin_bottom = Inches(0.1)

    p_b1 = tf_ban.paragraphs[0]
    p_b1.text = "THANK YOU  ·  TEAM SPARKLERS"
    p_b1.font.name = FONT_MAIN
    p_b1.font.size = Pt(18)
    p_b1.font.bold = True
    p_b1.font.color.rgb = BG_WHITE
    p_b1.alignment = PP_ALIGN.CENTER

    p_b2 = tf_ban.add_paragraph()
    p_b2.text = "Aerophilia 2026 Agentic AI Hackathon  |  Claims Triage Agent (Insurance)"
    p_b2.font.name = FONT_MAIN
    p_b2.font.size = Pt(11)
    p_b2.font.color.rgb = BLUE_TINT_BDR
    p_b2.space_before = Pt(3)
    p_b2.alignment = PP_ALIGN.CENTER

    # Save presentation
    output_filename = "Spark_FNOL_Aerophilia_2026.pptx"
    prs.save(output_filename)
    print(f"Presentation successfully saved to: {output_filename}")
    return output_filename

if __name__ == "__main__":
    create_presentation()

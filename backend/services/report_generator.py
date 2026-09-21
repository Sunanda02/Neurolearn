"""
============================================================
REPORT CARD GENERATOR
Creates a professional PDF report card for a student session.

Contains:
    - Student info & session metadata
    - Assessment score (circular gauge drawn in PDF)
    - Behavioral Cue metrics (score, eye contact, head pose, blink rate)
    - Behavioral Cue timeline chart (line graph)
    - Adaptive analysis (trend, strengths, weaknesses)
    - Question-by-question breakdown
    - Recommendations

Usage:
    from services.report_generator import generate_report_card
    pdf_bytes = generate_report_card(report_data)
============================================================
"""

import io
import math
import time
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image,
)
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Polygon
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
import logging
logger = logging.getLogger("neurolearn.report")


# ── Colors matching NeuroLearn theme ──
GREEN_DARK = HexColor("#2A5C1E")
GREEN = HexColor("#4C9F38")
GREEN_MID = HexColor("#6BBF59")
GREEN_LIGHT = HexColor("#A8D5A0")
GREEN_PALE = HexColor("#E8F5E2")
AMBER = HexColor("#D4940E")
RED = HexColor("#DC2626")
TEXT_DARK = HexColor("#1A1A2E")
TEXT_MID = HexColor("#3A3A50")
TEXT_MUTED = HexColor("#6B6B80")
BG_CARD = HexColor("#F7FAF5")
BORDER = HexColor("#D5ECD0")


def _make_styles():
    """Custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    styles = {}
    styles["title"] = ParagraphStyle(
        "ReportTitle", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=22, textColor=GREEN_DARK,
        spaceAfter=4, alignment=TA_LEFT,
    )
    styles["subtitle"] = ParagraphStyle(
        "ReportSubtitle", parent=base["Normal"],
        fontName="Helvetica", fontSize=11, textColor=TEXT_MUTED,
        spaceAfter=12,
    )
    styles["section"] = ParagraphStyle(
        "SectionHead", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=14, textColor=GREEN_DARK,
        spaceBefore=16, spaceAfter=8,
    )
    styles["body"] = ParagraphStyle(
        "Body", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, textColor=TEXT_MID,
        spaceAfter=6, leading=14,
    )
    styles["bold"] = ParagraphStyle(
        "BoldBody", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=10, textColor=TEXT_DARK,
        spaceAfter=4,
    )
    styles["small"] = ParagraphStyle(
        "Small", parent=base["Normal"],
        fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED,
        spaceAfter=2,
    )
    styles["center"] = ParagraphStyle(
        "Center", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, textColor=TEXT_MID,
        alignment=TA_CENTER,
    )
    return styles


def _score_color(score: float) -> HexColor:
    if score >= 80:
        return GREEN
    elif score >= 60:
        return GREEN_MID
    elif score >= 40:
        return AMBER
    else:
        return RED


def _draw_score_gauge(score: float, label: str, size: float = 80) -> Drawing:
    """Draw a circular score gauge."""
    d = Drawing(size + 20, size + 30)
    cx, cy = (size + 20) / 2, (size + 30) / 2 + 5
    r = size / 2 - 4
    color = _score_color(score)

    # Background ring
    d.add(Circle(cx, cy, r, strokeColor=HexColor("#E0E0E0"), strokeWidth=6, fillColor=None))

    # Score arc (approximated with thick circle + masking)
    d.add(Circle(cx, cy, r, strokeColor=color, strokeWidth=6, fillColor=None))

    # Center text
    d.add(String(cx, cy - 4, f"{score:.0f}%",
                 fontSize=16, fontName="Helvetica-Bold", fillColor=color, textAnchor="middle"))
    d.add(String(cx, cy + 12, label,
                 fontSize=7, fontName="Helvetica", fillColor=TEXT_MUTED, textAnchor="middle"))
    return d


def _draw_bar_chart(data: list[tuple[str, float]], title: str, width=400, height=150) -> Drawing:
    """Draw a horizontal bar chart."""
    d = Drawing(width, height)
    max_val = max(v for _, v in data) if data else 1
    bar_h = min(18, (height - 30) / len(data) - 4) if data else 18
    y_start = height - 25

    d.add(String(10, height - 10, title,
                 fontSize=9, fontName="Helvetica-Bold", fillColor=TEXT_DARK))

    for i, (label, val) in enumerate(data):
        y = y_start - i * (bar_h + 6)
        bar_w = (val / max_val) * (width - 130) if max_val > 0 else 0
        color = _score_color(val)

        # Label
        d.add(String(10, y - bar_h / 2 + 3, label,
                     fontSize=8, fontName="Helvetica", fillColor=TEXT_MID))
        # Bar
        d.add(Rect(100, y - bar_h + 2, bar_w, bar_h - 2,
                    fillColor=color, strokeColor=None, rx=3, ry=3))
        # Value
        d.add(String(105 + bar_w, y - bar_h / 2 + 3, f"{val:.1f}%",
                     fontSize=8, fontName="Helvetica-Bold", fillColor=color))
    return d


def _draw_attention_timeline(scores: list[float], width=460, height=120) -> Drawing:
    """Draw behavioral-cue score timeline as a line chart."""
    d = Drawing(width, height)
    if len(scores) < 2:
        d.add(String(width / 2, height / 2, "Not enough data",
                     fontSize=9, fillColor=TEXT_MUTED, textAnchor="middle"))
        return d

    pad_l, pad_r, pad_t, pad_b = 40, 10, 20, 25
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    # Title
    d.add(String(10, height - 8, "Behavioral Cue Score Over Session",
                 fontSize=9, fontName="Helvetica-Bold", fillColor=TEXT_DARK))

    # Axes
    d.add(Line(pad_l, pad_b, pad_l, pad_b + chart_h,
               strokeColor=HexColor("#CCCCCC"), strokeWidth=0.5))
    d.add(Line(pad_l, pad_b, pad_l + chart_w, pad_b,
               strokeColor=HexColor("#CCCCCC"), strokeWidth=0.5))

    # Y-axis labels
    for val in [0, 25, 50, 75, 100]:
        y = pad_b + (val / 100) * chart_h
        d.add(String(pad_l - 5, y - 3, str(val),
                     fontSize=6, fontName="Helvetica", fillColor=TEXT_MUTED, textAnchor="end"))
        d.add(Line(pad_l, y, pad_l + chart_w, y,
                   strokeColor=HexColor("#EEEEEE"), strokeWidth=0.3))

    # Threshold lines
    y65 = pad_b + (65 / 100) * chart_h
    y35 = pad_b + (35 / 100) * chart_h
    d.add(Line(pad_l, y65, pad_l + chart_w, y65,
               strokeColor=GREEN_LIGHT, strokeWidth=0.8, strokeDashArray=[4, 2]))
    d.add(Line(pad_l, y35, pad_l + chart_w, y35,
               strokeColor=HexColor("#FFAAAA"), strokeWidth=0.8, strokeDashArray=[4, 2]))

    # Plot line
    step = chart_w / (len(scores) - 1)
    points = []
    for i, s in enumerate(scores):
        x = pad_l + i * step
        y = pad_b + (min(max(s, 0), 100) / 100) * chart_h
        points.append((x, y))

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        d.add(Line(x1, y1, x2, y2, strokeColor=GREEN, strokeWidth=1.5))

    # Data points
    for x, y in points:
        d.add(Circle(x, y, 2, fillColor=GREEN, strokeColor=white, strokeWidth=0.5))

    # X-axis label
    d.add(String(pad_l + chart_w / 2, 3, "Snapshots over time",
                 fontSize=6, fillColor=TEXT_MUTED, textAnchor="middle"))

    return d


def _draw_pie_chart(segments: list[tuple[str, float, HexColor]], title: str,
                    width=200, height=160) -> Drawing:
    """Draw a simple pie chart."""
    d = Drawing(width, height)
    d.add(String(width / 2, height - 8, title,
                 fontSize=9, fontName="Helvetica-Bold", fillColor=TEXT_DARK, textAnchor="middle"))

    pc = Pie()
    pc.x = width / 2 - 40
    pc.y = 15
    pc.width = 80
    pc.height = 80
    pc.data = [s[1] for s in segments]
    pc.labels = [f"{s[0]} ({s[1]:.0f}%)" for s in segments]
    for i, seg in enumerate(segments):
        pc.slices[i].fillColor = seg[2]
        pc.slices[i].strokeColor = white
        pc.slices[i].strokeWidth = 1
    pc.slices.fontName = "Helvetica"
    pc.slices.fontSize = 7
    pc.slices.labelRadius = 1.35
    d.add(pc)
    return d


def generate_report_card(data: dict) -> bytes:
    """
    Generate a PDF report card from session data.

    Expected data shape:
    {
        "student": { "name", "email", "id", "level", "xp" },
        "course": { "title", "id" },
        "video": { "title", "id", "duration" },
        "assessment": {
            "sessionId", "score", "totalPoints", "earnedPoints",
            "percentage", "xpEarned", "timeSpent",
            "correctAnswers", "totalQuestions", "difficulty",
            "message", "nextDifficulty", "suggestedTopics",
            "adaptiveResponse": {
                "performanceTrend", "recommendedAction",
                "nextAssessmentDifficulty", "strengthAreas", "weakAreas"
            }
        },
        "behavioral_cue": {
            "avgScore", "scoreHistory": [...],
            "totalSnapshots", "attentivePercent", "inattentivePercent", "unfocusedPercent",
            "avgEyeContact", "avgBlinkRate", "headPoseDistribution": {...}
        },
        "transcription": { "totalSegments", "avgConfidence" },
        "generatedAt": "ISO timestamp"
    }
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title="NeuroLearn Report Card",
        author="NeuroLearn Platform",
    )

    styles = _make_styles()
    story = []

    student = data.get("student", {})
    course = data.get("course", {})
    video = data.get("video", {})
    assess = data.get("assessment", {})
    attn = data.get("behavioral_cue", {})
    trans = data.get("transcription", {})
    adaptive = assess.get("adaptiveResponse", {})
    generated_at = data.get("generatedAt", time.strftime("%Y-%m-%d %H:%M"))

    pct = assess.get("percentage", 0)
    attn_avg = attn.get("avgScore", 0)

    # ════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("NeuroLearn Report Card", styles["title"]))
    story.append(Paragraph(
        f"Generated: {generated_at} | Session: {assess.get('sessionId', 'N/A')[:12]}",
        styles["subtitle"],
    ))

    # Student info table
    info_data = [
        ["Student", student.get("name", "N/A"), "Course", course.get("title", "N/A")],
        ["Email", student.get("email", "N/A"), "Video", video.get("title", "N/A")],
        ["Level", str(student.get("level", 0)), "Difficulty", assess.get("difficulty", "N/A").title()],
    ]
    info_table = Table(info_data, colWidths=[60, 160, 60, 160])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), TEXT_MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), TEXT_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("TEXTCOLOR", (3, 0), (3, -1), TEXT_DARK),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # ════════════════════════════════════════════════════════
    # SCORE OVERVIEW — Big Numbers
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("Performance Overview", styles["section"]))

    score_data = [
        [
            _draw_score_gauge(pct, "Assessment"),
            _draw_score_gauge(attn_avg, "Behavioral Cue"),
            _draw_score_gauge(
                (pct * 0.6 + attn_avg * 0.4),
                "Overall"
            ),
        ],
    ]
    score_table = Table(score_data, colWidths=[155, 155, 155])
    score_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 6))

    # Score details
    details = [
        ["Metric", "Value"],
        ["Assessment Score", f"{pct:.1f}%"],
        ["Correct Answers", f"{assess.get('correctAnswers', 0)} / {assess.get('totalQuestions', 0)}"],
        ["Points Earned", f"{assess.get('earnedPoints', 0)} / {assess.get('totalPoints', 0)}"],
        ["XP Earned", f"+{assess.get('xpEarned', 0)} XP"],
        ["Time Spent", f"{assess.get('timeSpent', 0)}s"],
        ["Avg Behavioral Cue", f"{attn_avg:.1f}%"],
        ["Total Snapshots", str(attn.get("totalSnapshots", 0))],
        ["Transcript Confidence", f"{trans.get('avgConfidence', 0):.1%}"],
    ]
    det_table = Table(details, colWidths=[220, 220])
    det_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 0), (-1, 0), GREEN_DARK),
        ("TEXTCOLOR", (0, 1), (0, -1), TEXT_MID),
        ("TEXTCOLOR", (1, 1), (1, -1), TEXT_DARK),
        ("BACKGROUND", (0, 1), (-1, -1), BG_CARD),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_CARD, white]),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 12))

    # ════════════════════════════════════════════════════════
    # ATTENTION ANALYSIS
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("Behavioral Cue Analysis", styles["section"]))

    # Behavioral Cue timeline chart
    score_history = attn.get("scoreHistory", [])
    if score_history:
        timeline_drawing = _draw_attention_timeline(score_history)
        story.append(timeline_drawing)
        story.append(Spacer(1, 8))

    # Behavioral Cue state distribution pie + metrics bar
    att_pct = attn.get("attentivePercent", 70)
    inatt_pct = attn.get("inattentivePercent", 20)
    unfoc_pct = attn.get("unfocusedPercent", 10)

    attn_charts = [
        [
            # FIX (B-6/J-1): "Attentive"/"Inattentive"/"Unfocused" were
            # direct learner-facing psychological-state judgment labels in
            # a report the student downloads. Relabeled to the same
            # neutral operational bands used in the live UI (AttentionPanel).
            _draw_pie_chart([
                ("High signal band", att_pct, GREEN),
                ("Medium signal band", inatt_pct, AMBER),
                ("Low signal band", unfoc_pct, RED),
            ], "Behavioral Cue Signal Bands"),
            _draw_bar_chart([
                ("Eye Contact", attn.get("avgEyeContact", 0.8) * 100),
                ("Blink Normality", min(100, max(0, 100 - abs(attn.get("avgBlinkRate", 16) - 17) * 6))),
                ("Session Avg", attn_avg),
            ], "Behavioral Cue Sub-Metrics", width=260),
        ],
    ]
    attn_table = Table(attn_charts, colWidths=[210, 260])
    attn_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(attn_table)
    story.append(Spacer(1, 12))

    # ════════════════════════════════════════════════════════
    # ADAPTIVE ANALYSIS
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("Adaptive Engine Analysis", styles["section"]))

    trend = adaptive.get("performanceTrend", "stable")
    trend_icon = {"improving": "IMPROVING", "stable": "STABLE", "declining": "DECLINING"}.get(trend, trend)
    trend_color = {"improving": "green", "stable": "#D4940E", "declining": "red"}.get(trend, "black")

    story.append(Paragraph(
        f"<b>Performance Trend:</b> <font color='{trend_color}'>{trend_icon}</font>",
        styles["body"],
    ))
    story.append(Paragraph(
        f"<b>Current Difficulty:</b> {assess.get('difficulty', 'N/A').title()}"
        f" &rarr; <b>Next:</b> {adaptive.get('nextAssessmentDifficulty', 'N/A').title()}",
        styles["body"],
    ))
    story.append(Paragraph(
        f"<b>Recommendation:</b> {adaptive.get('recommendedAction', 'Keep learning!')}",
        styles["body"],
    ))
    story.append(Spacer(1, 6))

    # Strengths & Weaknesses
    strengths = adaptive.get("strengthAreas", [])
    weaknesses = adaptive.get("weakAreas", [])

    sw_data = [["Strength Areas", "Areas to Improve"]]
    max_len = max(len(strengths), len(weaknesses), 1)
    for i in range(max_len):
        s = strengths[i] if i < len(strengths) else ""
        w = weaknesses[i] if i < len(weaknesses) else ""
        sw_data.append([s, w])

    sw_table = Table(sw_data, colWidths=[220, 220])
    sw_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, 0), GREEN_DARK),
        ("TEXTCOLOR", (1, 0), (1, 0), AMBER),
        ("TEXTCOLOR", (0, 1), (0, -1), GREEN),
        ("TEXTCOLOR", (1, 1), (1, -1), RED),
        ("BACKGROUND", (0, 0), (-1, 0), BG_CARD),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sw_table)
    story.append(Spacer(1, 10))

    # Suggested topics
    topics = assess.get("suggestedTopics", [])
    if topics:
        story.append(Paragraph("Suggested Review Topics", styles["bold"]))
        for t in topics:
            story.append(Paragraph(f"- {t}", styles["body"]))
        story.append(Spacer(1, 8))

    # ════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report was generated by NeuroLearn Adaptive Learning Platform. "
        "Scores are computed using MediaPipe (behavioral_cue), Whisper (transcription), "
        "FLAN-T5 (questions), and a 5-factor adaptive difficulty engine.",
        styles["small"],
    ))
    story.append(Paragraph(
        f"Report ID: {assess.get('sessionId', 'N/A')} | {generated_at}",
        styles["small"],
    ))

    # Build PDF
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    logger.info(f"Report card generated: {len(pdf_bytes)} bytes")
    return pdf_bytes
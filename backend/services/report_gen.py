"""
PDF report generation using ReportLab.
Produces a professional, multi-page analysis report for benefits consultants.
Cover page is drawn entirely with canvas; content pages have a running header/footer.
"""

from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    KeepTogether,
)

from .models import PBMAnalysisReport, ContactInfo

# ── Page dimensions ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = letter   # 612 x 792 points
CONTENT_W = 6.8 * inch    # 8.5 - 0.85 - 0.85

# ── Brand palette ────────────────────────────────────────────────────────────
PRIMARY       = colors.HexColor("#1e3a5f")
PRIMARY_DARK  = colors.HexColor("#152d4a")
PRIMARY_LIGHT = colors.HexColor("#2d5a8e")
ACCENT        = colors.HexColor("#c9960f")
ACCENT_LIGHT  = colors.HexColor("#e8b020")
LIGHT_BG      = colors.HexColor("#f5f7fa")
WHITE         = colors.white
DARK_TEXT     = colors.HexColor("#0f172a")
MUTED         = colors.HexColor("#64748b")

GRADE_COLORS = {
    "A": colors.HexColor("#16a34a"),
    "B": colors.HexColor("#1d4ed8"),
    "C": colors.HexColor("#d97706"),
    "D": colors.HexColor("#ea580c"),
    "F": colors.HexColor("#dc2626"),
}
GRADE_BG = {
    "A": colors.HexColor("#f0fdf4"),
    "B": colors.HexColor("#eff6ff"),
    "C": colors.HexColor("#fffbeb"),
    "D": colors.HexColor("#fff7ed"),
    "F": colors.HexColor("#fef2f2"),
}
GRADE_LABELS = {
    "A": "Excellent — Top of Market",
    "B": "Good — Above Average Terms",
    "C": "Average — Market Rate",
    "D": "Below Market — Needs Improvement",
    "F": "Unfavorable — Significant Concerns",
}
RISK_COLORS = {
    "high":   colors.HexColor("#dc2626"),
    "medium": colors.HexColor("#d97706"),
    "low":    colors.HexColor("#16a34a"),
}
# (background, text) tuples for assessment column
ASSESSMENT_STYLE = {
    "favorable":    (colors.HexColor("#f0fdf4"), colors.HexColor("#16a34a")),
    "at market":    (colors.HexColor("#eff6ff"), colors.HexColor("#1d4ed8")),
    "below market": (colors.HexColor("#fffbeb"), colors.HexColor("#d97706")),
    "unfavorable":  (colors.HexColor("#fef2f2"), colors.HexColor("#dc2626")),
}


# ── Canvas helpers ───────────────────────────────────────────────────────────

def _draw_cover(c, analysis: PBMAnalysisReport, contact_info: ContactInfo,
                analysis_date: str):
    """Render the entire cover page using low-level canvas commands."""
    grade       = analysis.overall_grade
    grade_color = GRADE_COLORS.get(grade, PRIMARY)
    grade_bg    = GRADE_BG.get(grade, LIGHT_BG)
    grade_label = GRADE_LABELS.get(grade, "")

    # ── Full dark background ──────────────────────────────────────────────
    c.setFillColor(PRIMARY_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Lighter center band for depth
    c.setFillColor(PRIMARY)
    c.rect(0, PAGE_H * 0.22, PAGE_W, PAGE_H * 0.58, fill=1, stroke=0)

    # ── Gold top stripe ───────────────────────────────────────────────────
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 26, PAGE_W, 26, fill=1, stroke=0)
    c.setFillColor(ACCENT_LIGHT)
    c.rect(0, PAGE_H - 30, PAGE_W, 4, fill=1, stroke=0)

    # ── Gold bottom stripe ────────────────────────────────────────────────
    c.setFillColor(ACCENT)
    c.rect(0, 0, PAGE_W, 18, fill=1, stroke=0)

    # ── Dark title bar ────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#0d2240"))
    c.rect(0, PAGE_H - 82, PAGE_W, 52, fill=1, stroke=0)

    # Title text
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 57, "PBM CONTRACT ANALYSIS REPORT")

    # Subtitle
    c.setFillColor(colors.HexColor("#a8c4e0"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 97,
                        "Confidential  ·  AI-Powered  ·  Benefits Consulting Tool")

    # Gold separator line
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.line(1.1 * inch, PAGE_H - 114, PAGE_W - 1.1 * inch, PAGE_H - 114)

    # ── Client info box ───────────────────────────────────────────────────
    bx = 1.0 * inch
    bw = PAGE_W - 2.0 * inch
    by = PAGE_H - 300
    bh = 170

    # Drop shadow
    c.setFillColor(colors.HexColor("#07172a"))
    c.rect(bx + 4, by - 4, bw, bh, fill=1, stroke=0)

    # White box
    c.setFillColor(WHITE)
    c.rect(bx, by, bw, bh, fill=1, stroke=0)

    # Gold left accent stripe
    c.setFillColor(ACCENT)
    c.rect(bx, by, 5, bh, fill=1, stroke=0)

    # Row 1: prepared for / date
    lx = bx + 22
    rx = bx + bw / 2 + 12
    row_y = [
        (by + bh - 28, by + bh - 48),   # row 1 label/value
        (by + bh - 82, by + bh - 102),  # row 2
        (by + bh - 136, by + bh - 156), # row 3
    ]

    def info_label(x, y, text):
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x, y, text)

    def info_value_bold(x, y, text, size=13):
        c.setFillColor(DARK_TEXT)
        c.setFont("Helvetica-Bold", size)
        c.drawString(x, y, text)

    def info_value(x, y, text, size=12):
        c.setFillColor(DARK_TEXT)
        c.setFont("Helvetica", size)
        c.drawString(x, y, text)

    def separator(y_pos):
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.setLineWidth(0.4)
        c.line(lx, y_pos, bx + bw - 18, y_pos)

    info_label(lx, row_y[0][0], "PREPARED FOR")
    info_label(rx, row_y[0][0], "ANALYSIS DATE")
    info_value_bold(lx, row_y[0][1], f"{contact_info.first_name} {contact_info.last_name}")
    info_value(rx, row_y[0][1], analysis_date)

    separator(row_y[1][0] + 14)
    info_label(lx, row_y[1][0], "COMPANY")
    info_label(rx, row_y[1][0], "EMAIL")
    info_value(lx, row_y[1][1], contact_info.company[:42])
    info_value(rx, row_y[1][1], contact_info.email[:38])

    separator(row_y[2][0] + 14)
    info_label(lx, row_y[2][0], "PHONE")
    info_value(lx, row_y[2][1], contact_info.phone)

    # ── Grade box ─────────────────────────────────────────────────────────
    gb_y = PAGE_H - 490
    gb_h = 168

    # Drop shadow
    c.setFillColor(colors.HexColor("#07172a"))
    c.rect(bx + 4, gb_y - 4, bw, gb_h, fill=1, stroke=0)

    # Grade background
    c.setFillColor(grade_bg)
    c.rect(bx, gb_y, bw, gb_h, fill=1, stroke=0)

    # Colored left stripe
    c.setFillColor(grade_color)
    c.rect(bx, gb_y, 6, gb_h, fill=1, stroke=0)

    # Colored top border
    c.setFillColor(grade_color)
    c.rect(bx, gb_y + gb_h - 4, bw, 4, fill=1, stroke=0)

    # "OVERALL CONTRACT GRADE" label
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(bx + 22, gb_y + gb_h - 24, "OVERALL CONTRACT GRADE")

    # Big grade letter
    c.setFillColor(grade_color)
    c.setFont("Helvetica-Bold", 90)
    c.drawString(bx + 22, gb_y + gb_h - 108, grade)

    # Grade label and description (right of the letter)
    c.setFillColor(grade_color)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(bx + 118, gb_y + gb_h - 65, grade_label)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    c.drawString(bx + 118, gb_y + gb_h - 83,
                 "Based on pricing competitiveness, risk exposure,")
    c.drawString(bx + 118, gb_y + gb_h - 97,
                 "and client protection vs. current market standards.")

    # ── Disclaimer ────────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#6b96be"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, 32,
                        "This report is AI-generated and intended for qualified "
                        "benefits consultants only.")


def _draw_header_footer(c, doc):
    """Draw the running header and footer on content pages (2+)."""
    # Header bar
    c.setFillColor(PRIMARY)
    c.rect(0, PAGE_H - 34, PAGE_W, 34, fill=1, stroke=0)

    # Gold accent line under header
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 36, PAGE_W, 2, fill=1, stroke=0)

    # Header text
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(0.85 * inch, PAGE_H - 21, "PBM CONTRACT ANALYSIS REPORT")

    c.setFont("Helvetica", 7.5)
    c.drawRightString(PAGE_W - 0.85 * inch, PAGE_H - 21, f"Page {doc.page}")

    # Footer separator
    c.setStrokeColor(colors.HexColor("#d1d9e0"))
    c.setLineWidth(0.4)
    c.line(0.85 * inch, 0.44 * inch, PAGE_W - 0.85 * inch, 0.44 * inch)

    # Footer text
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawCentredString(PAGE_W / 2, 0.27 * inch,
                        "CONFIDENTIAL — For Benefits Consultant Use Only")


# ── Paragraph styles ─────────────────────────────────────────────────────────

def make_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "section_num": ParagraphStyle(
            "section_num", parent=base["Normal"],
            fontSize=8.5, fontName="Helvetica-Bold", textColor=ACCENT,
            spaceBefore=16, spaceAfter=1, letterSpacing=1.2,
        ),
        "section_heading": ParagraphStyle(
            "section_heading", parent=base["Normal"],
            fontSize=19, fontName="Helvetica-Bold", textColor=PRIMARY,
            spaceBefore=0, spaceAfter=4, leading=23,
        ),
        "subsection_heading": ParagraphStyle(
            "subsection_heading", parent=base["Normal"],
            fontSize=11.5, fontName="Helvetica-Bold", textColor=DARK_TEXT,
            spaceBefore=6, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=10.5, fontName="Helvetica", textColor=DARK_TEXT,
            leading=16, alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "body_left": ParagraphStyle(
            "body_left", parent=base["Normal"],
            fontSize=10, fontName="Helvetica", textColor=DARK_TEXT,
            leading=14, spaceAfter=3,
        ),
        "table_header": ParagraphStyle(
            "table_header", parent=base["Normal"],
            fontSize=8.5, fontName="Helvetica-Bold", textColor=WHITE, leading=12,
        ),
        "table_cell": ParagraphStyle(
            "table_cell", parent=base["Normal"],
            fontSize=9.5, fontName="Helvetica", textColor=DARK_TEXT, leading=13,
        ),
        "table_cell_bold": ParagraphStyle(
            "table_cell_bold", parent=base["Normal"],
            fontSize=9.5, fontName="Helvetica-Bold", textColor=DARK_TEXT, leading=13,
        ),
        "table_cell_muted": ParagraphStyle(
            "table_cell_muted", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Oblique", textColor=MUTED, leading=13,
        ),
        "concern_text": ParagraphStyle(
            "concern_text", parent=base["Normal"],
            fontSize=10, fontName="Helvetica", textColor=colors.HexColor("#7f1d1d"),
            leading=14,
        ),
        "market_summary": ParagraphStyle(
            "market_summary", parent=base["Normal"],
            fontSize=10, fontName="Helvetica", textColor=DARK_TEXT,
            leading=15, leftIndent=0, spaceBefore=0, spaceAfter=0,
        ),
        "footer_text": ParagraphStyle(
            "footer_text", parent=base["Normal"],
            fontSize=8, fontName="Helvetica", textColor=MUTED, alignment=TA_CENTER,
        ),
    }


# ── Story helpers ────────────────────────────────────────────────────────────

def section_header(num: str, title: str, styles: dict) -> list:
    """Return [num_para, title_para, gold_hr] for a numbered section heading."""
    return [
        Paragraph(num, styles["section_num"]),
        Paragraph(title, styles["section_heading"]),
        HRFlowable(width="100%", thickness=3, color=ACCENT,
                   spaceAfter=14, spaceBefore=5, lineCap="round"),
    ]


def get_assessment_style(assessment: str):
    """Return (bg_color, fg_color) for an assessment string."""
    lower = assessment.lower()
    for key, style in ASSESSMENT_STYLE.items():
        if key in lower:
            return style
    return LIGHT_BG, DARK_TEXT


# ── Main report builder ──────────────────────────────────────────────────────

def generate_pdf_report(analysis: PBMAnalysisReport, contact_info: ContactInfo,
                        output_path: str):
    analysis_date = datetime.now().strftime("%B %d, %Y")
    # Shift section numbers by 1 when Library Comparison card is present (matches web UI)
    _o = 1 if analysis.library_comparison else 0
    def sn(n: int) -> str:
        return f"{n + _o:02d}"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.75 * inch,    # leaves ~0.25" gap below the 34pt header bar
        bottomMargin=0.60 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
    )

    styles = make_styles()

    # Page callbacks (closures capture analysis/contact_info/date)
    def _on_first_page(canvas, doc):
        canvas.saveState()
        _draw_cover(canvas, analysis, contact_info, analysis_date)
        canvas.restoreState()

    def _on_later_pages(canvas, doc):
        canvas.saveState()
        _draw_header_footer(canvas, doc)
        canvas.restoreState()

    story = []

    # ── COVER PAGE ──────────────────────────────────────────────────────────
    # Page 1 is drawn entirely by _on_first_page via canvas.
    # A leading Spacer ensures page 1 is properly triggered before the break.
    story.append(Spacer(1, 0.01))
    story.append(PageBreak())

    # ── 01 LIBRARY COMPARISON (only when library has ≥3 contracts) ──────────
    if analysis.library_comparison:
        lc = analysis.library_comparison
        story += section_header("01", "Library Comparison", styles)

        # Summary line: count + percentile badge
        is_top = lc.grade_percentile.startswith("top")
        pct_color = colors.HexColor("#16a34a") if is_top else colors.HexColor("#dc2626")
        pct_bg    = colors.HexColor("#f0fdf4") if is_top else colors.HexColor("#fef2f2")
        pct_border= colors.HexColor("#86efac") if is_top else colors.HexColor("#fca5a5")

        summary_row = Table(
            [[
                Paragraph(
                    f"Benchmarked against <b>{lc.contracts_in_library}</b> contracts in our database",
                    styles["body_left"],
                ),
                Paragraph(
                    lc.grade_percentile,
                    ParagraphStyle(
                        "lc_pct", parent=styles["body_left"],
                        textColor=pct_color, fontName="Helvetica-Bold",
                        fontSize=11, alignment=TA_CENTER,
                    ),
                ),
            ]],
            colWidths=[CONTENT_W - 1.4 * inch, 1.4 * inch],
        )
        summary_row.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), LIGHT_BG),
            ("BACKGROUND",    (1, 0), (1, 0), pct_bg),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
            ("LINEAFTER",     (0, 0), (0, 0), 0.5, colors.HexColor("#d1d9e0")),
            ("LINEBEFORE",    (0, 0), (0, -1), 4, ACCENT),
            ("BOX",           (1, 0), (1, 0), 1, pct_border),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (0, 0),  14),
            ("RIGHTPADDING",  (0, 0), (0, 0),  10),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(summary_row)
        story.append(Spacer(1, 0.14 * inch))

        # Grade distribution pills row
        GRADE_PILL_COLORS = {
            "A": (colors.HexColor("#f0fdf4"), colors.HexColor("#16a34a"), colors.HexColor("#86efac")),
            "B": (colors.HexColor("#eff6ff"), colors.HexColor("#1d4ed8"), colors.HexColor("#bfdbfe")),
            "C": (colors.HexColor("#fffbeb"), colors.HexColor("#d97706"), colors.HexColor("#fcd34d")),
            "D": (colors.HexColor("#fff7ed"), colors.HexColor("#ea580c"), colors.HexColor("#fdba74")),
            "F": (colors.HexColor("#fef2f2"), colors.HexColor("#dc2626"), colors.HexColor("#fca5a5")),
        }
        dist_cells = []
        for grade in ["A", "B", "C", "D", "F"]:
            count = lc.grade_distribution.get(grade, 0)
            if count == 0:
                continue
            bg, fg, border = GRADE_PILL_COLORS.get(grade, (LIGHT_BG, DARK_TEXT, colors.HexColor("#d1d9e0")))
            cell = Table(
                [[Paragraph(f"{grade}: {count}", ParagraphStyle(
                    f"gp{grade}", parent=styles["body_left"],
                    textColor=fg, fontName="Helvetica-Bold",
                    fontSize=10, alignment=TA_CENTER, spaceAfter=0,
                ))]],
                colWidths=[0.7 * inch],
            )
            cell.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), bg),
                ("BOX",           (0, 0), (-1, -1), 1, border),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ]))
            dist_cells.append(cell)

        if dist_cells:
            # Pad row to CONTENT_W with spacers
            pill_row = Table(
                [dist_cells],
                colWidths=[0.7 * inch] * len(dist_cells),
            )
            pill_row.setStyle(TableStyle([
                ("LEFTPADDING",  (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(pill_row)
            story.append(Spacer(1, 0.16 * inch))

        # Pricing comparison table
        pricing_comp_data = [
            [
                Paragraph("Pricing Category",  styles["table_header"]),
                Paragraph("This Contract",     styles["table_header"]),
                Paragraph("Library Average",   styles["table_header"]),
            ],
            [
                Paragraph("Brand Retail AWP Discount",   styles["table_cell"]),
                Paragraph(lc.this_brand_retail,          styles["table_cell_bold"]),
                Paragraph(lc.avg_brand_retail,           styles["table_cell_muted"]),
            ],
            [
                Paragraph("Generic Retail AWP Discount", styles["table_cell"]),
                Paragraph(lc.this_generic_retail,        styles["table_cell_bold"]),
                Paragraph(lc.avg_generic_retail,         styles["table_cell_muted"]),
            ],
            [
                Paragraph("Specialty AWP Discount",      styles["table_cell"]),
                Paragraph(lc.this_specialty,             styles["table_cell_bold"]),
                Paragraph(lc.avg_specialty,              styles["table_cell_muted"]),
            ],
        ]
        pricing_comp_table = Table(
            pricing_comp_data,
            colWidths=[2.8 * inch, 2.0 * inch, 2.0 * inch],
        )
        pricing_comp_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  PRIMARY),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d9e0")),
            ("LINEBEFORE",    (0, 0), (0, -1),  4, ACCENT),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(pricing_comp_table)
        story.append(Spacer(1, 0.25 * inch))

    # ── 01 EXECUTIVE SUMMARY ────────────────────────────────────────────────
    story += section_header(sn(1), "Executive Summary", styles)
    for para in analysis.executive_summary.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["body"]))
    story.append(Spacer(1, 0.18 * inch))

    # ── 02 KEY CONCERNS ─────────────────────────────────────────────────────
    story += section_header(sn(2), "Key Concerns", styles)

    for i, concern in enumerate(analysis.key_concerns, 1):
        row = Table(
            [[
                Paragraph(str(i), ParagraphStyle(
                    f"cn{i}", parent=styles["body_left"],
                    textColor=WHITE, fontName="Helvetica-Bold",
                    fontSize=10, alignment=TA_CENTER, spaceAfter=0,
                )),
                Paragraph(concern, styles["concern_text"]),
            ]],
            colWidths=[0.38 * inch, CONTENT_W - 0.38 * inch],
        )
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#dc2626")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (0, 0), 0),
            ("RIGHTPADDING",  (0, 0), (0, 0), 0),
            ("LEFTPADDING",   (1, 0), (1, 0), 13),
            ("RIGHTPADDING",  (1, 0), (1, 0), 12),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (0, 0), (0, 0), "CENTER"),
        ]))
        story.append(row)
        story.append(Spacer(1, 5))

    story.append(PageBreak())

    # ── 03 CONTRACT OVERVIEW ────────────────────────────────────────────────
    story += section_header(sn(3), "Contract Overview", styles)

    co = analysis.contract_overview
    overview_data = [
        [Paragraph("Field", styles["table_header"]),
         Paragraph("Details", styles["table_header"])],
    ] + [
        [Paragraph(label, styles["table_cell"]),
         Paragraph(value or "—", styles["table_cell"])]
        for label, value in [
            ("Contracting Parties",  co.parties),
            ("Contract Term",        co.contract_term),
            ("Effective Date",       co.effective_date),
            ("Expiration Date",      co.expiration_date),
            ("Renewal Terms",        co.renewal_terms),
            ("Termination",          co.termination_provisions),
        ]
    ]
    overview_table = Table(overview_data, colWidths=[2.0 * inch, 4.8 * inch])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  PRIMARY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
        ("LINEAFTER",     (0, 0), (0, -1),  0.5, colors.HexColor("#d1d9e0")),
        ("LINEBEFORE",    (0, 0), (0, -1),  4,   ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── 04 PRICING TERMS ────────────────────────────────────────────────────
    story += section_header(sn(4), "Pricing Terms", styles)

    pt = analysis.pricing_terms
    pricing_rows = [
        ("Brand Retail AWP Discount",       pt.brand_retail_awp_discount,   "15–22% off AWP"),
        ("Brand Mail Order AWP Discount",   pt.brand_mail_awp_discount,     "20–28% off AWP"),
        ("Generic Retail AWP Discount",     pt.generic_retail_awp_discount, "78–88% off AWP"),
        ("Generic Mail Order AWP Discount", pt.generic_mail_awp_discount,   "80–90% off AWP"),
        ("Specialty AWP Discount",          pt.specialty_awp_discount,      "10–20% off AWP"),
        ("Retail Dispensing Fee",           pt.retail_dispensing_fee,       "$0.00–$2.50/claim"),
        ("Mail Order Dispensing Fee",       pt.mail_dispensing_fee,         "$0.00–$1.50/Rx"),
        ("Administrative Fees",            pt.admin_fees,                  "0–3% of claims"),
        ("Rebate Guarantee",               pt.rebate_guarantee,            "$100–$400 PEPM"),
        ("MAC Pricing Terms",              pt.mac_pricing_terms,           "Transparent, appeal rights"),
    ]
    pricing_data = [
        [Paragraph("Pricing Component", styles["table_header"]),
         Paragraph("Contract Terms",    styles["table_header"]),
         Paragraph("Market Benchmark",  styles["table_header"])],
    ] + [
        [Paragraph(label,     styles["table_cell"]),
         Paragraph(contract,  styles["table_cell_bold"]),
         Paragraph(benchmark, styles["table_cell_muted"])]
        for label, contract, benchmark in pricing_rows
    ]
    pricing_table = Table(pricing_data, colWidths=[2.4 * inch, 2.5 * inch, 1.9 * inch])
    pricing_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  PRIMARY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d9e0")),
        ("LINEBEFORE",    (0, 0), (0, -1),  4,   ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(pricing_table)
    story.append(PageBreak())

    # ── 05 MARKET COMPARISON ────────────────────────────────────────────────
    story += section_header(sn(5), "Market Comparison", styles)

    mc = analysis.market_comparison
    comp_rows = [
        ("Brand Retail",  mc.brand_retail_benchmark,  mc.brand_retail_contract,  mc.brand_retail_assessment),
        ("Generic Retail",mc.generic_retail_benchmark, mc.generic_retail_contract, mc.generic_retail_assessment),
        ("Specialty",     mc.specialty_benchmark,      mc.specialty_contract,      mc.specialty_assessment),
    ]
    comp_data = [
        [Paragraph("Category",         styles["table_header"]),
         Paragraph("Market Benchmark", styles["table_header"]),
         Paragraph("This Contract",    styles["table_header"]),
         Paragraph("Assessment",       styles["table_header"])],
    ] + [
        [Paragraph(cat,      styles["table_cell"]),
         Paragraph(bench,    styles["table_cell"]),
         Paragraph(contract, styles["table_cell_bold"]),
         Paragraph(assess,   ParagraphStyle(
             f"as{i}", parent=styles["table_cell"],
             textColor=get_assessment_style(assess)[1],
             fontName="Helvetica-Bold",
         ))]
        for i, (cat, bench, contract, assess) in enumerate(comp_rows)
    ]
    comp_style = [
        ("BACKGROUND",    (0, 0), (-1, 0),  PRIMARY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d9e0")),
        ("LINEBEFORE",    (0, 0), (0, -1),  4,   ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (3, 1), (3, -1),  "CENTER"),
    ]
    # Colored background for assessment column
    for i, (_, _, _, assess) in enumerate(comp_rows, 1):
        bg, _ = get_assessment_style(assess)
        comp_style.append(("BACKGROUND", (3, i), (3, i), bg))

    comp_table = Table(comp_data, colWidths=[1.4 * inch, 2.0 * inch, 2.0 * inch, 1.4 * inch])
    comp_table.setStyle(TableStyle(comp_style))
    story.append(comp_table)
    story.append(Spacer(1, 0.12 * inch))

    # Market position callout box
    callout = Table(
        [[Paragraph(mc.overall_market_position, styles["market_summary"])]],
        colWidths=[CONTENT_W],
    )
    callout.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BG),
        ("LINEBEFORE",    (0, 0), (-1, -1), 4, PRIMARY_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    story.append(callout)
    story.append(Spacer(1, 0.25 * inch))

    # ── 06 COST RISK AREAS ──────────────────────────────────────────────────
    story += section_header(sn(6), "Cost Risk Areas", styles)

    for risk in analysis.cost_risk_areas:
        risk_color = RISK_COLORS.get(risk.risk_level.lower(), MUTED)
        risk_label = risk.risk_level.upper()

        # Each risk is a 2-row, 2-column table:
        # Row 0: [area name]  [HIGH/MED/LOW badge]
        # Row 1: [description] [financial impact]
        risk_block = Table(
            [
                [
                    Paragraph(risk.area, ParagraphStyle(
                        f"rh{risk.area[:4]}", parent=styles["subsection_heading"],
                        spaceBefore=0, spaceAfter=0, textColor=DARK_TEXT,
                    )),
                    Paragraph(risk_label, ParagraphStyle(
                        f"rb{risk.area[:4]}", parent=styles["body_left"],
                        textColor=WHITE, fontName="Helvetica-Bold",
                        fontSize=8.5, spaceAfter=0, alignment=TA_CENTER,
                    )),
                ],
                [
                    Paragraph(risk.description, styles["table_cell"]),
                    Paragraph(
                        f"Est. Impact:\n{risk.financial_impact}",
                        ParagraphStyle(
                            f"ri{risk.area[:4]}", parent=styles["table_cell"],
                            textColor=risk_color, fontName="Helvetica-Bold",
                        ),
                    ),
                ],
            ],
            colWidths=[CONTENT_W - 0.9 * inch, 0.9 * inch],
        )
        risk_block.setStyle(TableStyle([
            # Row 0 backgrounds
            ("BACKGROUND", (0, 0), (0, 0), LIGHT_BG),
            ("BACKGROUND", (1, 0), (1, 0), risk_color),
            # Row 1 backgrounds
            ("BACKGROUND", (0, 1), (0, 1), WHITE),
            ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#f8fafc")),
            # Thick left accent stripe (overrides box on left edge)
            ("LINEBEFORE", (0, 0), (0, -1), 5, risk_color),
            # Borders
            ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
            ("LINEBELOW",  (0, 0), (-1, 0),  0.5, colors.HexColor("#d1d9e0")),
            # Padding
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (0, -1), 14),
            ("RIGHTPADDING",  (0, 0), (0, -1), 10),
            ("LEFTPADDING",   (1, 0), (1, 0), 4),
            ("RIGHTPADDING",  (1, 0), (1, 0), 4),
            ("LEFTPADDING",   (1, 1), (1, 1), 10),
            ("RIGHTPADDING",  (1, 1), (1, 1), 10),
            ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",   (1, 0), (1, 0),   "CENTER"),
            ("VALIGN",  (0, 1), (-1, 1),  "TOP"),
        ]))
        story.append(KeepTogether([risk_block, Spacer(1, 9)]))

    story.append(PageBreak())

    # ── 07 NEGOTIATION GUIDANCE ─────────────────────────────────────────────
    story += section_header(sn(7), "Negotiation Guidance", styles)
    story.append(Paragraph(
        "The following recommendations are specific to the terms found in this contract. "
        "Present these points during renegotiation to improve client value.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    for i, guidance in enumerate(analysis.negotiation_guidance, 1):
        g_row = Table(
            [[
                Paragraph(str(i), ParagraphStyle(
                    f"gn{i}", parent=styles["body_left"],
                    textColor=WHITE, fontName="Helvetica-Bold",
                    fontSize=11, alignment=TA_CENTER, spaceAfter=0,
                )),
                Paragraph(guidance, styles["body_left"]),
            ]],
            colWidths=[0.38 * inch, CONTENT_W - 0.38 * inch],
        )
        g_row.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), ACCENT),
            ("BACKGROUND",    (1, 0), (1, 0), LIGHT_BG),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d9e0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (0, 0),   0),
            ("RIGHTPADDING",  (0, 0), (0, 0),   0),
            ("LEFTPADDING",   (1, 0), (1, 0),   14),
            ("RIGHTPADDING",  (1, 0), (1, 0),   12),
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("ALIGN",   (0, 0), (0, 0),   "CENTER"),
        ]))
        story.append(g_row)
        story.append(Spacer(1, 5))

    # ── Final disclaimer ─────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#d1d9e0")))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"PBM Contract Analysis Report  ·  Generated {analysis_date}  ·  Confidential\n"
        "This report is produced by AI-assisted analysis for use by qualified benefits professionals. "
        "It does not constitute legal or financial advice.",
        styles["footer_text"],
    ))

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)

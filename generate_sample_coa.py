"""Generate a sample pharmaceutical Certificate of Analysis (COA) PDF for pipeline testing."""

import json
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_PDF = "sample_coa.pdf"

PRODUCT_INFO = {
    "product_name": "Acetaminophen Tablets USP, 500mg",
    "batch_id": "B-2026-001",
    "lot_number": "LOT-2026-001A",
    "cmo_name": "CMO Alpha Pharmaceuticals",
    "cmo_id": "cmo-alpha",
    "manufacturing_date": "2026-01-10",
    "expiry_date": "2028-01-10",
    "quantity": "500,000 tablets",
    "analyst": "Dr. Jane Smith",
    "qa_approver": "Dr. Robert Chen",
}

TEST_RESULTS = [
    {"test_name": "Appearance", "method": "Visual", "specification": "White, round, biconvex tablets", "result": "Conforms", "unit": "", "pass": True},
    {"test_name": "Identification (HPLC)", "method": "USP <621>", "specification": "Matches reference standard", "result": "Conforms", "unit": "", "pass": True},
    {"test_name": "Assay / Potency", "method": "USP <621>", "specification": "95.0 – 105.0", "result": "99.8", "unit": "%", "pass": True},
    {"test_name": "Dissolution (Q=80%)", "method": "USP <711>", "specification": "NLT 80% in 30 min", "result": "92", "unit": "%", "pass": True},
    {"test_name": "Uniformity of Dosage", "method": "USP <905>", "specification": "AV ≤ 15.0", "result": "3.2", "unit": "AV", "pass": True},
    {"test_name": "Water Content", "method": "USP <921>", "specification": "NMT 2.0", "result": "0.8", "unit": "%", "pass": True},
    {"test_name": "Microbial Limits (TAMC)", "method": "USP <61>", "specification": "NMT 1000", "result": "< 10", "unit": "CFU/g", "pass": True},
    {"test_name": "Microbial Limits (TYMC)", "method": "USP <62>", "specification": "NMT 100", "result": "< 10", "unit": "CFU/g", "pass": True},
    {"test_name": "Sterility", "method": "USP <71>", "specification": "No growth", "result": "No growth", "unit": "", "pass": True},
    {"test_name": "Endotoxins", "method": "USP <85>", "specification": "NMT 5.0", "result": "< 0.5", "unit": "EU/mg", "pass": True},
    {"test_name": "Heavy Metals (Pb)", "method": "USP <232>", "specification": "NMT 0.5", "result": "< 0.1", "unit": "ppm", "pass": True},
    {"test_name": "Residual Solvents", "method": "USP <467>", "specification": "Within ICH Q3C limits", "result": "Conforms", "unit": "", "pass": True},
]


def build_pdf():
    doc = SimpleDocTemplate(OUTPUT_PDF, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, spaceAfter=4)
    subtitle = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    elements = []

    # Header
    elements.append(Paragraph("CERTIFICATE OF ANALYSIS", title_style))
    elements.append(Paragraph(f"{PRODUCT_INFO['cmo_name']}  |  GMP Compliant  |  Document generated {date.today().isoformat()}", subtitle))
    elements.append(Spacer(1, 0.2 * inch))

    # Product info table
    info_data = [
        ["Product Name", PRODUCT_INFO["product_name"], "Batch / Lot", f"{PRODUCT_INFO['batch_id']} / {PRODUCT_INFO['lot_number']}"],
        ["Mfg Date", PRODUCT_INFO["manufacturing_date"], "Expiry Date", PRODUCT_INFO["expiry_date"]],
        ["Quantity", PRODUCT_INFO["quantity"], "CMO ID", PRODUCT_INFO["cmo_id"]],
    ]
    info_table = Table(info_data, colWidths=[1.2 * inch, 2.3 * inch, 1.2 * inch, 2.3 * inch])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8eaf6")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8eaf6")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.25 * inch))

    # Test results table
    header = ["Test", "Method", "Specification", "Result", "Unit", "Status"]
    rows = [header]
    for t in TEST_RESULTS:
        status = "PASS ✓" if t["pass"] else "FAIL ✗"
        rows.append([t["test_name"], t["method"], t["specification"], t["result"], t["unit"], status])

    col_widths = [1.6 * inch, 0.9 * inch, 1.6 * inch, 0.9 * inch, 0.6 * inch, 0.7 * inch]
    results_table = Table(rows, colWidths=col_widths, repeatRows=1)
    results_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    # Color PASS green
    for i in range(1, len(rows)):
        clr = colors.HexColor("#2e7d32") if TEST_RESULTS[i - 1]["pass"] else colors.red
        results_table.setStyle(TableStyle([("TEXTCOLOR", (5, i), (5, i), clr)]))

    elements.append(Paragraph("<b>Analytical Test Results</b>", styles["Heading2"]))
    elements.append(results_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Disposition
    elements.append(Paragraph("<b>Disposition: APPROVED — All tests within specification</b>", styles["Heading3"]))
    elements.append(Spacer(1, 0.15 * inch))

    sig_data = [
        ["Analyst", PRODUCT_INFO["analyst"], "Date", date.today().isoformat()],
        ["QA Approver", PRODUCT_INFO["qa_approver"], "Date", date.today().isoformat()],
    ]
    sig_table = Table(sig_data, colWidths=[1.2 * inch, 2.3 * inch, 0.8 * inch, 2 * inch])
    sig_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8eaf6")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8eaf6")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(
        "<i>This document is electronically generated. Unauthorized reproduction is prohibited.</i>",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey),
    ))

    doc.build(elements)
    print(f"COA PDF generated: {OUTPUT_PDF}")

    # Also update the test JSON to match all results
    json_results = [
        {
            "batch_id": PRODUCT_INFO["batch_id"],
            "test_name": t["test_name"],
            "result": t["result"],
            "unit": t["unit"],
            "specification": t["specification"],
            "method": t["method"],
            "pass": t["pass"],
        }
        for t in TEST_RESULTS
    ]
    with open("test-coa-data.json", "w") as f:
        json.dump(json_results, f, indent=2)
    print("Updated test-coa-data.json with full test results")


if __name__ == "__main__":
    build_pdf()

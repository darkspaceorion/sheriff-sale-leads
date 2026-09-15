"""Makes two fake county sheriff sale lists for the demo. Names and cases are invented.
  sample_sale_list.pdf         week 1, six listings
  sample_sale_list_week2.pdf   week 2: Smith flips to Adjourned, one new listing added
Run once: python make_sample_pdf.py"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROWS = [
    ["Sheriff #", "Sale Date", "Plaintiff", "Defendant", "Property Address", "Lot", "Block", "Status", "Attorney"],
    ["F-24-001234", "10/07/2026", "WELLS FARGO BANK NA", "SMITH, JOHN AND JANE SMITH", "12 MAIN ST, FREEHOLD, NJ 07728", "4", "112", "Scheduled", "PHELAN HALLINAN"],
    ["F-24-001301", "10/07/2026", "US BANK TRUST", "GARCIA, MARIA", "88 OCEAN AVE APT 2, LONG BRANCH, NJ 07740", "17.01", "203", "Adjourned", "RAS CITRON LLC"],
    ["F-24-001355", "10/14/2026", "NEWREZ LLC", "ESTATE OF ROBERT LEE", "301 ROUTE 9 NORTH, HOWELL, NJ 07731", "2", "45", "Cancelled", "MCCALLA RAYMER"],
    ["F-24-001402", "10/14/2026", "PENNYMAC LOAN SERVICES", "PATEL, RAJ ET AL", "5 BIRCH CT, MARLBORO, NJ 07746", "9", "310", "Scheduled", "KML LAW GROUP"],
    ["F-24-001410", "10/21/2026", "TOWNSHIP OF NEPTUNE", "BLUE HARBOR HOLDINGS LLC", "1400 CORLIES AVE, NEPTUNE, NJ 07753", "1", "88", "Scheduled", "MUNICIPAL COUNSEL"],
    ["F-24-001466", "10/21/2026", "ROCKET MORTGAGE", "O'BRIEN, KEVIN M", "22 LAKESIDE DR, MANALAPAN, NJ 07726", "31", "6", "Bankruptcy", "PHELAN HALLINAN"],
]

WEEK2 = [r[:] for r in ROWS]
WEEK2[1][7] = "Adjourned"  # Smith moves from Scheduled to Adjourned
WEEK2.append(["F-24-001501", "10/28/2026", "CITIZENS BANK NA", "NGUYEN, LINH T", "9 HARBOR VIEW LN, ATLANTIC HIGHLANDS, NJ 07716", "12", "78", "Scheduled", "RAS CITRON LLC"])


def build(name: str, rows: list, week: str) -> None:
    out = Path(__file__).parent / name
    doc = SimpleDocTemplate(str(out), pagesize=landscape(letter), leftMargin=30, rightMargin=30)
    styles = getSampleStyleSheet()
    story = [Paragraph("EXAMPLE COUNTY SHERIFF'S OFFICE - FORECLOSURE SALE LIST", styles["Title"]),
             Paragraph(f"{week}. Sales held Wednesdays at 2:00 PM. List updated weekly. Sample data for demo only.", styles["Normal"]),
             Spacer(1, 12)]
    cell = styles["Normal"].clone("cell", fontSize=7, leading=8)
    wrapped = [[Paragraph(str(c), cell) for c in r] for r in rows]
    t = Table(wrapped, repeatRows=1, colWidths=[70, 60, 110, 120, 150, 35, 40, 60, 90])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    doc.build(story)
    print(f"wrote {out}")


build("sample_sale_list.pdf", ROWS, "Week of October 5, 2026")
build("sample_sale_list_week2.pdf", WEEK2, "Week of October 12, 2026")

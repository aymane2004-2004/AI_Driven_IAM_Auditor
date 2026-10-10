"""Step 4 - Professional PDF report (ReportLab)."""
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from config import CLIENT_NAME

NAVY, ORANGE = colors.HexColor("#1F2A44"), colors.HexColor("#E0301E")
SEV_COLOR = {"Critique": "#B00020", "Élevé": "#E0301E", "Moyen": "#E8A200", "Faible": "#4C9A2A"}

def build_pdf(path, summary, stats, rows):
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=NAVY)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=ORANGE)
    body = ParagraphStyle("b", parent=ss["BodyText"], leading=14)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    s = [Spacer(1, 6*cm), Paragraph("Rapport d'audit des accès IAM", ParagraphStyle("t", parent=h1, fontSize=28, leading=34)),
         Paragraph("Entitlement &amp; Anomalies Review", h2), Spacer(1, 1*cm),
         Paragraph(f"Client : {CLIENT_NAME}<br/>Date : {date.today():%d/%m/%Y}<br/>Classification : Confidentiel", body),
         PageBreak(), Paragraph("1. Executive Summary", h1), Paragraph(escape(summary or "n/a"), body), Spacer(1, .5*cm)]
    t = Table([["Comptes analysés", "Constats", "Critiques", "Élevés", "Moyens"],
               [stats["total_users"], stats["total_findings"], stats["by_severity"].get("Critique", 0),
                stats["by_severity"].get("Élevé", 0), stats["by_severity"].get("Moyen", 0)]], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), .5, colors.grey),
                           ("FONTSIZE", (0, 1), (-1, 1), 14)]))
    s += [t, PageBreak(), Paragraph("2. Constats détaillés", h1)]
    for r in rows:
        r = {k: escape(str(v)) for k, v in r.items()}
        c = SEV_COLOR.get(r["criticite"], "#333333")
        s += [Paragraph(f"{r['user_id']} - {r['nom']} <font color='{c}'>[{r['criticite']}]</font>", h2),
              Paragraph(f"<b>Poste :</b> {r['poste']} | <b>Règle :</b> {r['rule']}", small),
              Paragraph(f"<b>Risque :</b> {r['risque']}", body),
              Paragraph(f"<b>Recommandation :</b> {r['recommandation']}", body),
              Paragraph(f"<b>Référentiels :</b> {r['frameworks']}", small), Spacer(1, .4*cm)]
    doc.build(s)

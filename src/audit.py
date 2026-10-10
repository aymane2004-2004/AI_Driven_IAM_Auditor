"""Orchestrator: inventory -> rules -> LLM -> JSON + Markdown + PDF.
Usage: python src/audit.py [--no-llm] [--deep]"""
import argparse, json
from collections import Counter
from config import DATA_DIR, OUT_DIR
from rules import run_rules, SEV_ORDER
from report_pdf import build_pdf

def pseudo(u):  # no name / no identity sent to the LLM
    return {k: u.get(k) for k in ("id", "poste", "departement", "roles_azure", "roles_entra", "mfa_active",
                                   "type_compte", "user_type", "enabled", "statut_rh", "derniere_connexion")}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="rules only, no AI")
    ap.add_argument("--deep", action="store_true", help="LLM context review of ALL users")
    ap.add_argument("--input", default="iam_inventory.json", help="file in data/ (real: iam_inventory_real.json)")
    args = ap.parse_args()

    users = json.loads((DATA_DIR / args.input).read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in users}
    findings = run_rules(users)
    print(f"[rules] {len(findings)} constats sur {len(users)} comptes")

    grouped = {}
    for f in findings: grouped.setdefault(f["user_id"], []).append(f)

    analyses, summary, extra = {}, "", []
    if not args.no_llm:
        import llm_client as llm
        flagged = [{"profile": pseudo(by_id[uid]), "findings": [{"rule": f["rule"], "detail": f["detail"]} for f in fs]}
                   for uid, fs in grouped.items()]
        for i in range(0, len(flagged), 15):  # chunking
            for a in llm.analyze_findings(flagged[i:i + 15]): analyses[a["user_id"]] = a
        if args.deep:
            others = [pseudo(u) for u in users if u["id"] not in grouped]
            for i in range(0, len(others), 30): extra += llm.context_review(others[i:i + 30])
            print(f"[deep] {len(extra)} profil(s) suspect(s) supplémentaire(s)")

    rows = []
    for uid, fs in grouped.items():
        a, u = analyses.get(uid, {}), by_id[uid]
        for f in fs[:1] if a else fs:  # one LLM write-up per user, else one row per rule
            rows.append({"user_id": uid, "nom": u["nom"], "poste": u["poste"], "rule": ", ".join(x["rule"] for x in fs) if a else f["rule"],
                         "criticite": a.get("criticite", f["severity"]), "risque": a.get("risque", f["detail"]),
                         "recommandation": a.get("recommandation", "Révoquer / réduire les accès et appliquer le MFA."),
                         "frameworks": " ; ".join(sorted({x["frameworks"] for x in fs}))})
    for e in extra:
        u = by_id.get(e["user_id"]);  
        if u: rows.append({"user_id": u["id"], "nom": u["nom"], "poste": u["poste"], "rule": "LLM_CONTEXT_REVIEW",
                           "criticite": e.get("criticite", "Moyen"), "risque": e["raison"],
                           "recommandation": "Valider avec le manager et réduire les rôles si non justifiés.",
                           "frameworks": "ISO 27001:2022 A.5.15 | NIST CSF 2.0 PR.AA-05"})
    rows.sort(key=lambda r: SEV_ORDER.get(r["criticite"], 9))

    stats = {"total_users": len(users), "total_findings": len(rows),
             "by_severity": dict(Counter(r["criticite"] for r in rows)),
             "by_rule": dict(Counter(f["rule"] for f in findings))}
    if not args.no_llm: summary = llm.executive_summary(stats)
    else: summary = (f"{stats['total_findings']} constats sur {stats['total_users']} comptes "
                     f"(répartition : {stats['by_severity']}). Mode sans IA : analyse par règles uniquement.")

    (OUT_DIR / "audit_result.json").write_text(json.dumps({"stats": stats, "summary": summary, "findings": rows},
                                                          indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# Rapport d'audit IAM\n\n## Executive Summary\n{summary}\n"]
    md += [f"### {r['user_id']} - {r['nom']} [{r['criticite']}]\n- **Risque** : {r['risque']}\n- **Remédiation** : {r['recommandation']}\n- **Référentiels** : {r['frameworks']}\n" for r in rows]
    (OUT_DIR / "audit_report.md").write_text("\n".join(md), encoding="utf-8")
    build_pdf(OUT_DIR / "audit_report.pdf", summary, stats, rows)
    print("[ok] outputs/audit_result.json, audit_report.md, audit_report.pdf")

if __name__ == "__main__":
    main()

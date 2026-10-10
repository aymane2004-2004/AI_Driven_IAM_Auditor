"""Deterministic rule engine (cheap, explainable, no AI). Works on fake AND real (Entra ID) inventories.
Unknown data (None) never triggers a finding: we don't accuse on missing information."""
from datetime import date
from config import DORMANT_DAYS, PRIV_DEPTS

PRIVILEGED = {"Global Administrator", "Privileged Role Administrator", "Privileged Authentication Administrator",
              "Security Administrator", "Security Admin", "User Administrator", "Application Administrator",
              "Cloud Application Administrator", "Conditional Access Administrator", "Exchange Administrator",
              "SharePoint Administrator", "Owner", "User Access Administrator"}
UNKNOWN = {None, "", "Non renseigné"}
SEV_ORDER = {"Critique": 0, "Élevé": 1, "Moyen": 2, "Faible": 3}

FRAMEWORKS = {
    "EXCESSIVE_PRIVILEGE": "ISO 27001:2022 A.5.15, A.8.2 | NIST CSF 2.0 PR.AA-05",
    "PRIVILEGED_NO_MFA": "ISO 27001:2022 A.8.5 | NIST CSF 2.0 PR.AA-03",
    "DORMANT_ACCOUNT": "ISO 27001:2022 A.5.18 | NIST CSF 2.0 PR.AA-01",
    "LEAVER_STILL_ACTIVE": "ISO 27001:2022 A.5.18, A.6.5 | NIST CSF 2.0 PR.AA-01",
    "DISABLED_WITH_ROLES": "ISO 27001:2022 A.5.18 | NIST CSF 2.0 PR.AA-01",
    "GUEST_PRIVILEGED": "ISO 27001:2022 A.5.15, A.5.19 | NIST CSF 2.0 PR.AA-05",
    "SERVICE_PRINCIPAL_PRIVILEGED": "ISO 27001:2022 A.5.15, A.8.2 | NIST CSF 2.0 PR.AA-05",
}

def _finding(u, rule, sev, detail):
    return {"user_id": u["id"], "rule": rule, "severity": sev, "detail": detail, "frameworks": FRAMEWORKS[rule]}

def days_since(iso):
    return (date.today() - date.fromisoformat(iso[:10])).days if iso else None

def run_rules(users):
    out = []
    for u in users:
        roles = set(u.get("roles_azure", [])) | set(u.get("roles_entra", []))
        priv = PRIVILEGED & roles
        kind = u.get("type_compte", "humain")
        poste = (u.get("poste") or "").lower()
        junior = any(k in poste for k in ("stagiaire", "intern", "junior"))
        dept = u.get("departement")
        if priv and kind == "humain" and (junior or (dept not in UNKNOWN and dept not in PRIV_DEPTS)):
            out.append(_finding(u, "EXCESSIVE_PRIVILEGE", "Critique",
                                f"Rôle(s) privilégié(s) {sorted(priv)} incompatibles avec le poste « {u['poste']} » ({dept})."))
        if priv and u.get("mfa_active") is False:
            out.append(_finding(u, "PRIVILEGED_NO_MFA", "Critique", f"Compte privilégié {sorted(priv)} sans MFA."))
        if priv and kind == "service" and u.get("mfa_active") is None:
            out.append(_finding(u, "SERVICE_PRINCIPAL_PRIVILEGED", "Élevé",
                                f"Service principal avec rôle(s) privilégié(s) {sorted(priv)}: vérifier nécessité et rotation des secrets."))
        if priv and u.get("user_type") == "Guest":
            out.append(_finding(u, "GUEST_PRIVILEGED", "Élevé", f"Compte invité (externe) avec rôle(s) privilégié(s) {sorted(priv)}."))
        if u.get("statut_rh") == "parti" and roles:
            out.append(_finding(u, "LEAVER_STILL_ACTIVE", "Critique", "Collaborateur parti avec accès toujours actifs."))
        if u.get("enabled") is False and roles:
            out.append(_finding(u, "DISABLED_WITH_ROLES", "Moyen", "Compte désactivé mais rôles toujours assignés."))
        age = days_since(u.get("derniere_connexion"))
        if age is not None and age > DORMANT_DAYS and roles and u.get("statut_rh") == "actif":
            out.append(_finding(u, "DORMANT_ACCOUNT", "Moyen", f"Aucune connexion depuis {age} jours, rôles toujours assignés."))
    return sorted(out, key=lambda f: SEV_ORDER[f["severity"]])

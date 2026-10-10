"""Collect REAL IAM data: Microsoft Entra ID (Graph API) + Azure RBAC (ARM API).
Auth: app registration (AZURE_* in .env, for automation) OR `az login` (easiest, manual).
Output: data/iam_inventory_real.json (same schema as the fake inventory)."""
import json, shutil, subprocess, sys
import requests
from config import *

GRAPH, ARM = "https://graph.microsoft.com/v1.0", "https://management.azure.com"
NA = "Non renseigné"

def get_token(resource):
    if AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
        r = requests.post(f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token", timeout=30,
                          data={"grant_type": "client_credentials", "client_id": AZURE_CLIENT_ID,
                                "client_secret": AZURE_CLIENT_SECRET, "scope": f"{resource}/.default"})
        r.raise_for_status()
        return r.json()["access_token"]
    az = shutil.which("az")
    if not az:
        sys.exit("Aucune authentification: renseigne AZURE_* dans .env ou installe Azure CLI puis `az login`.")
    out = subprocess.run([az, "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit("Fais d'abord `az login` :\n" + out.stderr)
    return out.stdout.strip()

def get_all(url, token, params=None, soft=False):
    """Follow pagination. soft=True -> return None on 400/401/403 (missing licence/permission)."""
    items, headers = [], {"Authorization": f"Bearer {token}"}
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        if soft and r.status_code in (400, 401, 403):
            print(f"  ! indisponible ({r.status_code}): {url.split('?')[0].split('v1.0')[-1]}")
            return None
        r.raise_for_status()
        j = r.json()
        items += j.get("value", [])
        url, params = j.get("@odata.nextLink") or j.get("nextLink"), None
    return items

def build_inventory(users, mfa, entra_roles, azure_roles, sps, leavers):
    """Pure function (unit-tested). entra_roles/azure_roles = [(principal_id, role_name)]."""
    inv = {}
    for u in users:
        si = u.get("signInActivity") or {}
        last = si.get("lastSuccessfulSignInDateTime") or si.get("lastSignInDateTime")
        upn = u.get("userPrincipalName") or ""
        inv[u["id"]] = {"id": u["id"], "nom": f"{u.get('displayName')} ({upn})",
                        "poste": u.get("jobTitle") or NA, "departement": u.get("department") or NA,
                        "roles_azure": [], "roles_entra": [], "mfa_active": mfa.get(u["id"]),
                        "type_compte": "humain", "user_type": u.get("userType"), "enabled": u.get("accountEnabled"),
                        "statut_rh": "parti" if upn.lower() in leavers else "actif",
                        "derniere_connexion": last[:10] if last else None}
    for key, pairs in (("roles_entra", entra_roles), ("roles_azure", azure_roles)):
        for pid, role in pairs:
            if pid not in inv:  # service principal or group holding a role
                sp = sps.get(pid)
                inv[pid] = {"id": pid, "nom": (sp or {}).get("displayName") or f"Principal {pid[:8]}",
                            "poste": "Service principal" if sp else "Groupe / autre", "departement": NA,
                            "roles_azure": [], "roles_entra": [], "mfa_active": None,
                            "type_compte": "service" if sp else "groupe", "user_type": None, "enabled": True,
                            "statut_rh": "actif", "derniere_connexion": None}
            if role and role not in inv[pid][key]:
                inv[pid][key].append(role)
    return list(inv.values())

def main():
    g = get_token("https://graph.microsoft.com")
    print("[1/5] Utilisateurs Entra ID")
    sel = "id,displayName,userPrincipalName,jobTitle,department,accountEnabled,userType,createdDateTime"
    users = get_all(f"{GRAPH}/users", g, {"$select": sel + ",signInActivity", "$top": 999}, soft=True)
    if users is None:
        print("  -> dernières connexions indisponibles (licence Entra ID P1/P2 requise): règle 'dormant' désactivée")
        users = get_all(f"{GRAPH}/users", g, {"$select": sel, "$top": 999})
    print("[2/5] Enregistrement MFA")
    reg = get_all(f"{GRAPH}/reports/authenticationMethods/userRegistrationDetails", g, {"$top": 999}, soft=True)
    mfa = {r["id"]: r.get("isMfaRegistered") for r in reg} if reg is not None else {}
    if reg is None: print("  -> MFA inconnu: règle 'privilégié sans MFA' désactivée")
    print("[3/5] Rôles d'annuaire Entra ID")
    defs = {d["id"]: d["displayName"] for d in get_all(f"{GRAPH}/roleManagement/directory/roleDefinitions", g)}
    ras = get_all(f"{GRAPH}/roleManagement/directory/roleAssignments", g)
    entra_roles = [(r["principalId"], defs.get(r["roleDefinitionId"])) for r in ras]
    sps = {s["id"]: s for s in (get_all(f"{GRAPH}/servicePrincipals", g, {"$select": "id,displayName", "$top": 999}, soft=True) or [])}
    print("[4/5] Rôles Azure RBAC (abonnements)")
    azure_roles = []
    try:
        a = get_token("https://management.azure.com")
    except SystemExit:
        a = None
        print("  -> pas d'accès ARM / abonnement: Azure RBAC ignoré")
    for sub in (get_all(f"{ARM}/subscriptions?api-version=2022-12-01", a, soft=True) if a else None) or []:
        base = f"{ARM}/subscriptions/{sub['subscriptionId']}/providers/Microsoft.Authorization"
        rd = {d["id"]: d["properties"]["roleName"] for d in get_all(f"{base}/roleDefinitions?api-version=2022-04-01", a)}
        for ra in get_all(f"{base}/roleAssignments?api-version=2022-04-01", a):
            p = ra["properties"]
            azure_roles.append((p["principalId"], rd.get(p["roleDefinitionId"])))
    leavers = set()
    f = DATA_DIR / "hr_leavers.txt"  # optional: one UPN per line = people who left the company (HR list)
    if f.exists():
        leavers = {l.strip().lower() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    print("[5/5] Construction de l'inventaire")
    inv = build_inventory(users, mfa, entra_roles, azure_roles, sps, leavers)
    (DATA_DIR / "iam_inventory_real.json").write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(inv)} identités -> data/iam_inventory_real.json")

if __name__ == "__main__":
    main()

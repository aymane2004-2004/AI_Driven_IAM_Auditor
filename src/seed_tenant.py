"""Seed a TEST Entra ID tenant with realistic users + IAM anomalies, then clean up.
Everything created is named "[TEST] ..." / "iamtest-..." so `cleanup` removes exactly that.

  python src/seed_tenant.py create [--azure-rbac] [--dry-run]
  python src/collect_entra.py
  python src/seed_tenant.py overlay     # adds sign-in dates / MFA state (a brand-new account has none)
  python src/audit.py --input iam_inventory_real.json
  python src/seed_tenant.py cleanup

Use ONLY on a tenant you own that holds no real data."""
import argparse, json, secrets, string, time, uuid
from datetime import date, timedelta
import requests
from config import *
from collect_entra import get_token, get_all, GRAPH, ARM

STATE = DATA_DIR / "seed_state.json"
AZ_ROLE_IDS = {"Owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
               "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
               "Reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7"}

def S(key, name, title="", dept="", roles=(), type="member", enabled=True, leaver=False,
      days=None, mfa=None, azure=(), expected=(), email=""):
    return {"key": key, "name": f"[TEST] {name}", "upn": f"iamtest-{key}", "title": title, "dept": dept,
            "roles": list(roles), "type": type, "enabled": enabled, "leaver": leaver, "email": email,
            "azure": list(azure), "overlay": {"days": days, "mfa": mfa} if days is not None else None,
            "expected": set(expected)}

SCENARIOS = [
    # --- normal users (should produce NO finding) ---
    S("sarah", "Sarah Bensouda", "Consultante RH", "RH", days=2, mfa=True),
    S("yassine", "Yassine El Amrani", "Développeur Python Junior", "IT", days=1, mfa=True),
    S("john", "John lander", "Manager SecOps", "Sécurité", ["Security Administrator"], days=1, mfa=True),  # legit admin
    S("nadia", "Nadia Tazi", "Analyste Finance", "Finance", days=4, mfa=True),
    # --- anomalies ---
    S("intern", "Amine Chraibi", "Stagiaire Marketing", "Marketing", ["Global Administrator"], azure=["Owner"],
      days=3, mfa=True, expected={"EXCESSIVE_PRIVILEGE"}),                                  # privilege creep
    S("leaver", "Fatima Zahra", "Analyste Finance", "Finance", ["Reports Reader"], leaver=True,
      days=12, mfa=True, expected={"LEAVER_STILL_ACTIVE"}),                                 # left, still has access
    S("disabled", "Karim Alaoui", "Prestataire IT", "IT", ["Helpdesk Administrator"], enabled=False,
      expected={"DISABLED_WITH_ROLES"}),                                                    # disabled but roles remain
    S("guest", "Guest Auditor", type="guest", email="iamtest.guest@example.org", roles=["User Administrator"],
      expected={"GUEST_PRIVILEGED"}),                                                       # external + privileged
    S("svc", "svc-cicd-pipeline", type="service", roles=["Application Administrator"],
      expected={"SERVICE_PRINCIPAL_PRIVILEGED"}),                                           # privileged app identity
    S("dormant", "Mehdi Cherkaoui", "Analyste Finance", "Finance", ["Reports Reader"],
      days=135, mfa=True, expected={"DORMANT_ACCOUNT"}),                                    # unused 135 days
    S("nomfa", "Zineb Lahlou", "Consultante RH", "RH", ["User Administrator"],
      days=5, mfa=False, expected={"EXCESSIVE_PRIVILEGE", "PRIVILEGED_NO_MFA"}),           # toxic combo
]

def call(method, url, token, **kw):
    r = requests.request(method, url, headers={"Authorization": f"Bearer {token}"}, timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}

def retry(fn, tries=6, wait=5):  # new objects take a few seconds to replicate in Entra
    for i in range(tries):
        try: return fn()
        except RuntimeError as e:
            m = str(e)
            if i == tries - 1 or not ("404" in m or "does not exist" in m or "PrincipalNotFound" in m): raise
            time.sleep(wait)

def apply_overlay(inventory, state):
    """Pure function: inject sign-in date / MFA state on the test identities."""
    by_id = {i["id"]: i for i in inventory}
    for s in SCENARIOS:
        item, ov = by_id.get(state["users"].get(s["key"])), s["overlay"]
        if item and ov:
            item["derniere_connexion"] = (date.today() - timedelta(days=ov["days"])).isoformat()
            item["mfa_active"] = ov["mfa"]
    return inventory

def create(a):
    if a.dry_run:
        for s in SCENARIOS:
            print(f"{s['upn']:<20} {s['type']:<8} roles={s['roles'] or '-'!s:<30} -> attendu: {sorted(s['expected']) or 'rien'}")
        return
    g = get_token("https://graph.microsoft.com")
    domain = next(d["id"] for d in get_all(f"{GRAPH}/domains", g) if d.get("isDefault"))
    defs = {d["displayName"]: d["id"] for d in get_all(f"{GRAPH}/roleManagement/directory/roleDefinitions", g)}
    state, leavers = {"users": {}, "azure": []}, []
    sub = None
    if a.azure_rbac:
        arm = get_token("https://management.azure.com")
        subs = get_all(f"{ARM}/subscriptions?api-version=2022-12-01", arm)
        sub = subs[0]["subscriptionId"] if subs else None
        if not sub: print("! aucun abonnement dans ce tenant: Azure RBAC ignoré")
    for s in SCENARIOS:
        if s["type"] == "service":
            app = call("POST", f"{GRAPH}/applications", g, json={"displayName": s["name"]})
            pid = call("POST", f"{GRAPH}/servicePrincipals", g, json={"appId": app["appId"]})["id"]
        elif s["type"] == "guest":
            pid = call("POST", f"{GRAPH}/invitations", g, json={
                "invitedUserEmailAddress": s["email"], "invitedUserDisplayName": s["name"],
                "inviteRedirectUrl": "https://myapps.microsoft.com", "sendInvitationMessage": False})["invitedUser"]["id"]
        else:
            pwd = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%") for _ in range(24)) + "aA1!"
            upn = f"{s['upn']}@{domain}"
            body = {"accountEnabled": s["enabled"], "displayName": s["name"], "mailNickname": s["upn"],
                    "userPrincipalName": upn, "jobTitle": s["title"], "department": s["dept"],
                    "passwordProfile": {"forceChangePasswordNextSignIn": True, "password": pwd}}
            pid = call("POST", f"{GRAPH}/users", g, json=body)["id"]
            if s["leaver"]: leavers.append(upn)
        state["users"][s["key"]] = pid
        for role in s["roles"]:
            retry(lambda: call("POST", f"{GRAPH}/roleManagement/directory/roleAssignments", g, json={
                "principalId": pid, "roleDefinitionId": defs[role], "directoryScopeId": "/"}))
        if sub:
            for role in s["azure"]:
                scope, aid = f"/subscriptions/{sub}", str(uuid.uuid4())
                url = f"{ARM}{scope}/providers/Microsoft.Authorization/roleAssignments/{aid}?api-version=2022-04-01"
                retry(lambda: call("PUT", url, arm, json={"properties": {
                    "roleDefinitionId": f"{scope}/providers/Microsoft.Authorization/roleDefinitions/{AZ_ROLE_IDS[role]}",
                    "principalId": pid, "principalType": "ServicePrincipal" if s["type"] == "service" else "User"}}))
                state["azure"].append(url.split("?")[0])
        print(f"  créé: {s['name']}  roles={s['roles']}")
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    (DATA_DIR / "hr_leavers.txt").write_text("\n".join(leavers) + "\n", encoding="utf-8")
    print("OK. Étape suivante: python src/collect_entra.py")

def overlay():
    inv_path = DATA_DIR / "iam_inventory_real.json"
    if not (STATE.exists() and inv_path.exists()):
        raise SystemExit("Lance d'abord `create` puis `python src/collect_entra.py`.")
    inv = apply_overlay(json.loads(inv_path.read_text(encoding="utf-8")), json.loads(STATE.read_text(encoding="utf-8")))
    inv_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    print("OK: dates de connexion / MFA injectés sur les comptes [TEST].")

def cleanup():
    g = get_token("https://graph.microsoft.com")
    def delete(url, tok):
        r = requests.delete(url, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
        if r.status_code >= 400 and r.status_code != 404: print(f"  ! {url.split('?')[0]} -> {r.status_code}")
    if STATE.exists():
        arm = get_token("https://management.azure.com") if json.loads(STATE.read_text())["azure"] else None
        for rid in json.loads(STATE.read_text())["azure"]: delete(f"{ARM}{rid}?api-version=2022-04-01", arm)
    flt = {"$filter": "startswith(displayName,'[TEST]')", "$select": "id,displayName"}
    for kind in ("users", "servicePrincipals", "applications"):
        for o in get_all(f"{GRAPH}/{kind}", g, flt):
            delete(f"{GRAPH}/{kind}/{o['id']}", g); print(f"  supprimé: {kind}: {o['displayName']}")
    for f in (STATE, DATA_DIR / "hr_leavers.txt"): f.unlink(missing_ok=True)
    print("OK: tenant nettoyé (les utilisateurs supprimés restent 30 jours dans la corbeille Entra).")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--azure-rbac", action="store_true"); c.add_argument("--dry-run", action="store_true")
    sub.add_parser("overlay"); sub.add_parser("cleanup")
    a = ap.parse_args()
    {"create": lambda: create(a), "overlay": overlay, "cleanup": cleanup}[a.cmd]()

if __name__ == "__main__":
    main()

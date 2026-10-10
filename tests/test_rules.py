import sys; sys.path.insert(0, "src")
from datetime import date, timedelta
from rules import run_rules

def u(**kw):
    base = {"id": "U1", "poste": "Dev", "departement": "IT", "roles_azure": ["Reader"], "mfa_active": True,
            "type_compte": "humain", "statut_rh": "actif", "derniere_connexion": date.today().isoformat()}
    return {**base, **kw}

def rules_for(user): return {f["rule"] for f in run_rules([user])}

def test_clean_user(): assert rules_for(u()) == set()
def test_intern_global_admin(): assert "EXCESSIVE_PRIVILEGE" in rules_for(u(poste="Stagiaire", departement="Marketing", roles_azure=["Global Administrator"]))
def test_no_mfa(): assert "PRIVILEGED_NO_MFA" in rules_for(u(roles_azure=["Owner"], mfa_active=False))
def test_dormant(): assert "DORMANT_ACCOUNT" in rules_for(u(derniere_connexion=(date.today()-timedelta(days=120)).isoformat()))
def test_leaver(): assert "LEAVER_STILL_ACTIVE" in rules_for(u(statut_rh="parti"))

def test_disabled_with_roles(): assert "DISABLED_WITH_ROLES" in rules_for(u(enabled=False))
def test_guest_privileged(): assert "GUEST_PRIVILEGED" in rules_for(u(user_type="Guest", roles_entra=["Global Administrator"]))
def test_unknown_mfa_not_flagged(): assert "PRIVILEGED_NO_MFA" not in rules_for(u(roles_azure=["Owner"], mfa_active=None))
def test_unknown_signin_not_dormant(): assert "DORMANT_ACCOUNT" not in rules_for(u(derniere_connexion=None))

def test_build_inventory():
    from collect_entra import build_inventory
    users = [{"id": "a", "displayName": "A", "userPrincipalName": "a@x.com", "jobTitle": None, "department": None,
              "accountEnabled": True, "userType": "Member",
              "signInActivity": {"lastSuccessfulSignInDateTime": "2026-01-02T10:00:00Z"}}]
    inv = {i["id"]: i for i in build_inventory(users, {"a": True}, [("a", "Global Administrator"), ("sp1", "Owner")],
                                               [("a", "Reader")], {"sp1": {"displayName": "ci"}}, set())}
    assert inv["a"]["roles_entra"] == ["Global Administrator"] and inv["a"]["roles_azure"] == ["Reader"]
    assert inv["a"]["derniere_connexion"] == "2026-01-02" and inv["a"]["poste"] == "Non renseigné"
    assert inv["sp1"]["type_compte"] == "service" and inv["sp1"]["roles_entra"] == ["Owner"]

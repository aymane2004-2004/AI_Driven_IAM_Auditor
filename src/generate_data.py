"""Step 1 - Generate a fake IAM inventory (normal users + hidden anomalies)."""
import json, random
from datetime import date, timedelta
from config import DATA_DIR

random.seed(42)
TODAY = date.today()
FIRST = ["Yassine", "Sarah", "Omar", "Salma", "Karim", "Nadia", "Hamza", "Imane", "Reda", "Lina"]
LAST = ["El Amrani", "Bensouda", "Alaoui", "Tazi", "Berrada", "Idrissi", "Fassi", "Ouazzani"]
PROFILES = [  # (poste, departement, roles)
    ("Développeur Python Junior", "IT", ["Reader", "Contributor-Dev-RG"]),
    ("Ingénieur Cloud", "IT", ["Contributor-Prod-RG", "Reader"]),
    ("Consultante RH", "RH", ["RH-User-Access"]),
    ("Analyste Finance", "Finance", ["Billing Reader"]),
    ("Chargé Marketing", "Marketing", ["Reader"]),
    ("Manager SecOps", "Sécurité", ["Security Admin", "Log Analytics Contributor"]),
]

def d(days_ago): return (TODAY - timedelta(days=days_ago)).isoformat()

def user(i, nom, poste, dep, roles, mfa=True, last=None, statut="actif", type_="humain"):
    return {"id": f"USR{i:03d}", "nom": nom, "poste": poste, "departement": dep,
            "roles_azure": roles, "mfa_active": mfa, "type_compte": type_,
            "statut_rh": statut, "derniere_connexion": d(last if last is not None else random.randint(0, 20))}

users = []
for i in range(1, 25):
    poste, dep, roles = random.choice(PROFILES)
    users.append(user(i, f"{random.choice(FIRST)} {random.choice(LAST)}", poste, dep, roles))

# --- Hidden anomalies ---
users += [
    user(25, "Amine Chraibi", "Stagiaire Marketing", "Marketing", ["Reader", "Global Administrator"]),  # privilege creep
    user(26, "Admin-Service-CI-CD", "Compte de Service Automatisation", "IT", ["Owner"], mfa=False, type_="service"),  # no MFA
    user(27, "Fatima Zahra", "Ex-Employée (départ mai)", "Finance", ["Billing Reader", "Contributor"], last=12, statut="parti"),  # leaver
    user(28, "Mehdi Cherkaoui", "Analyste Finance", "Finance", ["Billing Reader", "Contributor"], last=135),  # dormant
    user(29, "Zineb Lahlou", "Consultante RH", "RH", ["RH-User-Access", "User Access Administrator"], mfa=False),  # toxic combo
]

with open(DATA_DIR / "iam_inventory.json", "w", encoding="utf-8") as f:
    json.dump(users, f, indent=2, ensure_ascii=False)
print(f"OK: {len(users)} comptes écrits dans data/iam_inventory.json")

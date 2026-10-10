# Step by step: build the project, simulate IAM anomalies in a real tenant, audit them

## A. Prerequisites (once)
Python 3.11+, VS Code, Git, Azure CLI (learn.microsoft.com/cli/azure/install-azure-cli), a GitHub account (Student Pack).

## B. Project setup
```bash
python -m venv .venv && .venv\Scripts\activate      # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests                                     # all green = code is fine
```

## C. Offline demo (no cloud) - see the pipeline work
```bash
python src/generate_data.py
python src/audit.py --no-llm                        # -> outputs/audit_report.pdf
```

## D. Connect the LLM (Gemini only)
aistudio.google.com/apikey -> Create API key.
```bash
copy .env.example .env     # then edit: GEMINI_API_KEY=...
python src/audit.py        # now with AI explanations + executive summary
```

## E. Create YOUR test tenant (never use a school/company tenant)
1. portal.azure.com -> Microsoft Entra ID -> Manage tenants -> Create -> Microsoft Entra ID -> name + domain (e.g. iamlab) -> Create.
2. Switch to it (Manage tenants -> Switch). You are Global Administrator of this empty tenant.
3. Terminal: `az login --tenant iamlab.onmicrosoft.com --allow-no-subscriptions`

## F. Simulate the anomalies in the tenant
```bash
python src/seed_tenant.py create --dry-run          # preview: who gets which roles, what we expect
python src/seed_tenant.py create                    # creates 11 [TEST] identities + role assignments
python src/collect_entra.py                         # reads the REAL tenant -> data/iam_inventory_real.json
python src/seed_tenant.py overlay                   # injects sign-in dates / MFA state (new accounts have none)
python src/audit.py --input iam_inventory_real.json # rules + LLM + PDF
```
Optional Azure RBAC anomaly (intern = Owner of a subscription): only if the tenant has a subscription -> add `--azure-rbac` to `create`.

## G. What you must find in the report
| Identity | Anomaly | Rule | Severity |
|---|---|---|---|
| intern | Marketing intern = Global Administrator | EXCESSIVE_PRIVILEGE | Critique |
| leaver | left the company, still has a role | LEAVER_STILL_ACTIVE | Critique |
| nomfa | HR consultant = User Administrator, no MFA | EXCESSIVE_PRIVILEGE + PRIVILEGED_NO_MFA | Critique |
| guest | external guest = User Administrator | GUEST_PRIVILEGED | Élevé |
| svc | app identity = Application Administrator | SERVICE_PRINCIPAL_PRIVILEGED | Élevé |
| disabled | disabled account, role kept | DISABLED_WITH_ROLES | Moyen |
| dormant | no sign-in for 135 days, role kept | DORMANT_ACCOUNT | Moyen |
| sarah, yassine, john, nadia | normal (john = legit Security Admin) | none | - |

## H. Clean up
```bash
python src/seed_tenant.py cleanup
```

## I. Automate + publish
Private GitHub repo -> Settings -> Secrets: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET -> `.github/workflows/iam-audit.yml` runs weekly.
Screenshot the PDF into the README for your CV.

## Honest limits
- Real sign-in dates and MFA state need Entra ID P1/P2 and real logins. `overlay` simulates them on the test accounts only.
- A new tenant has no Azure subscription: Azure RBAC simulation is optional.

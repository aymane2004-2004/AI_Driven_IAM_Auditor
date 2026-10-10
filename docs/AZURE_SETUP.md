# Azure setup guide for IAM Auditor

This guide helps you configure a clean Azure lab environment and connect the project to your Microsoft Entra tenant and model tokens.

## 1. Create a dedicated lab tenant

Use a new tenant only for testing. Do not use a company or school tenant.

1. Open https://portal.azure.com
2. Go to Microsoft Entra ID
3. Select Manage tenants
4. Click Create
5. Choose a lab tenant name such as `iamlabdemo`
6. Wait for the tenant to be created
7. Switch to it from the tenant picker

> Use a custom domain such as `iamlabdemo.onmicrosoft.com`.

## 2. Create or verify a subscription

1. Open Subscriptions in Azure Portal
2. Check whether your GitHub Student Pack credit is active
3. If needed, create a low-cost subscription under the new tenant
4. Keep this environment fully isolated from real business resources

## 3. Install Azure CLI

Windows PowerShell:

```powershell
winget install Microsoft.AzureCLI
```

Then verify:

```powershell
az version
```

## 4. Sign in to the tenant

```powershell
az login --tenant <your-tenant-domain>.onmicrosoft.com --allow-no-subscriptions
az account list -o table
```

If you do not know your domain, use:

```powershell
az login --use-device-code
```

## 5. Create a local environment file

At the project root, create a `.env` file from the sample:

```powershell
Copy-Item .env.example .env
```

Then update the real values:

```dotenv
GEMINI_API_KEY=your_gemini_key
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_app_registration_client_id
AZURE_CLIENT_SECRET=your_app_registration_client_secret
```

## 6. Create an app registration for Entra access

If you want to use the real Entra data collection path:

1. Go to Microsoft Entra ID
2. App registrations
3. New registration
4. Name: `iam-auditor-lab`
5. Add a client secret under Certificates & Secrets
6. Record the Application (client) ID and Secret Value
7. Go to API permissions
8. Add the following Microsoft Graph permissions:
   - Directory.Read.All
   - User.Read.All
   - RoleManagement.Read.Directory
   - GroupMember.Read.All
9. Grant admin consent

## 7. Add the Gemini key

1. Visit https://aistudio.google.com/apikey
2. Create an API key
3. Store it in `.env`

```dotenv
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

## 8. Validate the setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q tests
python src/generate_data.py
python src/audit.py --no-llm
```

## 9. Real tenant workflow

```powershell
python src/seed_tenant.py create --dry-run
python src/seed_tenant.py create
python src/collect_entra.py
python src/seed_tenant.py overlay
python src/audit.py --input iam_inventory_real.json
python src/seed_tenant.py cleanup
```

## 10. For screenshots and portfolio use

Use the dashboard UI to run the audit and capture attractive screenshots.

```powershell
python app.py
```

Then open:

- http://127.0.0.1:5000

## 11. Security reminders

- Never run this against a real production tenant
- Use a lab tenant only
- Remove all test accounts after use
- Keep tokens in `.env` and never commit them to GitHub
- Add `.env` to `.gitignore`

## 12. Recommended repo hygiene

Make sure these are ignored:

```gitignore
.env
__pycache__/
outputs/
data/iam_inventory_real.json
data/hr_leavers.txt
data/seed_state.json
```

This is already included in the repo’s `.gitignore`.

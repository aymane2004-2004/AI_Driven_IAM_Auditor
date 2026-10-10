# Architecture & workflows

## 1. Global pipeline
```mermaid
flowchart LR
  A[generate_data.py<br/>fake IAM inventory] --> B[(iam_inventory.json)]
  B --> C[rules.py<br/>deterministic detections]
  C --> D{--no-llm ?}
  D -- yes --> G
  D -- no --> E[llm_client.py<br/>pseudonymised batches]
  E --> F[Gemini<br/>risk + remediation + summary]
  F --> G[audit.py<br/>merge + sort by severity]
  G --> H[audit_result.json]
  G --> I[audit_report.md]
  G --> J[report_pdf.py -> audit_report.pdf]
```

## 2. Per-account decision flow
```mermaid
flowchart TD
  U[Account] --> P{Privileged role?}
  P -- yes --> Q{Dept not IT/Sec<br/>or intern/junior?}
  Q -- yes --> X1[EXCESSIVE_PRIVILEGE - Critique]
  P -- yes --> M{MFA off?}
  M -- yes --> X2[PRIVILEGED_NO_MFA - Critique]
  U --> L{HR status = parti<br/>and roles remain?}
  L -- yes --> X3[LEAVER_STILL_ACTIVE - Critique]
  U --> D{Last login > 90 d<br/>and roles remain?}
  D -- yes --> X4[DORMANT_ACCOUNT - Moyen]
```

## 3. LLM interaction
```mermaid
sequenceDiagram
  participant A as audit.py
  participant L as llm_client
  participant M as LLM
  A->>L: findings batch (max 15, no names)
  L->>M: system prompt + JSON data (temp 0.2, JSON mode)
  M-->>L: JSON analyses
  L-->>A: parsed (retry x2 if invalid)
  A->>L: global stats
  L->>M: executive summary prompt
  M-->>A: summary text
```

## 4. Azure target architecture
```mermaid
flowchart LR
  S[Entra ID export / logs] --> B[(Blob Storage)]
  B -- blob trigger --> F[Azure Function Python<br/>rules.py]
  F --> O[Azure OpenAI gpt-4o-mini]
  O --> F --> R[(Blob: report PDF)]
```

## 5. Data model (iam_inventory.json)
id, nom, poste, departement, roles_azure[], mfa_active, type_compte (humain|service), statut_rh (actif|parti), derniere_connexion (ISO date)

"""Step 3 - LLM layer: Google Gemini only. Always returns parsed JSON."""
import json, time
from config import *

SYSTEM = """Tu es consultant senior en cybersécurité / audit IAM dans un cabinet Big 4.
Réponds UNIQUEMENT en JSON valide, en français, ton professionnel et factuel.
Base-toi uniquement sur les données fournies. N'invente aucun fait. Référence ISO 27001:2022 / NIST CSF 2.0."""

def _gemini(system, user):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    r = client.models.generate_content(
        model=GEMINI_MODEL, contents=user,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.2,
                                           response_mime_type="application/json"))
    return r.text

def ask_json(user_prompt, retries=2):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY manquante: renseigne-la dans .env (aistudio.google.com) ou utilise --no-llm")
    for attempt in range(retries + 1):
        try:
            return json.loads(_gemini(SYSTEM, user_prompt))
        except Exception as e:  # invalid JSON, rate limit (429) on free tier, network...
            if attempt == retries: raise RuntimeError(f"Appel Gemini échoué: {e}")
            time.sleep(5 * (attempt + 1))

def analyze_findings(batch):
    """batch = list of {profile, findings}. Names are NOT sent (pseudonymisation)."""
    prompt = ("Pour chaque utilisateur ci-dessous, rédige l'analyse d'audit (user_id = profile.id).\n"
              'Format: {"analyses":[{"user_id":"","risque":"2-3 phrases","criticite":"Critique|Élevé|Moyen|Faible",'
              '"recommandation":"actions techniques concrètes"}]}\n\nDONNÉES:\n'
              + json.dumps(batch, ensure_ascii=False))
    return ask_json(prompt).get("analyses", [])

def context_review(profiles):
    """Deep mode: spot job-title vs roles mismatches the rules miss."""
    prompt = ("Revue contextuelle (user_id = champ id): pour chaque profil, indique si les rôles sont cohérents avec le poste "
              "et le principe du moindre privilège. Retourne UNIQUEMENT les profils suspects.\n"
              'Format: {"suspects":[{"user_id":"","raison":"","criticite":"Élevé|Moyen|Faible"}]}\n\nDONNÉES:\n'
              + json.dumps(profiles, ensure_ascii=False))
    return ask_json(prompt).get("suspects", [])

def executive_summary(stats):
    prompt = ("Rédige un Executive Summary d'audit (max 150 mots) : contexte, constats clés, niveau de risque global, "
              'top 3 priorités. Format: {"summary":"..."}\n\nSTATS:\n' + json.dumps(stats, ensure_ascii=False))
    return ask_json(prompt).get("summary", "")

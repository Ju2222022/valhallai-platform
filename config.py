"""
VALHALLAI - Configuration centralisée
Modifie les valeurs ici pour personnaliser l'application.
"""

# =============================================================================
# INFORMATIONS APPLICATION
# =============================================================================
APP_NAME = "VALHALLAI"
APP_ICON = "🛡️"
APP_TAGLINE = "REGULATORY SHIELD"
APP_SLOGAN = "Simplify today, amplify tomorrow."

# =============================================================================
# MODÈLES OPENAI
# =============================================================================
OPENAI_MODEL = "gpt-4o"  # Modèle principal
OPENAI_TEMPERATURE = 0.1  # Créativité (0 = précis, 1 = créatif)

# =============================================================================
# MARCHÉS DISPONIBLES (modifie cette liste selon tes besoins)
# =============================================================================
DEFAULT_MARKETS = [
    "EU (CE)",
    "USA (FDA)", 
    "China (NMPA)",
    "UK (UKCA)",
    "Japan (PMDA)",
    "Canada (Health Canada)",
    "Australia (TGA)",
    "Brazil (ANVISA)",
    "South Korea (MFDS)",
    "Switzerland (Swissmedic)",
]

# =============================================================================
# LANGUES DISPONIBLES
# =============================================================================
AVAILABLE_LANGUAGES = [
    "English",
    "French", 
    "German",
    "Spanish",
    "Italian",
]

# =============================================================================
# COULEURS DU THÈME
# =============================================================================
COLORS = {
    # Mode clair
    "light": {
        "background": "#F5F7F9",
        "card": "#FFFFFF",
        "text": "#1A202C",
        "text_secondary": "#4A5568",
        "primary": "#295A63",
        "accent": "#C8A951",
        "button_text": "#FFFFFF",
        "border": "#E2E8F0",
    },
    # Mode sombre
    "dark": {
        "background": "#0F2E33",
        "card": "#1A3C42",
        "text": "#FFFFFF",
        "text_secondary": "#A0B0B5",
        "primary": "#C8A951",
        "accent": "#295A63",
        "button_text": "#000000",
        "border": "#295A63",
    },
}

# =============================================================================
# MESSAGES D'ERREUR
# =============================================================================
ERRORS = {
    "no_api_key": "⚠️ Clé API OpenAI non configurée. Contacte l'administrateur.",
    "no_admin_token": "⚠️ Token admin non configuré dans les secrets.",
    "access_denied": "🚫 Accès refusé. Vérifie ton mot de passe.",
    "api_error": "❌ Erreur de communication avec l'API.",
    "pdf_error": "❌ Impossible de lire ce fichier PDF.",
}

# =============================================================================
# DESCRIPTIONS DES AGENTS
# =============================================================================
AGENTS = {
    "olivia": {
        "name": "OlivIA",
        "icon": "🤖",
        "title": "Regulatory Mapping Agent",
        "description": "Define product DNA & map regulatory landscape across multiple markets.",
    },
    "eva": {
        "name": "EVA", 
        "icon": "🔍",
        "title": "Compliance Audit Agent",
        "description": "Audit technical documentation against regulatory requirements.",
    },
}

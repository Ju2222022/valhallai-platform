"""
VALHALLAI - Regulatory Intelligence Platform
Application principale Streamlit
"""

import streamlit as st
import os
import io
import base64
from openai import OpenAI
from pypdf import PdfReader

# Import de la configuration
import config

# =============================================================================
# 1. CONFIGURATION STREAMLIT
# =============================================================================
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# 2. INITIALISATION DU SESSION STATE
# =============================================================================
def init_session_state():
    """Initialise toutes les variables de session."""
    defaults = {
        "authenticated": False,
        "admin_authenticated": False,
        "current_page": "Dashboard",
        "dark_mode": False,
        "last_olivia_report": None,
        "custom_markets": [],  # Marchés ajoutés par l'admin (temporaires)
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 3. FONCTIONS UTILITAIRES
# =============================================================================
def navigate_to(page_name):
    """Change de page et rafraîchit."""
    st.session_state["current_page"] = page_name
    st.rerun()

def get_api_key():
    """Récupère la clé API OpenAI de manière sécurisée."""
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def get_openai_client():
    """Crée un client OpenAI si la clé est disponible."""
    api_key = get_api_key()
    if api_key:
        return OpenAI(api_key=api_key)
    return None

def get_all_markets():
    """Retourne tous les marchés (par défaut + personnalisés)."""
    all_markets = config.DEFAULT_MARKETS.copy()
    for market in st.session_state.get("custom_markets", []):
        if market not in all_markets:
            all_markets.append(market)
    return all_markets

def extract_text_from_pdf(file_bytes):
    """Extrait le texte d'un fichier PDF."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        return f"{config.ERRORS['pdf_error']} Détail: {str(e)}"

# =============================================================================
# 4. AUTHENTIFICATION
# =============================================================================
def check_password():
    """Vérifie le mot de passe principal."""
    correct_token = st.secrets.get("APP_TOKEN")
    
    # Si pas de token configuré, accès libre (dev mode)
    if not correct_token:
        st.session_state["authenticated"] = True
        return
    
    user_input = st.session_state.get("password_input", "")
    if user_input == correct_token:
        st.session_state["authenticated"] = True
        # Nettoyer le champ de mot de passe
        if "password_input" in st.session_state:
            del st.session_state["password_input"]
    else:
        st.error(config.ERRORS["access_denied"])

def check_admin_password():
    """Vérifie le mot de passe admin."""
    admin_token = st.secrets.get("ADMIN_TOKEN")
    
    # Sécurité : pas de token par défaut
    if not admin_token:
        st.error(config.ERRORS["no_admin_token"])
        return
    
    user_input = st.session_state.get("admin_pass_input", "")
    if user_input == admin_token:
        st.session_state["admin_authenticated"] = True
        if "admin_pass_input" in st.session_state:
            del st.session_state["admin_pass_input"]
    else:
        st.error(config.ERRORS["access_denied"])

def logout():
    """Déconnexion complète."""
    st.session_state["authenticated"] = False
    st.session_state["admin_authenticated"] = False
    st.session_state["current_page"] = "Dashboard"
    st.session_state["last_olivia_report"] = None

# =============================================================================
# 5. PROMPTS IA
# =============================================================================
def create_olivia_prompt(description, countries, output_lang):
    """Génère le prompt pour OlivIA."""
    markets_str = ", ".join(countries)
    return f"""You are OlivIA, an expert regulatory affairs AI assistant from VALHALLAI.

PRODUCT DESCRIPTION:
{description}

TARGET MARKETS:
{markets_str}

YOUR MISSION:
Provide a comprehensive regulatory requirements analysis for the product above in each target market.

OUTPUT REQUIREMENTS:
1. Language: Respond STRICTLY in {output_lang}
2. Format: Use clear Markdown with tables
3. Structure for EACH market:
   - Regulatory pathway/classification
   - Key standards and regulations
   - Required documentation
   - Testing requirements
   - Timeline estimates
   - Key contacts/authorities

4. End with a comparative summary table

Be precise, practical, and actionable."""

def create_eva_prompt(context, doc_text, output_lang):
    """Génère le prompt pour EVA."""
    # Limiter le texte pour éviter de dépasser les limites
    max_chars = 6000
    truncated_text = doc_text[:max_chars]
    if len(doc_text) > max_chars:
        truncated_text += "\n\n[... Document tronqué pour l'analyse ...]"
    
    return f"""You are EVA, an expert compliance auditor AI from VALHALLAI.

REGULATORY CONTEXT & REQUIREMENTS:
{context}

DOCUMENT TO AUDIT:
'''
{truncated_text}
'''

YOUR MISSION:
Perform a detailed compliance audit of the document against the requirements.

OUTPUT REQUIREMENTS:
1. Language: Respond STRICTLY in {output_lang}
2. Start with an overall compliance status using these symbols:
   - ✅ COMPLIANT: All requirements met
   - ⚠️ PARTIALLY COMPLIANT: Some gaps identified
   - ❌ NON-COMPLIANT: Critical gaps found

3. For each requirement, indicate:
   - Status (✅/⚠️/❌)
   - Evidence found (or missing)
   - Specific recommendations

4. End with:
   - Priority action items
   - Risk assessment

Be thorough but concise."""

# =============================================================================
# 6. ASSETS VISUELS
# =============================================================================
def get_logo_svg():
    """Génère le logo SVG."""
    colors = config.COLORS["dark" if st.session_state["dark_mode"] else "light"]
    c1 = colors["primary"]
    c2 = colors["accent"]
    c3 = "#1A3C42"
    c4 = "#E6D5A7"
    
    return f"""
    <svg width="60" height="60" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="{c1}"/>
        <rect x="52" y="10" width="38" height="38" rx="8" fill="{c2}"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="{c3}"/>
        <rect x="52" y="52" width="38" height="38" rx="8" fill="{c4}"/>
    </svg>
    """

def get_logo_html():
    """Convertit le logo en HTML base64."""
    svg = get_logo_svg()
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="vertical-align: middle; margin-right: 15px;">'

# =============================================================================
# 7. THÈME CSS
# =============================================================================
def apply_theme():
    """Applique le thème CSS selon le mode."""
    mode = "dark" if st.session_state["dark_mode"] else "light"
    c = config.COLORS[mode]
    
    css = f"""
    <style>
    /* Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
    
    /* Base */
    .stApp {{
        background-color: {c['background']};
        font-family: 'Inter', sans-serif;
        color: {c['text']};
    }}
    
    /* Header */
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
    
    /* Hide Streamlit branding */
    .stDeployButton, #MainMenu, footer {{
        display: none;
    }}
    
    /* Headings */
    h1, h2, h3 {{
        font-family: 'Montserrat', sans-serif !important;
        color: {c['primary']} !important;
    }}
    
    /* Text */
    p, li, .stMarkdown {{
        color: {c['text']};
    }}
    
    .sub-text {{
        color: {c['text_secondary']};
        font-size: 0.9rem;
    }}
    
    /* Logo */
    .logo-text {{
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 1.4rem;
        color: {c['text']};
    }}
    
    .logo-sub {{
        font-size: 0.7rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: {c['text_secondary']};
        font-weight: 500;
    }}
    
    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {c['card']};
        border-right: 1px solid {c['border']};
    }}
    
    /* Inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        color: {c['text']};
        border-radius: 8px;
    }}
    
    /* Buttons */
    div.stButton > button:first-child {{
        background-color: {c['primary']} !important;
        color: {c['button_text']} !important;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
    }}
    
    div.stButton > button:first-child:hover {{
        opacity: 0.9;
        transform: translateY(-1px);
    }}
    
    /* Cards */
    .info-card {{
        background-color: {c['card']};
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid {c['border']};
        height: 100%;
        transition: all 0.3s ease;
    }}
    
    .info-card:hover {{
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }}
    
    /* Success messages */
    .stSuccess {{
        background-color: {c['card']};
        border-left: 4px solid {c['primary']};
    }}
    
    /* Radio buttons in sidebar */
    div[role="radiogroup"] label {{
        color: {c['text_secondary']};
        font-weight: 500;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# =============================================================================
# 8. PAGES
# =============================================================================
def page_dashboard():
    """Page d'accueil / Dashboard."""
    st.markdown(f"# {config.APP_ICON} Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    
    col1, col2 = st.columns(2)
    
    # Card OlivIA
    with col1:
        agent = config.AGENTS["olivia"]
        st.markdown(f"""
        <div class="info-card">
            <h3>{agent['icon']} {agent['name']}</h3>
            <p class='sub-text'>{agent['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button(f"Launch {agent['name']} Analysis →", key="btn_olivia"):
            navigate_to("OlivIA")
    
    # Card EVA
    with col2:
        agent = config.AGENTS["eva"]
        st.markdown(f"""
        <div class="info-card">
            <h3>{agent['icon']} {agent['name']}</h3>
            <p class='sub-text'>{agent['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button(f"Launch {agent['name']} Audit →", key="btn_eva"):
            navigate_to("EVA")
    
    # Stats (optionnel)
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("Available Markets", len(get_all_markets()))
    with stat_col2:
        st.metric("Languages", len(config.AVAILABLE_LANGUAGES))
    with stat_col3:
        status = "✅ Connected" if get_api_key() else "❌ Not configured"
        st.metric("API Status", status)

def page_olivia():
    """Page OlivIA - Analyse réglementaire."""
    agent = config.AGENTS["olivia"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    st.markdown(f"<span class='sub-text'>{agent['description']}</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Vérifier la clé API
    client = get_openai_client()
    if not client:
        st.error(config.ERRORS["no_api_key"])
        return
    
    # Récupérer les marchés
    available_markets = get_all_markets()
    
    # Interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        description = st.text_area(
            "📝 Product Definition",
            height=200,
            placeholder="Describe your product in detail...\n\nExample: Class IIa medical device for continuous glucose monitoring. Intended for home use by adult diabetic patients. Wireless connectivity to smartphone app."
        )
    
    with col2:
        countries = st.multiselect(
            "🌍 Target Markets",
            options=available_markets,
            default=[available_markets[0]] if available_markets else None,
            help="Select one or more target markets"
        )
        
        output_lang = st.selectbox(
            "🗣️ Output Language",
            options=config.AVAILABLE_LANGUAGES,
            help="Language for the analysis report"
        )
        
        st.write("")
        generate_btn = st.button("🚀 Generate Report", type="primary", use_container_width=True)
    
    # Génération du rapport
    if generate_btn:
        if not description.strip():
            st.warning("⚠️ Please enter a product description.")
        elif not countries:
            st.warning("⚠️ Please select at least one market.")
        else:
            with st.spinner("🔄 Analyzing regulatory requirements..."):
                try:
                    prompt = create_olivia_prompt(description, countries, output_lang)
                    response = client.chat.completions.create(
                        model=config.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    st.session_state["last_olivia_report"] = response.choices[0].message.content
                    st.rerun()
                except Exception as e:
                    st.error(f"{config.ERRORS['api_error']} Détail: {str(e)}")
    
    # Affichage du rapport
    if st.session_state.get("last_olivia_report"):
        st.markdown("---")
        st.success("✅ Analysis Generated Successfully")
        
        # Bouton pour copier dans EVA
        if st.button("📋 Use this report in EVA →"):
            navigate_to("EVA")
        
        st.markdown("### 📄 Regulatory Analysis Report")
        st.markdown(st.session_state["last_olivia_report"])
        
        # Bouton pour effacer
        if st.button("🗑️ Clear Report"):
            st.session_state["last_olivia_report"] = None
            st.rerun()

def page_eva():
    """Page EVA - Audit de conformité."""
    agent = config.AGENTS["eva"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    st.markdown(f"<span class='sub-text'>{agent['description']}</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Vérifier la clé API
    client = get_openai_client()
    if not client:
        st.error(config.ERRORS["no_api_key"])
        return
    
    # Contexte réglementaire
    default_context = st.session_state.get("last_olivia_report", "")
    has_olivia_report = bool(default_context)
    
    with st.expander("📋 Regulatory Context", expanded=not has_olivia_report):
        if has_olivia_report:
            st.info("💡 OlivIA report automatically loaded. You can modify it if needed.")
        context = st.text_area(
            "Requirements to check against",
            value=default_context,
            height=200,
            placeholder="Paste regulatory requirements here, or generate them with OlivIA first."
        )
    
    # Upload et configuration
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "📄 Upload Technical Documentation (PDF)",
            type=["pdf"],
            help="Upload the technical file to audit"
        )
        
        if uploaded_file:
            st.success(f"✅ File loaded: {uploaded_file.name}")
    
    with col2:
        audit_lang = st.selectbox(
            "🗣️ Audit Language",
            options=config.AVAILABLE_LANGUAGES,
            help="Language for the audit report"
        )
        
        st.write("")
        audit_btn = st.button("🔍 Run Compliance Audit", type="primary", use_container_width=True)
    
    # Exécution de l'audit
    if audit_btn:
        if not context.strip():
            st.warning("⚠️ Please provide regulatory context.")
        elif not uploaded_file:
            st.warning("⚠️ Please upload a document to audit.")
        else:
            with st.spinner("🔄 Auditing document..."):
                try:
                    # Extraire le texte du PDF
                    doc_text = extract_text_from_pdf(uploaded_file.read())
                    
                    if doc_text.startswith("❌"):
                        st.error(doc_text)
                        return
                    
                    # Générer l'audit
                    prompt = create_eva_prompt(context, doc_text, audit_lang)
                    response = client.chat.completions.create(
                        model=config.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    
                    # Afficher les résultats
                    st.markdown("---")
                    st.markdown("### 📊 Audit Results")
                    st.markdown(response.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"{config.ERRORS['api_error']} Détail: {str(e)}")

def page_admin():
    """Page Admin - Gestion."""
    st.title("⚙️ Admin Console")
    st.markdown("---")
    
    # Authentification admin
    if not st.session_state["admin_authenticated"]:
        st.markdown("### 🔐 Restricted Access")
        st.text_input(
            "Admin Password",
            type="password",
            key="admin_pass_input",
            on_change=check_admin_password
        )
        st.info("💡 Enter admin password to access management features.")
        return
    
    # Interface admin
    st.success("✅ Admin access granted")
    
    # Section: Gestion des marchés
    st.markdown("### 🌍 Market Management")
    st.info("ℹ️ Custom markets are stored in session. For permanent changes, edit `config.py`.")
    
    current_markets = get_all_markets()
    custom_markets = st.session_state.get("custom_markets", [])
    
    # Ajouter un marché
    with st.form("add_market_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_market = st.text_input(
                "Add New Market",
                placeholder="Example: India (CDSCO)"
            )
        with col2:
            st.write("")
            submitted = st.form_submit_button("➕ Add", use_container_width=True)
        
        if submitted:
            new_market = new_market.strip()
            if not new_market:
                st.warning("⚠️ Please enter a market name.")
            elif len(new_market) < 2:
                st.warning("⚠️ Name too short (minimum 2 characters).")
            elif new_market in current_markets:
                st.warning("⚠️ This market already exists.")
            else:
                st.session_state["custom_markets"].append(new_market)
                st.success(f"✅ Added: {new_market}")
                st.rerun()
    
    # Liste des marchés
    st.markdown("### 📋 Active Markets")
    
    col_default, col_custom = st.columns(2)
    
    with col_default:
        st.markdown("**Default Markets** (from config.py)")
        for market in config.DEFAULT_MARKETS:
            st.info(f"🌍 {market}")
    
    with col_custom:
        st.markdown("**Custom Markets** (session only)")
        if custom_markets:
            for i, market in enumerate(custom_markets):
                col_name, col_del = st.columns([3, 1])
                col_name.success(f"✨ {market}")
                if col_del.button("🗑️", key=f"del_{i}"):
                    st.session_state["custom_markets"].pop(i)
                    st.rerun()
        else:
            st.caption("No custom markets added yet.")
    
    # Section: Infos système
    st.markdown("---")
    st.markdown("### ℹ️ System Information")
    
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.markdown(f"**OpenAI Model:** `{config.OPENAI_MODEL}`")
        st.markdown(f"**API Key:** `{'✅ Configured' if get_api_key() else '❌ Missing'}`")
    with info_col2:
        st.markdown(f"**Total Markets:** {len(current_markets)}")
        st.markdown(f"**Languages:** {len(config.AVAILABLE_LANGUAGES)}")
    
    # Déconnexion admin
    st.markdown("---")
    if st.button("🚪 Logout Admin"):
        st.session_state["admin_authenticated"] = False
        st.rerun()

# =============================================================================
# 9. APPLICATION PRINCIPALE
# =============================================================================
def render_sidebar():
    """Affiche la sidebar avec navigation."""
    with st.sidebar:
        # Logo
        logo_html = get_logo_html()
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            {logo_html}
            <div>
                <div class="logo-text">{config.APP_NAME}</div>
                <div class="logo-sub">{config.APP_TAGLINE}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Navigation
        pages = ["Dashboard", "OlivIA", "EVA", "Admin"]
        current = st.session_state["current_page"]
        
        selected = st.radio(
            "NAVIGATION",
            pages,
            index=pages.index(current) if current in pages else 0,
            label_visibility="collapsed"
        )
        
        if selected != current:
            navigate_to(selected)
        
        st.markdown("---")
        
        # Dark mode toggle
        dark_mode = st.checkbox(
            "🌙 Night Mode",
            value=st.session_state["dark_mode"]
        )
        if dark_mode != st.session_state["dark_mode"]:
            st.session_state["dark_mode"] = dark_mode
            st.rerun()
        
        st.markdown("---")
        
        # Logout
        if st.button("🚪 Log Out", use_container_width=True):
            logout()
            st.rerun()

def render_login():
    """Affiche la page de connexion."""
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Logo centré
        st.markdown(
            f"<div style='text-align: center;'>{get_logo_html()}</div>",
            unsafe_allow_html=True
        )
        
        # Titre
        st.markdown(
            f"<h1 style='text-align: center; color: #295A63;'>{config.APP_NAME}</h1>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<p style='text-align: center; color: #666;'>{config.APP_TAGLINE}</p>",
            unsafe_allow_html=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Champ de mot de passe
        st.text_input(
            "🔐 Security Token",
            type="password",
            key="password_input",
            on_change=check_password,
            placeholder="Enter your access token"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Contact administrator for access credentials.")

def main():
    """Point d'entrée principal."""
    # Appliquer le thème
    apply_theme()
    
    # Vérifier l'authentification
    if st.session_state["authenticated"]:
        # Afficher la sidebar
        render_sidebar()
        
        # Router vers la bonne page
        page = st.session_state["current_page"]
        
        if page == "Dashboard":
            page_dashboard()
        elif page == "OlivIA":
            page_olivia()
        elif page == "EVA":
            page_eva()
        elif page == "Admin":
            page_admin()
        else:
            page_dashboard()
    else:
        # Page de connexion
        render_login()

# Lancement
if __name__ == "__main__":
    main()

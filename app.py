"""
VALHALLAI - Regulatory Intelligence Platform
Application principale Streamlit
Version 2.0 - Admin amélioré
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
        "markets_list": None,  # None = utiliser config.DEFAULT_MARKETS
        "editing_market_index": None,  # Index du marché en cours d'édition
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 3. GESTION DES MARCHÉS
# =============================================================================
def get_markets():
    """Retourne la liste des marchés (modifiée ou par défaut)."""
    if st.session_state["markets_list"] is not None:
        return st.session_state["markets_list"]
    return config.DEFAULT_MARKETS.copy()

def set_markets(markets_list):
    """Sauvegarde la liste des marchés dans la session."""
    st.session_state["markets_list"] = markets_list

def reset_markets():
    """Réinitialise aux marchés par défaut."""
    st.session_state["markets_list"] = None
    st.session_state["editing_market_index"] = None

def add_market(market_name):
    """Ajoute un marché à la liste."""
    markets = get_markets()
    if market_name not in markets:
        markets.append(market_name)
        set_markets(markets)
        return True
    return False

def remove_market(index):
    """Supprime un marché par son index."""
    markets = get_markets()
    if 0 <= index < len(markets):
        markets.pop(index)
        set_markets(markets)

def update_market(index, new_name):
    """Modifie le nom d'un marché."""
    markets = get_markets()
    if 0 <= index < len(markets):
        markets[index] = new_name
        set_markets(markets)

def move_market(index, direction):
    """Déplace un marché vers le haut (-1) ou le bas (+1)."""
    markets = get_markets()
    new_index = index + direction
    if 0 <= new_index < len(markets):
        markets[index], markets[new_index] = markets[new_index], markets[index]
        set_markets(markets)

# =============================================================================
# 4. FONCTIONS UTILITAIRES
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
# 5. AUTHENTIFICATION
# =============================================================================
def check_password():
    """Vérifie le mot de passe principal."""
    correct_token = st.secrets.get("APP_TOKEN")
    
    if not correct_token:
        st.session_state["authenticated"] = True
        return
    
    user_input = st.session_state.get("password_input", "")
    if user_input == correct_token:
        st.session_state["authenticated"] = True
        if "password_input" in st.session_state:
            del st.session_state["password_input"]
    else:
        st.error(config.ERRORS["access_denied"])

def check_admin_password():
    """Vérifie le mot de passe admin."""
    admin_token = st.secrets.get("ADMIN_TOKEN")
    
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
# 6. PROMPTS IA
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
# 7. ASSETS VISUELS
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
# 8. THÈME CSS
# =============================================================================
def apply_theme():
    """Applique le thème CSS selon le mode."""
    mode = "dark" if st.session_state["dark_mode"] else "light"
    c = config.COLORS[mode]
    
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
    
    .stApp {{
        background-color: {c['background']};
        font-family: 'Inter', sans-serif;
        color: {c['text']};
    }}
    
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
    
    .stDeployButton, #MainMenu, footer {{
        display: none;
    }}
    
    h1, h2, h3 {{
        font-family: 'Montserrat', sans-serif !important;
        color: {c['primary']} !important;
    }}
    
    p, li, .stMarkdown {{
        color: {c['text']};
    }}
    
    .sub-text {{
        color: {c['text_secondary']};
        font-size: 0.9rem;
    }}
    
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
    
    section[data-testid="stSidebar"] {{
        background-color: {c['card']};
        border-right: 1px solid {c['border']};
    }}
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        color: {c['text']};
        border-radius: 8px;
    }}
    
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
    
    .stSuccess {{
        background-color: {c['card']};
        border-left: 4px solid {c['primary']};
    }}
    
    div[role="radiogroup"] label {{
        color: {c['text_secondary']};
        font-weight: 500;
    }}
    
    .market-item {{
        background-color: {c['card']};
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid {c['border']};
        margin-bottom: 0.5rem;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# =============================================================================
# 9. PAGES
# =============================================================================
def page_dashboard():
    """Page d'accueil / Dashboard."""
    st.markdown(f"# {config.APP_ICON} Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    
    col1, col2 = st.columns(2)
    
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
    
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("Available Markets", len(get_markets()))
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
    
    client = get_openai_client()
    if not client:
        st.error(config.ERRORS["no_api_key"])
        return
    
    available_markets = get_markets()
    
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
    
    if st.session_state.get("last_olivia_report"):
        st.markdown("---")
        st.success("✅ Analysis Generated Successfully")
        
        if st.button("📋 Use this report in EVA →"):
            navigate_to("EVA")
        
        st.markdown("### 📄 Regulatory Analysis Report")
        st.markdown(st.session_state["last_olivia_report"])
        
        if st.button("🗑️ Clear Report"):
            st.session_state["last_olivia_report"] = None
            st.rerun()

def page_eva():
    """Page EVA - Audit de conformité."""
    agent = config.AGENTS["eva"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    st.markdown(f"<span class='sub-text'>{agent['description']}</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    client = get_openai_client()
    if not client:
        st.error(config.ERRORS["no_api_key"])
        return
    
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
    
    if audit_btn:
        if not context.strip():
            st.warning("⚠️ Please provide regulatory context.")
        elif not uploaded_file:
            st.warning("⚠️ Please upload a document to audit.")
        else:
            with st.spinner("🔄 Auditing document..."):
                try:
                    doc_text = extract_text_from_pdf(uploaded_file.read())
                    
                    if doc_text.startswith("❌"):
                        st.error(doc_text)
                        return
                    
                    prompt = create_eva_prompt(context, doc_text, audit_lang)
                    response = client.chat.completions.create(
                        model=config.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    
                    st.markdown("---")
                    st.markdown("### 📊 Audit Results")
                    st.markdown(response.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"{config.ERRORS['api_error']} Détail: {str(e)}")

def page_admin():
    """Page Admin - Gestion complète des marchés."""
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
    
    st.success("✅ Admin access granted")
    
    # ===========================================
    # SECTION: Gestion des marchés
    # ===========================================
    st.markdown("### 🌍 Market Management")
    
    # Avertissement sur la persistance
    is_modified = st.session_state["markets_list"] is not None
    if is_modified:
        st.warning("⚠️ You have unsaved changes. These will be lost if the app restarts. See 'Export' section below to save permanently.")
    
    current_markets = get_markets()
    
    # --- Formulaire d'ajout ---
    st.markdown("#### ➕ Add New Market")
    with st.form("add_market_form", clear_on_submit=True):
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            new_market = st.text_input(
                "Market name",
                placeholder="Example: India (CDSCO)",
                label_visibility="collapsed"
            )
        with col_btn:
            add_submitted = st.form_submit_button("Add", use_container_width=True)
        
        if add_submitted and new_market:
            new_market = new_market.strip()
            if len(new_market) < 2:
                st.error("❌ Name too short (min 2 characters)")
            elif new_market in current_markets:
                st.error("❌ This market already exists")
            else:
                add_market(new_market)
                st.success(f"✅ Added: {new_market}")
                st.rerun()
    
    # --- Liste des marchés ---
    st.markdown("#### 📋 Current Markets")
    st.caption(f"Total: {len(current_markets)} markets")
    
    if not current_markets:
        st.info("No markets configured. Add one above!")
    else:
        for i, market in enumerate(current_markets):
            # Vérifier si on est en mode édition pour ce marché
            is_editing = st.session_state.get("editing_market_index") == i
            
            col_num, col_name, col_up, col_down, col_edit, col_del = st.columns([0.5, 3, 0.5, 0.5, 0.7, 0.7])
            
            with col_num:
                st.markdown(f"**{i+1}.**")
            
            with col_name:
                if is_editing:
                    # Mode édition
                    new_name = st.text_input(
                        "Edit name",
                        value=market,
                        key=f"edit_input_{i}",
                        label_visibility="collapsed"
                    )
                else:
                    st.markdown(f"🌍 {market}")
            
            with col_up:
                # Bouton monter (désactivé si premier)
                if i > 0:
                    if st.button("⬆️", key=f"up_{i}", help="Move up"):
                        move_market(i, -1)
                        st.rerun()
                else:
                    st.write("")  # Placeholder
            
            with col_down:
                # Bouton descendre (désactivé si dernier)
                if i < len(current_markets) - 1:
                    if st.button("⬇️", key=f"down_{i}", help="Move down"):
                        move_market(i, 1)
                        st.rerun()
                else:
                    st.write("")  # Placeholder
            
            with col_edit:
                if is_editing:
                    # Bouton sauvegarder
                    if st.button("💾", key=f"save_{i}", help="Save"):
                        new_name = st.session_state.get(f"edit_input_{i}", market).strip()
                        if new_name and new_name != market:
                            if new_name in current_markets and new_name != market:
                                st.error("Name already exists!")
                            else:
                                update_market(i, new_name)
                                st.session_state["editing_market_index"] = None
                                st.rerun()
                        else:
                            st.session_state["editing_market_index"] = None
                            st.rerun()
                else:
                    # Bouton éditer
                    if st.button("✏️", key=f"edit_{i}", help="Edit"):
                        st.session_state["editing_market_index"] = i
                        st.rerun()
            
            with col_del:
                # Bouton supprimer
                if st.button("🗑️", key=f"del_{i}", help="Delete"):
                    remove_market(i)
                    st.session_state["editing_market_index"] = None
                    st.rerun()
    
    # --- Actions globales ---
    st.markdown("---")
    st.markdown("#### 🔄 Global Actions")
    
    col_reset, col_export = st.columns(2)
    
    with col_reset:
        if st.button("🔄 Reset to Default", use_container_width=True):
            reset_markets()
            st.success("✅ Markets reset to default values")
            st.rerun()
    
    with col_export:
        if st.button("📤 Show Export Code", use_container_width=True):
            st.session_state["show_export"] = not st.session_state.get("show_export", False)
            st.rerun()
    
    # --- Zone d'export ---
    if st.session_state.get("show_export", False):
        st.markdown("---")
        st.markdown("#### 📤 Export for Permanent Save")
        st.info("👇 Copy this code and paste it in your `config.py` file on GitHub to make changes permanent.")
        
        # Générer le code Python
        markets_code = "DEFAULT_MARKETS = [\n"
        for market in current_markets:
            markets_code += f'    "{market}",\n'
        markets_code += "]"
        
        st.code(markets_code, language="python")
        
        st.markdown("""
        **How to update config.py on GitHub:**
        1. Go to your GitHub repository
        2. Click on `config.py`
        3. Click the ✏️ pencil icon to edit
        4. Find `DEFAULT_MARKETS = [...]`
        5. Replace it with the code above
        6. Click "Commit changes"
        """)
    
    # --- Infos système ---
    st.markdown("---")
    st.markdown("### ℹ️ System Information")
    
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.markdown(f"**OpenAI Model:** `{config.OPENAI_MODEL}`")
        st.markdown(f"**API Key:** `{'✅ Configured' if get_api_key() else '❌ Missing'}`")
    with info_col2:
        st.markdown(f"**Total Markets:** {len(current_markets)}")
        st.markdown(f"**Modified:** {'⚠️ Yes' if is_modified else '✅ No (using defaults)'}")
    
    # Déconnexion admin
    st.markdown("---")
    if st.button("🚪 Logout Admin", use_container_width=True):
        st.session_state["admin_authenticated"] = False
        st.rerun()

# =============================================================================
# 10. APPLICATION PRINCIPALE
# =============================================================================
def render_sidebar():
    """Affiche la sidebar avec navigation."""
    with st.sidebar:
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
        
        dark_mode = st.checkbox(
            "🌙 Night Mode",
            value=st.session_state["dark_mode"]
        )
        if dark_mode != st.session_state["dark_mode"]:
            st.session_state["dark_mode"] = dark_mode
            st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Log Out", use_container_width=True):
            logout()
            st.rerun()

def render_login():
    """Affiche la page de connexion."""
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        st.markdown(
            f"<div style='text-align: center;'>{get_logo_html()}</div>",
            unsafe_allow_html=True
        )
        
        st.markdown(
            f"<h1 style='text-align: center; color: #295A63;'>{config.APP_NAME}</h1>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<p style='text-align: center; color: #666;'>{config.APP_TAGLINE}</p>",
            unsafe_allow_html=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
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
    apply_theme()
    
    if st.session_state["authenticated"]:
        render_sidebar()
        
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
        render_login()

if __name__ == "__main__":
    main()

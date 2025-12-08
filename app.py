import streamlit as st
import os
import io
import base64
from openai import OpenAI
from pypdf import PdfReader
import gspread # La librairie pour Google Sheets

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
    defaults = {
        "authenticated": False,
        "admin_authenticated": False,
        "current_page": "Dashboard",
        "dark_mode": False,
        "last_olivia_report": None,
        "editing_market_index": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 3. GESTION DES MARCHÉS (GOOGLE SHEETS - BLINDÉE)
# =============================================================================
@st.cache_resource
def get_gsheet_connection():
    """Connexion sécurisée à Google Sheets via Secrets."""
    try:
        # Vérification de base
        if "service_account" not in st.secrets:
            st.error("⚠️ Secrets 'service_account' introuvables.")
            return None
            
        # On construit le dictionnaire manuellement pour éviter les erreurs de parsing
        # Cela force les clés à être présentes
        sa_secrets = st.secrets["service_account"]
        
        creds_dict = {
            "type": sa_secrets["type"],
            "project_id": sa_secrets["project_id"],
            "private_key_id": sa_secrets["private_key_id"],
            "private_key": sa_secrets["private_key"].replace("\\n", "\n"), # Correction cruciale des sauts de ligne
            "client_email": sa_secrets["client_email"],
            "client_id": sa_secrets["client_id"],
            "auth_uri": sa_secrets["auth_uri"],
            "token_uri": sa_secrets["token_uri"],
            "auth_provider_x509_cert_url": sa_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": sa_secrets["client_x509_cert_url"]
        }

        # Connexion
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open_by_url(st.secrets["gsheets"]["url"])
        return sh.sheet1 # On travaille sur le premier onglet
    except Exception as e:
        # Affiche l'erreur exacte pour le débogage
        st.error(f"❌ Erreur connexion Google Sheets: {e}")
        return None

def get_markets():
    """Lit la liste des marchés depuis le Sheet."""
    sheet = get_gsheet_connection()
    if sheet:
        try:
            # Récupère toute la colonne A
            vals = sheet.col_values(1)
            return vals if vals else []
        except:
            return config.DEFAULT_MARKETS
    return config.DEFAULT_MARKETS

def add_market(market_name):
    """Ajoute un marché dans le Sheet."""
    sheet = get_gsheet_connection()
    if sheet:
        try:
            current = sheet.col_values(1)
            if market_name not in current:
                sheet.append_row([market_name])
                st.cache_data.clear() # Force le rechargement
                return True
        except Exception as e:
            st.error(f"Erreur d'écriture : {e}")
    return False

def remove_market(index):
    """Supprime un marché du Sheet."""
    sheet = get_gsheet_connection()
    if sheet:
        try:
            # +1 car Google Sheets commence ligne 1
            sheet.delete_rows(index + 1)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Erreur de suppression : {e}")

def update_market(index, new_name):
    """Renomme un marché."""
    sheet = get_gsheet_connection()
    if sheet:
        try:
            sheet.update_cell(index + 1, 1, new_name)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Erreur de modification : {e}")

# =============================================================================
# 4. FONCTIONS UTILITAIRES
# =============================================================================
def navigate_to(page_name):
    st.session_state["current_page"] = page_name
    st.rerun()

def get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def get_openai_client():
    api_key = get_api_key()
    if api_key:
        return OpenAI(api_key=api_key)
    return None

def extract_text_from_pdf(file_bytes):
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
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True; return
    
    if st.session_state.get("password_input", "") == correct_token:
        st.session_state["authenticated"] = True
        del st.session_state["password_input"]
    else:
        st.error(config.ERRORS["access_denied"])

def check_admin_password():
    admin_token = st.secrets.get("ADMIN_TOKEN")
    if not admin_token:
        st.error(config.ERRORS["no_admin_token"]); return
    
    if st.session_state.get("admin_pass_input", "") == admin_token:
        st.session_state["admin_authenticated"] = True
        del st.session_state["admin_pass_input"]
    else:
        st.error(config.ERRORS["access_denied"])

def logout():
    st.session_state["authenticated"] = False
    st.session_state["admin_authenticated"] = False
    st.session_state["current_page"] = "Dashboard"

# =============================================================================
# 6. PROMPTS IA & UI HELPERS
# =============================================================================
def create_olivia_prompt(description, countries, output_lang):
    markets_str = ", ".join(countries)
    return f"""You are OlivIA (VALHALLAI). Product: {description} | Markets: {markets_str}. 
    Mission: List regulatory requirements strictly in {output_lang}. Translate all headers.
    Format: Markdown tables. Be professional."""

def create_eva_prompt(context, doc_text, output_lang):
    return f"""You are EVA (VALHALLAI). Context: {context}. Doc: '''{doc_text[:6000]}'''. 
    Mission: Verify compliance in {output_lang}. Start with ✅/⚠️/❌."""

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
    svg = get_logo_svg()
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="vertical-align: middle; margin-right: 15px;">'

def apply_theme():
    mode = "dark" if st.session_state["dark_mode"] else "light"
    c = config.COLORS[mode]
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
    .stApp {{ background-color: {c['background']}; font-family: 'Inter', sans-serif; color: {c['text']}; }}
    h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {c['primary']} !important; }}
    .info-card {{ background-color: {c['card']}; padding: 2rem; border-radius: 12px; border: 1px solid {c['border']}; }}
    .logo-text {{ font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 1.4rem; color: {c['text']}; }}
    .logo-sub {{ font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: {c['text_secondary']}; font-weight: 500; }}
    div.stButton > button:first-child {{ background-color: {c['primary']} !important; color: {c['button_text']} !important; border-radius: 8px; font-weight: 600; width: 100%;}}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 7. PAGES
# =============================================================================
def page_admin():
    st.title("⚙️ Admin Console (Google Sheets DB)")
    st.markdown("---")
    
    if not st.session_state["admin_authenticated"]:
        st.markdown("### 🔐 Restricted Access")
        st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password)
        return
    
    # Check connection
    sheet = get_gsheet_connection()
    if not sheet:
        st.error("❌ Erreur : Impossible de se connecter au Google Sheet. Vérifiez les secrets.")
        return

    st.success(f"✅ Connecté à la base de données : {sheet.title}")
    
    # --- Formulaire Ajout ---
    current_markets = get_markets()
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        new = col1.text_input("Nouveau Marché")
        if col2.form_submit_button("Ajouter"):
            if new and add_market(new):
                st.success(f"Ajouté : {new}")
                st.rerun()
            else:
                st.error("Erreur ou doublon")

    # --- Liste ---
    st.markdown("### Marchés Actifs")
    for i, m in enumerate(current_markets):
        c1, c2, c3 = st.columns([4, 1, 1])
        
        # Mode lecture
        if st.session_state.get("editing_market_index") != i:
            c1.info(f"🌍 {m}")
            if c2.button("✏️", key=f"ed_{i}"):
                st.session_state["editing_market_index"] = i
                st.rerun()
            if c3.button("🗑️", key=f"del_{i}"):
                remove_market(i)
                st.rerun()
        
        # Mode édition
        else:
            new_val = c1.text_input("Edit", value=m, key=f"val_{i}", label_visibility="collapsed")
            if c2.button("💾", key=f"save_{i}"):
                update_market(i, new_val)
                st.session_state["editing_market_index"] = None
                st.rerun()
            if c3.button("❌", key=f"cancel_{i}"):
                st.session_state["editing_market_index"] = None
                st.rerun()

def page_olivia():
    agent = config.AGENTS["olivia"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    available_markets = get_markets() # Charge depuis GSheets
    
    col1, col2 = st.columns([2, 1])
    with col1: desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
    with col2:
        countries = st.multiselect("Target Markets", available_markets, default=[available_markets[0]] if available_markets else None)
        output_lang = st.selectbox("Language", config.AVAILABLE_LANGUAGES)
        if st.button("Generate Report"):
            client = get_openai_client()
            if client and desc:
                with st.spinner("Analyzing..."):
                    try:
                        res = client.chat.completions.create(
                            model=config.OPENAI_MODEL,
                            messages=[{"role": "user", "content": create_olivia_prompt(desc, countries, output_lang)}],
                            temperature=config.OPENAI_TEMPERATURE
                        )
                        st.session_state["last_olivia_report"] = res.choices[0].message.content
                        st.rerun()
                    except Exception as e: st.error(str(e))
    
    if st.session_state["last_olivia_report"]:
        st.markdown("---"); st.markdown(st.session_state["last_olivia_report"])

def page_dashboard():
    st.title("Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    col1, col2 = st.columns(2)
    with col1: 
        st.markdown(f"""<div class="info-card"><h3>🤖 OlivIA</h3><p class='sub-text'>{config.AGENTS['olivia']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch OlivIA Analysis ->"): navigate_to("OlivIA")
    with col2: 
        st.markdown(f"""<div class="info-card"><h3>🔍 EVA</h3><p class='sub-text'>{config.AGENTS['eva']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch EVA Audit ->"): navigate_to("EVA")

def page_eva():
    st.title("EVA Workspace")
    ctx = st.text_area("Context", value=st.session_state.get("last_olivia_report", ""))
    up = st.file_uploader("PDF", type="pdf")
    lang = st.selectbox("Audit Language", config.AVAILABLE_LANGUAGES)
    
    if st.button("Audit"):
        client = get_openai_client()
        if client and up:
            with st.spinner("Auditing..."):
                txt = extract_text_from_pdf(up.read())
                try:
                    res = client.chat.completions.create(
                        model="gpt-4o", messages=[{"role":"user","content":create_eva_prompt(ctx,txt,lang)}], temperature=config.OPENAI_TEMPERATURE
                    )
                    st.markdown("### Audit Results")
                    st.markdown(res.choices[0].message.content)
                except Exception as e: st.error(str(e))

def render_sidebar():
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
        sel = st.radio("NAVIGATION", ["Dashboard", "OlivIA", "EVA", "Admin"], index=["Dashboard", "OlivIA", "EVA", "Admin"].index(st.session_state["current_page"]) if st.session_state["current_page"] in ["Dashboard", "OlivIA", "EVA", "Admin"] else 0)
        
        if sel != st.session_state["current_page"]: navigate_to(sel)
        
        st.markdown("---")
        is_dark = st.checkbox("Night Mode", value=st.session_state["dark_mode"])
        if is_dark != st.session_state["dark_mode"]: st.session_state["dark_mode"] = is_dark; st.rerun()
        
        st.markdown("---")
        if st.button("Log Out"): logout(); st.rerun()

def render_login():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center'>{get_logo_html()}</div>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; color: #295A63;'>{config.APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #666;'>{config.APP_TAGLINE}</p>", unsafe_allow_html=True)
        st.text_input("Security Token", type="password", key="password_input", on_change=check_password)

def main():
    apply_theme()
    if st.session_state["authenticated"]:
        render_sidebar()
        if st.session_state["current_page"] == "Dashboard": page_dashboard()
        elif st.session_state["current_page"] == "OlivIA": page_olivia()
        elif st.session_state["current_page"] == "EVA": page_eva()
        elif st.session_state["current_page"] == "Admin": page_admin()
        else: page_dashboard()
    else:
        render_login()

if __name__ == "__main__": main()

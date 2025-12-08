import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io
import base64
import json  # <--- INDISPENSABLE pour la page Admin

# --- 1. CONFIGURATION & STATE MANAGEMENT ---
st.set_page_config(
    page_title="VALHALLAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Fichier de stockage des marchés
MARKETS_FILE = "markets.json"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

def navigate_to(page_name):
    st.session_state["current_page"] = page_name
    st.rerun()

# --- 2. GESTION DES DONNÉES (JSON) ---
# C'est cette partie qui manquait probablement et causait le NameError
def load_markets():
    """Charge les marchés depuis le JSON ou retourne une liste par défaut."""
    if os.path.exists(MARKETS_FILE):
        try:
            with open(MARKETS_FILE, "r") as f:
                return json.load(f)
        except:
            pass # Si erreur lecture, on ignore
    
    # Liste par défaut
    default_markets = ["EU (CE)", "USA (FDA)", "China (NMPA)", "UK (UKCA)"]
    # On tente de créer le fichier pour la prochaine fois
    try:
        save_markets(default_markets)
    except:
        pass 
    return default_markets

def save_markets(markets_list):
    """Sauvegarde la liste modifiée dans le JSON."""
    with open(MARKETS_FILE, "w") as f:
        json.dump(markets_list, f)

# --- 3. ASSETS & THEME ---
def get_logo_svg():
    color_1, color_2 = "#295A63", "#C8A951"
    color_3, color_4 = "#1A3C42", "#E6D5A7"
    return f"""
    <svg width="60" height="60" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="{color_1}"/>
        <rect x="52" y="10" width="38" height="38" rx="8" fill="{color_2}"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="{color_3}"/>
        <rect x="52" y="52" width="38" height="38" rx="8" fill="{color_4}"/>
    </svg>
    """

def get_logo_html():
    svg = get_logo_svg()
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="vertical-align: middle; margin-right: 15px;">'

def get_theme_css():
    if st.session_state["dark_mode"]:
        bg_color, card_bg = "#0F2E33", "#1A3C42"
        text_color, sub_text_color = "#FFFFFF", "#A0B0B5"
        primary_color, button_text = "#C8A951", "#000000"
        border_color, input_bg, sidebar_bg = "#295A63", "#13363C", "#0F2E33"
        logo_text_color = "#FFFFFF"
    else:
        bg_color, card_bg = "#F5F7F9", "#FFFFFF"
        text_color, sub_text_color = "#1A202C", "#4A5568"
        primary_color, button_text = "#295A63", "#FFFFFF"
        border_color, input_bg, sidebar_bg = "#FFFFFF", "#FFFFFF", "#FFFFFF"
        logo_text_color = "#295A63"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
    .stApp {{ background-color: {bg_color}; font-family: 'Inter', sans-serif; color: {text_color}; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    .stDeployButton, #MainMenu, footer {{ display:none; }}
    h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {primary_color if not st.session_state["dark_mode"] else "#FFFFFF"} !important; }}
    p, li, .stMarkdown {{ color: {text_color}; }}
    .sub-text {{ color: {sub_text_color}; font-size: 0.9rem; }}
    .logo-text {{ font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 1.4rem; color: {logo_text_color}; }}
    .logo-sub {{ font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: {sub_text_color}; font-weight: 500; }}
    section[data-testid="stSidebar"] {{ background-color: {sidebar_bg}; border-right: 1px solid {border_color}; }}
    div[role="radiogroup"] label {{ color: {sub_text_color}; font-weight: 500; }}
    div[role="radiogroup"] label[data-checked="true"] {{ background-color: {primary_color} !important; color: {button_text} !important; }}
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {{ background-color: {input_bg}; border: 1px solid {border_color}; color: {text_color}; border-radius: 8px; }}
    div.stButton > button:first-child {{ background-color: {primary_color} !important; color: {button_text} !important; border-radius: 8px; border: none; font-weight: 600; width: 100%; }}
    .info-card {{ background-color: {card_bg}; padding: 2rem; border-radius: 12px; border: 1px solid {border_color}; height: 100%; }}
    .stSuccess {{ background-color: {card_bg}; border-left: 4px solid #295A63; }}
    </style>
    """
st.markdown(get_theme_css(), unsafe_allow_html=True)

# --- 4. BACKEND HELPERS ---
def check_password():
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token: 
        st.session_state["authenticated"] = True; return
    if st.session_state["password_input"] == correct_token:
        st.session_state["authenticated"] = True; del st.session_state["password_input"]
    else: st.error("Access Denied.")

def check_admin_password():
    admin_token = st.secrets.get("ADMIN_TOKEN", "admin123") 
    if st.session_state["admin_pass_input"] == admin_token:
        st.session_state["admin_authenticated"] = True
        del st.session_state["admin_pass_input"]
    else:
        st.error("Admin Access Denied.")

def logout():
    st.session_state["authenticated"] = False
    st.session_state["admin_authenticated"] = False
    st.session_state["current_page"] = "Dashboard"

def get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def extract_text_from_pdf(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = [page.extract_text() for page in reader.pages if page.extract_text()]
        return "\n".join(text)
    except Exception as e: return f"Error: {str(e)}"

# --- 5. PROMPTS ---
def prompt_olivia(description, countries, output_lang):
    pays_str = ", ".join(countries)
    return f"""You are OlivIA (VALHALLAI). Product: {description} | Markets: {pays_str}. Mission: List regulatory requirements strictly in {output_lang}. Format: Markdown tables."""

def prompt_eva(context, doc_text, output_lang):
    return f"""You are EVA (VALHALLAI). Context: {context}. Doc: '''{doc_text[:4000]}'''. Mission: Verify compliance in {output_lang}. Start with ✅/⚠️/❌."""

# --- 6. ADMIN PAGE ---
def admin_page():
    st.title("⚙️ Admin Console")
    st.markdown("---")
    
    if not st.session_state["admin_authenticated"]:
        st.markdown("### Restricted Access")
        st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password)
        return

    st.subheader("Market Management (OlivIA)")
    
    current_markets = load_markets()
    
    with st.form("add_market_form"):
        col_new, col_btn = st.columns([3, 1])
        new_market = col_new.text_input("Add New Market", placeholder="ex: Japan (PMDA)")
        submitted = col_btn.form_submit_button("Add Market")
        if submitted and new_market:
            if new_market not in current_markets:
                current_markets.append(new_market)
                save_markets(current_markets)
                st.success(f"Added: {new_market}")
                st.rerun()
            else:
                st.warning("Market already exists.")

    st.markdown("### Active Markets List")
    for i, market in enumerate(current_markets):
        col_name, col_del = st.columns([4, 1])
        col_name.info(f"🌍 {market}")
        if col_del.button("Remove", key=f"del_{i}"):
            current_markets.pop(i)
            save_markets(current_markets)
            st.rerun()

# --- 7. MAIN APP ---
def main_app():
    with st.sidebar:
        logo_html = get_logo_html()
        st.markdown(f"""<div class="logo-container">{logo_html}<div><div class="logo-text">VALHALLAI</div><div class="logo-sub">REGULATORY SHIELD</div></div></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        # C'est ICI que l'Admin a été ajouté à la liste
        pages_list = ["Dashboard", "OlivIA", "EVA", "Admin"]
        
        selected_page = st.radio("NAVIGATION", pages_list, index=pages_list.index(st.session_state["current_page"]), label_visibility="collapsed")
        
        if selected_page != st.session_state["current_page"]: 
            navigate_to(selected_page)

        st.markdown("---")
        is_dark = st.checkbox("Night Mode", value=st.session_state["dark_mode"])
        if is_dark != st.session_state["dark_mode"]: st.session_state["dark_mode"] = is_dark; st.rerun()
        st.markdown("---")
        if st.button("Log Out"): logout(); st.rerun()

    api_key = get_api_key(); client = OpenAI(api_key=api_key) if api_key else None

    # --- ROUTING ---
    if st.session_state["current_page"] == "Dashboard":
        st.markdown("# Dashboard")
        st.markdown(f"<span class='sub-text'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        st.markdown("###")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""<div class="info-card"><h3>🤖 OlivIA</h3><p class='sub-text'>Define product DNA & map regulatory landscape.</p></div>""", unsafe_allow_html=True)
            st.write(""); if st.button("Launch OlivIA Analysis ->"): navigate_to("OlivIA")
        with col2:
            st.markdown("""<div class="info-card"><h3>🔍 EVA</h3><p class='sub-text'>Audit technical documentation against requirements.</p></div>""", unsafe_allow_html=True)
            st.write(""); if st.button("Launch EVA Audit ->"): navigate_to("EVA")

    elif st.session_state["current_page"] == "OlivIA":
        st.title("OlivIA Workspace")
        st.markdown("<span class='sub-text'>Define product parameters to generate requirements.</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Appel de la fonction chargée plus haut
        available_markets = load_markets()
        
        col1, col2 = st.columns([2, 1])
        with col1: desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
        with col2:
            countries = st.multiselect("Markets", available_markets, default=[available_markets[0]] if available_markets else None)
            output_lang = st.selectbox("Output Language", ["English", "French", "German"])
            st.write(""); if st.button("Generate Report"):
                if client and desc:
                    with st.spinner("Analyzing..."):
                        try:
                            response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt_olivia(desc, countries, output_lang)}], temperature=0.1)
                            st.session_state["last_olivia_report"] = response.choices[0].message.content; st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
        if "last_olivia_report" in st.session_state: st.markdown("---"); st.success("Analysis Generated"); st.markdown(st.session_state["last_olivia_report"])

    elif st.session_state["current_page"] == "EVA":
        st.title("EVA Workspace")
        st.markdown("<span class='sub-text'>Verify documentation compliance.</span>", unsafe_allow_html=True)
        st.markdown("---")
        default_ctx = st.session_state.get("last_olivia_report", "")
        with st.expander("Regulatory Context", expanded=not bool(default_ctx)): context = st.text_area("Requirements", value=default_ctx, height=150)
        col1, col2 = st.columns([2,1])
        with col1: uploaded = st.file_uploader("Technical File (PDF)", type="pdf")
        with col2:
            lang = st.selectbox("Audit Language", ["English", "French"])
            st.write(""); if st.button("Run Audit"):
                if client and uploaded:
                    with st.spinner("Auditing..."):
                        txt = extract_text_from_pdf(uploaded.read())
                        try:
                            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt_eva(context, txt, lang)}], temperature=0.1)
                            st.markdown("### Audit Results"); st.markdown(res.choices[0].message.content)
                        except Exception as e: st.error(f"Error: {e}")

    elif st.session_state["current_page"] == "Admin":
        admin_page()

def main():
    if st.session_state["authenticated"]: main_app()
    else:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center'>{get_logo_html()}</div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; color: #295A63;'>VALHALLAI</h1>", unsafe_allow_html=True)
            st.text_input("Security Token", type="password", key="password_input", on_change=check_password)

if __name__ == "__main__": main()

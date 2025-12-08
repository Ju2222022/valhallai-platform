import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io

# --- 1. CONFIGURATION & STATE MANAGEMENT ---
st.set_page_config(
    page_title="VALHALLAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation des variables de session
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False # Par défaut en clair

# Fonction de navigation interne
def navigate_to(page_name):
    st.session_state["current_page"] = page_name
    st.rerun()

# --- 2. THEME ENGINE (CSS DYNAMIQUE) ---
def get_theme_css():
    # Définition des palettes
    if st.session_state["dark_mode"]:
        # MODE SOMBRE (Racing Night)
        bg_color = "#0F2E33"      # Vert très sombre
        card_bg = "#1A3C42"       # Vert légèrement plus clair
        text_color = "#FFFFFF"
        sub_text_color = "#A0B0B5"
        primary_color = "#C8A951" # Gold pour les actions en mode sombre
        button_text = "#000000"   # Texte noir sur bouton Or
        border_color = "#295A63"
        input_bg = "#13363C"
        sidebar_bg = "#0F2E33"
    else:
        # MODE CLAIR (Racing Day - Apple Style)
        bg_color = "#F5F7F9"      # Gris bleuté très pâle (plus pro que le blanc pur)
        card_bg = "#FFFFFF"       # Blanc pur pour les cartes
        text_color = "#1A202C"    # Noir graphite (pas noir pur, plus doux)
        sub_text_color = "#4A5568"
        primary_color = "#295A63" # Racing Green pour les actions
        button_text = "#FFFFFF"   # Texte BLANC forcé sur fond Vert
        border_color = "#E2E8F0"
        input_bg = "#FFFFFF"
        sidebar_bg = "#FFFFFF"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

    /* BASE */
    .stApp {{
        background-color: {bg_color};
        font-family: 'Inter', sans-serif;
        color: {text_color};
    }}
    
    /* HEADER CLEANUP */
    header[data-testid="stHeader"] {{ background: transparent; }}
    .stDeployButton {{ display:none; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* TYPOGRAPHY */
    h1, h2, h3 {{
        font-family: 'Montserrat', sans-serif !important;
        color: {primary_color if not st.session_state["dark_mode"] else "#FFFFFF"} !important;
        letter-spacing: -0.5px;
    }}
    p, li, .stMarkdown {{ color: {text_color}; font-weight: 400; line-height: 1.6; }}
    .sub-text {{ color: {sub_text_color}; font-size: 0.9rem; }}

    /* SIDEBAR NAVIGATION (PRO STYLE) */
    section[data-testid="stSidebar"] {{
        background-color: {sidebar_bg};
        border-right: 1px solid {border_color};
    }}
    /* Cache les ronds des radio buttons */
    div[role="radiogroup"] > label > div:first-child {{
        display: none !important;
    }}
    /* Transforme les labels en boutons de navigation */
    div[role="radiogroup"] label {{
        padding: 12px 20px;
        border-radius: 6px;
        margin-bottom: 8px;
        border: 1px solid transparent;
        transition: all 0.2s;
        cursor: pointer;
        color: {sub_text_color};
        font-weight: 500;
    }}
    /* Hover effect */
    div[role="radiogroup"] label:hover {{
        background-color: {bg_color};
        color: {primary_color};
    }}
    /* Selected Item Styling */
    div[role="radiogroup"] label[data-checked="true"] {{
        background-color: {primary_color if not st.session_state["dark_mode"] else "#C8A951"} !important;
        color: {button_text if not st.session_state["dark_mode"] else "#000000"} !important;
        font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }}

    /* CARDS & CONTAINERS */
    .info-card {{
        background-color: {card_bg};
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid {border_color};
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}

    /* INPUTS */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {{
        background-color: {input_bg};
        border: 1px solid {border_color};
        color: {text_color};
        border-radius: 8px;
        padding: 10px;
    }}
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {{
        border-color: {primary_color};
        box-shadow: 0 0 0 1px {primary_color};
    }}
    
    /* BUTTONS (CORRECTION CONTRASTE) */
    .stButton>button {{
        background-color: {primary_color} !important;
        color: {button_text} !important; /* FORCE LA COULEUR DU TEXTE */
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s;
        margin-top: 10px;
    }}
    .stButton>button:hover {{
        filter: brightness(1.1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    
    /* ALERTS */
    .stSuccess {{ background-color: {card_bg}; border-left: 4px solid #295A63; color: {text_color}; }}
    .stInfo, .stWarning {{ background-color: {card_bg}; border-left: 4px solid #C8A951; color: {text_color}; }}
    
    </style>
    """

# Injection du CSS
st.markdown(get_theme_css(), unsafe_allow_html=True)

# --- 3. BACKEND HELPERS ---

def check_password():
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True
        return
    if st.session_state["password_input"] == correct_token:
        st.session_state["authenticated"] = True
        del st.session_state["password_input"]
    else:
        st.error("Access Denied.")

def logout():
    st.session_state["authenticated"] = False
    st.session_state["current_page"] = "Dashboard"

def get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def extract_text_from_pdf(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = []
        for page in reader.pages:
            t = page.extract_text()
            if t: text.append(t)
        return "\n".join(text)
    except Exception as e:
        return f"Error: {str(e)}"

# --- 4. PROMPTS ---
def prompt_olivia(description, countries, output_lang):
    pays_str = ", ".join(countries)
    return f"""
    You are OlivIA, expert in regulation (VALHALLAI).
    Product: {description} | Markets: {pays_str}
    Mission: List regulatory requirements strictly in {output_lang}.
    Format: Markdown tables. Be professional and concise.
    """

def prompt_eva(context, doc_text, output_lang):
    return f"""
    You are EVA, quality auditor (VALHALLAI).
    Context: {context}
    Doc: '''{doc_text[:4000]}'''
    Mission: Verify compliance in {output_lang}. Start with ✅/⚠️/❌.
    """

# --- 5. MAIN APPLICATION ---

def main_app():
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("## VALHALLAI")
        st.markdown(f"<div style='margin-top: -15px; color: {'#A0B0B5' if st.session_state['dark_mode'] else '#558D98'}; font-size: 0.8rem; letter-spacing: 1px; font-weight: 600;'>REGULATORY SHIELD</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        # NAVIGATION
        pages_list = ["Dashboard", "OlivIA", "EVA"]
        
        if st.session_state["current_page"] not in pages_list:
            st.session_state["current_page"] = "Dashboard"
            
        current_index = pages_list.index(st.session_state["current_page"])
        
        selected_page = st.radio(
            "NAVIGATION", 
            pages_list,
            index=current_index,
            label_visibility="collapsed"
        )
        
        if selected_page != st.session_state["current_page"]:
            st.session_state["current_page"] = selected_page
            st.rerun()

        st.markdown("---")
        
        # DARK MODE TOGGLE
        col_dark, col_lbl = st.columns([1, 4])
        with col_dark:
            is_dark = st.checkbox("", value=st.session_state["dark_mode"])
        with col_lbl:
            st.write("Night Mode")
            
        if is_dark != st.session_state["dark_mode"]:
            st.session_state["dark_mode"] = is_dark
            st.rerun()

        st.markdown("---")
        if st.button("Log Out"):
            logout()
            st.rerun()

    # --- API CLIENT ---
    api_key = get_api_key()
    client = OpenAI(api_key=api_key) if api_key else None

    # --- PAGES ---
    
    # 1. DASHBOARD
    if st.session_state["current_page"] == "Dashboard":
        st.markdown("# Dashboard")
        st.markdown(f"<span class='sub-text'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        st.markdown("###") # Spacer
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="info-card">
                <h3>🤖 OlivIA</h3>
                <p class='sub-text'>Define product DNA & map regulatory landscape.</p>
            </div>
            """, unsafe_allow_html=True)
            st.write("") 
            if st.button("Launch OlivIA Analysis ->"):
                navigate_to("OlivIA")

        with col2:
            st.markdown("""
            <div class="info-card">
                <h3>🔍 EVA</h3>
                <p class='sub-text'>Audit technical documentation against requirements.</p>
            </div>
            """, unsafe_allow_html=True)
            st.write("") 
            if st.button("Launch EVA Audit ->"):
                navigate_to("EVA")

    # 2. OLIVIA
    elif st.session_state["current_page"] == "OlivIA":
        st.title("OlivIA Workspace")
        st.markdown("<span class='sub-text'>Define product parameters to generate requirements.</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
        with col2:
            countries = st.multiselect("Markets", ["EU (CE)", "USA (FDA)", "China", "UK"], default=["EU (CE)"])
            output_lang = st.selectbox("Output Language", ["English", "French", "German"])
            st.write("")
            if st.button("Generate Report"):
                if client and desc:
                    with st.spinner("Analyzing..."):
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o", 
                                messages=[{"role": "user", "content": prompt_olivia(desc, countries, output_lang)}],
                                temperature=0.1
                            )
                            st.session_state["last_olivia_report"] = response.choices[0].message.content
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

        if "last_olivia_report" in st.session_state:
            st.markdown("---")
            st.success("Analysis Generated")
            st.markdown(st.session_state["last_olivia_report"])

    # 3. EVA
    elif st.session_state["current_page"] == "EVA":
        st.title("EVA Workspace")
        st.markdown("<span class='sub-text'>Verify documentation compliance.</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        default_ctx = st.session_state.get("last_olivia_report", "")
        with st.expander("Regulatory Context", expanded=not bool(default_ctx)):
            context = st.text_area("Requirements", value=default_ctx, height=150)
            
        col1, col2 = st.columns([2,1])
        with col1:
            uploaded = st.file_uploader("Technical File (PDF)", type="pdf")
        with col2:
            lang = st.selectbox("Audit Language", ["English", "French"])
            st.write("")
            if st.button("Run Audit"):
                if client and uploaded:
                    with st.spinner("Auditing..."):
                        txt = extract_text_from_pdf(uploaded.read())
                        try:
                            res = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "user", "content": prompt_eva(context, txt, lang)}],
                                temperature=0.1
                            )
                            st.markdown("### Audit Results")
                            st.markdown(res.choices[0].message.content)
                        except Exception as e: st.error(f"Error: {e}")

# --- ENTRY POINT ---

def main():
    if st.session_state["authenticated"]:
        main_app()
    else:
        # LOGIN SCREEN
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; color: #295A63;'>VALHALLAI</h1>", unsafe_allow_html=True)
            st.text_input("Security Token", type="password", key="password_input", on_change=check_password)

if __name__ == "__main__":
    main()

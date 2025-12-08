import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io
import base64

# --- 1. CONFIGURATION & STATE MANAGEMENT ---
st.set_page_config(
    page_title="VALHALLAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

def navigate_to(page_name):
    st.session_state["current_page"] = page_name
    st.rerun()

# --- 2. ASSETS & LOGO GENERATOR (SVG - DAMIER) ---
def get_logo_svg():
    """Génère un damier 4 carrés aux couleurs Valhallai"""
    # Palette Damier
    color_1 = "#295A63" # Racing Green (Haut Gauche)
    color_2 = "#C8A951" # Gold (Haut Droite)
    color_3 = "#1A3C42" # Racing Green Foncé (Bas Gauche)
    color_4 = "#E6D5A7" # Gold Clair/Crème (Bas Droite)
    
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

# --- 3. THEME ENGINE (CSS) ---
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

    h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {primary_color if not st.session_state["dark_mode"] else "#FFFFFF"} !important; letter-spacing: -0.5px; }}
    p, li, .stMarkdown {{ color: {text_color}; }}
    .sub-text {{ color: {sub_text_color}; font-size: 0.9rem; }}
    
    .logo-container {{ display: flex; align-items: center; margin-bottom: 20px; }}
    .logo-text {{ font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 1.4rem; color: {logo_text_color}; line-height: 1.2; }}
    .logo-sub {{ font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: {sub_text_color}; font-weight: 500; }}

    section[data-testid="stSidebar"] {{ background-color: {sidebar_bg}; border-right: 1px solid {border_color}; }}
    div[role="radiogroup"] > label > div:first-child {{ display: none !important; }}
    div[role="radiogroup"] label {{ padding: 12px 20px; border-radius: 6px; margin-bottom: 8px; cursor: pointer; color: {sub_text_color}; font-weight: 500; transition: all 0.2s; }}
    div[role="radiogroup"] label:hover {{ background-color: {bg_color}; color: {primary_color}; }}
    div[role="radiogroup"] label[data-checked="true"] {{ background-color: {primary_color if not st.session_state["dark_mode"] else "#C8A951"} !important; color: {button_text if not st.session_state["dark_mode"] else "#000000"} !important; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}

    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {{ background-color: {input_bg}; border: 1px solid {border_color}; color: {text_color}; border-radius: 8px; }}
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {{ border-color: {primary_color}; }}
    
    div.stButton > button:first-child {{ background-color: {primary_color} !important; color: {button_text} !important; border-radius: 8px; border: none; padding: 0.6rem 1.2rem; font-family: 'Montserrat', sans-serif; font-weight: 600; width: 100%; margin-top: 10px; }}
    div.stButton > button:first-child p {{ color: {button_text} !important; }}
    div.stButton > button:first-child:hover {{ filter: brightness(1.1); color: {button_text} !important; }}

    .info-card {{ background-color: {card_bg}; padding: 2rem; border-radius: 12px; border: 1px solid {border_color}; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
    .stSuccess {{ background-color: {card_bg}; border-left: 4px solid #295A63; color: {text_color}; }}
    .stInfo, .stWarning {{ background-color: {card_bg}; border-left: 4px solid #C8A951; color: {text_color}; }}
    </style>
    """
st.markdown(get_theme_css(), unsafe_allow_html=True)

# --- 4. BACKEND HELPERS ---
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
    except Exception as e: return f"Error: {str(e)}"

# --- 5. PROMPTS ---
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

# --- 6. MAIN APP ---
def main_app():
    with st.sidebar:
        logo_html = get_logo_html()
        st.markdown(f"""
        <div class="logo-container">
            {logo_html}
            <div>
                <div class="logo-text">VALHALLAI</div>
                <div class="logo-sub">REGULATORY SHIELD</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        pages_list = ["Dashboard", "OlivIA", "EVA"]
        if st.session_state["current_page"] not in pages_list: 
            st.session_state["current_page"] = "Dashboard"
            
        selected_page = st.radio("NAVIGATION", pages_list, index=pages_list.index(st.session_state["current_page"]), label_visibility="collapsed")
        
        if selected_page != st.session_state["current_page"]: 
            navigate_to(selected_page)

        st.markdown("---")
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

    api_key = get_api_key()
    client = OpenAI(api_key=api_key) if api_key else None

    # --- DASHBOARD PAGE ---
    if st.session_state["current_page"] == "Dashboard":
        st.markdown("# Dashboard")
        st.markdown(f"<span class='sub-text'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        st.markdown("###")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""<div class="info-card"><h3>🤖 OlivIA</h3><p class='sub-text'>Define product DNA & map regulatory landscape.</p></div>""", unsafe_allow_html=True)
            st.write("")
            if st.button("Launch OlivIA Analysis ->"): 
                navigate_to("OlivIA")
        with col2:
            st.markdown("""<div class="info-card"><h3>🔍 EVA</h3><p class='sub-text'>Audit technical documentation against requirements.</p></div>""", unsafe_allow_html=True)
            st.write("")
            if st.button("Launch EVA Audit ->"): 
                navigate_to("EVA")

    # --- OLIVIA PAGE ---
    elif st.session_state["current_page"] == "OlivIA":
        st.title("OlivIA Workspace")
        st.markdown("<span class='sub-text'>Define product parameters to generate requirements.</span>", unsafe_allow_html=True)
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1: 
            desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
        with col2:
            countries = st.multiselect("Markets", ["Europe", "USA", "China", "UK", Canada], default=["EU"])
            output_lang = st.selectbox("Output Language", ["English", "French", "German"])
            
            st.write("")
            if st.button("Generate Report"):
                if client and desc:
                    with st.spinner("Analyzing..."):
                        try:
                            response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt_olivia(desc, countries, output_lang)}], temperature=0.1)
                            st.session_state["last_olivia_report"] = response.choices[0].message.content
                            st.rerun()
                        except Exception as e: 
                            st.error(f"Error: {e}")
                            
        if "last_olivia_report" in st.session_state: 
            st.markdown("---")
            st.success("Analysis Generated")
            st.markdown(st.session_state["last_olivia_report"])

    # --- EVA PAGE ---
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
                            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt_eva(context, txt, lang)}], temperature=0.1)
                            st.markdown("### Audit Results")
                            st.markdown(res.choices[0].message.content)
                        except Exception as e: 
                            st.error(f"Error: {e}")

def main():
    if st.session_state["authenticated"]: 
        main_app()
    else:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center'>{get_logo_html()}</div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; color: #295A63;'>VALHALLAI</h1>", unsafe_allow_html=True)
            st.text_input("Security Token", type="password", key="password_input", on_change=check_password)

if __name__ == "__main__": 
    main()

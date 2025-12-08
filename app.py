import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io

# --- CONFIGURATION DE LA PAGE (Mode Wide & Clean) ---
st.set_page_config(
    page_title="VALHALLAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LUXURY & MINIMALIST CSS INJECTION ---
st.markdown("""
    <style>
    /* Import Fonts: Montserrat (Titres) & Inter (Corps) */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Inter:wght@300;400;600&display=swap');

    /* 1. RESET GLOBAL & BACKGROUND */
    .stApp {
        background-color: #FAFAFA; /* Blanc cassé très léger pour moins de fatigue oculaire */
        font-family: 'Inter', sans-serif;
        color: #212121;
    }
    
    /* Supprimer la barre colorée en haut de Streamlit */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .stDeployButton {display:none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* 2. TYPOGRAPHIE (Prestige) */
    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif !important;
        color: #295A63 !important; /* Racing Green */
        letter-spacing: -0.5px;
    }
    h1 { font-weight: 700; font-size: 2.5rem !important; }
    h2 { font-weight: 600; font-size: 1.8rem !important; margin-top: 1.5rem !important; }
    p, li, .stMarkdown { font-weight: 300; line-height: 1.6; }

    /* 3. SIDEBAR (Épurée) */
    section[data-testid="stSidebar"] {
        background-color: #F4F5F7; /* Gris très pâle */
        border-right: 1px solid #E1E3E6;
        box-shadow: none;
    }
    
    /* 4. INPUT FIELDS (Style Apple: Minimaliste & Focus) */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        background-color: #FFFFFF;
        border: 1px solid #E1E3E6;
        border-radius: 8px; /* Coins adoucis */
        color: #295A63;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    /* Focus state : Bordure Racing Green */
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #295A63;
        box-shadow: 0 0 0 1px #295A63;
    }

    /* 5. BUTTONS (Action Principale) */
    .stButton>button {
        background-color: #295A63;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 6px rgba(41, 90, 99, 0.2);
        transition: all 0.2s ease;
        width: 100%; /* Pleine largeur pour l'harmonie */
    }
    .stButton>button:hover {
        background-color: #1A3C42; /* Darker Green */
        transform: translateY(-1px);
        box-shadow: 0 6px 8px rgba(41, 90, 99, 0.3);
    }

    /* 6. CARDS & CONTAINERS (Pour structurer l'info) */
    .info-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E1E3E6;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 1rem;
    }
    
    /* 7. ALERTS (Custom Gold/Green) */
    .stSuccess {
        background-color: #F1F8F9;
        border-left: 4px solid #295A63;
        color: #295A63;
    }
    .stWarning, .stInfo {
        background-color: #FFFCF2; /* Fond crème */
        border-left: 4px solid #C8A951; /* Gold */
    }
    
    /* Gold Accent Class */
    .gold-accent { color: #C8A951; font-weight: 600; }
    
    /* Login Box Centering */
    .login-container {
        display: flex; 
        justify-content: center; 
        align-items: center; 
        height: 80vh;
    }
    </style>
""", unsafe_allow_html=True)

# --- SECURITY & AUTHENTICATION ---

def check_password():
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True # Mode dev si pas de secret
        return

    if st.session_state["password_input"] == correct_token:
        st.session_state["authenticated"] = True
        del st.session_state["password_input"]
    else:
        st.session_state["authenticated"] = False
        st.error("Identifiants incorrects.")

def logout():
    st.session_state["authenticated"] = False

# --- BACKEND LOGIC ---

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

# --- PROMPTS (Keeping them standard) ---
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

# --- MAIN APP (The "Apple-like" Layout) ---

def main_app():
    # SIDEBAR
    with st.sidebar:
        st.markdown("## VALHALLAI")
        st.markdown("<div style='margin-top: -15px; color: #558D98; font-size: 0.8rem; letter-spacing: 1px;'>REGULATORY SHIELD</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation Stylisée
        mode = st.radio(
            "WORKSPACE", 
            ["Dashboard", "OlivIA (Analysis)", "EVA (Audit)"],
            label_visibility="collapsed" # On cache le titre "WORKSPACE" pour épuré
        )
        
        st.markdown("---")
        st.caption("System Status: Online 🟢")
        if st.button("Log Out", type="secondary"):
            logout()
            st.rerun()

    # API Check
    api_key = get_api_key()
    client = OpenAI(api_key=api_key) if api_key else None
    
    # --- DASHBOARD (Accueil) ---
    if mode == "Dashboard":
        st.markdown("# Welcome back.")
        st.markdown(f"<span class='gold-accent'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        
        st.markdown("###") # Spacer
        
        # Layout en 2 colonnes style "Cartes"
        col1, col2 = st.columns(2)
        with col1:
            st.info("""
            **🤖 Start with OlivIA**
            
            Define your product DNA and let AI map out the global regulatory landscape.
            """)
        with col2:
            st.warning("""
            **🔍 Continue with EVA**
            
            Upload technical files (PDF) and verify them against OlivIA's requirements.
            """)

    # --- MODULE OLIVIA ---
    elif "OlivIA" in mode:
        st.title("OlivIA")
        st.markdown("**Regulatory Intelligence Engine**")
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            desc = st.text_area("Product Definition", height=200, placeholder="Describe materials, technology, usage, and target audience...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True) # Petit ajustement vertical
            countries = st.multiselect("Target Jurisdictions", ["EU (CE)", "USA (FDA/FCC)", "China (CCC)", "UK (UKCA)"], default=["EU (CE)"])
            output_lang = st.selectbox("Output Language", ["English", "French", "German"])
            
            st.markdown("###") # Space
            if st.button("Generate Requirements"):
                if client and desc:
                    with st.spinner("Analyzing regulatory landscape..."):
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o", 
                                messages=[{"role": "user", "content": prompt_olivia(desc, countries, output_lang)}],
                                temperature=0.1
                            )
                            st.session_state["last_olivia_report"] = response.choices[0].message.content
                            st.rerun() # Refresh to show result below
                        except Exception as e: st.error(f"Error: {e}")

        # Résultat affiché dans une "Carte" propre
        if "last_olivia_report" in st.session_state:
            st.markdown("###")
            st.success("Analysis Complete")
            with st.container():
                st.markdown(st.session_state["last_olivia_report"])

    # --- MODULE EVA ---
    elif "EVA" in mode:
        st.title("EVA")
        st.markdown("**Compliance Verification Auditor**")
        st.markdown("---")
        
        # Contexte
        default_context = st.session_state.get("last_olivia_report", "")
        with st.expander("Reference Regulatory Context", expanded=not bool(default_context)):
            context = st.text_area("Requirements", value=default_context, height=150, placeholder="Paste requirements here...")
            
        col1, col2 = st.columns([2,1])
        with col1:
            uploaded_file = st.file_uploader("Upload Technical Documentation", type="pdf")
        with col2:
            output_lang_eva = st.selectbox("Audit Language", ["English", "French"])
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Run Compliance Audit"):
                if client and uploaded_file:
                    with st.spinner("Scanning document structure..."):
                        doc_text = extract_text_from_pdf(uploaded_file.read())
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "user", "content": prompt_eva(context, doc_text, output_lang_eva)}],
                                temperature=0.1
                            )
                            st.markdown("### Audit Report")
                            st.markdown(response.choices[0].message.content)
                        except Exception as e: st.error(f"Error: {e}")

# --- LOGIN SCREEN (Minimalist) ---

def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        main_app()
    else:
        # Centered Login Layout
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; color: #295A63;'>VALHALLAI</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #558D98; letter-spacing: 2px; font-size: 0.8em;'>ACCESS CONTROL</p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.text_input("Security Token", type="password", key="password_input", on_change=check_password)
            st.markdown("<p style='text-align: center; font-size: 0.7em; color: #aaa; margin-top: 20px;'>Restricted Area • Authorized Personnel Only</p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

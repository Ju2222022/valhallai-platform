import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="VALHALLAI - Login",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed" # Caché tant qu'on n'est pas connecté
)

# --- GRAPHIC CHART & CSS (VALHALLAI THEME) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Inter:wght@400;600&display=swap');

    /* Global */
    .stApp {
        background-color: #FFFFFF;
        font-family: 'Inter', sans-serif;
        color: #212121;
    }
    
    /* Headings */
    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif !important;
        color: #295A63 !important;
        font-weight: 700;
    }

    /* Buttons */
    .stButton>button {
        background-color: #295A63;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #000000;
        color: #C8A951;
        border: 1px solid #C8A951;
    }

    /* Inputs */
    .stTextInput>div>div>input {
        border-color: #295A63;
    }
    
    /* Login Box Styling */
    .login-box {
        padding: 2rem;
        border-radius: 10px;
        border: 1px solid #E1E3E6;
        background-color: #F8F9FA;
        text-align: center;
        margin-top: 50px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SECURITY & AUTHENTICATION ---

def check_password():
    """Vérifie le token entré par l'utilisateur"""
    
    # 1. On cherche le vrai token dans les secrets, sinon on utilise une valeur par défaut pour tester
    correct_token = st.secrets.get("APP_TOKEN")
    
    # Si pas de token configuré dans les secrets, on laisse passer (mode dev) ou on bloque
    if not correct_token:
        st.warning("⚠️ Warning: No APP_TOKEN set in Streamlit Secrets. Access is open.")
        st.session_state["authenticated"] = True
        return

    # 2. Vérification
    if st.session_state["password_input"] == correct_token:
        st.session_state["authenticated"] = True
        del st.session_state["password_input"] # On nettoie le champ
    else:
        st.session_state["authenticated"] = False
        st.error("⛔ Access Denied: Invalid Token")

def logout():
    st.session_state["authenticated"] = False

# --- BACKEND FUNCTIONS ---

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
        return f"Error reading PDF: {str(e)}"

# --- PROMPTS ---

def prompt_olivia(description, countries, output_lang):
    pays_str = ", ".join(countries)
    return f"""
    You are OlivIA, the expert AI in product regulation from the VALHALLAI platform.
    CONTEXT: Product: {description} | Target Markets: {pays_str}
    MISSION: List the applicable regulatory requirements. Be factual and authoritative.
    OUTPUT FORMAT (Markdown): Answer strictly in {output_lang}.
    ## 1. Regulatory Synthesis
    ## 2. Standards & Directives (Table)
    ## 3. Required Documents (Table)
    ## 4. Markings (Table)
    """

def prompt_eva(context, doc_text, output_lang):
    return f"""
    You are EVA, the senior quality auditor of VALHALLAI.
    PRODUCT/REGULATORY CONTEXT: {context}
    ANALYZED DOCUMENT CONTENT: '''{doc_text[:4000]}'''
    MISSION: Verify compliance. Identify inconsistencies, expired dates, or missing mentions.
    OUTPUT: Answer strictly in {output_lang}. Start with status: ✅ COMPLIANT / ⚠️ REVIEW NEEDED / ❌ NON-COMPLIANT.
    """

# --- MAIN APP ORCHESTRATOR ---

def main_app():
    # C'est l'application complète (visible seulement si connecté)
    
    # Sidebar Navigation
    with st.sidebar:
        st.title("VALHALLAI")
        st.markdown("<span style='color:#C8A951; font-weight:bold'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        mode = st.radio("Navigation", ["🏠 Home", "🤖 OlivIA (Analysis)", "🔍 EVA (Audit)"])
        
        st.markdown("---")
        if st.button("🔒 Logout"):
            logout()
            st.rerun()

    # Initialize OpenAI
    api_key = get_api_key()
    client = OpenAI(api_key=api_key) if api_key else None
    
    if not api_key:
        st.warning("⚠️ OpenAI API Key missing in Secrets.")

    # --- HOME PAGE ---
    if "Home" in mode:
        st.header("Welcome to VALHALLAI")
        st.markdown("""
        **The intelligent modular platform that automates and secures regulatory compliance.**
        * **🤖 OlivIA**: Regulatory analysis.
        * **🔍 EVA**: Document auditing.
        """)
        st.info("👈 Select a module from the sidebar.")

    # --- MODULE OLIVIA ---
    elif "OlivIA" in mode:
        st.header("Module OlivIA")
        col1, col2 = st.columns([2, 1])
        with col1:
            desc = st.text_area("Product Description", height=150, placeholder="Ex: Medical device...")
        with col2:
            countries = st.multiselect("Markets", ["EU", "USA", "China", "UK"], default=["EU"])
            output_lang = st.selectbox("Report Language", ["English", "French", "German"])

        if st.button("Start Analysis", type="primary"):
            if client and desc:
                with st.spinner("OlivIA is scanning..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o", 
                            messages=[{"role": "user", "content": prompt_olivia(desc, countries, output_lang)}],
                            temperature=0.2
                        )
                        st.session_state["last_olivia_report"] = response.choices[0].message.content
                        st.success("Analysis Complete!")
                        st.markdown(st.session_state["last_olivia_report"])
                    except Exception as e: st.error(f"Error: {e}")

    # --- MODULE EVA ---
    elif "EVA" in mode:
        st.header("Module EVA")
        default_context = st.session_state.get("last_olivia_report", "")
        col1, col2 = st.columns([2, 1])
        with col1:
             context = st.text_area("Regulatory Context", value=default_context, height=150)
        with col2:
             output_lang_eva = st.selectbox("Audit Language", ["English", "French"])

        uploaded_file = st.file_uploader("Document (PDF)", type="pdf")
        
        if st.button("Start Audit", type="primary"):
            if client and uploaded_file:
                with st.spinner("EVA is analyzing..."):
                    doc_text = extract_text_from_pdf(uploaded_file.read())
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt_eva(context, doc_text, output_lang_eva)}],
                            temperature=0.1
                        )
                        st.markdown(response.choices[0].message.content)
                    except Exception as e: st.error(f"Error: {e}")

# --- ENTRY POINT (LOGIN GATE) ---

def main():
    # Initialisation de l'état de connexion
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Si connecté, on lance l'app
    if st.session_state["authenticated"]:
        main_app()
    
    # Sinon, on affiche l'écran de login
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.title("VALHALLAI")
            st.markdown("### Secure Access")
            st.markdown("Please enter your access token to proceed.")
            
            st.text_input("Access Token", type="password", key="password_input", on_change=check_password)
            
            st.markdown("<br><small>Authorized Personnel Only</small>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

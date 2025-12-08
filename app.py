import streamlit as st
import os
from openai import OpenAI
from pypdf import PdfReader
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="VALHALLAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LUXURY CSS & "NO-BUBBLE" SIDEBAR ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Inter:wght@300;400;600&display=swap');

    /* 1. GLOBAL RESET & STYLE */
    .stApp {
        background-color: #FAFAFA;
        font-family: 'Inter', sans-serif;
        color: #212121;
    }
    
    /* Cacher les éléments Streamlit par défaut */
    header[data-testid="stHeader"] { background: transparent; }
    .stDeployButton { display:none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* 2. TYPOGRAPHIE */
    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif !important;
        color: #295A63 !important;
        letter-spacing: -0.5px;
    }
    
    /* 3. SIDEBAR "PRO" (Transformation du Radio Button) */
    section[data-testid="stSidebar"] {
        background-color: #F4F5F7;
        border-right: 1px solid #E1E3E6;
    }
    
    /* Cacher le cercle du radio button */
    div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    /* Transformer le texte en "Bouton/Lien" */
    div[role="radiogroup"] label {
        margin-bottom: 5px;
        padding: 10px 15px;
        border-radius: 6px;
        transition: all 0.2s;
        border: 1px solid transparent;
    }
    
    /* État Normal */
    div[role="radiogroup"] label p {
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
        font-size: 1rem;
        color: #5E6C75; /* Gris moyen */
    }
    
    /* État Survol (Hover) */
    div[role="radiogroup"] label:hover {
        background-color: rgba(41, 90, 99, 0.05); /* Vert très pâle */
        color: #295A63;
    }
    
    /* État Sélectionné (Active) - C'est un peu tricky en CSS pur Streamlit, 
       on se base sur l'ordre ou on accepte un style simple. 
       L'option choisie sera mise en valeur par le widget lui-même. */
    div[role="radiogroup"] div[data-checked="true"] label {
        background-color: #295A63 !important;
    }
    div[role="radiogroup"] div[data-checked="true"] label p {
        color: #FFFFFF !important;
    }

    /* 4. BOUTONS DASHBOARD (Grosses cartes cliquables) */
    .dashboard-btn-container {
        border: 1px solid #E1E3E6;
        border-radius: 12px;
        padding: 20px;
        background: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s;
        height: 100%;
    }
    .dashboard-btn-container:hover {
        transform: translateY(-3px);
        border-color: #295A63;
    }

    /* 5. INPUTS APPLE-LIKE */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        border-radius: 8px;
        border: 1px solid #E1E3E6;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #295A63;
        box-shadow: 0 0 0 1px #295A63;
    }
    </style>
""", unsafe_allow_html=True)

# --- SECURITY ---
def check_password():
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True
        return
    if st.session_state["password_input"] == correct_token:
        st.session_state["authenticated"] = True
        del st.session_state["password_input"]
    else:
        st.error("Identifiants incorrects.")

def logout():
    st.session_state["authenticated"] = False
    st.rerun()

# --- BACKEND TOOLS ---
def get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def extract_text_from_pdf(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = []
        for page in reader.pages:
            t = page.extract_text() if page.extract_text() else ""
            text.append(t)
        return "\n".join(text)
    except Exception:
        return ""

# --- NAVIGATION HELPERS ---
# Ces fonctions permettent de changer la page depuis le Dashboard
def go_to_olivia():
    st.session_state.nav_selection = "OlivIA (Analysis)"

def go_to_eva():
    st.session_state.nav_selection = "EVA (Audit)"

# --- PROMPTS ---
def prompt_olivia(description, countries, output_lang):
    pays_str = ", ".join(countries)
    return f"""
    You are OlivIA (VALHALLAI Platform).
    Product: {description}
    Markets: {pays_str}
    Task: List regulatory requirements (Directives, Standards, Documentation, Markings).
    Output Language: {output_lang}.
    Format: Markdown Tables. Professional tone.
    """

def prompt_eva(context, doc_text, output_lang):
    return f"""
    You are EVA (VALHALLAI Platform).
    Context: {context}
    Document content: '''{doc_text[:4000]}'''
    Task: Verify compliance against context.
    Output Language: {output_lang}.
    Format: Start with ✅ COMPLIANT / ⚠️ WARNING / ❌ NON-COMPLIANT. Bullet points.
    """

# --- MAIN APPLICATION ---
def main_app():
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("VALHALLAI")
        st.markdown("<div style='margin-top: -20px; color: #558D98; font-size: 0.75rem; letter-spacing: 1px; margin-bottom: 20px;'>REGULATORY SHIELD</div>", unsafe_allow_html=True)
        
        # Initialisation de la navigation par défaut
        if "nav_selection" not in st.session_state:
            st.session_state.nav_selection = "Dashboard"

        # LE MENU PRO (Styled Radio)
        # On utilise "key" pour lier ce widget au session_state
        mode = st.radio(
            "Navigation",
            ["Dashboard", "OlivIA (Analysis)", "EVA (Audit)"],
            key="nav_selection", # C'est ici que la magie opère pour la synchro
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.caption("Secure Connection 🔒")
        if st.button("Log Out"):
            logout()

    # --- API CHECK ---
    api_key = get_api_key()
    client = OpenAI(api_key=api_key) if api_key else None

    # --- DASHBOARD ---
    if mode == "Dashboard":
        st.markdown("# Welcome back.")
        st.markdown("<span style='color:#C8A951; font-weight:600'>Simplify today, amplify tomorrow.</span>", unsafe_allow_html=True)
        st.markdown("###")

        # Layout Cartes Interactives
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("""
            <div class="dashboard-btn-container">
                <h3 style="margin:0">🤖 OlivIA</h3>
                <p style="color:#666; font-size:0.9rem;">Regulatory Intelligence Engine</p>
                <p>Define product DNA and map global requirements.</p>
            </div>
            """, unsafe_allow_html=True)
            # Bouton invisible qui couvre la zone visuelle ou bouton standard en dessous
            st.button("Launch OlivIA Analysis →", on_click=go_to_olivia, use_container_width=True)

        with c2:
            st.markdown("""
            <div class="dashboard-btn-container">
                <h3 style="margin:0">🔍 EVA</h3>
                <p style="color:#666; font-size:0.9rem;">Compliance Verification</p>
                <p>Upload PDFs and audit them against regulations.</p>
            </div>
            """, unsafe_allow_html=True)
            st.button("Launch EVA Audit →", on_click=go_to_eva, use_container_width=True)

    # --- OLIVIA ---
    elif mode == "OlivIA (Analysis)":
        st.title("OlivIA Workspace")
        st.caption("ANALYSE RÉGLEMENTAIRE")
        st.markdown("---")
        
        c1, c2 = st.columns([2,1])
        with c1:
            desc = st.text_area("Product Description", height=200, placeholder="Ex: Class IIa Medical Device, Bluetooth Low Energy...")
        with c2:
            countries = st.multiselect("Target Markets", ["EU (CE)", "USA (FDA)", "UK (UKCA)", "China"], default=["EU (CE)"])
            output_lang = st.selectbox("Report Language", ["English", "French"])
            st.markdown("###")
            run_btn = st.button("Generate Requirements", type="primary", use_container_width=True)

        if run_btn:
            if not client or not desc:
                st.warning("Please provide description and API Key.")
            else:
                with st.spinner("OlivIA is thinking..."):
                    try:
                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role":"user", "content":prompt_olivia(desc, countries, output_lang)}],
                            temperature=0.1
                        )
                        st.session_state["olivia_result"] = res.choices[0].message.content
                        st.rerun()
                    except Exception as e: st.error(str(e))

        if "olivia_result" in st.session_state:
            st.markdown("###")
            st.success("Analysis Generated")
            st.markdown(st.session_state["olivia_result"])

    # --- EVA ---
    elif mode == "EVA (Audit)":
        st.title("EVA Workspace")
        st.caption("AUDIT DOCUMENTAIRE")
        st.markdown("---")

        # Auto-fill context
        default_ctx = st.session_state.get("olivia_result", "")
        
        with st.expander("Context / Requirements", expanded=not bool(default_ctx)):
            ctx = st.text_area("Paste Requirements here", value=default_ctx, height=150)

        c1, c2 = st.columns([2,1])
        with c1:
            f = st.file_uploader("Upload Technical File (PDF)", type="pdf")
        with c2:
            lang_eva = st.selectbox("Audit Language", ["English", "French"])
            st.markdown("###")
            audit_btn = st.button("Run Compliance Audit", type="primary", use_container_width=True)

        if audit_btn:
            if not client or not f:
                st.error("Missing file or API key.")
            else:
                with st.spinner("Reading & Analyzing..."):
                    txt = extract_text_from_pdf(f.read())
                    try:
                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role":"user", "content":prompt_eva(ctx, txt, lang_eva)}],
                            temperature=0.1
                        )
                        st.markdown("### Audit Report")
                        st.markdown(res.choices[0].message.content)
                    except Exception as e: st.error(str(e))

# --- LOGIN ---
def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    if st.session_state["authenticated"]:
        main_app()
    else:
        # Centered Login
        _, c2, _ = st.columns([1,1.5,1])
        with c2:
            st.markdown("<br><br><h1 style='text-align:center'>VALHALLAI</h1>", unsafe_allow_html=True)
            st.text_input("Access Token", type="password", key="password_input", on_change=check_password)

if __name__ == "__main__":
    main()

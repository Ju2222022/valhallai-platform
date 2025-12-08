import streamlit as st
import os
import io
import base64
import uuid
from datetime import datetime
from openai import OpenAI
from pypdf import PdfReader
import gspread 
from tavily import TavilyClient  # <--- Le moteur de recherche

# Imports locaux
import config
from utils_pdf import generate_pdf_report

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
        "last_olivia_id": None, 
        "last_eva_report": None,
        "last_eva_id": None,
        "editing_market_index": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 3. GESTION DES DONNÉES (GOOGLE SHEETS)
# =============================================================================
@st.cache_resource
def get_gsheet_workbook():
    """Retourne le CLASSEUR entier."""
    try:
        if "service_account" not in st.secrets:
            st.error("⚠️ Secrets 'service_account' not found.")
            return None
            
        sa_secrets = st.secrets["service_account"]
        raw_key = sa_secrets.get("private_key", "")
        clean_key = raw_key.replace("\\n", "\n")
        
        if "-----BEGIN PRIVATE KEY-----" not in clean_key:
            clean_key = "-----BEGIN PRIVATE KEY-----\n" + clean_key.strip()
        if "-----END PRIVATE KEY-----" not in clean_key:
            clean_key = clean_key.strip() + "\n-----END PRIVATE KEY-----"
            
        creds_dict = {
            "type": sa_secrets["type"],
            "project_id": sa_secrets["project_id"],
            "private_key_id": sa_secrets["private_key_id"],
            "private_key": clean_key,
            "client_email": sa_secrets["client_email"],
            "client_id": sa_secrets["client_id"],
            "auth_uri": sa_secrets["auth_uri"],
            "token_uri": sa_secrets["token_uri"],
            "auth_provider_x509_cert_url": sa_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": sa_secrets["client_x509_cert_url"]
        }

        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open_by_url(st.secrets["gsheets"]["url"])
        
    except Exception as e:
        st.error(f"❌ Google Sheets Connection Error: {e}")
        return None

def get_markets_sheet():
    wb = get_gsheet_workbook()
    return wb.sheet1 if wb else None

def log_usage(report_type, report_id, details="", extra_metrics=""):
    """
    Enregistre l'activité dans l'onglet 'Logs'.
    - details (Col E) : Description produit ou nom fichier
    - extra_metrics (Col F) : Nombre de marchés, Web Search utilisé, etc.
    """
    wb = get_gsheet_workbook()
    if not wb: return

    try:
        try:
            log_sheet = wb.worksheet("Logs")
        except:
            # Création si inexistant
            log_sheet = wb.add_worksheet(title="Logs", rows=1000, cols=6)
            log_sheet.append_row(["Date", "Time", "Report ID", "Type", "Details", "Metrics"])

        now = datetime.now()
        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            report_id,
            report_type,
            details,        # Col E
            extra_metrics   # Col F
        ]
        log_sheet.append_row(row)
        
    except Exception as e:
        print(f"Logging failed: {e}")

def get_markets():
    sheet = get_markets_sheet()
    if sheet:
        try:
            vals = sheet.col_values(1)
            return (vals if vals else []), True
        except:
            return config.DEFAULT_MARKETS, False
    return config.DEFAULT_MARKETS, False

def add_market(market_name):
    sheet = get_markets_sheet()
    if sheet:
        try:
            current = sheet.col_values(1)
            if market_name not in current:
                sheet.append_row([market_name])
                st.cache_data.clear()
                return True
        except Exception as e:
            st.error(f"Write Error: {e}")
    return False

def remove_market(index):
    sheet = get_markets_sheet()
    if sheet:
        try:
            sheet.delete_rows(index + 1)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Delete Error: {e}")

def update_market(index, new_name):
    sheet = get_markets_sheet()
    if sheet:
        try:
            sheet.update_cell(index + 1, 1, new_name)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Update Error: {e}")

# =============================================================================
# 4. FONCTIONS UTILITAIRES & DEEP SEARCH
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

def run_deep_search(query):
    """Exécute une recherche web via Tavily (pour le RAG)."""
    try:
        tavily_key = st.secrets.get("TAVILY_API_KEY")
        if not tavily_key:
            return None, "Tavily Key Missing"
            
        tavily = TavilyClient(api_key=tavily_key)
        
        # Recherche contextuelle
        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=3,
            include_domains=["europa.eu", "eur-lex.europa.eu/oj", "fda.gov", "iso.org", "gov.uk", "reuters.com"] 
        )
        
        context_text = "### LIVE REGULATORY DATA (FROM WEB):\n"
        for result in response['results']:
            context_text += f"- SOURCE: {result['title']}\n  URL: {result['url']}\n  CONTENT: {result['content'][:600]}...\n\n"
            
        return context_text, None
    except Exception as e:
        return None, str(e)

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
        return f"{config.ERRORS['pdf_error']} Detail: {str(e)}"

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
        st.error("Admin Token missing in secrets."); return
    
    if st.session_state.get("admin_pass_input", "") == admin_token:
        st.session_state["admin_authenticated"] = True
        del st.session_state["admin_pass_input"]
    else:
        st.error("Access Denied.")

def logout():
    st.session_state["authenticated"] = False
    st.session_state["admin_authenticated"] = False
    st.session_state["current_page"] = "Dashboard"

# =============================================================================
# 6. PROMPTS IA (EXPERT LEVEL)
# =============================================================================
def create_olivia_prompt(description, countries):
    markets_str = ", ".join(countries)
    return f"""
    ROLE: You are OlivIA, a Senior Regulatory Affairs Strategy Consultant at VALHALLAI.
    
    INPUT DATA:
    - Product Description: "{description}"
    - Target Markets: {markets_str}
    
    MISSION:
    Conduct a comprehensive regulatory landscape analysis. Your goal is to provide a clear roadmap for market entry.
    
    STRICT OUTPUT STRUCTURE (Markdown):
    
    ## 1. Executive Summary
    Brief overview of the product classification and complexity level (1 paragraph).
    
    ## 2. Product Classification & Pathway
    For each market, determine the classification (e.g., Class I/II/III for MedTech, or General Consumer Goods) and the required conformity assessment route.
    
    ## 3. Applicable Regulations & Directives
    List the binding laws.
    | Region | Regulation ID | Title | Key Requirement |
    |---|---|---|---|
    | ... | ... | ... | ... |
    
    ## 4. Mandatory Standards (The "Technical Core")
    List specific ISO/IEC/EN standards required for testing.
    | Standard ID | Title | Type (Safety/EMC/Performance) |
    |---|---|---|
    | ... | ... | ... |
    
    ## 5. Technical Documentation & Labeling
    Bullet points list of required documents (e.g., Technical File, DoC, IFU) and specific labeling symbols required.
    
    ## 6. Action Plan
    A numbered list of 5-7 concrete steps the user must take next.
    
    CONSTRAINTS:
    - Language: STRICTLY ENGLISH.
    - Translate all headers/titles to English.
    - Tone: Professional, authoritative, and precise.
    - No filler text, focus on actionable data.
    """

def create_eva_prompt(context, doc_text):
    return f"""
    ROLE: You are EVA, a Lead Technical Auditor and Compliance Officer at VALHALLAI.
    
    INPUT DATA:
    1. REGULATORY CONTEXT (The Rules):
    {context}
    
    2. TECHNICAL DOCUMENTATION (The Evidence):
    '''{doc_text[:10000]}''' 
    (Note: Text truncated for analysis limit)
    
    MISSION:
    Audit the provided documentation against the Regulatory Context. Find gaps, inconsistencies, or missing evidence.
    
    STRICT OUTPUT STRUCTURE (Markdown):
    
    ## 1. Audit Verdict
    **Overall Status:** [COMPLIANT / PARTIALLY COMPLIANT / NON-COMPLIANT]
    Summary of the findings in 2-3 sentences.
    
    ## 2. Gap Analysis Table
    Analyze specific requirements mentioned in the context.
    | Requirement | Status (✅/⚠️/❌) | Evidence Found in Doc | Missing / Recommendation |
    |---|---|---|---|
    | [Requirement Name] | [Icon] | [Quote or Page Ref] | [Action needed] |
    
    ## 3. Critical Risks
    List any blocking issues that prevent market entry immediately.
    
    ## 4. Improvement Recommendations
    Bulleted list of technical improvements for the documentation.
    
    CONSTRAINTS:
    - Language: STRICTLY ENGLISH.
    - Translate all headers/titles to English.
    - Be strict: If evidence is vague, mark it as ⚠️.
    """

# --- FONCTIONS VISUELLES ---
def get_logo_svg():
    colors = config.COLORS["dark" if st.session_state["dark_mode"] else "light"]
    c1, c2 = colors["primary"], colors["accent"]
    c3, c4 = "#1A3C42", "#E6D5A7"
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
    st.title("⚙️ Admin Console")
    st.markdown("---")
    
    if not st.session_state["admin_authenticated"]:
        st.markdown("### 🔐 Restricted Access")
        st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password)
        return
    
    wb = get_gsheet_workbook()
    col_status, col_refresh = st.columns([3, 1])
    with col_status:
        if wb: st.success(f"✅ Database Connected: {wb.title}")
        else: st.error("❌ Connection Failed.")
    with col_refresh:
        if st.button("🔄 Force Refresh"):
            st.cache_data.clear(); st.rerun()

    current_markets, is_live = get_markets()
    if not is_live: st.warning("🟠 Default List (Offline)")
    else: st.info("🟢 Source: Live Database")

    st.markdown("#### Add New Market")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        new = col1.text_input("Market Name")
        if col2.form_submit_button("Add"):
            if new and add_market(new): st.success(f"Added: {new}"); st.rerun()
            else: st.error("Error")

    st.markdown("#### Active Markets")
    for i, m in enumerate(current_markets):
        c1, c2, c3 = st.columns([4, 1, 1])
        if st.session_state.get("editing_market_index") != i:
            c1.info(f"🌍 {m}")
            if c2.button("✏️", key=f"ed_{i}"): st.session_state["editing_market_index"] = i; st.rerun()
            if c3.button("🗑️", key=f"del_{i}"): remove_market(i); st.rerun()
        else:
            new_val = c1.text_input("Edit", value=m, key=f"val_{i}", label_visibility="collapsed")
            if c2.button("💾", key=f"save_{i}"):
                update_market(i, new_val)
                st.session_state["editing_market_index"] = None; st.rerun()
            if c3.button("❌", key=f"cancel_{i}"):
                st.session_state["editing_market_index"] = None; st.rerun()

def page_olivia():
    agent = config.AGENTS["olivia"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    
    available_markets, _ = get_markets()
    
    col1, col2 = st.columns([2, 1])
    with col1: desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
    with col2:
        countries = st.multiselect("Target Markets", available_markets, default=[available_markets[0]] if available_markets else None)
        
        st.write("")
        if st.button("Generate Report", type="primary"):
            client = get_openai_client()
            if client and desc:
                # 1. LOGIQUE HYBRIDE : DEEP SEARCH
                # On active la recherche pour les marchés complexes
                target_regions = ["EU", "USA", "China", "UK"]
                use_deep_search = any(r in str(countries) for r in target_regions)
                deep_context = ""
                
                status_msg = "Analyzing... 🌍 Deep Search Active" if use_deep_search else "Analyzing..."
                
                with st.spinner(status_msg):
                    try:
                        # Etape A : Recherche Web (Tavily)
                        if use_deep_search:
                            search_q = f"Latest regulatory requirements standards for {desc} in {', '.join(countries)}"
                            web_data, error = run_deep_search(search_q)
                            if web_data: deep_context = web_data
                        
                        # Etape B : Construction du Prompt Final
                        final_prompt = create_olivia_prompt(desc, countries)
                        if deep_context:
                            final_prompt += f"\n\n[IMPORTANT] USE THIS REAL-TIME WEB DATA TO CITE REGULATIONS:\n{deep_context}"

                        # Etape C : Appel GPT-4o
                        res = client.chat.completions.create(
                            model=config.OPENAI_MODEL,
                            messages=[{"role": "user", "content": final_prompt}],
                            temperature=config.OPENAI_TEMPERATURE
                        )
                        st.session_state["last_olivia_report"] = res.choices[0].message.content
                        
                        # Etape D : Logging & ID
                        new_id = str(uuid.uuid4())
                        st.session_state["last_olivia_id"] = new_id
                        
                        log_meta = f"Mkts: {len(countries)} | Web: {'YES' if deep_context else 'NO'}"
                        log_usage("OlivIA", new_id, desc, log_meta)
                        
                        st.rerun()
                    except Exception as e: st.error(str(e))
    
    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("✅ Analysis Generated Successfully")
        st.markdown(st.session_state["last_olivia_report"])
        
        st.markdown("---")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        file_name = f"VALHALLAI_Report_{timestamp}.pdf"
        report_id = st.session_state.get("last_olivia_id", "Unknown-ID")
        
        col_space, col_btn = st.columns([4, 1])
        with col_btn:
            pdf_data = generate_pdf_report("Regulatory Analysis Report", st.session_state["last_olivia_report"], report_id)
            st.download_button("📥 Download PDF", pdf_data, file_name, "application/pdf", use_container_width=True)

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
    
    if st.button("Run Audit", type="primary"):
        client = get_openai_client()
        if client and up:
            with st.spinner("Auditing..."):
                txt = extract_text_from_pdf(up.read())
                try:
                    res = client.chat.completions.create(
                        model="gpt-4o", 
                        messages=[{"role":"user","content":create_eva_prompt(ctx,txt)}], 
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    st.session_state["last_eva_report"] = res.choices[0].message.content
                    new_id = str(uuid.uuid4())
                    st.session_state["last_eva_id"] = new_id
                    log_usage("EVA", new_id, f"File: {up.name}", "N/A")
                except Exception as e: st.error(str(e))

    if st.session_state.get("last_eva_report"):
        st.markdown("### Audit Results")
        st.markdown(st.session_state["last_eva_report"])
        st.markdown("---")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        file_name = f"VALHALLAI_Audit_{timestamp}.pdf"
        report_id = st.session_state.get("last_eva_id", "Unknown-ID")
        col_space, col_btn = st.columns([4, 1])
        with col_btn:
            pdf_data = generate_pdf_report("Compliance Audit Report", st.session_state["last_eva_report"], report_id)
            st.download_button("📥 Download PDF", pdf_data, file_name, "application/pdf", use_container_width=True)

def render_sidebar():
    with st.sidebar:
        logo_html = get_logo_html()
        st.markdown(f"""<div style="display: flex; align-items: center; margin-bottom: 1rem;">{logo_html}<div><div class="logo-text">{config.APP_NAME}</div><div class="logo-sub">{config.APP_TAGLINE}</div></div></div>""", unsafe_allow_html=True)
        st.markdown("---")
        pages = ["Dashboard", "OlivIA", "EVA", "Admin"]
        current = st.session_state["current_page"]
        idx = pages.index(current) if current in pages else 0
        sel = st.radio("NAVIGATION", pages, index=idx)
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

import streamlit as st
import os
import io
import base64
import uuid
import json
from datetime import datetime
from openai import OpenAI
from pypdf import PdfReader
import gspread 
from tavily import TavilyClient

# Imports locaux
import config
from utils_pdf import generate_pdf_report

# =============================================================================
# 0. CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLE CSS "FORCE BRANDING" (Pour écraser le thème par défaut) ---
def inject_custom_css():
    # Couleurs Valhallai
    C_GREEN = "#295A63"
    C_GOLD = "#C8A951"
    C_DARK = "#1A3C42"
    
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Inter:wght@400;500;600&display=swap');
    
    /* 1. TYPOGRAPHIE & TITRES */
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    h1, h2, h3 {{ 
        font-family: 'Montserrat', sans-serif !important; 
        color: {C_GREEN} !important; 
    }}
    
    /* 2. FORCER LES BOUTONS EN VERT (Override Streamlit Red) */
    div.stButton > button:first-child {{
        background-color: {C_GREEN} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease;
    }}
    div.stButton > button:first-child:hover {{
        background-color: {C_GOLD} !important; /* Devient Or au survol */
        color: black !important;
        transform: translateY(-2px);
    }}
    div.stButton > button:first-child:active {{
        background-color: {C_DARK} !important;
    }}

    /* 3. INPUTS & CHAMPS (Bordure au focus) */
    .stTextInput > div > div {{
        border-radius: 8px !important;
    }}
    .stTextInput > div > div:focus-within {{
        border-color: {C_GREEN} !important;
        box-shadow: 0 0 0 1px {C_GREEN} !important;
    }}

    /* 4. SIDEBAR NAVIGATION (Radio Buttons) */
    div[role="radiogroup"] label[data-checked="true"] {{
        color: {C_GREEN} !important;
        font-weight: bold !important;
    }}
    div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {{
        font-size: 1rem;
    }}

    /* 5. CARTE INFO (Dashboard) */
    .info-card {{
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        background-color: white;
        height: 220px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    /* En mode sombre (détecté via CSS media query ou classe streamlit) */
    @media (prefers-color-scheme: dark) {{
        .info-card {{ background-color: #262730; border-color: #444; }}
        h1, h2, h3 {{ color: {C_GOLD} !important; }}
    }}
    </style>
    """, unsafe_allow_html=True)

# Configuration MIA
if "mia" not in config.AGENTS:
    config.AGENTS["mia"] = {
        "name": "MIA",
        "icon": "📡",
        "description": "Market Intelligence Agent (Regulatory Watch & Monitoring)."
    }

DEFAULT_DOMAINS = [
    "eur-lex.europa.eu", "europa.eu", "fda.gov", "iso.org", "gov.uk", 
    "reuters.com", "raps.org", "medtechdive.com"
]

# =============================================================================
# 1. SESSION STATE
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
        "last_mia_results": None,
        "editing_market_index": None,
        "editing_domain_index": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 2. GESTION DES DONNÉES
# =============================================================================
@st.cache_resource
def get_gsheet_workbook():
    try:
        if "service_account" not in st.secrets: return None
        sa_secrets = st.secrets["service_account"]
        raw_key = sa_secrets.get("private_key", "").replace("\\n", "\n")
        if "-----BEGIN" not in raw_key: raw_key = "-----BEGIN PRIVATE KEY-----\n" + raw_key.strip()
        if "-----END" not in raw_key: raw_key = raw_key.strip() + "\n-----END PRIVATE KEY-----"
        
        creds = {
            "type": sa_secrets["type"], "project_id": sa_secrets["project_id"],
            "private_key_id": sa_secrets["private_key_id"], "private_key": raw_key,
            "client_email": sa_secrets["client_email"], "client_id": sa_secrets["client_id"],
            "auth_uri": sa_secrets["auth_uri"], "token_uri": sa_secrets["token_uri"],
            "auth_provider_x509_cert_url": sa_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": sa_secrets["client_x509_cert_url"]
        }
        gc = gspread.service_account_from_dict(creds)
        return gc.open_by_url(st.secrets["gsheets"]["url"])
    except: return None

def log_usage(report_type, report_id, details="", extra_metrics=""):
    wb = get_gsheet_workbook()
    if not wb: return
    try:
        try: log_sheet = wb.worksheet("Logs")
        except: log_sheet = wb.add_worksheet(title="Logs", rows=1000, cols=6)
        if not log_sheet.cell(1, 1).value:
            log_sheet.update("A1:F1", [["Date", "Time", "Report ID", "Type", "Details", "Metrics"]])
        now = datetime.now()
        log_sheet.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), report_id, report_type, details, extra_metrics])
    except: pass

def get_markets():
    wb = get_gsheet_workbook()
    if wb:
        try: return (wb.sheet1.col_values(1) if wb.sheet1.col_values(1) else []), True
        except: pass
    return config.DEFAULT_MARKETS, False

def add_market(name):
    wb = get_gsheet_workbook()
    if wb:
        try:
            if name not in wb.sheet1.col_values(1): wb.sheet1.append_row([name]); st.cache_data.clear(); return True
        except: pass
    return False

def remove_market(idx):
    wb = get_gsheet_workbook()
    if wb:
        try: wb.sheet1.delete_rows(idx + 1); st.cache_data.clear()
        except: pass

def update_market(idx, name):
    wb = get_gsheet_workbook()
    if wb:
        try: wb.sheet1.update_cell(idx + 1, 1, name); st.cache_data.clear()
        except: pass

def get_domains():
    wb = get_gsheet_workbook()
    if wb:
        try:
            try: sheet = wb.worksheet("Watch_domains")
            except: 
                sheet = wb.add_worksheet("Watch_domains", 100, 1)
                for d in DEFAULT_DOMAINS: sheet.append_row([d])
            return (sheet.col_values(1) if sheet.col_values(1) else DEFAULT_DOMAINS), True
        except: pass
    return DEFAULT_DOMAINS, False

def add_domain(name):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sh = wb.worksheet("Watch_domains")
            if name not in sh.col_values(1): sh.append_row([name]); st.cache_data.clear(); return True
        except: pass
    return False

def remove_domain(idx):
    wb = get_gsheet_workbook()
    if wb:
        try: wb.worksheet("Watch_domains").delete_rows(idx + 1); st.cache_data.clear()
        except: pass

def update_domain(idx, name):
    wb = get_gsheet_workbook()
    if wb:
        try: wb.worksheet("Watch_domains").update_cell(idx + 1, 1, name); st.cache_data.clear()
        except: pass

# =============================================================================
# 4. API & SEARCH & CACHING
# =============================================================================
def get_api_key(): return st.secrets.get("OPENAI_API_KEY")
def get_openai_client():
    k = get_api_key()
    return OpenAI(api_key=k) if k else None

@st.cache_data(show_spinner=False, ttl=3600)
def cached_run_deep_search(query, days=None):
    try:
        k = st.secrets.get("TAVILY_API_KEY")
        if not k: return None, "Key Missing"
        tavily = TavilyClient(api_key=k)
        doms, _ = get_domains()
        params = {"query": query, "search_depth": "advanced", "max_results": 5 if days else 3, "include_domains": doms}
        if days: params["days"] = days
        response = tavily.search(**params)
        txt = "### WEB RESULTS:\n"
        for r in response['results']:
            txt += f"- Title: {r['title']}\n  URL: {r['url']}\n  Content: {r['content'][:800]}...\n\n"
        return txt, None
    except Exception as e: return None, str(e)

@st.cache_data(show_spinner=False)
def cached_ai_generation(prompt, model, temp, json_mode=False):
    client = get_openai_client()
    if not client: return None
    kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temp}
    if json_mode: kwargs["response_format"] = {"type": "json_object"}
    res = client.chat.completions.create(**kwargs)
    return res.choices[0].message.content

def extract_text_from_pdf(b):
    try:
        r = PdfReader(io.BytesIO(b)); txt=[]
        for p in r.pages: txt.append(p.extract_text() or "")
        return "\n".join(txt)
    except Exception as e: return str(e)

# =============================================================================
# 5. AUTH & PROMPTS
# =============================================================================
def check_password():
    if not st.secrets.get("APP_TOKEN"): st.session_state["authenticated"]=True; return
    if st.session_state.get("password_input")==st.secrets["APP_TOKEN"]:
        st.session_state["authenticated"]=True; del st.session_state["password_input"]
    else: st.error("Access Denied")

def check_admin_password():
    if st.session_state.get("admin_pass_input")==st.secrets.get("ADMIN_TOKEN"):
        st.session_state["admin_authenticated"]=True; del st.session_state["admin_pass_input"]
    else: st.error("Denied")

def logout():
    st.session_state["authenticated"]=False
    st.session_state["admin_authenticated"]=False
    st.session_state["current_page"]="Dashboard"

def create_olivia_prompt(desc, countries):
    return f"""ROLE: Senior Regulatory Consultant (VALHALLAI). Product: "{desc}" | Markets: {', '.join(countries)}.
    Mission: Comprehensive regulatory analysis. Output: Strict English Markdown.
    Structure: 1. Executive Summary, 2. Classification, 3. Regulations Table, 4. Standards Table, 5. Docs/Labeling, 6. Action Plan."""

def create_eva_prompt(ctx, doc):
    return f"""ROLE: Lead Auditor (VALHALLAI). Rules: {ctx}. Doc: '''{doc[:10000]}'''.
    Mission: Compliance Audit. Output: Strict English Markdown.
    Structure: 1. Verdict, 2. Gap Table (Requirement|Status|Evidence|Missing), 3. Risks, 4. Recommendations."""

def create_mia_prompt(topic, markets, raw_search_data, timeframe_label):
    return f"""
    ROLE: You are MIA (Market Intelligence Agent).
    CONTEXT: User monitoring: "{topic}" | Markets: {', '.join(markets)}
    SELECTED TIMEFRAME: {timeframe_label}
    RAW SEARCH DATA: {raw_search_data}
    MISSION: Filter raw data. Keep only relevant updates.
    OUTPUT FORMAT (Strict JSON):
    {{
        "executive_summary": "Summary...",
        "items": [
            {{ "title": "...", "date": "YYYY-MM-DD", "source_name": "...", "url": "...", "summary": "...", "tags": ["Tag1"], "impact": "High/Medium/Low", "category": "Regulation" }}
        ]
    }}
    """

def get_logo_html():
    svg = """<svg width="60" height="60" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="#295A63"/>
        <rect x="52" y="10" width="38" height="38" rx="8" fill="#C8A951"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="#1A3C42"/>
        <rect x="52" y="52" width="38" height="38" rx="8" fill="#E6D5A7"/>
    </svg>"""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="vertical-align: middle; margin-right: 15px;">'

# =============================================================================
# 7. PAGES UI
# =============================================================================
def page_admin():
    st.title("⚙️ Admin Console"); st.markdown("---")
    if not st.session_state["admin_authenticated"]:
        st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password); return
    
    wb = get_gsheet_workbook()
    c1, c2 = st.columns([3, 1])
    c1.success(f"✅ DB: {wb.title}" if wb else "❌ DB Error")
    if c2.button("🔄 Refresh"): st.cache_data.clear(); st.rerun()

    tm, td = st.tabs(["🌍 Markets", "🕵️‍♂️ Sources"])
    with tm:
        mkts, _ = get_markets()
        with st.form("add_m"):
            c1, c2 = st.columns([3,1]); new = c1.text_input("Name")
            if c2.form_submit_button("Add") and new: add_market(new); st.rerun()
        for i, m in enumerate(mkts):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.info(f"🌍 {m}")
            if c3.button("🗑️", key=f"dm{i}"): remove_market(i); st.rerun()
    with td:
        doms, _ = get_domains()
        st.info("💡 Deep Search Sources.")
        with st.form("add_d"):
            c1, c2 = st.columns([3,1]); new = c1.text_input("Domain")
            if c2.form_submit_button("Add") and new: add_domain(new); st.rerun()
        for i, d in enumerate(doms):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.success(f"🌐 {d}")
            if c3.button("🗑️", key=f"dd{i}"): remove_domain(i); st.rerun()

def page_mia():
    st.title("📡 MIA Watch Tower"); st.markdown("---")
    markets, _ = get_markets()
    
    # --- MISE EN PAGE : 2 Lignes pour aérer ---
    c1, c2 = st.columns([1, 1])
    with c1: 
        topic = st.text_input("🔎 Product / Topic", placeholder="e.g. Cybersecurity for SaMD", key="mia_topic")
    with c2:
        safe_markets = [markets[0]] if markets else []
        selected_markets = st.multiselect("🌍 Markets", markets, default=safe_markets, key="mia_mkts")
    
    c3, c4 = st.columns([1, 2])
    with c3:
        time_map = {"⚡ 30 Days": 30, "📅 12 Months": 365, "🏛️ 3 Years": 1095}
        selected_label = st.selectbox("⏱️ Timeframe", list(time_map.keys()), index=1, key="mia_time")
        days_limit = time_map[selected_label]
    
    with c4:
        st.write("") # Spacer
        st.write("") 
        launch = st.button("🚀 Launch Monitoring", type="primary", use_container_width=True)

    if launch and topic:
        with st.spinner(f"📡 MIA is scanning... ({selected_label})"):
            query = f"New regulations guidelines for {topic} in {', '.join(selected_markets)} released recently"
            raw_data, error = cached_run_deep_search(query, days=days_limit)
            if not raw_data: st.error(f"Search failed: {error}")
            else:
                prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
                json_str = cached_ai_generation(prompt, config.OPENAI_MODEL, 0.1, json_mode=True)
                if json_str:
                    st.session_state["last_mia_results"] = json.loads(json_str)
                    log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label}")
                    # Pas de rerun, on laisse afficher
                else: st.error("Analysis failed.")

    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("### 📋 Monitoring Report")
        st.info(f"**Executive Summary:** {results.get('executive_summary', 'No summary.')}")
        
        # FILTRES ALIGNÉS
        f1, f2, f3 = st.columns(3)
        with f1:
            cats = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            sel_types = st.multiselect("🗂️ Type", cats, default=cats, key="mia_type")
        with f2:
            sel_impacts = st.multiselect("🌪️ Impact", ["High", "Medium", "Low"], default=["High", "Medium", "Low"], key="mia_imp")
        with f3:
            st.caption("Legend:")
            st.markdown("🔴 High | 🟡 Medium | 🟢 Low")
        
        st.markdown("---")
        items = results.get("items", [])
        filtered = [i for i in items if i.get('impact','Low').capitalize() in sel_impacts and i.get('category','News').capitalize() in sel_types]
        
        if not filtered: st.warning("No updates found.")
        for item in filtered:
            impact = item.get('impact', 'Low').lower()
            cat = item.get('category', 'News')
            icon = "🔴" if impact=='high' else "🟡" if impact=='medium' else "🟢"
            cat_map = {"Regulation":"🏛️", "Standard":"📏", "Guidance":"📘", "Enforcement":"📢", "News":"📰"}
            
            with st.container():
                st.markdown(f"""
                <div class="info-card" style="min-height:auto; padding:1.5rem; margin-bottom:1rem;">
                    <div style="display:flex;">
                        <div style="font-size:1.5rem; margin-right:15px;">{icon}</div>
                        <div>
                            <div style="font-weight:bold; font-size:1.1em;">
                                <a href="{item['url']}" target="_blank" style="text-decoration:none; color:inherit;">
                                    {cat_map.get(cat,'📄')} {item['title']}
                                </a>
                            </div>
                            <div style="font-size:0.85em; opacity:0.7; margin-bottom:5px;">
                                📅 {item['date']} | 🏛️ {item['source_name']}
                            </div>
                            <div>{item['summary']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

def page_olivia():
    st.title("🤖 OlivIA Workspace")
    markets, _ = get_markets()
    c1, c2 = st.columns([2, 1])
    with c1: desc = st.text_area("Product Definition", height=200, key="oli_desc")
    with c2: 
        safe_mkts = [markets[0]] if markets else []
        ctrys = st.multiselect("Target Markets", markets, default=safe_mkts, key="oli_mkts")
        st.write(""); gen = st.button("Generate Report", type="primary", key="oli_btn")
    
    if gen and desc:
        with st.spinner("Analyzing..."):
            try:
                use_ds = any(x in str(ctrys) for x in ["EU","USA","China"])
                ctx = ""
                if use_ds: 
                    d, _ = cached_run_deep_search(f"Regulations for {desc} in {ctrys}")
                    if d: ctx = d
                p = create_olivia_prompt(desc, ctrys)
                if ctx: p += f"\n\nCONTEXT:\n{ctx}"
                resp = cached_ai_generation(p, config.OPENAI_MODEL, 0.1)
                st.session_state["last_olivia_report"] = resp
                st.session_state["last_olivia_id"] = str(uuid.uuid4())
                log_usage("OlivIA", st.session_state["last_olivia_id"], desc, f"Mkts:{len(ctrys)}")
                st.toast("Done!", icon="✅")
            except Exception as e: st.error(str(e))

    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("✅ Analysis Generated")
        st.markdown(st.session_state["last_olivia_report"])
        st.markdown("---")
        # Correction PDF Crash
        pdf_data = generate_pdf_report("Regulatory Analysis Report", st.session_state["last_olivia_report"], st.session_state.get("last_olivia_id", "ID"))
        if pdf_data:
             st.download_button("📥 Download PDF", pdf_data, f"VALHALLAI_Report.pdf", "application/pdf")
        else:
             st.warning("PDF generation failed.")

def page_eva():
    st.title("🔍 EVA Workspace")
    ctx = st.text_area("Context", value=st.session_state.get("last_olivia_report", ""), key="eva_ctx")
    up = st.file_uploader("PDF", type="pdf", key="eva_up")
    if st.button("Run Audit", type="primary", key="eva_btn") and up:
        with st.spinner("Auditing..."):
            try:
                txt = extract_text_from_pdf(up.read())
                resp = cached_ai_generation(create_eva_prompt(ctx, txt), "gpt-4o", 0.1)
                st.session_state["last_eva_report"] = resp
                st.session_state["last_eva_id"] = str(uuid.uuid4())
                log_usage("EVA", st.session_state["last_eva_id"], f"File: {up.name}")
                st.toast("Done!", icon="🔍")
            except Exception as e: st.error(str(e))
    
    if st.session_state.get("last_eva_report"):
        st.markdown("### Audit Results")
        st.markdown(st.session_state["last_eva_report"])
        st.markdown("---")
        # Correction PDF Crash
        pdf_data = generate_pdf_report("Compliance Audit Report", st.session_state["last_eva_report"], st.session_state.get("last_eva_id", "ID"))
        if pdf_data:
            st.download_button("📥 Download PDF", pdf_data, f"VALHALLAI_Audit.pdf", "application/pdf")
        else:
            st.warning("PDF generation failed.")

def page_dashboard():
    st.title("Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    
    # CSS Custom pour les cartes (Définition locale pour être sûr)
    st.markdown("""
    <style>
    .dash-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ddd;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .dark-mode .dash-card { background-color: #262730; border-color: #444; }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    
    with c1: 
        st.markdown(f"""
        <div class="dash-card">
            <h3>🤖 OlivIA</h3>
            <p>{config.AGENTS['olivia']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Launch OlivIA ->", key="dash_oli"): 
            st.session_state["current_page"] = "OlivIA"
            st.rerun()
    with c2: 
        st.markdown(f"""
        <div class="dash-card">
            <h3>🔍 EVA</h3>
            <p>{config.AGENTS['eva']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Launch EVA ->", key="dash_eva"): 
            st.session_state["current_page"] = "EVA"
            st.rerun()
    with c3: 
        st.markdown(f"""
        <div class="dash-card">
            <h3>{config.AGENTS['mia']['icon']} {config.AGENTS['mia']['name']}</h3>
            <p>{config.AGENTS['mia']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Launch MIA ->", key="dash_mia"): 
            st.session_state["current_page"] = "MIA"
            st.rerun()

def render_sidebar():
    with st.sidebar:
        if st.button("🏠 Dashboard", use_container_width=True):
             st.session_state["current_page"] = "Dashboard"
             st.rerun()

        st.markdown(get_logo_html(), unsafe_allow_html=True)
        st.markdown(f"<div class='logo-text'>{config.APP_NAME}</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        pages = ["Dashboard", "OlivIA", "EVA", "MIA", "Admin"]
        curr = st.session_state["current_page"]
        
        idx = pages.index(curr) if curr in pages else 0
        selected = st.radio("NAV", pages, index=idx, label_visibility="collapsed")
        
        if selected != curr:
            st.session_state["current_page"] = selected
            st.rerun()

        st.markdown("---")
        
        # Toggle Dark Mode
        is_dark = st.checkbox("🌙 Night Mode", value=st.session_state["dark_mode"])
        if is_dark != st.session_state["dark_mode"]:
            st.session_state["dark_mode"] = is_dark
            st.rerun()

        st.markdown("---")
        if st.button("Log Out"): logout(); st.rerun()

def render_login():
    # Fond Vert Valhallai Forcé via CSS spécifique au login
    st.markdown("""
    <style>
    .stApp { background-color: #295A63; }
    .login-box {
        background-color: white;
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.container():
            st.markdown(f"""
            <div class="login-box">
                {get_logo_html()}
                <h1 style="color:#295A63; margin:0;">{config.APP_NAME}</h1>
                <p style="color:#C8A951; font-weight:bold; letter-spacing:2px;">{config.APP_TAGLINE}</p>
            </div>
            """, unsafe_allow_html=True)
            st.write("")
            st.text_input("🔐 Enter Security Token", type="password", key="password_input", on_change=check_password)

def main():
    inject_custom_css() # Injection du style global (Boutons verts, Font)
    if st.session_state["authenticated"]:
        render_sidebar()
        p = st.session_state["current_page"]
        if p == "Dashboard": page_dashboard()
        elif p == "OlivIA": page_olivia()
        elif p == "EVA": page_eva()
        elif p == "MIA": page_mia()
        elif p == "Admin": page_admin()
        else: page_dashboard()
    else: render_login()

if __name__ == "__main__": main()

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
# 0. CONFIGURATION & SETUP
# =============================================================================
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETTE DE COULEURS (Hardcoded pour la stabilité du design) ---
C_GREEN_DARK = "#1A3C42"   # Fond sombre / Sidebar Dark
C_GREEN_MAIN = "#295A63"   # Couleur Principale (Boutons, Titres)
C_GOLD       = "#C8A951"   # Accent (Focus, Hover)
C_GOLD_LIGHT = "#E6D5A7"   # Fond léger
C_BG_LIGHT   = "#F8F9FA"   # Fond d'écran Light
C_TEXT_MAIN  = "#1E293B"   # Texte principal

# Configuration MIA
if "mia" not in config.AGENTS:
    config.AGENTS["mia"] = {
        "name": "MIA",
        "icon": "📡",
        "description": "Market Intelligence Agent (Regulatory Watch & Monitoring)."
    }

DEFAULT_DOMAINS = [
    "eur-lex.europa.eu", "europa.eu", "fda.gov", "iso.org", "gov.uk", 
    "reuters.com", "raps.org", "medtechdive.com", "complianceandrisks.com"
]

# =============================================================================
# 1. STYLE CSS AVANCÉ (THEME ENGINE)
# =============================================================================
def inject_custom_css():
    """Injecte le CSS pour surcharger le thème Streamlit par défaut."""
    
    # Détection du mode pour ajuster quelques couleurs
    is_dark = st.session_state.get("dark_mode", False)
    bg_color = "#0e1117" if is_dark else C_BG_LIGHT
    card_bg = "#262730" if is_dark else "#FFFFFF"
    text_color = "#FAFAFA" if is_dark else C_TEXT_MAIN
    
    st.markdown(f"""
    <style>
    /* IMPORTS FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

    /* --- GLOBAL --- */
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
        font-family: 'Inter', sans-serif;
    }}
    
    h1, h2, h3 {{
        font-family: 'Montserrat', sans-serif !important;
        color: {C_GREEN_MAIN} !important;
        font-weight: 700 !important;
    }}
    
    /* En Dark Mode, on passe les titres en Or pour la lisibilité */
    @media (prefers-color-scheme: dark) {{
        h1, h2, h3 {{ color: {C_GOLD} !important; }}
    }}
    
    /* --- SIDEBAR --- */
    [data-testid="stSidebar"] {{
        background-color: {card_bg};
        border-right: 1px solid rgba(41, 90, 99, 0.1);
    }}

    /* --- BOUTONS (Override du Rouge Streamlit) --- */
    div.stButton > button {{
        background-color: {C_GREEN_MAIN} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
        font-family: 'Montserrat', sans-serif !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
    }}
    
    div.stButton > button:hover {{
        background-color: {C_GOLD} !important;
        color: white !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.15) !important;
    }}

    /* Boutons secondaires (Ghost) */
    div.stButton > button[kind="secondary"] {{
        background-color: transparent !important;
        border: 1px solid {C_GREEN_MAIN} !important;
        color: {C_GREEN_MAIN} !important;
    }}

    /* --- INPUTS & CHAMPS --- */
    /* On enlève la bordure rouge par défaut au focus */
    .stTextInput > div > div {{
        border-radius: 8px !important;
        border: 1px solid #E0E0E0 !important;
    }}
    
    /* Focus : Vert Valhallai */
    .stTextInput > div > div:focus-within {{
        border-color: {C_GREEN_MAIN} !important;
        box-shadow: 0 0 0 1px {C_GREEN_MAIN} !important;
    }}
    
    /* Selectbox & Multiselect focus */
    .stSelectbox > div > div[aria-expanded="true"], 
    .stMultiSelect > div > div[aria-expanded="true"] {{
        border-color: {C_GREEN_MAIN} !important;
    }}

    /* Tags dans Multiselect (Les fameux rouges) -> On les met en Vert/Or */
    .stMultiSelect span[data-baseweb="tag"] {{
        background-color: {C_GREEN_MAIN}20 !important; /* 20% opacité */
        border: 1px solid {C_GREEN_MAIN}40 !important;
    }}
    .stMultiSelect span[data-baseweb="tag"] span {{
        color: {C_GREEN_MAIN} !important;
    }}

    /* --- CARDS (Custom Class) --- */
    .info-card {{
        background-color: {card_bg};
        padding: 2rem;
        border-radius: 16px;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
        height: 100%;
        min-height: 250px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .info-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: {C_GOLD};
    }}
    
    /* --- LOGIN PAGE SPECIAL --- */
    .login-wrapper {{
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(135deg, {C_GREEN_MAIN} 0%, {C_GREEN_DARK} 100%);
        z-index: 0;
    }}
    .login-box {{
        background: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        text-align: center;
        position: relative;
        z-index: 1;
    }}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# INITIALISATION
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
# DATA LAYER
# =============================================================================
@st.cache_resource
def get_gsheet_workbook():
    try:
        if "service_account" not in st.secrets: return None
        sa_secrets = st.secrets["service_account"]
        raw_key = sa_secrets.get("private_key", "").replace("\\n", "\n")
        if "-----BEGIN" not in raw_key: raw_key = "-----BEGIN PRIVATE KEY-----\n" + raw_key.strip()
        if "-----END" not in raw_key: raw_key = raw_key.strip() + "\n-----END PRIVATE KEY-----"
        
        creds_dict = {
            "type": sa_secrets["type"], "project_id": sa_secrets["project_id"],
            "private_key_id": sa_secrets["private_key_id"], "private_key": raw_key,
            "client_email": sa_secrets["client_email"], "client_id": sa_secrets["client_id"],
            "auth_uri": sa_secrets["auth_uri"], "token_uri": sa_secrets["token_uri"],
            "auth_provider_x509_cert_url": sa_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": sa_secrets["client_x509_cert_url"]
        }
        gc = gspread.service_account_from_dict(creds_dict)
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

# =============================================================================
# API LAYER
# =============================================================================
def get_api_key(): return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
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
# LOGIC & PROMPTS
# =============================================================================
def check_password():
    if not st.secrets.get("APP_TOKEN"): st.session_state["authenticated"]=True; return
    if st.session_state.get("password_input")==st.secrets["APP_TOKEN"]:
        st.session_state["authenticated"]=True; del st.session_state["password_input"]
    else: st.error("Access Denied")

def logout():
    st.session_state["authenticated"]=False
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

def get_logo_html(size=50):
    svg = f"""<svg width="{size}" height="{size}" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="#295A63"/>
        <rect x="52" y="10" width="38" height="38" rx="8" fill="#C8A951"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="#1A3C42"/>
        <rect x="52" y="52" width="38" height="38" rx="8" fill="#E6D5A7"/>
    </svg>"""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="display:block; margin:auto;">'

# =============================================================================
# PAGES
# =============================================================================
def page_dashboard():
    st.title("Dashboard")
    st.markdown(f"<span style='color:#666; font-size:1.1em;'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    
    # CSS GRID pour alignement parfait
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1: 
        st.markdown(f"""
        <div class="info-card">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">🤖</div>
            <h3 style="margin:0; color:#295A63;">OlivIA</h3>
            <p style="color:#666; flex-grow:1; margin-top:10px;">{config.AGENTS['olivia']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Start Strategy →", key="btn_oli"):
            st.session_state["current_page"] = "OlivIA"
            st.rerun()

    with col2: 
        st.markdown(f"""
        <div class="info-card">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">🔍</div>
            <h3 style="margin:0; color:#295A63;">EVA</h3>
            <p style="color:#666; flex-grow:1; margin-top:10px;">{config.AGENTS['eva']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Start Audit →", key="btn_eva"):
            st.session_state["current_page"] = "EVA"
            st.rerun()

    with col3: 
        st.markdown(f"""
        <div class="info-card">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">📡</div>
            <h3 style="margin:0; color:#295A63;">MIA</h3>
            <p style="color:#666; flex-grow:1; margin-top:10px;">{config.AGENTS['mia']['description']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Start Watch →", key="btn_mia"):
            st.session_state["current_page"] = "MIA"
            st.rerun()

def page_olivia():
    st.title("🤖 OlivIA Workspace")
    markets, _ = get_markets()
    c1, c2 = st.columns([2, 1], gap="large")
    with c1: desc = st.text_area("Product Definition", height=200, placeholder="Ex: Medical device class IIa...")
    with c2: 
        safe_default = [markets[0]] if markets else []
        ctrys = st.multiselect("Target Markets", markets, default=safe_default)
        st.write("")
        gen = st.button("🚀 Generate Report", type="primary")
    
    if gen and desc:
        with st.spinner("Analyzing regulatory landscape..."):
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
                st.rerun()
            except Exception as e: st.error(str(e))

    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("Analysis Generated")
        st.markdown(st.session_state["last_olivia_report"])
        try:
            pdf = generate_pdf_report("Regulatory Report", st.session_state["last_olivia_report"], st.session_state.get("last_olivia_id", "ID"))
            st.download_button("📥 Download PDF", pdf, "report.pdf", "application/pdf")
        except: pass

def page_eva():
    st.title("🔍 EVA Workspace")
    ctx = st.text_area("Regulatory Context", value=st.session_state.get("last_olivia_report", ""))
    up = st.file_uploader("Technical Documentation (PDF)", type="pdf")
    if st.button("Run Audit", type="primary") and up:
        with st.spinner("Auditing..."):
            try:
                txt = extract_text_from_pdf(up.read())
                resp = cached_ai_generation(create_eva_prompt(ctx, txt), "gpt-4o", 0.1)
                st.session_state["last_eva_report"] = resp
                st.session_state["last_eva_id"] = str(uuid.uuid4())
                log_usage("EVA", st.session_state["last_eva_id"], f"File: {up.name}")
                st.rerun()
            except Exception as e: st.error(str(e))
    
    if st.session_state.get("last_eva_report"):
        st.markdown("### Audit Results")
        st.markdown(st.session_state["last_eva_report"])
        try:
            pdf = generate_pdf_report("Audit Report", st.session_state["last_eva_report"], st.session_state.get("last_eva_id", "ID"))
            st.download_button("📥 Download PDF", pdf, "audit.pdf", "application/pdf")
        except: pass

def page_mia():
    agent = config.AGENTS["mia"]
    st.title(f"{agent['icon']} {agent['name']} Watch Tower")
    st.markdown(f"<span class='sub-text'>{agent['description']}</span>", unsafe_allow_html=True)
    st.markdown("---")

    markets, _ = get_markets()
    col1, col2, col3 = st.columns([2, 2, 1], gap="large")
    
    with col1: 
        topic = st.text_input("🔎 Watch Topic / Product", placeholder="e.g. Cybersecurity for SaMD", key="mia_topic")
    with col2: 
        # Sécurité pour éviter liste vide
        safe_markets = [markets[0]] if markets else []
        selected_markets = st.multiselect("🌍 Markets", markets, default=safe_markets, key="mia_mkts")
    with col3:
        # Map des durées
        timeframe_map = {
            "⚡ 30 Days": 30, 
            "📅 12 Months": 365, 
            "🏛️ 3 Years": 1095
        }
        selected_label = st.selectbox("⏱️ Timeframe", list(timeframe_map.keys()), index=1, key="mia_time")
        days_limit = timeframe_map[selected_label]

    if st.button("🚀 Launch Monitoring", type="primary"):
        if topic:
            with st.spinner(f"📡 MIA is scanning... ({selected_label})"):
                # --- CORRECTION ICI : On injecte la période dans le texte ---
                # Cela force le système de cache à voir une différence et aide Tavily
                clean_timeframe = selected_label.replace("⚡ ", "").replace("📅 ", "").replace("🏛️ ", "")
                query = f"New regulations and guidelines for {topic} in {', '.join(selected_markets)} released in the {clean_timeframe}"
                
                # Appel avec le texte modifié ET le paramètre days
                raw_data, error = cached_run_deep_search(query, days=days_limit)
                
                if not raw_data:
                    st.error(f"Search failed: {error}")
                else:
                    prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
                    json_str = cached_ai_generation(prompt, config.OPENAI_MODEL, 0.1, json_mode=True)
                    
                    if json_str:
                        st.session_state["last_mia_results"] = json.loads(json_str)
                        log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label}")
                        st.toast("Monitoring Complete!", icon="🎉")
                    else: st.error("Analysis failed.")

    # Affichage des résultats (inchangé)
    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("### 📋 Monitoring Report")
        st.info(f"**Executive Summary:** {results.get('executive_summary', 'No summary.')}")
        
        c_filter1, c_filter2, c_legend = st.columns([2, 2, 1], gap="large")
        with c_filter1:
            all_cat = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            sel_types = st.multiselect("🗂️ Filter by Type", all_cat, default=all_cat, key="mia_type")
        with c_filter2:
            sel_impacts = st.multiselect("🌪️ Filter by Impact", ["High", "Medium", "Low"], default=["High", "Medium", "Low"], key="mia_imp")
        with c_legend:
            st.write(""); st.write("")
            st.markdown("<div><span style='color:#e53935'>●</span> High <span style='color:#fb8c00'>●</span> Medium <span style='color:#43a047'>●</span> Low</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        items = results.get("items", [])
        filtered = [i for i in items if i.get('impact','Low').capitalize() in sel_impacts and i.get('category','News').capitalize() in sel_types]
        
        if not filtered: st.warning("No updates found matching filters.")
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

def page_admin():
    st.title("⚙️ Admin")
    st.info("Configuration protected.")

def render_sidebar():
    with st.sidebar:
        if st.button("🏠 Home"): 
            st.session_state["current_page"]="Dashboard"
            st.rerun()
        st.markdown("---")
        pg = st.radio("Menu", ["Dashboard", "OlivIA", "EVA", "MIA", "Admin"], label_visibility="collapsed")
        if pg != st.session_state["current_page"]:
            st.session_state["current_page"] = pg
            st.rerun()
        st.markdown("---")
        
        # Toggle Dark Mode Simple
        is_dark = st.toggle("🌙 Dark Mode", value=st.session_state["dark_mode"])
        if is_dark != st.session_state["dark_mode"]:
            st.session_state["dark_mode"] = is_dark
            st.rerun()
            
        if st.button("Log Out"): logout(); st.rerun()

def render_login():
    # CSS SPÉCIFIQUE LOGIN (Fond Vert + Centrage)
    st.markdown("""
    <style>
    .stApp { background-color: #295A63; }
    .login-container {
        background-color: white;
        padding: 50px;
        border-radius: 15px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        text-align: center;
        margin-top: 15vh;
    }
    .login-container h1 { color: #295A63 !important; }
    .login-container p { color: #C8A951 !important; letter-spacing: 2px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.container():
            st.markdown(f"""
            <div class="login-container">
                {get_logo_html(80)}
                <h1>{config.APP_NAME}</h1>
                <p>{config.APP_TAGLINE}</p>
            </div>
            """, unsafe_allow_html=True)
            st.text_input("Enter Access Token", type="password", key="password_input", on_change=check_password)

def main():
    apply_theme()
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

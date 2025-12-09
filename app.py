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

# Configuration MIA
if "mia" not in config.AGENTS:
    config.AGENTS["mia"] = {
        "name": "MIA",
        "icon": "📡",
        "description": "Market Intelligence Agent (Regulatory Watch & Monitoring)."
    }

# Liste de secours
DEFAULT_DOMAINS = [
    "eur-lex.europa.eu", "europa.eu", "echa.europa.eu", "cenelec.eu", 
    "single-market-economy.ec.europa.eu",
    "fda.gov", "fcc.gov", "cpsc.gov", "osha.gov", "phmsa.dot.gov",
    "iso.org", "iec.ch", "unece.org", "iata.org",
    "gov.uk", "meti.go.jp", "kats.go.kr",
    "reuters.com", "raps.org", "medtechdive.com", "complianceandrisks.com"
]

# =============================================================================
# 1. INITIALISATION STATE
# =============================================================================
def init_session_state():
    defaults = {
        "authenticated": False,
        "admin_authenticated": False,
        "current_page": "Dashboard",
        "last_olivia_report": None,
        "last_olivia_id": None, 
        "last_eva_report": None,
        "last_eva_id": None,
        "last_mia_results": None,
        "editing_market_index": None,
        "editing_domain_index": None,
        # Variables persistantes pour le formulaire MIA
        "mia_topic_val": "",
        "mia_markets_val": [],
        "mia_timeframe_index": 1,
        "current_watchlist": None, # Pour éviter le re-toast en boucle
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

# --- GESTION DES WATCHLISTS ---
def get_watchlists():
    wb = get_gsheet_workbook()
    watchlists = []
    if wb:
        try:
            try: 
                sheet = wb.worksheet("Watchlists")
            except: 
                sheet = wb.add_worksheet("Watchlists", 100, 5)
                sheet.append_row(["ID", "Name", "Topic", "Markets", "Timeframe"])
                return []
            
            rows = sheet.get_all_values()
            if len(rows) > 1:
                for row in rows[1:]:
                    if len(row) >= 5:
                        watchlists.append({
                            "id": row[0],
                            "name": row[1],
                            "topic": row[2],
                            "markets": row[3], 
                            "timeframe": row[4]
                        })
        except: pass
    return watchlists

def save_watchlist(name, topic, markets_list, timeframe):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sheet = wb.worksheet("Watchlists")
            new_id = str(uuid.uuid4())[:8]
            markets_str = ", ".join(markets_list)
            sheet.append_row([new_id, name, topic, markets_str, timeframe])
            return True
        except: pass
    return False

def delete_watchlist(watchlist_id):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sheet = wb.worksheet("Watchlists")
            cell = sheet.find(watchlist_id)
            if cell:
                sheet.delete_rows(cell.row)
                return True
        except: pass
    return False

# =============================================================================
# 4. API & SEARCH & CACHING
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
# 5. AUTH & PROMPTS
# =============================================================================
def check_password_manual(token):
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True
        st.rerun()
    
    if token == correct_token:
        st.session_state["authenticated"] = True
        st.rerun()
    else:
        st.error("🚫 Access Denied: Invalid Token")

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
    
    MISSION:
    1. FILTER by PUBLICATION DATE (The "Signal"): 
       - Keep items where the ARTICLE/UPDATE ITSELF was published within {timeframe_label}.
       - INCLUDE: Recent articles discussing old regulations, recent reminders, new interpretations of old laws.
       - EXCLUDE: Old articles that do not fall within the timeline.
       
    2. Analyze Impact (High/Medium/Low) based on the relevance to the user's topic.
    
    3. CLASSIFY each item into: "Regulation", "Standard", "Guidance", "Enforcement", "News".
    
    OUTPUT FORMAT (Strict JSON):
    {{
        "executive_summary": "Summary...",
        "items": [
            {{ 
                "title": "...", 
                "date": "YYYY-MM-DD (Publication date of the source)", 
                "source_name": "...", 
                "url": "...", 
                "summary": "...", 
                "tags": ["Tag1"], 
                "impact": "High/Medium/Low",
                "category": "Regulation"
            }}
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
    return f'<img src="data:image/svg+xml;base64,{b64}" style="vertical-align: middle; margin-right: 10px; display: inline-block;">'

# --- THEME CSS ---
def apply_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Montserrat', sans-serif !important; color: #295A63 !important; }
    
    /* Boutons */
    div.stButton > button:first-child { 
        background-color: #295A63 !important; color: white !important; 
        border-radius: 8px; font-weight: 600; width: 100%; border: none;
    }
    div.stButton > button:first-child:hover { background-color: #C8A951 !important; color: black !important; }
    
    /* Cartes */
    .info-card { 
        background-color: white; padding: 2rem; border-radius: 12px; border: 1px solid #E2E8F0; 
        min-height: 220px; display: flex; flex-direction: column; justify-content: flex-start;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Inputs */
    .stTextInput > div > div:focus-within { border-color: #295A63 !important; box-shadow: 0 0 0 1px #295A63 !important; }
    
    /* Text Justifié (Classe Custom) */
    .justified-text {
        text-align: justify;
        line-height: 1.6;
        color: #2c3e50;
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #295A63;
    }
    </style>
    """, unsafe_allow_html=True)

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
    
    # 1. Gestion des Watchlists
    watchlists = get_watchlists()
    wl_names = ["-- New Watch --"] + [w["name"] for w in watchlists]
    
    selected_wl = st.selectbox("📂 Load Saved Watchlist", wl_names)
    
    # Chargement
    if selected_wl != "-- New Watch --" and st.session_state.get("current_watchlist") != selected_wl:
        wl_data = next((w for w in watchlists if w["name"] == selected_wl), None)
        if wl_data:
            st.session_state["mia_topic_val"] = wl_data["topic"]
            st.session_state["mia_markets_val"] = [m.strip() for m in wl_data["markets"].split(",")]
            timeframe_map = {"⚡ Last 30 Days": 30, "📅 Last 12 Months": 365, "🏛️ Last 3 Years": 1095}
            try:
                st.session_state["mia_timeframe_index"] = list(timeframe_map.keys()).index(wl_data["timeframe"])
            except: st.session_state["mia_timeframe_index"] = 1
            
            st.session_state["current_watchlist"] = selected_wl # Marqueur pour ne pas re-toaster
            st.toast(f"✅ Watch loaded: {selected_wl}")

    # 2. Formulaire
    markets, _ = get_markets()
    col1, col2, col3 = st.columns([2, 2, 1], gap="large")
    
    with col1: 
        topic = st.text_input(
            "🔎 Watch Topic / Product", 
            value=st.session_state.get("mia_topic_val", ""),
            placeholder="e.g. Cybersecurity for SaMD"
        )
    with col2: 
        default_mkts = [m for m in st.session_state.get("mia_markets_val", []) if m in markets]
        if not default_mkts and markets: default_mkts = [markets[0]]
            
        selected_markets = st.multiselect(
            "🌍 Markets", 
            markets, 
            default=default_mkts
        )
    with col3:
        timeframe_map = {"⚡ Last 30 Days": 30, "📅 Last 12 Months": 365, "🏛️ Last 3 Years": 1095}
        selected_label = st.selectbox(
            "⏱️ Timeframe", 
            list(timeframe_map.keys()), 
            index=st.session_state.get("mia_timeframe_index", 1)
        )
        days_limit = timeframe_map[selected_label]

    # Bouton Launch dynamique
    launch_label = f"🚀 Launch {selected_wl}" if selected_wl != "-- New Watch --" else "🚀 Launch Monitoring"
    
    c_launch, c_save = st.columns([1, 4])
    with c_launch:
        launch = st.button(launch_label, type="primary")
    
    with c_save:
        # Save Button (Visible uniquement si topic rempli)
        if topic:
            with st.popover("💾 Save as Watchlist"):
                new_wl_name = st.text_input("Name", placeholder="e.g. Monthly Cardio Watch")
                if st.button("Save"):
                    if new_wl_name:
                        save_watchlist(new_wl_name, topic, selected_markets, selected_label)
                        st.success("Saved!")
                        st.cache_data.clear()
                        st.rerun()

    if launch and topic:
        with st.spinner(f"📡 MIA is scanning... ({selected_label})"):
            clean_timeframe = selected_label.replace("⚡ ", "").replace("📅 ", "").replace("🏛️ ", "")
            query = f"New regulations guidelines for {topic} in {', '.join(selected_markets)} released in the {clean_timeframe}"
            raw_data, error = cached_run_deep_search(query, days=days_limit)
            if not raw_data: st.error(f"Search failed: {error}")
            else:
                prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
                json_str = cached_ai_generation(prompt, config.OPENAI_MODEL, 0.1, json_mode=True)
                if json_str:
                    st.session_state["last_mia_results"] = json.loads(json_str)
                    log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label}")
                else: st.error("Analysis failed.")

    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("### 📋 Monitoring Report")
        
        # Résumé Justifié
        summary = results.get('executive_summary', 'No summary.')
        st.markdown(f"""<div class="justified-text"><strong>Executive Summary:</strong> {summary}</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True) # Espacement

        # Filtres
        c_filter1, c_filter2, c_legend = st.columns([2, 2, 1], gap="large")
        with c_filter1:
            all_cat = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            sel_types = st.multiselect("🗂️ Filter by Type", all_cat, default=all_cat)
        with c_filter2:
            sel_impacts = st.multiselect("🌪️ Filter by Impact", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
        with c_legend:
            st.write(""); st.write("")
            st.markdown("<div><span style='color:#e53935'>●</span> High <span style='color:#fb8c00'>●</span> Medium <span style='color:#43a047'>●</span> Low <br><span style='font-size:0.8em; color:gray'>📅 Dates = Publication</span></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        items = results.get("items", [])
        filtered = [i for i in items if i.get('impact','Low').capitalize() in sel_impacts and i.get('category','News').capitalize() in sel_types]
        
        if not filtered: st.warning("No updates found matching filters.")
        for item in filtered:
            impact = item.get('impact', 'Low').lower()
            category = item.get('category', 'News')
            
            if impact == 'high': icon = "🔴"
            elif impact == 'medium': icon = "🟡"
            else: icon = "🟢"
            
            cat_map = {"Regulation":"🏛️", "Standard":"📏", "Guidance":"📘", "Enforcement":"📢", "News":"📰"}
            
            with st.container():
                c1, c2 = st.columns([0.1, 0.9])
                with c1: st.markdown(f"## {icon}")
                with c2:
                    st.markdown(f"**[{cat_map.get(cat,'📄')} {cat}]** [{item['title']}]({item['url']})")
                    st.caption(f"📅 {item['date']} | 🏛️ {item['source_name']}")
                    st.write(item['summary'])
                st.markdown("---")

def page_olivia():
    st.title("🤖 OlivIA Workspace")
    markets, _ = get_markets()
    c1, c2 = st.columns([2, 1])
    with c1: desc = st.text_area("Product Definition", height=200, key="oli_desc")
    with c2: 
        safe_default = [markets[0]] if markets else []
        ctrys = st.multiselect("Target Markets", markets, default=safe_default, key="oli_mkts")
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
                
                new_id = str(uuid.uuid4())
                st.session_state["last_olivia_id"] = new_id
                log_usage("OlivIA", st.session_state["last_olivia_id"], desc, f"Mkts:{len(ctrys)}")
                st.toast("Analysis Ready!", icon="✅")
            except Exception as e: st.error(str(e))

    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("✅ Analysis Generated")
        st.markdown(st.session_state["last_olivia_report"])
        st.markdown("---")
        try:
            pdf = generate_pdf_report("Regulatory Analysis Report", st.session_state["last_olivia_report"], st.session_state.get("last_olivia_id", "ID"))
            st.download_button("📥 Download PDF", pdf, f"VALHALLAI_Report.pdf", "application/pdf")
        except:
            st.download_button("📥 Download Raw Text", st.session_state["last_olivia_report"], "report.md")

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
                st.toast("Audit Complete!", icon="🔍")
            except Exception as e: st.error(str(e))
    
    if st.session_state.get("last_eva_report"):
        st.markdown("### Audit Results")
        st.markdown(st.session_state["last_eva_report"])
        st.markdown("---")
        try:
            pdf = generate_pdf_report("Compliance Audit Report", st.session_state["last_eva_report"], st.session_state.get("last_eva_id", "ID"))
            st.download_button("📥 Download PDF", pdf, f"VALHALLAI_Audit.pdf", "application/pdf")
        except:
            st.download_button("📥 Download Text", st.session_state["last_eva_report"], "audit.md")

def page_dashboard():
    st.title("Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    c1, c2, c3 = st.columns(3)
    
    with c1: 
        st.markdown(f"""<div class="info-card"><h3>🤖 OlivIA</h3><p class='sub-text'>{config.AGENTS['olivia']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch OlivIA ->"): 
            st.session_state["current_page"] = "OlivIA"
            st.rerun()
    with c2: 
        st.markdown(f"""<div class="info-card"><h3>🔍 EVA</h3><p class='sub-text'>{config.AGENTS['eva']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch EVA ->"): 
            st.session_state["current_page"] = "EVA"
            st.rerun()
    with c3: 
        st.markdown(f"""<div class="info-card"><h3>{config.AGENTS['mia']['icon']} {config.AGENTS['mia']['name']}</h3><p class='sub-text'>{config.AGENTS['mia']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch MIA ->"): 
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
        if st.button("Log Out"): logout(); st.rerun()

def render_login():
    # Page centrée sobre
    _, col, _ = st.columns([1, 1.5, 1])
    
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Encart Login Sobre (Sans fond vert, juste centré propre)
        st.markdown(f"""
        <div style="text-align: center;">
            {get_logo_html(100)}
            <h1 style="color: #295A63; font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 2.5em; margin-bottom: 0;">{config.APP_NAME}</h1>
            <p style="color: #C8A951; font-family: 'Inter', sans-serif; font-weight: 600; letter-spacing: 2px; font-size: 0.9em; margin-top: 5px;">{config.APP_TAGLINE}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Spacer
        
        # Champ de saisie standard (l'oeil fonctionne nativement ici car pas de on_change)
        token = st.text_input("🔐 Access Token", type="password")
        
        # Bouton Enter explicite
        if st.button("Enter", type="primary", use_container_width=True):
            check_password_manual(token)

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

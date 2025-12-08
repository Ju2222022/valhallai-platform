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
# 0. CONFIG & CONSTANTES
# =============================================================================
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

if "mia" not in config.AGENTS:
    config.AGENTS["mia"] = {
        "name": "MIA",
        "icon": "📡",
        "description": "Market Intelligence Agent (Regulatory Watch & Monitoring)."
    }

DEFAULT_DOMAINS = [
    # EUROPE
    "eur-lex.europa.eu", "europa.eu", "echa.europa.eu", "cenelec.eu", 
    "single-market-economy.ec.europa.eu",
    # USA
    "fda.gov", "fcc.gov", "cpsc.gov", "osha.gov", "phmsa.dot.gov",
    # INTERNATIONAL
    "iso.org", "iec.ch", "unece.org", "iata.org",
    # UK & ASIE
    "gov.uk", "meti.go.jp", "kats.go.kr",
    # NEWS & VEILLE
    "reuters.com", "raps.org", "medtechdive.com", "complianceandrisks.com"
]

# =============================================================================
# 1. INITIALISATION DU SESSION STATE
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
# 2. GESTION DES DONNÉES (GOOGLE SHEETS)
# =============================================================================
@st.cache_resource
def get_gsheet_workbook():
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
            "type": sa_secrets["type"], "project_id": sa_secrets["project_id"],
            "private_key_id": sa_secrets["private_key_id"], "private_key": clean_key,
            "client_email": sa_secrets["client_email"], "client_id": sa_secrets["client_id"],
            "auth_uri": sa_secrets["auth_uri"], "token_uri": sa_secrets["token_uri"],
            "auth_provider_x509_cert_url": sa_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": sa_secrets["client_x509_cert_url"]
        }
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open_by_url(st.secrets["gsheets"]["url"])
    except Exception as e:
        st.error(f"❌ Google Sheets Connection Error: {e}")
        return None

def log_usage(report_type, report_id, details="", extra_metrics=""):
    wb = get_gsheet_workbook()
    if not wb: return
    try:
        try: log_sheet = wb.worksheet("Logs")
        except: log_sheet = wb.add_worksheet(title="Logs", rows=1000, cols=6)
        
        if not log_sheet.cell(1, 1).value:
            log_sheet.update("A1:F1", [["Date", "Time", "Report ID", "Type", "Details", "Metrics"]])
            
        now = datetime.now()
        row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), report_id, report_type, details, extra_metrics]
        log_sheet.append_row(row)
    except Exception as e: print(f"Logging failed: {e}")

# --- MARCHÉS ---
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

# --- DOMAINES ---
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
# 4. API & SEARCH & PDF
# =============================================================================
def navigate_to(page):
    st.session_state["current_page"] = page
    st.rerun()

def get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def get_openai_client():
    k = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=k) if k else None

def run_deep_search(query, days=None):
    try:
        k = st.secrets.get("TAVILY_API_KEY")
        if not k: return None, "Key Missing"
        tavily = TavilyClient(api_key=k)
        doms, _ = get_domains()
        
        params = {
            "query": query,
            "search_depth": "advanced",
            "max_results": 5 if days else 3,
            "include_domains": doms
        }
        
        if days: params["days"] = days
            
        response = tavily.search(**params)
        
        txt = "### WEB RESULTS:\n"
        for r in response['results']:
            txt += f"- Title: {r['title']}\n  URL: {r['url']}\n  Content: {r['content'][:800]}...\n\n"
        return txt, None
    except Exception as e: return None, str(e)

def extract_text_from_pdf(b):
    try:
        r = PdfReader(io.BytesIO(b)); txt=[]
        for p in r.pages: txt.append(p.extract_text() or "")
        return "\n".join(txt)
    except Exception as e: return str(e)

# =============================================================================
# 5. AUTH
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
    st.session_state["authenticated"]=False; st.session_state["admin_authenticated"]=False
    st.session_state["current_page"]="Dashboard"

# =============================================================================
# 6. PROMPTS & UI HELPERS
# =============================================================================
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
    1. Filter raw data to keep only relevant updates.
    2. Analyze Impact (High/Medium/Low).
    3. CLASSIFY each item into one of these strict categories:
       - "Regulation" (Laws, Directives, Acts)
       - "Standard" (ISO, IEC, EN norms)
       - "Guidance" (MDCG, FDA Guidance, Whitepapers)
       - "Enforcement" (Warning Letters, Recalls, Audit Findings)
       - "News" (Articles, Press Releases, Trends)
    
    OUTPUT FORMAT (Strict JSON):
    {{
        "executive_summary": "Summary...",
        "items": [
            {{ 
                "title": "...", 
                "date": "YYYY-MM-DD", 
                "source_name": "...", 
                "url": "...", 
                "summary": "...", 
                "tags": ["Tag1"], 
                "impact": "High/Medium/Low",
                "category": "Regulation" (or Standard, Guidance, Enforcement, News)
            }}
        ]
    }}
    """

def get_logo_svg():
    colors = config.COLORS["dark" if st.session_state["dark_mode"] else "light"]
    c1, c2 = colors["primary"], colors["accent"]
    c3, c4 = "#1A3C42", "#E6D5A7"
    return f"""<svg width="60" height="60" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="{c1}"/><rect x="52" y="10" width="38" height="38" rx="8" fill="{c2}"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="{c3}"/><rect x="52" y="52" width="38" height="38" rx="8" fill="{c4}"/>
    </svg>"""

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
    .info-card {{ 
        background-color: {c['card']}; padding: 2rem; border-radius: 12px; border: 1px solid {c['border']}; 
        min-height: 220px; display: flex; flex-direction: column; justify-content: flex-start;
    }}
    .logo-text {{ font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 1.4rem; color: {c['text']}; }}
    .logo-sub {{ font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: {c['text_secondary']}; font-weight: 500; }}
    div.stButton > button:first-child {{ background-color: {c['primary']} !important; color: {c['button_text']} !important; border-radius: 8px; font-weight: 600; width: 100%;}}
    
    /* HARMONISATION COULEURS */
    .stMultiSelect span[data-baseweb="tag"] {{ background-color: {c['primary']} !important; color: {c['button_text']} !important; }}
    div[role="radiogroup"] label[data-checked="true"] {{ color: {c['primary']} !important; font-weight: bold !important; }}
    div[data-baseweb="checkbox"] div[aria-checked="true"] {{ background-color: {c['primary']} !important; border-color: {c['primary']} !important; }}
    .stTextInput > div > div[data-baseweb="input"]:focus-within {{ border-color: {c['primary']} !important; box-shadow: 0 0 0 1px {c['primary']} !important; }}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 7. UI PAGES
# =============================================================================
def page_admin():
    st.title("⚙️ Admin Console"); st.markdown("---")
    if not st.session_state["admin_authenticated"]:
        st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password); return
    
    wb = get_gsheet_workbook()
    c1, c2 = st.columns([3, 1])
    c1.success(f"✅ DB: {wb.title}" if wb else "❌ DB Error")
    if c2.button("🔄 Refresh"): st.cache_data.clear(); st.rerun()

    tm, td = st.tabs(["🌍 Markets", "🕵️‍♂️ Sources (Deep Search)"])
    
    with tm:
        mkts, _ = get_markets()
        with st.form("add_m"):
            c1, c2 = st.columns([3,1])
            new = c1.text_input("Name")
            if c2.form_submit_button("Add") and new: add_market(new); st.rerun()
        for i, m in enumerate(mkts):
            c1, c2, c3 = st.columns([4, 1, 1])
            if st.session_state.get("editing_market_index") != i:
                c1.info(f"🌍 {m}")
                if c2.button("✏️", key=f"em{i}"): st.session_state["editing_market_index"] = i; st.rerun()
                if c3.button("🗑️", key=f"dm{i}"): remove_market(i); st.rerun()
            else:
                nv = c1.text_input("Edit", m, key=f"vm{i}")
                if c2.button("💾", key=f"sm{i}"): update_market(i, nv); st.session_state["editing_market_index"]=None; st.rerun()
                if c3.button("❌", key=f"cm{i}"): st.session_state["editing_market_index"]=None; st.rerun()

    with td:
        doms, _ = get_domains()
        st.info("💡 Allowed domains for Deep Search & MIA Monitoring.")
        with st.form("add_d"):
            c1, c2 = st.columns([3,1])
            new = c1.text_input("Domain")
            if c2.form_submit_button("Add") and new: add_domain(new); st.rerun()
        for i, d in enumerate(doms):
            c1, c2, c3 = st.columns([4, 1, 1])
            if st.session_state.get("editing_domain_index") != i:
                c1.success(f"🌐 {d}")
                if c2.button("✏️", key=f"ed{i}"): st.session_state["editing_domain_index"] = i; st.rerun()
                if c3.button("🗑️", key=f"dd{i}"): remove_domain(i); st.rerun()
            else:
                nv = c1.text_input("Edit", d, key=f"vd{i}")
                if c2.button("💾", key=f"sd{i}"): update_domain(i, nv); st.session_state["editing_domain_index"]=None; st.rerun()
                if c3.button("❌", key=f"cd{i}"): st.session_state["editing_domain_index"]=None; st.rerun()

def page_mia():
    agent = config.AGENTS["mia"]
    st.title(f"{agent['icon']} {agent['name']} Watch Tower")
    st.markdown(f"<span class='sub-text'>{agent['description']}</span>", unsafe_allow_html=True)
    st.markdown("---")

    markets, _ = get_markets()
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: topic = st.text_input("🔎 Watch Topic / Product", placeholder="e.g. Cybersecurity for SaMD")
    with col2: selected_markets = st.multiselect("🌍 Markets", markets, default=[markets[0]] if markets else None)
    with col3:
        timeframe_map = {"⚡ Last 30 Days": 30, "📅 Last 12 Months": 365, "🏛️ Last 3 Years": 1095}
        selected_label = st.selectbox("⏱️ Timeframe", list(timeframe_map.keys()), index=1)
        days_limit = timeframe_map[selected_label]

    if st.button("🚀 Launch Monitoring", type="primary"):
        client = get_openai_client()
        if client and topic:
            with st.spinner(f"📡 MIA is scanning the horizon... ({selected_label})"):
                try:
                    query = f"New regulations and guidelines for {topic} in {', '.join(selected_markets)} released recently"
                    raw_data, error = run_deep_search(query, days=days_limit)
                    if not raw_data: st.error(f"Search failed: {error}")
                    else:
                        prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
                        res = client.chat.completions.create(model=config.OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.1, response_format={"type": "json_object"})
                        st.session_state["last_mia_results"] = json.loads(res.choices[0].message.content)
                        log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label}")
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("### 📋 Monitoring Report")
        st.info(f"**Executive Summary:** {results.get('executive_summary', 'No summary.')}")
        
        # --- MISE EN PAGE CORRIGÉE (2-2-1) ---
        c_filter1, c_filter2, c_legend = st.columns([2, 2, 1], gap="large")
        
        with c_filter1:
            all_categories = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            selected_types = st.multiselect("🗂️ Filter by Type", all_categories, default=all_categories)
            
        with c_filter2:
            selected_impacts = st.multiselect("🌪️ Filter by Impact", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
            
        with c_legend:
            # Spacer pour aligner verticalement avec les boîtes de saisie
            st.write("") 
            st.write("")
            st.markdown(
                """
                <div style="padding-top: 5px; font-size: 0.9em; white-space: nowrap;">
                    <span style='color: #e53935;'>●</span> High &nbsp;
                    <span style='color: #fb8c00;'>●</span> Medium &nbsp;
                    <span style='color: #43a047;'>●</span> Low
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        st.markdown("---")
        
        items = results.get("items", [])
        
        filtered_items = [
            i for i in items 
            if i.get('impact', 'Low').capitalize() in selected_impacts
            and i.get('category', 'News').capitalize() in selected_types
        ]
        
        if not filtered_items: st.warning("No updates found matching your filters.")
        
        for item in filtered_items:
            impact = item.get('impact', 'Low').lower()
            category = item.get('category', 'News')
            
            if impact == 'high': icon = "🔴"
            elif impact == 'medium': icon = "🟡"
            else: icon = "🟢"
            
            cat_map = {
                "Regulation": "🏛️", 
                "Standard": "📏", 
                "Guidance": "📘", 
                "Enforcement": "📢", 
                "News": "📰"
            }
            cat_icon = cat_map.get(category, "📄")
            
            with st.container():
                c1, c2 = st.columns([0.1, 0.9])
                with c1: st.markdown(f"## {icon}")
                with c2:
                    st.markdown(f"**[{cat_icon} {category}]** [{item['title']}]({item['url']})")
                    st.caption(f"📅 {item['date']} | 🏛️ {item['source_name']}")
                    st.write(item['summary'])
                    tags = "".join([f"<span style='background-color:#eee; padding:2px 8px; border-radius:10px; font-size:0.8em; margin-right:5px; color:#333'>{tag}</span>" for tag in item.get('tags', [])])
                    st.markdown(tags, unsafe_allow_html=True)
                st.markdown("---")

def page_olivia():
    agent = config.AGENTS["olivia"]
    st.title(f"{agent['icon']} {agent['name']} Workspace")
    markets, _ = get_markets()
    c1, c2 = st.columns([2, 1])
    with c1: desc = st.text_area("Product Definition", height=200)
    with c2: 
        ctrys = st.multiselect("Target Markets", markets)
        st.write(""); gen = st.button("Generate Report", type="primary")
    
    if gen and desc:
        client = get_openai_client()
        with st.spinner("Analyzing..."):
            try:
                use_ds = any(x in str(ctrys) for x in ["EU","USA","China"])
                ctx = ""
                if use_ds: 
                    d, _ = run_deep_search(f"Regulations for {desc} in {ctrys}")
                    if d: ctx = d
                
                p = create_olivia_prompt(desc, ctrys)
                if ctx: p += f"\n\nCONTEXT:\n{ctx}"
                
                r = client.chat.completions.create(model=config.OPENAI_MODEL, messages=[{"role":"user","content":p}], temperature=0.1)
                st.session_state["last_olivia_report"] = r.choices[0].message.content
                st.session_state["last_olivia_id"] = str(uuid.uuid4())
                log_usage("OlivIA", st.session_state["last_olivia_id"], desc, f"Mkts:{len(ctrys)}")
                st.rerun()
            except Exception as e: st.error(str(e))

    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("✅ Analysis Generated")
        st.markdown(st.session_state["last_olivia_report"])
        st.markdown("---")
        pdf = generate_pdf_report("Regulatory Analysis Report", st.session_state["last_olivia_report"], st.session_state.get("last_olivia_id", "ID"))
        st.download_button("📥 Download PDF", pdf, f"VALHALLAI_Report.pdf", "application/pdf")

def page_eva():
    st.title("EVA Workspace")
    ctx = st.text_area("Context", value=st.session_state.get("last_olivia_report", ""))
    up = st.file_uploader("PDF", type="pdf")
    if st.button("Run Audit", type="primary") and up:
        client = get_openai_client()
        with st.spinner("Auditing..."):
            try:
                txt = extract_text_from_pdf(up.read())
                r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":create_eva_prompt(ctx, txt)}], temperature=0.1)
                st.session_state["last_eva_report"] = r.choices[0].message.content
                st.session_state["last_eva_id"] = str(uuid.uuid4())
                log_usage("EVA", st.session_state["last_eva_id"], f"File: {up.name}")
            except Exception as e: st.error(str(e))
    
    if st.session_state.get("last_eva_report"):
        st.markdown("### Audit Results")
        st.markdown(st.session_state["last_eva_report"])
        st.markdown("---")
        pdf = generate_pdf_report("Compliance Audit Report", st.session_state["last_eva_report"], st.session_state.get("last_eva_id", "ID"))
        st.download_button("📥 Download PDF", pdf, f"VALHALLAI_Audit.pdf", "application/pdf")

def page_dashboard():
    st.title("Dashboard")
    st.markdown(f"<span class='sub-text'>{config.APP_SLOGAN}</span>", unsafe_allow_html=True)
    st.markdown("###")
    c1, c2, c3 = st.columns(3)
    
    with c1: 
        st.markdown(f"""<div class="info-card"><h3>🤖 OlivIA</h3><p class='sub-text'>{config.AGENTS['olivia']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch OlivIA ->"): navigate_to("OlivIA")
    with c2: 
        st.markdown(f"""<div class="info-card"><h3>🔍 EVA</h3><p class='sub-text'>{config.AGENTS['eva']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch EVA ->"): navigate_to("EVA")
    with c3: 
        st.markdown(f"""<div class="info-card"><h3>{config.AGENTS['mia']['icon']} {config.AGENTS['mia']['name']}</h3><p class='sub-text'>{config.AGENTS['mia']['description']}</p></div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Launch MIA ->"): navigate_to("MIA")

def render_sidebar():
    with st.sidebar:
        st.markdown(get_logo_html(), unsafe_allow_html=True)
        st.markdown(f"<div class='logo-text'>{config.APP_NAME}</div>", unsafe_allow_html=True)
        st.markdown("---")
        pages = ["Dashboard", "OlivIA", "EVA", "MIA", "Admin"]
        curr = st.session_state["current_page"]
        sel = st.radio("NAV", pages, index=pages.index(curr) if curr in pages else 0, label_visibility="collapsed")
        if sel != curr: navigate_to(sel)
        st.markdown("---")
        if st.checkbox("Dark Mode", value=st.session_state["dark_mode"]): st.session_state["dark_mode"]=True; st.rerun()
        else: 
            if st.session_state["dark_mode"]: st.session_state["dark_mode"]=False; st.rerun()
        st.markdown("---")
        if st.button("Log Out"): logout(); st.rerun()

def render_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(get_logo_html(), unsafe_allow_html=True)
        st.title(config.APP_NAME)
        st.text_input("Token", type="password", key="password_input", on_change=check_password)

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

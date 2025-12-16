import streamlit as st
import os
import io
import base64
import uuid
import json
import hashlib
import asyncio
import aiohttp
import fitz  # PyMuPDF
import re
from urllib.parse import urlparse, quote_plus
from datetime import datetime, timedelta
from openai import OpenAI
from pypdf import PdfReader
import gspread 
from tavily import TavilyClient
import plotly.express as px
import pandas as pd

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

if "mia" not in config.AGENTS:
    config.AGENTS["mia"] = {
        "name": "MIA",
        "icon": "📡",
        "description": "Market Intelligence Agent (Regulatory Watch & Monitoring)."
    }

DEFAULT_DOMAINS = [
    "eur-lex.europa.eu", "europa.eu", "echa.europa.eu", "cenelec.eu", 
    "single-market-economy.ec.europa.eu",
    "fda.gov", "fcc.gov", "cpsc.gov", "osha.gov", "phmsa.dot.gov",
    "iso.org", "iec.ch", "unece.org", "iata.org",
    "gov.uk", "meti.go.jp", "kats.go.kr",
    "reuters.com", "raps.org", "medtechdive.com", "complianceandrisks.com"
]

DEFAULT_APP_CONFIG = {
    "enable_impact_analysis": "TRUE",
    "cache_ttl_hours": "1",
    "max_search_results": "20",
    "provider_google": "TRUE",
    "provider_tavily": "TRUE"
}

def get_google_search_keys():
    return st.secrets.get("GOOGLE_SEARCH_API_KEY"), st.secrets.get("GOOGLE_SEARCH_CX")

# =============================================================================
# 1. GESTION DES DONNÉES (CORRECTIF PERSISTANCE V51)
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
    except Exception as e: 
        return None

def get_app_config():
    """Lit la config et assure la synchro des clés manquantes."""
    wb = get_gsheet_workbook()
    config_dict = DEFAULT_APP_CONFIG.copy()
    
    if wb:
        try:
            try: 
                sheet = wb.worksheet("MIA_App_Config")
            except:
                # Création initiale si n'existe pas
                sheet = wb.add_worksheet("MIA_App_Config", 20, 2)
                sheet.append_row(["Setting_Key", "Value"])
                for k, v in DEFAULT_APP_CONFIG.items(): sheet.append_row([k, v])
                return config_dict
            
            # Lecture des données existantes
            rows = sheet.get_all_values()
            existing_keys = set()
            
            if len(rows) > 1:
                for row in rows[1:]:
                    if len(row) >= 2:
                        key = str(row[0]).strip()
                        val = str(row[1]).strip()
                        config_dict[key] = val
                        existing_keys.add(key)
            
            # AUTO-SYNC : Si une clé par défaut manque dans le Sheet, on l'ajoute
            # Cela corrige le problème de persistance des nouveaux boutons
            missing_keys = [k for k in DEFAULT_APP_CONFIG.keys() if k not in existing_keys]
            if missing_keys:
                for k in missing_keys:
                    sheet.append_row([k, DEFAULT_APP_CONFIG[k]])
                    
        except: pass
    return config_dict

def update_app_config(key, value):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sheet = wb.worksheet("MIA_App_Config")
            cell = sheet.find(key)
            if cell:
                sheet.update_cell(cell.row, 2, str(value))
            else:
                sheet.append_row([key, str(value)])
            
            st.cache_data.clear() # Force le rechargement
            return True
        except: pass
    return False

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

# --- HELPERS BDD ---
def get_markets():
    wb = get_gsheet_workbook()
    if wb:
        try: 
            vals = wb.sheet1.col_values(1)
            if not vals:
                 for m in config.DEFAULT_MARKETS: wb.sheet1.append_row([m])
                 return config.DEFAULT_MARKETS, True
            return vals, True
        except: pass
    return [], False

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
                return DEFAULT_DOMAINS, True
            vals = sheet.col_values(1)
            if not vals:
                 for d in DEFAULT_DOMAINS: sheet.append_row([d])
                 return DEFAULT_DOMAINS, True
            return vals, True
        except: pass
    return [], False

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

def get_watchlists():
    wb = get_gsheet_workbook()
    watchlists = []
    if wb:
        try:
            try: sheet = wb.worksheet("Watchlists")
            except: 
                sheet = wb.add_worksheet("Watchlists", 100, 5)
                sheet.append_row(["ID", "Name", "Topic", "Markets", "Timeframe"])
                return []
            rows = sheet.get_all_values()
            if len(rows) > 1:
                for row in rows[1:]:
                    if len(row) >= 5:
                        watchlists.append({"id":row[0], "name":row[1], "topic":row[2], "markets":row[3], "timeframe":row[4]})
        except: pass
    return watchlists

def save_watchlist(name, topic, markets_list, timeframe):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sheet = wb.worksheet("Watchlists")
            sheet.append_row([str(uuid.uuid4())[:8], name, topic, ", ".join(markets_list), timeframe])
            return True
        except: pass
    return False

def delete_watchlist(watchlist_id):
    wb = get_gsheet_workbook()
    if wb:
        try:
            sheet = wb.worksheet("Watchlists")
            cell = sheet.find(watchlist_id)
            if cell: sheet.delete_rows(cell.row); return True
        except: pass
    return False

# =============================================================================
# 2. INITIALISATION SESSION STATE
# =============================================================================
def init_session_state():
    if "app_config" not in st.session_state:
        st.session_state["app_config"] = get_app_config()

    defaults = {
        "authenticated": False,
        "admin_authenticated": False,
        "current_page": "Dashboard",
        "last_olivia_report": None,
        "last_olivia_id": None, 
        "last_eva_report": None,
        "last_eva_id": None,
        "last_mia_results": None,
        "mia_impact_results": {}, 
        "active_analysis_id": None,
        "editing_market_index": None,
        "editing_domain_index": None,
        "mia_topic_val": "",
        "mia_markets_val": [],
        "mia_timeframe_index": 1,
        "current_watchlist": None,
        "mia_raw_count": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# 4. API & SEARCH & CACHING
# =============================================================================
def get_api_key(): return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
def get_openai_client():
    k = get_api_key()
    return OpenAI(api_key=k) if k else None

def extract_pdf_content_by_density(pdf_bytes, keywords, window_size=500):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        for page in doc: full_text += page.get_text() + "\n"
        doc.close()
        if not full_text.strip(): return "Error: Scanned PDF."
        
        words = re.findall(r'\b\w+\b', full_text.lower())
        norm_keywords = [w.lower() for w in keywords if len(w) > 2]
        if not norm_keywords: return full_text[:3000] 

        best_score = -1
        best_window_text = ""
        for i in range(0, len(words), 100):
            end = min(i + window_size, len(words))
            window = words[i:end]
            score = sum(window.count(k) for k in norm_keywords)
            if score > best_score:
                best_score = score
                snippet_start = full_text.lower().find(' '.join(words[i:i+5]).lower())
                if snippet_start != -1:
                    best_window_text = full_text[snippet_start : snippet_start + 4000]
        return best_window_text.strip() if best_window_text else full_text[:3000]
    except: return "PDF Error"

async def async_google_search(query, domains, max_results, date_restrict=None):
    # V48+ : Check Master Switch
    config = st.session_state.get("app_config", {})
    if config.get("provider_google", "TRUE") == "FALSE":
        return {"items": []}, "Google Search Disabled by Admin"

    api_key, cx = get_google_search_keys()
    if not api_key or not cx: return {"items": []}, "Google Search Keys Missing"

    BATCH_SIZE = 8
    domain_batches = [domains[i:i + BATCH_SIZE] for i in range(0, len(domains), BATCH_SIZE)]
    results_per_batch = min(max(int(int(max_results) / len(domain_batches)), 10), 20)

    base_url = "https://www.googleapis.com/customsearch/v1"
    tasks = []

    for batch in domain_batches:
        sites_str = " OR ".join([f"site:{d.strip()}" for d in batch if d.strip()])
        final_query = f"{query} {sites_str}"
        for start_index in range(1, results_per_batch + 1, 10):
            params = {'key': api_key, 'cx': cx, 'q': final_query, 'num': min(10, results_per_batch - start_index + 1), 'start': start_index}
            if date_restrict: params['dateRestrict'] = date_restrict
            tasks.append(params)

    async with aiohttp.ClientSession() as session:
        all_items = []
        fatal_error = None
        
        async def fetch_task(p):
            nonlocal fatal_error
            try:
                async with session.get(base_url, params=p) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('items', [])
                    elif response.status == 429:
                        fatal_error = "Google Quota Exceeded (429)"
                        return []
                    elif response.status == 403:
                        fatal_error = "Google Permission Denied (403)"
                        return []
                    return []
            except Exception as e:
                return []

        results_lists = await asyncio.gather(*[fetch_task(p) for p in tasks])
        
        if fatal_error: return {"items": []}, fatal_error

        for r_list in results_lists: all_items.extend(r_list)

        seen_links = set()
        unique_items = []
        for item in all_items:
            link = item.get('link')
            if link and link not in seen_links:
                seen_links.add(link)
                unique_items.append(item)

        return {"items": unique_items}, None

async def async_fetch_and_process_source(item, query_keywords, tavily_key):
    url = item.get('link')
    title = item.get('title')
    if not url: return None
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if url.lower().endswith('.pdf'):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200 and 'application/pdf' in resp.headers.get('Content-Type', ''):
                        pdf_bytes = await resp.read()
                        content = extract_pdf_content_by_density(pdf_bytes, query_keywords)
                        return {"source": url, "type": "pdf", "title": title, "content": content}
        except: pass 

    # V48+ : Check Tavily Switch
    config = st.session_state.get("app_config", {})
    if config.get("provider_tavily", "TRUE") == "TRUE":
        try:
            if not tavily_key: return None
            tavily = TavilyClient(api_key=tavily_key)
            response = tavily.search(query=url, search_depth="basic", max_results=1)
            if response and response.get('results'):
                content = response['results'][0]['content']
                return {"source": url, "type": "web", "title": title, "content": content[:8000]}
        except: pass
        
    return None

@st.cache_data(show_spinner=False, ttl=3600)
def cached_async_mia_deep_search(query, date_restrict_code, max_results):
    try:
        doms, _ = get_domains()
        tavily_key = st.secrets.get("TAVILY_API_KEY")
        if not doms: return None, "Configuration Error", 0
        
        keywords = re.findall(r'\b\w+\b', query.lower())

        async def run_pipeline():
            google_json, error = await async_google_search(query, doms, max_results, date_restrict=date_restrict_code)
            
            # V48+ : Gestion Disabled sans erreur fatale
            if error and "Disabled" in error:
                return [], 0, "DISABLED"
            if error: 
                return [], 0, error
            
            items = google_json.get('items', [])
            real_count = len(items)
            
            tasks = [async_fetch_and_process_source(i, keywords, tavily_key) for i in items]
            processed_results = await asyncio.gather(*tasks)
            return processed_results, real_count, None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        results, raw_count, error_msg = loop.run_until_complete(run_pipeline())
        
        if error_msg == "DISABLED":
            return "DISABLED", "Google Search Disabled", 0
        if error_msg: 
            return None, error_msg, 0
        
        clean_results = [r for r in results if r is not None]
        
        txt = f"### INTELLIGENT SEARCH ({raw_count} sources found, {len(clean_results)} processed):\n"
        for r in clean_results:
            txt += f"- Title: {r['title']}\n  URL: {r['source']}\n  Type: {r['type'].upper()}\n  Content: {r['content'][:800]}...\n\n"
            
        return txt, None, raw_count

    except Exception as e: return None, str(e), 0

@st.cache_data(show_spinner=False)
def cached_ai_generation(prompt, model, temp, json_mode=False, messages=None):
    client = get_openai_client()
    if not client: return None
    if messages: final_messages = messages
    else: final_messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "messages": final_messages, "temperature": temp}
    if json_mode: kwargs["response_format"] = {"type": "json_object"}
    res = client.chat.completions.create(**kwargs)
    return res.choices[0].message.content

def extract_text_from_pdf(b):
    try:
        r = PdfReader(io.BytesIO(b)); txt=[]
        for p in r.pages: txt.append(p.extract_text() or "")
        return "\n".join(txt)
    except: return "Error reading PDF"

# =============================================================================
# 5. VISUALISATION
# =============================================================================
def display_timeline(items):
    if not items: return
    timeline_data = []
    for item in items:
        if not isinstance(item, dict): continue
        if "timeline" in item and isinstance(item["timeline"], list) and item["timeline"]:
            for event in item["timeline"]:
                if isinstance(event, dict):
                    timeline_data.append({
                        "Task": event.get("label", "Event"),
                        "Date": event.get("date"),
                        "Description": f"{item.get('title','Update')}: {event.get('desc', '')}",
                        "Source": item.get("source_name", "Web")
                    })
        elif "date" in item:
            timeline_data.append({
                "Task": "Publication",
                "Date": item.get("date"),
                "Description": item.get("title", "Update"),
                "Source": item.get("source_name", "Web")
            })

    if not timeline_data: return
    df = pd.DataFrame(timeline_data)
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce', utc=True)
    df = df.dropna(subset=["Date"])
    if df.empty: return
    
    df["Date"] = df["Date"].dt.tz_localize(None)
    now = datetime.now()
    def get_color(d):
        delta = (d - now).days
        if delta < 0: return "Gray"
        if delta < 180: return "#e53935"
        if delta < 540: return "#fb8c00"
        return "#1E88E5"
    df["Color"] = df["Date"].apply(get_color)

    fig = px.scatter(
        df, x="Date", y=[1]*len(df), color="Color",
        hover_data=["Task", "Description", "Source"],
        color_discrete_map="identity", height=130
    )
    start_view = now - timedelta(days=365)
    end_view = now + timedelta(days=1095)
    fig.update_xaxes(range=[start_view, end_view], showgrid=True, gridcolor="#eee", zeroline=False)
    fig.update_yaxes(visible=False, showticklabels=False)
    fig.add_vline(x=now.timestamp() * 1000, line_width=2, line_dash="dot", line_color="#295A63", annotation_text="Today")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor='white', paper_bgcolor='white', showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.caption("🔘 Past Event")
    with c2: st.caption("🔴 < 6 Months (Urgent)")
    with c3: st.caption("🟠 < 18 Months (Plan)")
    with c4: st.caption("🔵 > 18 Months (Radar)")

# =============================================================================
# 6. AUTH & PROMPTS
# =============================================================================
def check_password_manual(token):
    correct_token = st.secrets.get("APP_TOKEN")
    if not correct_token:
        st.session_state["authenticated"] = True
        st.rerun()
    if token == correct_token:
        st.session_state["authenticated"] = True
        st.rerun()
    else: st.error("🚫 Access Denied: Invalid Token")

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
    # MODIF V48+ : Context "Sans Source"
    source_context = raw_search_data
    if raw_search_data == "DISABLED" or not raw_search_data:
        source_context = "NO EXTERNAL SOURCES AVAILABLE. USE YOUR INTERNAL KNOWLEDGE BASE (GPT-4o) TO GENERATE RELEVANT INSIGHTS FOR THIS TOPIC."

    return f"""
ROLE: You are MIA, a Regulatory Scout responsible for gathering ANY potential intelligence signal.
CONTEXT: Topic: "{topic}" | Markets: {', '.join(markets)} | Timeframe: {timeframe_label}
PHILOSOPHY: MAXIMIZE RECALL. Include "Low Impact" items. Even blogs/news are signals.
MODE: {"PURE KNOWLEDGE GENERATION" if raw_search_data == "DISABLED" else "SEARCH ANALYSIS"}

OUTPUT FORMAT (STRICT JSON):
{{
  "executive_summary": "Summary of signals.",
  "items": [
    {{
      "title": "Title",
      "date": "YYYY-MM-DD",
      "source_name": "Source (or AI Knowledge)",
      "url": "URL (or 'Internal')",
      "summary": "Summary.",
      "tags": ["Tag1"],
      "impact": "High/Medium/Low",
      "category": "Regulation/Standard/Guidance/Enforcement/News",
      "timeline": []
    }}
  ]
}}
RAW SEARCH DATA:
{source_context}
"""

def create_impact_analysis_prompt(prod_desc, item_content):
    return f"""
    ROLE: Senior Regulatory Affairs Expert.
    TASK: Specific Impact Assessment.
    PRODUCT CONTEXT: "{prod_desc}"
    REGULATORY UPDATE: "{item_content}"
    MISSION: Provide a factual Gap Analysis. Output: Markdown.
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

def apply_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Montserrat', sans-serif !important; color: #295A63 !important; }
    div.stButton > button:first-child { background-color: #295A63 !important; color: white !important; border-radius: 8px; font-weight: 600; width: 100%; border: none; }
    div.stButton > button:first-child:hover { background-color: #C8A951 !important; color: black !important; }
    .info-card { background-color: white; padding: 2rem; border-radius: 12px; border: 1px solid #E2E8F0; min-height: 220px; display: flex; flex-direction: column; justify-content: flex-start; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .stTextInput > div > div:focus-within { border-color: #295A63 !important; box-shadow: 0 0 0 1px #295A63 !important; }
    .justified-text { text-align: justify; line-height: 1.6; color: #2c3e50; background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #295A63; }
    .mia-link a { color: #295A63 !important; text-decoration: none; font-weight: 700; font-size: 1.1em; border-bottom: 2px solid #C8A951; }
    .mia-link a:hover { color: #C8A951 !important; background-color: #f0f0f0; }
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

    tm, td, tc = st.tabs(["🌍 Markets", "🕵️‍♂️ MIA Sources", "🎛️ MIA Settings"])
    with tm:
        mkts, _ = get_markets()
        with st.form("add_m"):
            c1, c2 = st.columns([4,1], vertical_alignment="bottom")
            new = c1.text_input("Name")
            if c2.form_submit_button("Add", use_container_width=True) and new: add_market(new); st.rerun()
        for i, m in enumerate(mkts):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.info(f"🌍 {m}")
            if c3.button("🗑️", key=f"dm{i}"):
                with st.popover("🗑️"): 
                     st.write("Delete?")
                     if st.button("Yes", key=f"y_m_{i}"): remove_market(i); st.rerun()
    with td:
        doms, _ = get_domains()
        with st.form("add_d"):
            c1, c2 = st.columns([4,1], vertical_alignment="bottom")
            new = c1.text_input("Domain")
            if c2.form_submit_button("Add", use_container_width=True) and new: add_domain(new); st.rerun()
        for i, d in enumerate(doms):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.success(f"🌐 {d}")
            if c3.button("🗑️", key=f"dd{i}"):
                with st.popover("🗑️"):
                     st.write("Delete?")
                     if st.button("Yes", key=f"y_d_{i}"): remove_domain(i); st.rerun()
    with tc:
        app_config = st.session_state.get("app_config", get_app_config())
        
        # --- SECTION PROVIDERS (FIX UX V51: INVERSION) ---
        st.markdown("#### 🔌 Search Providers (Feature Flags)")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            curr_google = app_config.get("provider_google", "TRUE") == "TRUE"
            new_google = st.toggle("Enable Google Search (Discovery)", value=curr_google)
            if new_google != curr_google:
                update_app_config("provider_google", "TRUE" if new_google else "FALSE")
                st.session_state["app_config"]["provider_google"] = "TRUE" if new_google else "FALSE"
                st.rerun()
        
        with c_p2:
            # FIX: Assess Impact déplacé ici pour l'harmonie
            curr_impact = app_config.get("enable_impact_analysis", "TRUE") == "TRUE"
            new_impact = st.toggle("Enable 'Assess Impact' Feature", value=curr_impact)
            if new_impact != curr_impact:
                update_app_config("enable_impact_analysis", "TRUE" if new_impact else "FALSE")
                st.session_state["app_config"]["enable_impact_analysis"] = "TRUE" if new_impact else "FALSE"
                st.rerun()

        st.write("")
        c_p3, c_p4 = st.columns(2)
        with c_p3:
            # FIX: Tavily déplacé ici (Ligne 2)
            curr_tavily = app_config.get("provider_tavily", "TRUE") == "TRUE"
            new_tavily = st.toggle("Enable Tavily (Deep Read)", value=curr_tavily)
            if new_tavily != curr_tavily:
                update_app_config("provider_tavily", "TRUE" if new_tavily else "FALSE")
                st.session_state["app_config"]["provider_tavily"] = "TRUE" if new_tavily else "FALSE"
                st.rerun()

        st.markdown("---")
        st.markdown("#### Performance")
        
        c_perf1, c_perf2 = st.columns(2)
        with c_perf1:
            curr_ttl = app_config.get("cache_ttl_hours", "1")
            new_ttl = st.text_input("Cache Duration (Hours)", value=curr_ttl)
            if st.button("Update Cache"):
                update_app_config("cache_ttl_hours", new_ttl)
                st.session_state["app_config"]["cache_ttl_hours"] = new_ttl
                st.success("Saved.")
        
        with c_perf2:
            curr_max = app_config.get("max_search_results", "20")
            new_max = st.text_input("🎯 Target Sources Volume (Max 100)", value=curr_max)
            if st.button("Update Volume"):
                if new_max.isdigit() and 1 <= int(new_max) <= 100:
                    update_app_config("max_search_results", new_max)
                    st.session_state["app_config"]["max_search_results"] = new_max
                    st.success("Updated!")

def page_mia():
    st.title("📡 MIA Watch Tower"); st.markdown("---")
    app_config = st.session_state.get("app_config", get_app_config())
    try: max_res = int(app_config.get("max_search_results", 20))
    except: max_res = 20

    watchlists = get_watchlists()
    wl_names = ["-- New Watch --"] + [w["name"] for w in watchlists]
    
    with st.expander("📂 Manage Watchlists (Load / Save)", expanded=False):
        c_load, c_action = st.columns([3, 1])
        with c_load: selected_wl = st.selectbox("Load", wl_names, label_visibility="collapsed")
        
        if selected_wl != "-- New Watch --" and st.session_state.get("current_watchlist") != selected_wl:
            wl_data = next((w for w in watchlists if w["name"] == selected_wl), None)
            if wl_data:
                st.session_state["mia_topic_val"] = wl_data["topic"]
                st.session_state["mia_markets_val"] = [m.strip() for m in wl_data["markets"].split(",")]
                timeframe_map = {"⚡ Last 30 Days": 30, "📅 Last 12 Months": 365, "🏛️ Last 3 Years": 1095}
                try: st.session_state["mia_timeframe_index"] = list(timeframe_map.keys()).index(wl_data["timeframe"])
                except: st.session_state["mia_timeframe_index"] = 1
                st.session_state["current_watchlist"] = selected_wl
                st.toast(f"✅ Loaded: {selected_wl}")
        
        if selected_wl != "-- New Watch --":
             with c_action:
                 with st.popover("🗑️ Delete"):
                     if st.button("Confirm Delete"):
                         wl = next((w for w in watchlists if w["name"] == selected_wl), None)
                         if wl and delete_watchlist(wl["id"]): st.success("Deleted."); st.cache_data.clear(); st.rerun()

    markets, _ = get_markets()
    col1, col2, col3 = st.columns([2, 2, 1], gap="large")
    with col1: 
        topic = st.text_input("🔎 Watch Topic / Product", value=st.session_state.get("mia_topic_val", ""), placeholder="e.g. lithium batteries")
    with col2: 
        default_mkts = [m for m in st.session_state.get("mia_markets_val", []) if m in markets]
        if not default_mkts and markets: default_mkts = [markets[0]]
        selected_markets = st.multiselect("🌍 Markets", markets, default=default_mkts)
    with col3:
        timeframe_options = { "⚡ Last 30 Days": "d30", "📅 Last 12 Months": "m12", "🏛️ Last 3 Years": "y3" }
        selected_label = st.selectbox("⏱️ Timeframe", list(timeframe_options.keys()), index=st.session_state.get("mia_timeframe_index", 1))
        date_restrict_code = timeframe_options[selected_label]

    launch_label = f"🚀 Launch {selected_wl}" if selected_wl != "-- New Watch --" else "🚀 Launch Monitoring"
    
    c_launch, c_save = st.columns([1, 4])
    with c_launch: launch = st.button(launch_label, type="primary")
    with c_save:
        if topic:
            with st.popover("💾 Save as Watchlist"):
                new_wl_name = st.text_input("Name your watchlist")
                if st.button("Save"):
                    if new_wl_name and topic:
                        save_watchlist(new_wl_name, topic, selected_markets, selected_label)
                        st.toast("Saved!", icon="💾")
                        st.cache_data.clear()
                        st.rerun()
                        
    if launch and topic:
        with st.spinner(f"📡 MIA is scanning... ({selected_label})"):
            clean_timeframe = selected_label.replace("⚡ ", "").replace("📅 ", "").replace("🏛️ ", "")
            query = f"regulations guidelines {topic} {', '.join(selected_markets)}"
            
            raw_data, error, raw_count = cached_async_mia_deep_search(query, date_restrict_code, max_res)
            
            is_offline_mode = (raw_data == "DISABLED")
            
            if not is_offline_mode and not raw_data and error:
                st.error(f"🛑 Critical Search Error: {error}")
                st.stop()
            elif not is_offline_mode and raw_count == 0:
                st.warning(f"⚠️ No updates found on Google. (Try enabling 'Pure GPT-4o Mode' by disabling Google in Admin).")
                st.stop()
            
            st.session_state["mia_raw_count"] = raw_count if not is_offline_mode else 0
            
            if is_offline_mode:
                st.info("🧠 Offline Mode Active: Generating insights from internal knowledge base.")

            prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
            json_str = cached_ai_generation(prompt, "gpt-4o", 0.1, json_mode=True)
            try:
                parsed_data = json.loads(json_str)
                if "items" not in parsed_data: parsed_data["items"] = []
                parsed_data["source_count"] = raw_count if not is_offline_mode else 0
                
                for item in parsed_data["items"]:
                    if "impact" not in item: item["impact"] = "Low"
                    if "category" not in item: item["category"] = "News"
                    item["impact"] = item["impact"].capitalize()
                    item["category"] = item["category"].capitalize()
                st.session_state["last_mia_results"] = parsed_data
                log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label} | Offline:{is_offline_mode}")
            except Exception as e: st.error(f"Data processing failed: {str(e)}")

    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("### 📋 Monitoring Report")
        
        raw_c = results.get("source_count", st.session_state.get("mia_raw_count", 0))
        kept_c = len(results.get("items", []))
        
        if raw_c == 0:
            st.caption(f"🧠 MIA Intelligence: Generated from Internal Knowledge (Offline Mode)")
        else:
            st.caption(f"🔍 MIA Intelligence: Analyzed {raw_c} sources → Kept {kept_c} relevant updates.")

        if results.get("items"):
            with st.expander("📅 View Strategic Timeline", expanded=False):
                display_timeline(results["items"])
        
        st.markdown("---")
        summary = results.get('executive_summary', 'No summary.')
        st.markdown(f"""<div class="justified-text"><strong>Executive Summary:</strong> {summary}</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        c_filter1, c_filter2, c_legend = st.columns([2, 2, 1], gap="large")
        with c_filter1:
            all_cat = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            sel_types = st.multiselect("🗂️ Filter by Type", all_cat, default=all_cat)
        with c_filter2:
            sel_impacts = st.multiselect("🌪️ Filter by Impact", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
        with c_legend:
            st.markdown("<div><span style='color:#e53935'>●</span> High <span style='color:#fb8c00'>●</span> Medium <span style='color:#43a047'>●</span> Low</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        items = results.get("items", [])
        filtered = [i for i in items if i.get('impact','Low').capitalize() in sel_impacts and i.get('category','News').capitalize() in sel_types]
        
        if not filtered: st.warning("No updates found matching filters.")
        for item in filtered:
            impact = item.get('impact', 'Low').lower()
            cat = item.get('category', 'News')
            icon = "🔴" if impact == 'high' else "🟡" if impact == 'medium' else "🟢"
            cat_map = {"Regulation":"🏛️", "Standard":"📏", "Guidance":"📘", "Enforcement":"📢", "News":"📰"}
            
            safe_id = hashlib.md5(item['title'].encode()).hexdigest()
            is_active = (st.session_state.get("active_analysis_id") == safe_id)
            
            with st.container():
                st.markdown(f"""
                <div class="info-card" style="min-height:auto; padding:1.5rem; margin-bottom:1rem;">
                    <div style="display:flex;">
                        <div style="font-size:1.5rem; margin-right:15px;">{icon}</div>
                        <div>
                            <div class="mia-link"><a href="{item['url']}" target="_blank">{cat_map.get(cat,'📄')} {item['title']}</a></div>
                            <div style="font-size:0.85em; opacity:0.7; margin-bottom:5px; color:#4A5568;">📅 {item['date']} | 🏛️ {item['source_name']}</div>
                            <div style="color:#2D3748;">{item['summary']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.session_state.get("app_config", {}).get("enable_impact_analysis", "TRUE") == "TRUE":
                    with st.expander(f"⚡ Analyze Impact (Beta)", expanded=is_active):
                        prod_ctx = st.text_input("Product Context:", value=topic, key=f"ctx_{safe_id}")
                        if st.button("Generate Analysis", key=f"btn_{safe_id}"):
                            st.session_state["active_analysis_id"] = safe_id
                            with st.spinner("Evaluating..."):
                                ia_prompt = create_impact_analysis_prompt(prod_ctx, f"{item['title']}: {item['summary']}")
                                ia_res = cached_ai_generation(ia_prompt, "gpt-4o", 0.1)
                                st.session_state["mia_impact_results"][safe_id] = ia_res
                                st.rerun()
                        if safe_id in st.session_state["mia_impact_results"]:
                            st.markdown("---")
                            st.markdown(st.session_state["mia_impact_results"][safe_id])

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
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown(f"""<div style="text-align: center;">{get_logo_html(100)}<h1 style="color: #295A63;">{config.APP_NAME}</h1><p style="color: #C8A951;">{config.APP_TAGLINE}</p></div>""", unsafe_allow_html=True)
        st.write("")
        token = st.text_input("🔐 Access Token", type="password")
        if st.button("Enter", type="primary", use_container_width=True): check_password_manual(token)

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

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

# =============================================================================
# CHARTE GRAPHIQUE - COULEURS
# =============================================================================
COLORS = {
    "primary": "#295A63",      # Vert Valhallai
    "secondary": "#C8A951",    # Or
    "dark": "#1A3C42",         # Vert foncé
    "light_gold": "#E6D5A7",   # Or clair
    "white": "#FFFFFF",
    "light_bg": "#F7F9FA",
    "light_card": "#FFFFFF",
    "light_border": "#E2E8F0",
    "light_text": "#1A202C",
    "light_text_muted": "#64748B",
    "dark_bg": "#0E1117",
    "dark_card": "#1E2530",
    "dark_border": "#2D3748",
    "dark_text": "#F7FAFC",
    "dark_text_muted": "#A0AEC0",
}

# =============================================================================
# INJECTION CSS - CHARTE GRAPHIQUE COMPLÈTE
# =============================================================================
def inject_custom_css():
    is_dark = st.session_state.get("dark_mode", False)
    
    # Variables dynamiques selon le mode
    bg_color = COLORS["dark_bg"] if is_dark else COLORS["light_bg"]
    card_bg = COLORS["dark_card"] if is_dark else COLORS["light_card"]
    border_color = COLORS["dark_border"] if is_dark else COLORS["light_border"]
    text_color = COLORS["dark_text"] if is_dark else COLORS["light_text"]
    text_muted = COLORS["dark_text_muted"] if is_dark else COLORS["light_text_muted"]
    title_color = COLORS["secondary"] if is_dark else COLORS["primary"]
    sidebar_bg = COLORS["dark"] if is_dark else COLORS["primary"]
    
    st.markdown(f"""
    <style>
    /* ============================================= */
    /* IMPORT FONTS                                  */
    /* ============================================= */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Inter:wght@300;400;500;600&display=swap');
    
    /* ============================================= */
    /* VARIABLES CSS                                 */
    /* ============================================= */
    :root {{
        --color-primary: {COLORS["primary"]};
        --color-secondary: {COLORS["secondary"]};
        --color-dark: {COLORS["dark"]};
        --color-bg: {bg_color};
        --color-card: {card_bg};
        --color-border: {border_color};
        --color-text: {text_color};
        --color-text-muted: {text_muted};
        --color-title: {title_color};
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.15);
        --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        --spacing-xs: 0.5rem;
        --spacing-sm: 1rem;
        --spacing-md: 1.5rem;
        --spacing-lg: 2rem;
        --spacing-xl: 3rem;
    }}
    
    /* ============================================= */
    /* BASE & TYPOGRAPHY                             */
    /* ============================================= */
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--color-text);
    }}
    
    .stApp {{
        background-color: var(--color-bg) !important;
    }}
    
    /* Titres */
    h1 {{
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 700 !important;
        font-size: 2.25rem !important;
        color: var(--color-title) !important;
        letter-spacing: -0.02em !important;
        margin-bottom: var(--spacing-sm) !important;
    }}
    
    h2 {{
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.5rem !important;
        color: var(--color-title) !important;
        letter-spacing: -0.01em !important;
    }}
    
    h3 {{
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.25rem !important;
        color: var(--color-title) !important;
    }}
    
    p, span, label {{
        font-size: 0.95rem;
        line-height: 1.6;
    }}
    
    /* ============================================= */
    /* SIDEBAR                                       */
    /* ============================================= */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {sidebar_bg} 0%, {COLORS["dark"]} 100%) !important;
        padding-top: var(--spacing-md);
    }}
    
    [data-testid="stSidebar"] * {{
        color: {COLORS["white"]} !important;
    }}
    
    [data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.15) !important;
        margin: var(--spacing-md) 0 !important;
    }}
    
    /* Sidebar Radio Navigation */
    [data-testid="stSidebar"] [role="radiogroup"] {{
        gap: 4px !important;
    }}
    
    [data-testid="stSidebar"] [role="radiogroup"] label {{
        background-color: rgba(255,255,255,0.05) !important;
        border-radius: var(--radius-sm) !important;
        padding: 0.75rem 1rem !important;
        margin: 2px 0 !important;
        transition: var(--transition) !important;
        border: 1px solid transparent !important;
    }}
    
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
        background-color: rgba(255,255,255,0.1) !important;
        border-color: rgba(200,169,81,0.3) !important;
    }}
    
    [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] {{
        background-color: {COLORS["secondary"]} !important;
        color: {COLORS["dark"]} !important;
        font-weight: 600 !important;
    }}
    
    [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] * {{
        color: {COLORS["dark"]} !important;
    }}
    
    /* Sidebar Buttons */
    [data-testid="stSidebar"] .stButton > button {{
        background-color: rgba(255,255,255,0.1) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: var(--transition) !important;
    }}
    
    [data-testid="stSidebar"] .stButton > button:hover {{
        background-color: {COLORS["secondary"]} !important;
        color: {COLORS["dark"]} !important;
        border-color: {COLORS["secondary"]} !important;
        transform: translateY(-1px) !important;
    }}
    
    /* ============================================= */
    /* BOUTONS - STYLE PRINCIPAL                     */
    /* ============================================= */
    .stButton > button {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["dark"]} 100%) !important;
        color: {COLORS["white"]} !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.65rem 1.5rem !important;
        letter-spacing: 0.02em !important;
        transition: var(--transition) !important;
        box-shadow: var(--shadow-sm) !important;
    }}
    
    .stButton > button:hover {{
        background: linear-gradient(135deg, {COLORS["secondary"]} 0%, {COLORS["light_gold"]} 100%) !important;
        color: {COLORS["dark"]} !important;
        transform: translateY(-2px) !important;
        box-shadow: var(--shadow-md) !important;
    }}
    
    .stButton > button:active {{
        transform: translateY(0) !important;
        box-shadow: var(--shadow-sm) !important;
    }}
    
    /* Bouton Primary (type="primary") */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, {COLORS["secondary"]} 0%, {COLORS["light_gold"]} 100%) !important;
        color: {COLORS["dark"]} !important;
        font-weight: 700 !important;
    }}
    
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["dark"]} 100%) !important;
        color: {COLORS["white"]} !important;
    }}
    
    /* ============================================= */
    /* INPUTS & FORM ELEMENTS                        */
    /* ============================================= */
    .stTextInput > div > div,
    .stTextArea > div > div,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {{
        background-color: var(--color-card) !important;
        border: 2px solid var(--color-border) !important;
        border-radius: var(--radius-sm) !important;
        transition: var(--transition) !important;
    }}
    
    .stTextInput > div > div:focus-within,
    .stTextArea > div > div:focus-within,
    .stSelectbox > div > div:focus-within,
    .stMultiSelect > div > div:focus-within {{
        border-color: {COLORS["primary"]} !important;
        box-shadow: 0 0 0 3px rgba(41,90,99,0.15) !important;
    }}
    
    .stTextInput input,
    .stTextArea textarea {{
        color: var(--color-text) !important;
        font-family: 'Inter', sans-serif !important;
    }}
    
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{
        color: var(--color-text-muted) !important;
        opacity: 0.7 !important;
    }}
    
    /* Labels */
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stMultiSelect label,
    .stFileUploader label {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        color: var(--color-text) !important;
        margin-bottom: 0.5rem !important;
    }}
    
    /* Multiselect Tags */
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: {COLORS["primary"]} !important;
        border-radius: 6px !important;
    }}
    
    /* ============================================= */
    /* CARDS & CONTAINERS                            */
    /* ============================================= */
    .valhalla-card {{
        background-color: var(--color-card);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        padding: var(--spacing-md);
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
        height: 100%;
        display: flex;
        flex-direction: column;
    }}
    
    .valhalla-card:hover {{
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
        border-color: {COLORS["secondary"]};
    }}
    
    .valhalla-card-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: var(--spacing-sm);
    }}
    
    .valhalla-card-icon {{
        font-size: 2rem;
        line-height: 1;
    }}
    
    .valhalla-card-title {{
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 1.25rem;
        color: var(--color-title);
        margin: 0;
    }}
    
    .valhalla-card-body {{
        flex: 1;
        color: var(--color-text-muted);
        font-size: 0.95rem;
        line-height: 1.6;
    }}
    
    .valhalla-card-footer {{
        margin-top: var(--spacing-sm);
        padding-top: var(--spacing-sm);
        border-top: 1px solid var(--color-border);
    }}
    
    /* Info Card (MIA results) */
    .info-card {{
        background-color: var(--color-card);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        padding: var(--spacing-md);
        margin-bottom: var(--spacing-sm);
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}
    
    .info-card:hover {{
        border-left: 4px solid {COLORS["secondary"]};
        box-shadow: var(--shadow-md);
    }}
    
    /* ============================================= */
    /* ALERTS & MESSAGES                             */
    /* ============================================= */
    .stSuccess {{
        background-color: rgba(41,90,99,0.1) !important;
        border-left: 4px solid {COLORS["primary"]} !important;
        border-radius: var(--radius-sm) !important;
    }}
    
    .stInfo {{
        background-color: rgba(200,169,81,0.1) !important;
        border-left: 4px solid {COLORS["secondary"]} !important;
        border-radius: var(--radius-sm) !important;
    }}
    
    .stWarning {{
        background-color: rgba(200,169,81,0.15) !important;
        border-left: 4px solid {COLORS["secondary"]} !important;
        border-radius: var(--radius-sm) !important;
    }}
    
    /* ============================================= */
    /* TABS                                          */
    /* ============================================= */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: transparent;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background-color: var(--color-card) !important;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
        border: 1px solid var(--color-border) !important;
        border-bottom: none !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 500 !important;
        color: var(--color-text-muted) !important;
        transition: var(--transition) !important;
    }}
    
    .stTabs [data-baseweb="tab"]:hover {{
        color: {COLORS["primary"]} !important;
    }}
    
    .stTabs [aria-selected="true"] {{
        background-color: {COLORS["primary"]} !important;
        color: white !important;
        border-color: {COLORS["primary"]} !important;
    }}
    
    /* ============================================= */
    /* FILE UPLOADER                                 */
    /* ============================================= */
    .stFileUploader {{
        border: 2px dashed var(--color-border) !important;
        border-radius: var(--radius-md) !important;
        padding: var(--spacing-md) !important;
        background-color: var(--color-card) !important;
        transition: var(--transition) !important;
    }}
    
    .stFileUploader:hover {{
        border-color: {COLORS["primary"]} !important;
        background-color: rgba(41,90,99,0.05) !important;
    }}
    
    /* ============================================= */
    /* DOWNLOAD BUTTON                               */
    /* ============================================= */
    .stDownloadButton > button {{
        background: linear-gradient(135deg, {COLORS["secondary"]} 0%, {COLORS["light_gold"]} 100%) !important;
        color: {COLORS["dark"]} !important;
        font-weight: 600 !important;
    }}
    
    .stDownloadButton > button:hover {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["dark"]} 100%) !important;
        color: white !important;
    }}
    
    /* ============================================= */
    /* CHECKBOX (Dark Mode Toggle)                   */
    /* ============================================= */
    [data-testid="stSidebar"] .stCheckbox {{
        background-color: rgba(255,255,255,0.05) !important;
        padding: 0.75rem 1rem !important;
        border-radius: var(--radius-sm) !important;
        margin-top: var(--spacing-xs) !important;
    }}
    
    [data-testid="stSidebar"] .stCheckbox:hover {{
        background-color: rgba(255,255,255,0.1) !important;
    }}
    
    /* ============================================= */
    /* SPINNER                                       */
    /* ============================================= */
    .stSpinner > div {{
        border-top-color: {COLORS["secondary"]} !important;
    }}
    
    /* ============================================= */
    /* MARKDOWN & HR                                 */
    /* ============================================= */
    hr {{
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--color-border), transparent) !important;
        margin: var(--spacing-lg) 0 !important;
    }}
    
    /* ============================================= */
    /* CUSTOM CLASSES                                */
    /* ============================================= */
    .sub-text {{
        color: var(--color-text-muted);
        font-size: 1.1rem;
        font-weight: 400;
    }}
    
    .logo-text {{
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
        color: {COLORS["white"]};
        text-align: center;
        margin-top: 0.5rem;
    }}
    
    .section-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: var(--spacing-md);
    }}
    
    .page-container {{
        max-width: 1400px;
        margin: 0 auto;
        padding: var(--spacing-md);
    }}
    
    /* Center content helper */
    .center-content {{
        display: flex;
        justify-content: center;
        align-items: center;
    }}
    
    /* ============================================= */
    /* LOGIN PAGE SPECIFIC                           */
    /* ============================================= */
    .login-container {{
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["dark"]} 100%);
    }}
    
    .login-box {{
        background: {COLORS["white"]};
        padding: 3rem;
        border-radius: var(--radius-lg);
        box-shadow: 0 25px 50px rgba(0,0,0,0.25);
        text-align: center;
        max-width: 420px;
        width: 100%;
    }}
    
    .login-logo {{
        margin-bottom: 1.5rem;
    }}
    
    .login-title {{
        font-family: 'Montserrat', sans-serif;
        font-weight: 800;
        font-size: 2rem;
        color: {COLORS["primary"]};
        margin: 1rem 0 0.5rem;
    }}
    
    .login-tagline {{
        color: {COLORS["secondary"]};
        font-weight: 600;
        font-size: 0.9rem;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 2rem;
    }}
    
    /* ============================================= */
    /* RESPONSIVE ADJUSTMENTS                        */
    /* ============================================= */
    @media (max-width: 768px) {{
        h1 {{ font-size: 1.75rem !important; }}
        h2 {{ font-size: 1.25rem !important; }}
        .valhalla-card {{ padding: var(--spacing-sm); }}
    }}
    
    /* ============================================= */
    /* EXPANDER                                      */
    /* ============================================= */
    .streamlit-expanderHeader {{
        background-color: var(--color-card) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
    }}
    
    /* ============================================= */
    /* FORM SUBMIT BUTTON                            */
    /* ============================================= */
    .stFormSubmitButton > button {{
        background: {COLORS["primary"]} !important;
        color: white !important;
    }}
    
    .stFormSubmitButton > button:hover {{
        background: {COLORS["secondary"]} !important;
        color: {COLORS["dark"]} !important;
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

def get_logo_html(size=60):
    svg = f"""<svg width="{size}" height="{size}" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="10" width="38" height="38" rx="8" fill="#295A63"/>
        <rect x="52" y="10" width="38" height="38" rx="8" fill="#C8A951"/>
        <rect x="10" y="52" width="38" height="38" rx="8" fill="#1A3C42"/>
        <rect x="52" y="52" width="38" height="38" rx="8" fill="#E6D5A7"/>
    </svg>"""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}" style="display: block; margin: 0 auto;">'

# =============================================================================
# 7. PAGES UI
# =============================================================================
def page_admin():
    st.title("⚙️ Admin Console")
    st.markdown("Manage your markets and data sources.")
    st.markdown("---")
    
    if not st.session_state["admin_authenticated"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("#### 🔐 Authentication Required")
            st.text_input("Admin Password", type="password", key="admin_pass_input", on_change=check_admin_password)
        return
    
    wb = get_gsheet_workbook()
    
    # Status bar
    status_col, refresh_col = st.columns([4, 1])
    with status_col:
        if wb:
            st.success(f"✅ Connected to database: **{wb.title}**")
        else:
            st.error("❌ Database connection error")
    with refresh_col:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("###")
    
    tm, td = st.tabs(["🌍 Markets", "🕵️‍♂️ Data Sources"])
    
    with tm:
        st.markdown("#### Manage Target Markets")
        st.markdown("")
        mkts, _ = get_markets()
        
        with st.form("add_market_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_market = st.text_input("Market Name", placeholder="e.g., Japan, Brazil, South Korea...")
            with col2:
                st.markdown("")  # Spacer for alignment
                submitted = st.form_submit_button("➕ Add", use_container_width=True)
            if submitted and new_market:
                add_market(new_market)
                st.rerun()
        
        st.markdown("---")
        st.markdown("##### Current Markets")
        
        for i, m in enumerate(mkts):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.info(f"🌍 {m}")
            with col2:
                if st.button("🗑️", key=f"del_market_{i}", help="Delete this market"):
                    remove_market(i)
                    st.rerun()
    
    with td:
        st.markdown("#### Manage Search Sources")
        st.info("💡 These domains are used by MIA for deep web searches.")
        st.markdown("")
        
        doms, _ = get_domains()
        
        with st.form("add_domain_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_domain = st.text_input("Domain URL", placeholder="e.g., example.gov")
            with col2:
                st.markdown("")
                submitted = st.form_submit_button("➕ Add", use_container_width=True)
            if submitted and new_domain:
                add_domain(new_domain)
                st.rerun()
        
        st.markdown("---")
        st.markdown("##### Current Sources")
        
        for i, d in enumerate(doms):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.success(f"🌐 {d}")
            with col2:
                if st.button("🗑️", key=f"del_domain_{i}", help="Delete this source"):
                    remove_domain(i)
                    st.rerun()

def page_mia():
    st.title("📡 MIA Watch Tower")
    st.markdown("Real-time regulatory monitoring and intelligence gathering.")
    st.markdown("---")
    
    markets, _ = get_markets()
    
    # Form section with proper spacing
    st.markdown("### 🎯 Configure Your Watch")
    st.markdown("")
    
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        topic = st.text_input(
            "🔎 Product / Topic",
            placeholder="e.g., Cybersecurity for SaMD, AI-based diagnostics...",
            key="mia_topic"
        )
    with col2:
        safe_markets = [markets[0]] if markets else []
        selected_markets = st.multiselect(
            "🌍 Target Markets",
            markets,
            default=safe_markets,
            key="mia_mkts"
        )
    
    st.markdown("")
    
    col3, col4, col5 = st.columns([1, 1, 1], gap="large")
    with col3:
        time_map = {"⚡ 30 Days": 30, "📅 12 Months": 365, "🏛️ 3 Years": 1095}
        selected_label = st.selectbox(
            "⏱️ Timeframe",
            list(time_map.keys()),
            index=1,
            key="mia_time"
        )
        days_limit = time_map[selected_label]
    with col4:
        st.markdown("")  # Spacer
    with col5:
        st.markdown("")
        st.markdown("")
        launch = st.button("🚀 Launch Monitoring", type="primary", use_container_width=True)

    if launch and topic:
        with st.spinner(f"📡 MIA is scanning the web... ({selected_label})"):
            query = f"New regulations guidelines for {topic} in {', '.join(selected_markets)} released recently"
            raw_data, error = cached_run_deep_search(query, days=days_limit)
            if not raw_data:
                st.error(f"Search failed: {error}")
            else:
                prompt = create_mia_prompt(topic, selected_markets, raw_data, selected_label)
                json_str = cached_ai_generation(prompt, config.OPENAI_MODEL, 0.1, json_mode=True)
                if json_str:
                    st.session_state["last_mia_results"] = json.loads(json_str)
                    log_usage("MIA", str(uuid.uuid4()), topic, f"Mkts: {len(selected_markets)} | {selected_label}")
                else:
                    st.error("Analysis failed.")

    results = st.session_state.get("last_mia_results")
    if results:
        st.markdown("---")
        st.markdown("### 📋 Intelligence Report")
        st.info(f"**Executive Summary:** {results.get('executive_summary', 'No summary available.')}")
        
        st.markdown("###")
        
        # Filters with proper alignment
        st.markdown("##### 🔍 Filter Results")
        f1, f2, f3 = st.columns([2, 2, 1], gap="medium")
        with f1:
            cats = ["Regulation", "Standard", "Guidance", "Enforcement", "News"]
            sel_types = st.multiselect("🗂️ Category", cats, default=cats, key="mia_type")
        with f2:
            sel_impacts = st.multiselect("🌪️ Impact Level", ["High", "Medium", "Low"], default=["High", "Medium", "Low"], key="mia_imp")
        with f3:
            st.markdown("##### Legend")
            st.markdown("🔴 High · 🟡 Medium · 🟢 Low")
        
        st.markdown("---")
        
        items = results.get("items", [])
        filtered = [i for i in items if i.get('impact','Low').capitalize() in sel_impacts and i.get('category','News').capitalize() in sel_types]
        
        if not filtered:
            st.warning("No updates match your filters.")
        
        for item in filtered:
            impact = item.get('impact', 'Low').lower()
            cat = item.get('category', 'News')
            icon = "🔴" if impact == 'high' else "🟡" if impact == 'medium' else "🟢"
            cat_map = {"Regulation": "🏛️", "Standard": "📏", "Guidance": "📘", "Enforcement": "📢", "News": "📰"}
            
            st.markdown(f"""
            <div class="info-card">
                <div style="display: flex; gap: 16px;">
                    <div style="font-size: 1.75rem; padding-top: 4px;">{icon}</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; font-size: 1.1rem; margin-bottom: 6px;">
                            <a href="{item['url']}" target="_blank" style="text-decoration: none; color: inherit;">
                                {cat_map.get(cat, '📄')} {item['title']}
                            </a>
                        </div>
                        <div style="font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 8px;">
                            📅 {item['date']} · 🏛️ {item['source_name']}
                        </div>
                        <div style="line-height: 1.6;">{item['summary']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def page_olivia():
    st.title("🤖 OlivIA Workspace")
    st.markdown("Automated regulatory analysis for medical devices worldwide.")
    st.markdown("---")
    
    markets, _ = get_markets()
    
    st.markdown("### 📝 Product Definition")
    st.markdown("")
    
    col1, col2 = st.columns([2, 1], gap="large")
    
    with col1:
        desc = st.text_area(
            "Product Description",
            height=200,
            placeholder="Describe your medical device in detail: intended use, technology, target population, etc.",
            key="oli_desc"
        )
    
    with col2:
        safe_mkts = [markets[0]] if markets else []
        ctrys = st.multiselect(
            "🌍 Target Markets",
            markets,
            default=safe_mkts,
            key="oli_mkts"
        )
        st.markdown("###")
        gen = st.button("🚀 Generate Report", type="primary", use_container_width=True, key="oli_btn")
    
    if gen and desc:
        with st.spinner("🤖 OlivIA is analyzing regulatory requirements..."):
            try:
                use_ds = any(x in str(ctrys) for x in ["EU", "USA", "China"])
                ctx = ""
                if use_ds:
                    d, _ = cached_run_deep_search(f"Regulations for {desc} in {ctrys}")
                    if d:
                        ctx = d
                p = create_olivia_prompt(desc, ctrys)
                if ctx:
                    p += f"\n\nCONTEXT:\n{ctx}"
                resp = cached_ai_generation(p, config.OPENAI_MODEL, 0.1)
                st.session_state["last_olivia_report"] = resp
                st.session_state["last_olivia_id"] = str(uuid.uuid4())
                log_usage("OlivIA", st.session_state["last_olivia_id"], desc, f"Mkts:{len(ctrys)}")
                st.toast("Analysis complete!", icon="✅")
            except Exception as e:
                st.error(str(e))

    if st.session_state["last_olivia_report"]:
        st.markdown("---")
        st.success("✅ Regulatory Analysis Generated Successfully")
        st.markdown("###")
        
        st.markdown(st.session_state["last_olivia_report"])
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            pdf_data = generate_pdf_report(
                "Regulatory Analysis Report",
                st.session_state["last_olivia_report"],
                st.session_state.get("last_olivia_id", "ID")
            )
            if pdf_data:
                st.download_button(
                    "📥 Download PDF Report",
                    pdf_data,
                    f"VALHALLAI_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                    "application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("PDF generation failed.")

def page_eva():
    st.title("🔍 EVA Workspace")
    st.markdown("AI-powered compliance audit for your technical documentation.")
    st.markdown("---")
    
    st.markdown("### 📋 Audit Configuration")
    st.markdown("")
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("##### Regulatory Context")
        ctx = st.text_area(
            "Reference Requirements",
            value=st.session_state.get("last_olivia_report", ""),
            height=250,
            placeholder="Paste regulatory requirements or use the output from OlivIA...",
            key="eva_ctx"
        )
    
    with col2:
        st.markdown("##### Document to Audit")
        up = st.file_uploader(
            "Upload your PDF document",
            type="pdf",
            key="eva_up",
            help="Upload the technical file or documentation to be audited"
        )
        st.markdown("###")
        if st.button("🔍 Run Compliance Audit", type="primary", use_container_width=True, key="eva_btn"):
            if up:
                with st.spinner("🔍 EVA is auditing your document..."):
                    try:
                        txt = extract_text_from_pdf(up.read())
                        resp = cached_ai_generation(create_eva_prompt(ctx, txt), "gpt-4o", 0.1)
                        st.session_state["last_eva_report"] = resp
                        st.session_state["last_eva_id"] = str(uuid.uuid4())
                        log_usage("EVA", st.session_state["last_eva_id"], f"File: {up.name}")
                        st.toast("Audit complete!", icon="🔍")
                    except Exception as e:
                        st.error(str(e))
            else:
                st.warning("Please upload a PDF document to audit.")
    
    if st.session_state.get("last_eva_report"):
        st.markdown("---")
        st.markdown("### 📊 Audit Results")
        st.markdown("")
        st.markdown(st.session_state["last_eva_report"])
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            pdf_data = generate_pdf_report(
                "Compliance Audit Report",
                st.session_state["last_eva_report"],
                st.session_state.get("last_eva_id", "ID")
            )
            if pdf_data:
                st.download_button(
                    "📥 Download Audit Report",
                    pdf_data,
                    f"VALHALLAI_Audit_{datetime.now().strftime('%Y%m%d')}.pdf",
                    "application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("PDF generation failed.")

def page_dashboard():
    # Header section
    st.title("Dashboard")
    st.markdown(f"<p class='sub-text'>{config.APP_SLOGAN}</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Agent cards
    st.markdown("### 🤖 AI Agents")
    st.markdown("Select an agent to start your regulatory workflow.")
    st.markdown("###")
    
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.markdown(f"""
        <div class="valhalla-card">
            <div class="valhalla-card-header">
                <span class="valhalla-card-icon">🤖</span>
                <h3 class="valhalla-card-title">OlivIA</h3>
            </div>
            <div class="valhalla-card-body">
                {config.AGENTS['olivia']['description']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        if st.button("Launch OlivIA →", key="dash_oli", use_container_width=True):
            st.session_state["current_page"] = "OlivIA"
            st.rerun()
    
    with col2:
        st.markdown(f"""
        <div class="valhalla-card">
            <div class="valhalla-card-header">
                <span class="valhalla-card-icon">🔍</span>
                <h3 class="valhalla-card-title">EVA</h3>
            </div>
            <div class="valhalla-card-body">
                {config.AGENTS['eva']['description']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        if st.button("Launch EVA →", key="dash_eva", use_container_width=True):
            st.session_state["current_page"] = "EVA"
            st.rerun()
    
    with col3:
        st.markdown(f"""
        <div class="valhalla-card">
            <div class="valhalla-card-header">
                <span class="valhalla-card-icon">{config.AGENTS['mia']['icon']}</span>
                <h3 class="valhalla-card-title">{config.AGENTS['mia']['name']}</h3>
            </div>
            <div class="valhalla-card-body">
                {config.AGENTS['mia']['description']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        if st.button("Launch MIA →", key="dash_mia", use_container_width=True):
            st.session_state["current_page"] = "MIA"
            st.rerun()

def render_sidebar():
    with st.sidebar:
        # Logo section
        st.markdown("<div style='text-align: center; padding: 1rem 0;'>", unsafe_allow_html=True)
        st.markdown(get_logo_html(70), unsafe_allow_html=True)
        st.markdown(f"<div class='logo-text'>{config.APP_NAME}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Navigation
        st.markdown("##### Navigation")
        pages = ["Dashboard", "OlivIA", "EVA", "MIA", "Admin"]
        page_icons = {"Dashboard": "🏠", "OlivIA": "🤖", "EVA": "🔍", "MIA": "📡", "Admin": "⚙️"}
        
        curr = st.session_state["current_page"]
        idx = pages.index(curr) if curr in pages else 0
        
        display_pages = [f"{page_icons[p]} {p}" for p in pages]
        selected_display = st.radio(
            "Navigation",
            display_pages,
            index=idx,
            label_visibility="collapsed"
        )
        
        selected = pages[display_pages.index(selected_display)]
        
        if selected != curr:
            st.session_state["current_page"] = selected
            st.rerun()

        st.markdown("---")
        
        # Dark Mode Toggle
        st.markdown("##### Appearance")
        
        dark_mode_label = "🌙 Dark Mode" if not st.session_state["dark_mode"] else "☀️ Light Mode"
        
        if st.button(dark_mode_label, use_container_width=True, key="dark_mode_toggle"):
            st.session_state["dark_mode"] = not st.session_state["dark_mode"]
            st.rerun()

        st.markdown("---")
        
        # Logout button
        if st.button("🚪 Log Out", use_container_width=True):
            logout()
            st.rerun()
        
        # Footer
        st.markdown("---")
        st.markdown(
            f"<div style='text-align: center; font-size: 0.75rem; opacity: 0.7;'>"
            f"© 2024 {config.APP_NAME}<br>v1.0"
            f"</div>",
            unsafe_allow_html=True
        )

def render_login():
    # Full page styling for login
    st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["dark"]} 100%) !important;
    }}
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # Centered login box
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<div style='height: 15vh;'></div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="login-box">
            <div class="login-logo">
                {get_logo_html(80)}
            </div>
            <h1 class="login-title">{config.APP_NAME}</h1>
            <p class="login-tagline">{config.APP_TAGLINE}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        
        # Login form with custom styling
        st.markdown("""
        <style>
        .login-form input {
            background-color: white !important;
            border: 2px solid #E2E8F0 !important;
            border-radius: 8px !important;
            padding: 0.75rem 1rem !important;
            font-size: 1rem !important;
        }
        .login-form input:focus {
            border-color: #C8A951 !important;
            box-shadow: 0 0 0 3px rgba(200, 169, 81, 0.2) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.text_input(
                "🔐 Security Token",
                type="password",
                key="password_input",
                on_change=check_password,
                placeholder="Enter your access token..."
            )

def main():
    # Inject global CSS
    inject_custom_css()
    
    if st.session_state["authenticated"]:
        render_sidebar()
        
        # Page routing
        page = st.session_state["current_page"]
        
        if page == "Dashboard":
            page_dashboard()
        elif page == "OlivIA":
            page_olivia()
        elif page == "EVA":
            page_eva()
        elif page == "MIA":
            page_mia()
        elif page == "Admin":
            page_admin()
        else:
            page_dashboard()
    else:
        render_login()

if __name__ == "__main__":
    main()

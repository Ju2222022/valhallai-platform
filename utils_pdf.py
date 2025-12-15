import os
import urllib.request
from datetime import datetime
from fpdf import FPDF, HTMLMixin
import markdown

# --- GESTION DES POLICES ---
FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
FONT_PATH = "NotoSans-Regular.ttf"
FONT_BOLD_PATH = "NotoSans-Bold.ttf"

def ensure_fonts_exist():
    if not os.path.exists(FONT_PATH):
        try: urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        except: pass
    if not os.path.exists(FONT_BOLD_PATH):
        try: urllib.request.urlretrieve(FONT_BOLD_URL, FONT_BOLD_PATH)
        except: pass

# On utilise HTMLMixin pour améliorer le rendu HTML
class ValhallaiPDF(FPDF, HTMLMixin):
    def __init__(self, title_doc, report_id):
        ensure_fonts_exist()
        super().__init__()
        self.title_doc = title_doc
        self.report_id = report_id
        
        try:
            self.add_font("NotoSans", style="", fname=FONT_PATH)
            self.add_font("NotoSans", style="B", fname=FONT_BOLD_PATH)
            self.main_font = "NotoSans"
        except:
            self.main_font = "Arial"

    def header(self):
        self.set_font(self.main_font, 'B', 20)
        self.set_text_color(41, 90, 99) # Vert Valhallai
        self.cell(0, 10, 'VALHALLAI', ln=1)
        
        self.set_font(self.main_font, '', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=1)
        
        self.set_draw_color(200, 169, 81) # Doré
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        
        self.set_xy(100, 12)
        self.set_font(self.main_font, 'B', 10)
        self.set_text_color(0)
        self.cell(100, 6, self.title_doc[:50], align='R', ln=1)
        
        self.set_xy(100, 18)
        self.set_font(self.main_font, '', 8)
        self.set_text_color(128)
        self.cell(100, 4, datetime.now().strftime("%Y-%m-%d"), align='R', ln=1)
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.main_font, '', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'ID: {self.report_id} | Page {self.page_no()}/{{nb}}', align='C')

def generate_pdf_report(title, content_markdown, report_id):
    pdf = ValhallaiPDF(title, report_id)
    pdf.add_page()
    
    # 1. Conversion Markdown -> HTML
    html_content = markdown.markdown(
        content_markdown, 
        extensions=['tables', 'fenced_code', 'sane_lists']
    )
    
    # 2. STYLING CSS POUR FPDF2 (CORRECTIF V43)
    # On force la couleur des listes (li) en noir (#333) pour éviter le rouge par défaut.
    # On ajoute des balises <font> globales.
    styled_html = f"""
    <style>
        h1 {{ color: #295A63; font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
        h2 {{ color: #295A63; font-size: 20px; font-weight: bold; margin-top: 20px; border-bottom: 1px solid #ccc; }}
        h3 {{ color: #1A3C42; font-size: 16px; font-weight: bold; margin-top: 15px; }}
        p {{ color: #333333; font-size: 11px; line-height: 1.5; text-align: justify; }}
        
        /* CORRECTION LISTES (V43) */
        ul {{ color: #333333; margin-left: 15px; }}
        ol {{ color: #333333; margin-left: 15px; }}
        li {{ color: #333333; margin-bottom: 5px; }}
        
        /* CORRECTION TABLEAUX */
        table {{ border: 1px solid #ddd; width: 100%; }}
        th {{ background-color: #f2f2f2; font-weight: bold; color: #295A63; padding: 5px; border: 1px solid #ccc; }}
        td {{ padding: 5px; border: 1px solid #ccc; color: #333; }}
    </style>
    
    <font face="{pdf.main_font}" color="#333333">
        {html_content}
    </font>
    """
    
    pdf.set_font(pdf.main_font, '', 11)
    
    # Utilisation de write_html avec gestion des styles
    try:
        pdf.write_html(styled_html)
    except Exception as e:
        pdf.multi_cell(0, 6, f"Error rendering HTML: {str(e)}\n\nRaw:\n{content_markdown}")

    return bytes(pdf.output())

import os
import urllib.request
from datetime import datetime
from fpdf import FPDF, HTMLMixin
from fpdf.fonts import FontFace
import markdown
import re

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

class ValhallaiPDF(FPDF, HTMLMixin):
    def __init__(self, title_doc, report_id):
        ensure_fonts_exist()
        super().__init__()
        self.title_doc = title_doc
        self.report_id = report_id
        
        # MARGES OPTIMISÉES (1.5 cm) pour éviter l'erreur "Not enough space"
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        
        try:
            self.add_font("NotoSans", style="", fname=FONT_PATH)
            self.add_font("NotoSans", style="B", fname=FONT_BOLD_PATH)
            self.main_font = "NotoSans"
        except:
            self.main_font = "Arial"

    def header(self):
        self.set_font(self.main_font, 'B', 20)
        self.set_text_color(41, 90, 99) 
        self.cell(0, 10, 'VALHALLAI', ln=1)
        
        self.set_font(self.main_font, '', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=1)
        
        self.set_draw_color(200, 169, 81)
        self.set_line_width(0.5)
        self.line(15, 28, 195, 28) # Ligne ajustée aux nouvelles marges
        
        self.set_xy(100, 12)
        self.set_font(self.main_font, 'B', 10)
        self.set_text_color(0)
        # Tronquer le titre s'il est trop long pour éviter le chevauchement
        clean_title = (self.title_doc[:45] + '...') if len(self.title_doc) > 45 else self.title_doc
        self.cell(95, 6, clean_title, align='R', ln=1)
        
        self.set_xy(100, 18)
        self.set_font(self.main_font, '', 8)
        self.set_text_color(128)
        self.cell(95, 4, datetime.now().strftime("%Y-%m-%d"), align='R', ln=1)
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
    
    # 2. Nettoyage et Force Borders sur les tableaux
    html_content = html_content.replace('<table>', '<table border="1" width="100%" cellpadding="3">')
    
    # 3. STYLES (Optimisés pour l'espace)
    valhallai_green = (41, 90, 99)
    dark_grey = (50, 50, 50)
    
    tag_styles = {
        "h1": FontFace(color=valhallai_green, emphasis="B", size_pt=18),
        "h2": FontFace(color=valhallai_green, emphasis="B", size_pt=14),
        "h3": FontFace(color=(26, 60, 66), emphasis="B", size_pt=12),
        "p": FontFace(color=dark_grey, size_pt=10),
        "li": FontFace(color=dark_grey, size_pt=10),
        
        # TABLEAUX : Police réduite pour éviter le débordement horizontal
        "table": FontFace(size_pt=8), 
        "th": FontFace(color=valhallai_green, emphasis="B", fill_color=(240, 240, 240), size_pt=9),
        "td": FontFace(size_pt=8),
    }
    
    # 4. Écriture avec FILET DE SÉCURITÉ
    pdf.set_font(pdf.main_font, '', 10)
    
    try:
        pdf.write_html(html_content, tag_styles=tag_styles, table_line_separators=True)
    except Exception as e:
        # PLAN DE SECOURS : Si le rendu HTML plante (tableau trop complexe),
        # on imprime une version texte simplifiée.
        print(f"PDF HTML Error: {e}")
        pdf.add_page()
        pdf.set_font(pdf.main_font, 'B', 12)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, "Complex Formatting Fallback", ln=1)
        
        pdf.set_font(pdf.main_font, '', 10)
        pdf.set_text_color(0)
        
        # Nettoyage basique du markdown pour le rendre lisible
        clean_text = content_markdown.replace('#', '').replace('*', '')
        pdf.multi_cell(0, 5, clean_text)

    return bytes(pdf.output())

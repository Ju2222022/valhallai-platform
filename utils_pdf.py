import os
import urllib.request
from datetime import datetime
from fpdf import FPDF, HTMLMixin
from fpdf.fonts import FontFace # Important pour le style
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
        # En-tête propre sans HTML
        self.set_font(self.main_font, 'B', 20)
        self.set_text_color(41, 90, 99) # Vert Valhallai
        self.cell(0, 10, 'VALHALLAI', ln=1)
        
        self.set_font(self.main_font, '', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=1)
        
        self.set_draw_color(200, 169, 81) # Doré
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        
        # Meta-data à droite
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
    
    # 2. HACK: Forcer les bordures des tableaux en HTML
    # Markdown ne met pas border="1", donc FPDF ne dessine pas les lignes par défaut.
    html_content = html_content.replace('<table>', '<table border="1" width="100%" cellpadding="5">')
    
    # 3. DÉFINITION DES STYLES (C'est ici qu'on corrige les couleurs et polices)
    # Plus de CSS texte, on utilise des objets FontFace que FPDF comprend.
    valhallai_green = (41, 90, 99)
    dark_grey = (50, 50, 50)
    
    tag_styles = {
        "h1": FontFace(color=valhallai_green, emphasis="B", size_pt=18),
        "h2": FontFace(color=valhallai_green, emphasis="B", size_pt=14),
        "h3": FontFace(color=(26, 60, 66), emphasis="B", size_pt=12),
        "p": FontFace(color=dark_grey, size_pt=10),
        "li": FontFace(color=dark_grey, size_pt=10), # Force les puces en gris foncé (plus de rouge)
        "table": FontFace(size_pt=9), # Tableaux un peu plus petits pour tenir
        "th": FontFace(color=valhallai_green, emphasis="B", fill_color=(240, 240, 240)), # Entête tableau
    }
    
    # 4. Écriture
    pdf.set_font(pdf.main_font, '', 10)
    
    try:
        # table_line_separators=True active le dessin des lignes de tableau
        pdf.write_html(html_content, tag_styles=tag_styles, table_line_separators=True)
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 5, f"Erreur PDF: {str(e)}")
        # En cas de crash HTML, on imprime le texte brut pour ne pas perdre l'info
        pdf.set_text_color(0)
        pdf.multi_cell(0, 5, content_markdown)

    return bytes(pdf.output())

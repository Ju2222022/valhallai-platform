import os
import urllib.request
from datetime import datetime
from fpdf import FPDF
from fpdf.fonts import FontFace
import markdown
import config

# --- GESTION AUTOMATIQUE DE LA POLICE UNICODE ---
FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
FONT_PATH = "NotoSans-Regular.ttf"
FONT_BOLD_PATH = "NotoSans-Bold.ttf"

def ensure_fonts_exist():
    """Télécharge les polices si elles sont absentes."""
    if not os.path.exists(FONT_PATH):
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    if not os.path.exists(FONT_BOLD_PATH):
        urllib.request.urlretrieve(FONT_BOLD_URL, FONT_BOLD_PATH)

class ValhallaiPDF(FPDF):
    def __init__(self, title_doc, report_id):
        ensure_fonts_exist()
        super().__init__()
        self.title_doc = title_doc
        self.report_id = report_id # On stocke l'ID unique
        self.colors = config.COLORS["light"]
        
        # Enregistrement de la police pour gérer l'Unicode
        self.add_font("NotoSans", style="", fname=FONT_PATH)
        self.add_font("NotoSans", style="B", fname=FONT_BOLD_PATH)

    def header(self):
        # --- LOGO & TITRE ---
        start_y = 12
        
        # Damier (Logo)
        self.set_fill_color(41, 90, 99) 
        self.rect(10, start_y, 5, 5, 'F')
        self.set_fill_color(200, 169, 81) 
        self.rect(16, start_y, 5, 5, 'F')
        self.set_fill_color(26, 60, 66) 
        self.rect(10, start_y + 6, 5, 5, 'F')
        self.set_fill_color(230, 213, 167) 
        self.rect(16, start_y + 6, 5, 5, 'F')

        # Titre
        self.set_font('NotoSans', 'B', 20)
        self.set_xy(24, start_y) 
        self.set_text_color(41, 90, 99)
        self.cell(0, 8, 'VALHALLAI', ln=0)
        
        # Sous-titre
        self.set_font('NotoSans', '', 9)
        self.set_xy(24, start_y + 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=0)

        # --- INFOS DOCUMENT ---
        self.set_xy(0, start_y)
        self.set_font('NotoSans', 'B', 10)
        self.set_text_color(0, 0, 0)
        self.cell(195, 6, self.title_doc, align='R', ln=1)
        
        # Date
        current_time = datetime.now().strftime("%d/%m/%Y")
        self.set_font('NotoSans', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(195, 4, f"Date: {current_time}", align='R')

        # Ligne séparation
        self.set_draw_color(200, 169, 81)
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSans', '', 8)
        self.set_text_color(128)
        self.set_draw_color(220, 220, 220)
        self.line(10, 282, 200, 282)
        
        # Affichage de l'ID Unique et pagination
        footer_text = f'Page {self.page_no()}/{{nb}} | Ref ID: {self.report_id} | Valhallai Confidential'
        self.cell(0, 10, footer_text, align='C')

    def add_formatted_content(self, markdown_text):
        self.add_page()
        self.set_font('NotoSans', '', 9)
        self.set_text_color(30, 30, 30) 
        self.set_draw_color(200, 200, 200) 
        self.set_line_width(0.1) 

        html_text = markdown.markdown(markdown_text, extensions=['tables', 'fenced_code'])

        primary_color = (41, 90, 99)
        tag_styles = {
            "h1": FontFace(color=primary_color, emphasis="B", size_pt=16),
            "h2": FontFace(color=primary_color, emphasis="B", size_pt=14),
            "h3": FontFace(color=(26, 60, 66), emphasis="B", size_pt=12),
        }

        self.write_html(html_text, table_line_separators=True, tag_styles=tag_styles)

def generate_pdf_report(title, content, report_id):
    pdf = ValhallaiPDF(title, report_id)
    pdf.alias_nb_pages()
    pdf.add_formatted_content(content)
    return bytes(pdf.output())

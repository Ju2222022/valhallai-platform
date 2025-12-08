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
        self.report_id = report_id
        self.colors = config.COLORS["light"]
        
        # Enregistrement de la police pour gérer l'Unicode
        self.add_font("NotoSans", style="", fname=FONT_PATH)
        self.add_font("NotoSans", style="B", fname=FONT_BOLD_PATH)

    def header(self):
        # --- 1. LOGO (GAUCHE) ---
        start_y = 12
        
        # Damier
        self.set_fill_color(41, 90, 99) 
        self.rect(10, start_y, 5, 5, 'F')
        self.set_fill_color(200, 169, 81) 
        self.rect(16, start_y, 5, 5, 'F')
        self.set_fill_color(26, 60, 66) 
        self.rect(10, start_y + 6, 5, 5, 'F')
        self.set_fill_color(230, 213, 167) 
        self.rect(16, start_y + 6, 5, 5, 'F')

        # Marque "VALHALLAI"
        self.set_font('NotoSans', 'B', 20)
        self.set_xy(24, start_y) 
        self.set_text_color(41, 90, 99)
        self.cell(0, 8, 'VALHALLAI', ln=0)
        
        # Slogan
        self.set_font('NotoSans', '', 9)
        self.set_xy(24, start_y + 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=0)

        # --- 2. INFOS DOCUMENT (DROITE) ---
        # Astuce : On utilise une cellule qui fait TOUTE la largeur (190mm)
        # et on aligne le texte à droite ('R'). Comme ça, c'est parfaitement calé.
        
        # Titre du document
        self.set_xy(10, start_y) # On repart de la marge gauche
        self.set_font('NotoSans', 'B', 10)
        self.set_text_color(0, 0, 0)
        self.cell(190, 6, self.title_doc, align='R', ln=1)
        
        # Date
        current_time = datetime.now().strftime("%d/%m/%Y")
        self.set_x(10) # Retour marge gauche
        self.set_font('NotoSans', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(190, 4, f"Date: {current_time}", align='R')

        # Ligne de séparation dorée
        self.set_draw_color(200, 169, 81)
        self.set_line_width(0.5)
        # La ligne va de 10 à 200 (190mm de large), donc le texte au dessus (width 190) s'aligne pile dessus.
        self.line(10, 28, 200, 28)
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSans', '', 7) # Police un peu plus petite pour le footer
        self.set_text_color(128)
        self.set_draw_color(220, 220, 220)
        self.line(10, 282, 200, 282)
        
        # ID Unique + Pagination
        footer_text = f'Ref ID: {self.report_id}  |  Valhallai Platform Confidential  |  Page {self.page_no()}/{{nb}}'
        self.cell(0, 10, footer_text, align='C')

    def add_formatted_content(self, markdown_text):
        self.add_page()
        
        # --- RÉGLAGES POUR TABLEAUX PROPRES ---
        self.set_font('NotoSans', '', 9)
        self.set_text_color(30, 30, 30) 
        self.set_draw_color(200, 200, 200) 
        self.set_line_width(0.1) 

        # Conversion Markdown -> HTML
        html_text = markdown.markdown(
            markdown_text, 
            extensions=['tables', 'fenced_code']
        )

        # Styles sécurisés (Uniquement Titres)
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

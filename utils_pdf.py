import os
import urllib.request
from datetime import datetime
from fpdf import FPDF
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

class ValhallaiPDF(FPDF):
    def __init__(self, title_doc, report_id):
        ensure_fonts_exist()
        super().__init__()
        self.title_doc = title_doc
        self.report_id = report_id
        
        # Police compatible Unicode
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
    
    # 1. Conversion Markdown -> HTML (avec extension TABLEAUX activée)
    # On ajoute des sauts de ligne pour aérer
    html_content = markdown.markdown(
        content_markdown, 
        extensions=['tables', 'fenced_code', 'sane_lists']
    )
    
    # 2. Injection de style pour aérer les tableaux et le texte
    # FPDF2 supporte un sous-ensemble de HTML
    styled_html = f"""
    <font face="{pdf.main_font}" color="#333333">
        {html_content}
    </font>
    """
    
    # 3. Écriture via le moteur HTML de FPDF2
    # Cela gère automatiquement les tableaux (<table>), le gras (<b>), les listes (<ul>)
    pdf.set_font(pdf.main_font, '', 11)
    
    # Astuce pour espacer les lignes : on joue sur le paramètre line_height de write_html si dispo,
    # sinon FPDF utilise l'interligne standard.
    try:
        pdf.write_html(styled_html, table_line_separators=True)
    except Exception as e:
        # Fallback si le HTML est trop complexe pour FPDF
        pdf.multi_cell(0, 6, f"Error rendering HTML layout: {str(e)}\n\nRaw Content:\n{content_markdown}")

    return bytes(pdf.output())

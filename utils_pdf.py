import os
import urllib.request
from datetime import datetime
from fpdf import FPDF

# --- GESTION AUTOMATIQUE DE LA POLICE UNICODE (OBLIGATOIRE POUR ACCENTS) ---
FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
FONT_PATH = "NotoSans-Regular.ttf"
FONT_BOLD_PATH = "NotoSans-Bold.ttf"

def ensure_fonts_exist():
    """Télécharge les polices si elles sont absentes."""
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
        
        # Enregistrement de la police UTF-8
        try:
            self.add_font("NotoSans", style="", fname=FONT_PATH)
            self.add_font("NotoSans", style="B", fname=FONT_BOLD_PATH)
            self.main_font = "NotoSans"
        except:
            self.main_font = "Arial" # Fallback si le téléchargement échoue

    def header(self):
        # --- EN-TÊTE STYLISÉ ---
        self.set_font(self.main_font, 'B', 20)
        self.set_text_color(41, 90, 99) # Couleur Valhallai
        self.cell(0, 10, 'VALHALLAI', ln=1)
        
        self.set_font(self.main_font, '', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'REGULATORY SHIELD', ln=1)
        
        # Ligne de séparation
        self.set_draw_color(200, 169, 81) # Doré
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        
        # Info Rapport (Aligné à droite)
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

    def chapter_title(self, label):
        self.ln(4)
        self.set_font(self.main_font, 'B', 14)
        self.set_text_color(41, 90, 99)
        self.cell(0, 10, label, ln=1)
        self.ln(2)

    def chapter_subtitle(self, label):
        self.ln(2)
        self.set_font(self.main_font, 'B', 12)
        self.set_text_color(26, 60, 66)
        self.cell(0, 8, label, ln=1)
        self.ln(1)

    def chapter_body(self, text, is_list=False):
        self.set_font(self.main_font, '', 10)
        self.set_text_color(30, 30, 30)
        
        if is_list:
            # Astuce pour lister : on décale à droite (indentation)
            self.set_x(15)
            # h=6 signifie 6mm de hauteur par ligne -> C'est ça qui aère le texte !
            self.multi_cell(0, 6, f"\x95  {text}") 
            self.ln(2) # Petit espace après chaque puce
        else:
            self.multi_cell(0, 6, text)
            self.ln(3) # Espace après paragraphe

    def parse_markdown(self, md_text):
        """
        Parseur manuel pour garantir l'espacement sans dépendre de HTML/CSS.
        """
        self.add_page()
        
        lines = md_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Détection Titre H1 (#)
            if line.startswith('# '):
                self.chapter_title(line.replace('# ', '').strip())
            
            # Détection Titre H2 (##)
            elif line.startswith('## '):
                self.chapter_title(line.replace('## ', '').strip())
            
            # Détection Titre H3 (###)
            elif line.startswith('### '):
                self.chapter_subtitle(line.replace('### ', '').strip())
            
            # Détection Liste (- ou *)
            elif line.startswith('- ') or line.startswith('* '):
                clean_line = line[2:].strip()
                # Nettoyage gras Markdown (**text**)
                clean_line = clean_line.replace('**', '').replace('__', '') 
                self.chapter_body(clean_line, is_list=True)
            
            # Détection Liste numérotée (1.)
            elif line[0].isdigit() and line[1] == '.':
                clean_line = line.split('.', 1)[1].strip()
                clean_line = clean_line.replace('**', '')
                self.chapter_body(clean_line, is_list=True)
                
            # Paragraphe standard
            else:
                clean_line = line.replace('**', '')
                self.chapter_body(clean_line, is_list=False)

def generate_pdf_report(title, content, report_id):
    try:
        pdf = ValhallaiPDF(title, report_id)
        pdf.alias_nb_pages()
        # On passe le texte brut au parseur manuel
        pdf.parse_markdown(content)
        return bytes(pdf.output())
    except Exception as e:
        print(f"PDF Error: {e}")
        return None

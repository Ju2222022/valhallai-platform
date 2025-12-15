import os
import urllib.request
from datetime import datetime
from fpdf import FPDF

# --- FONTS ---
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

    # --- MOTEUR DE RENDU MAISON (POUR TABLEAUX & LISTES) ---
    def print_chapter_title(self, label, level=1):
        self.ln(4)
        if level == 1:
            self.set_font(self.main_font, 'B', 16)
            self.set_text_color(41, 90, 99)
        else:
            self.set_font(self.main_font, 'B', 12)
            self.set_text_color(26, 60, 66)
        
        self.multi_cell(0, 8, label)
        self.ln(2)

    def print_text(self, text):
        self.set_font(self.main_font, '', 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def print_list_item(self, text):
        self.set_font(self.main_font, '', 10)
        self.set_text_color(30, 30, 30)
        # Balle noire simple + Indentation
        self.set_x(15) 
        self.multi_cell(0, 5, f"{chr(149)} {text}")
        self.ln(1)

    def print_table_row(self, cells, is_header=False):
        # Calcul largeur colonnes (équitable)
        page_width = self.w - 20 # Marges 10+10
        col_width = page_width / max(len(cells), 1)
        
        # Hauteur de ligne (le max nécessaire)
        self.set_font(self.main_font, 'B' if is_header else '', 9)
        line_height = 5
        
        # On sauvegarde la position Y avant d'écrire
        y_start = self.get_y()
        
        # On calcule la hauteur max de cette ligne (multiligne)
        max_h = 0
        for cell in cells:
            # Simulation pour connaître la hauteur
            lines = self.multi_cell(col_width, line_height, cell, split_only=True)
            h = len(lines) * line_height
            if h > max_h: max_h = h
        
        # Si on dépasse la page, on saute
        if y_start + max_h > self.page_break_trigger:
            self.add_page()
            y_start = self.get_y()

        # Écriture réelle
        x_start = 10
        for cell in cells:
            self.set_xy(x_start, y_start)
            # Fond gris pour header
            self.set_fill_color(240, 240, 240) if is_header else self.set_fill_color(255)
            self.multi_cell(col_width, line_height, cell, border=1, align='L', fill=is_header)
            x_start += col_width
            
        self.set_y(y_start + max_h)

    def parse_markdown(self, md_text):
        """Lit le markdown ligne par ligne et appelle la bonne méthode de dessin."""
        lines = md_text.split('\n')
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- TABLEAUX ---
            if '|' in line and len(line.split('|')) > 2:
                # C'est une ligne de tableau
                if '---' in line: continue # On saute la ligne de séparation markdown
                
                cells = [c.strip() for c in line.split('|') if c.strip() != '']
                if not in_table:
                    # Première ligne = Header
                    self.print_table_row(cells, is_header=True)
                    in_table = True
                else:
                    self.print_table_row(cells, is_header=False)
                continue
            else:
                in_table = False

            # --- TITRES ---
            if line.startswith('# '):
                self.print_chapter_title(line.replace('# ', ''), 1)
            elif line.startswith('## '):
                self.print_chapter_title(line.replace('## ', ''), 2)
            elif line.startswith('### '):
                self.print_chapter_title(line.replace('### ', ''), 2)
                
            # --- LISTES ---
            elif line.startswith('- ') or line.startswith('* '):
                clean = line[2:].replace('**', '').replace('__', '')
                self.print_list_item(clean)
            elif line[0].isdigit() and '. ' in line[:4]:
                clean = line.split('. ', 1)[1].replace('**', '')
                self.print_list_item(clean) # On traite les 1. comme des puces pour l'alignement
            
            # --- PARAGRAPHES ---
            else:
                clean = line.replace('**', '').replace('__', '')
                self.print_text(clean)

def generate_pdf_report(title, content, report_id):
    try:
        pdf = ValhallaiPDF(title, report_id)
        pdf.add_page() # Une seule page ajoutée au début = Pas de page blanche
        pdf.parse_markdown(content)
        return bytes(pdf.output())
    except Exception as e:
        print(f"PDF Error: {e}")
        return None

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
        
        # Marges standard
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
        self.line(15, 28, 195, 28)
        
        self.set_xy(100, 12)
        self.set_font(self.main_font, 'B', 10)
        self.set_text_color(0)
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

    # --- MOTEUR DE DESSIN MANUEL (LE SECRET POUR DES TABLEAUX PROPRES) ---
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
        # On utilise un caractère unicode "Balle" et un espace insécable
        formatted_text = f"  {chr(149)}  {text}"
        self.multi_cell(0, 5, formatted_text)
        self.ln(1)

    def print_table_row(self, cells, is_header=False):
        # 1. Configuration
        page_width = self.w - 30 # 15+15 marge
        if not cells: return
        col_width = page_width / len(cells)
        self.set_font(self.main_font, 'B' if is_header else '', 9)
        
        # 2. Calcul de la hauteur max de cette ligne
        # On simule l'écriture pour voir combien de lignes ça prendrait
        line_height = 5
        max_nb_lines = 1
        for cell in cells:
            # split_only=True nous dit comment FPDF couperait le texte
            lines = self.multi_cell(col_width, line_height, cell, split_only=True)
            max_nb_lines = max(max_nb_lines, len(lines))
        
        row_height = max_nb_lines * line_height

        # 3. Saut de page intelligent
        if self.get_y() + row_height > self.page_break_trigger:
            self.add_page()
            # Si c'est un header, on le réimprime ? Non, simplifions.

        # 4. Dessin réel
        y_start = self.get_y()
        x_start = 15
        
        for cell in cells:
            self.set_xy(x_start, y_start)
            # Fond gris pour le header
            if is_header:
                self.set_fill_color(240, 240, 240)
                self.rect(x_start, y_start, col_width, row_height, 'DF')
            else:
                self.set_fill_color(255, 255, 255)
                self.rect(x_start, y_start, col_width, row_height, 'D')
            
            # Texte
            self.multi_cell(col_width, line_height, cell, border=0, align='L')
            x_start += col_width
            
        # On déplace le curseur en bas de la ligne la plus haute
        self.set_y(y_start + row_height)

    def parse_markdown(self, md_text):
        """Transforme le markdown en instructions de dessin FPDF"""
        lines = md_text.split('\n')
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- DÉTECTION TABLEAU ---
            if '|' in line and len(line.split('|')) > 2:
                if '---' in line: continue # Ignorer la ligne de séparation
                
                # Nettoyage des cellules
                cells = [c.strip() for c in line.split('|') if c.strip() != '']
                # Parfois le split crée des vides au début/fin
                if len(cells) < 1: continue

                if not in_table:
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
                self.print_list_item(clean)
            
            # --- PARAGRAPHES ---
            else:
                clean = line.replace('**', '').replace('__', '')
                self.print_text(clean)

def generate_pdf_report(title, content, report_id):
    try:
        pdf = ValhallaiPDF(title, report_id)
        pdf.add_page() # Ajout page initiale OBLIGATOIRE
        pdf.parse_markdown(content)
        return bytes(pdf.output())
    except Exception as e:
        print(f"PDF Error: {e}")
        return None

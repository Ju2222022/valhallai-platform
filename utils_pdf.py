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
        clean_title = (self.title_doc[:45] + '...') if len(self.title_doc) > 45 else self.title_doc
        self.cell(100, 6, clean_title, align='R', ln=1)
        
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

    # --- MOTEUR DE RENDU AMÉLIORÉ ---
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
        
        # Astuce : On imprime la puce et le texte dans la même MultiCell
        # pour que l'indentation de la 2ème ligne soit alignée.
        # \x95 est le caractère "Bullet point" standard
        formatted_text = f"  {chr(149)}  {text}"
        self.multi_cell(0, 5, formatted_text)
        self.ln(1)

    def print_table_row(self, cells, is_header=False):
        page_width = self.w - 20
        col_width = page_width / max(len(cells), 1)
        line_height = 5
        
        self.set_font(self.main_font, 'B' if is_header else '', 9)
        
        # 1. Calcul de la hauteur MAX de la ligne (pour alignement)
        max_h = 0
        for cell in cells:
            # On demande à FPDF combien de lignes prendrait ce texte
            # get_string_width ne suffit pas car multi_cell wrap
            # On simule via le nombre de caractères approx (méthode robuste)
            nb_lines = len(self.multi_cell(col_width, line_height, cell, split_only=True))
            h = nb_lines * line_height
            if h > max_h: max_h = h
        
        # Sécurité minimum
        if max_h < line_height: max_h = line_height
        
        # Saut de page si nécessaire
        if self.get_y() + max_h > self.page_break_trigger:
            self.add_page()

        # 2. Dessin des cellules
        x_start = 10
        y_start = self.get_y()
        
        for cell in cells:
            self.set_xy(x_start, y_start)
            if is_header:
                self.set_fill_color(240, 240, 240)
                self.multi_cell(col_width, line_height, cell, border=1, align='L', fill=True)
            else:
                # On dessine d'abord le cadre vide de la bonne hauteur
                self.rect(x_start, y_start, col_width, max_h)
                # Puis on écrit le texte dedans
                self.multi_cell(col_width, line_height, cell, border=0, align='L')
            
            x_start += col_width
            
        self.set_y(y_start + max_h)

    def parse_markdown(self, md_text):
        lines = md_text.split('\n')
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- TABLEAUX ---
            if '|' in line and len(line.split('|')) > 2:
                if '---' in line: continue 
                cells = [c.strip() for c in line.split('|') if c.strip() != '']
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
                
            # --- LISTES (Fix Alignement) ---
            # On traite les puces (*) et les numéros (1.) de la même façon visuelle
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
        pdf.add_page()
        pdf.parse_markdown(content)
        return bytes(pdf.output())
    except Exception as e:
        print(f"PDF Error: {e}")
        return None

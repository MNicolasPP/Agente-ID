# funciones/curp.py
import sys, re, cv2, pytesseract, unicodedata, numpy as np, pandas as pd
from pathlib import Path
from pytesseract import Output

# Debug switches
DEBUG_SAVE_ROI = False
DEBUG_SAVE_WORDS_CSV = False

# Si tu Tesseract está en otra ruta, cámbiala:
# pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
pytesseract.pytesseract.tesseract_cmd = r'\Program Files\Tesseract-OCR\tesseract.exe'
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ===== Utilidades =====
def strip_accents(s): return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')
def norm(s): return re.sub(r'\s+', ' ', strip_accents(s).upper()).strip()

# Confusiones típicas OCR para posiciones de una CURP
MAP_LFROM_D = {'0':'O','1':'I','2':'Z','5':'S','8':'B'}
MAP_DFROM_L = {'O':'0','I':'1','Z':'2','S':'5','B':'8'}

def pos_fix_18(s: str) -> str:
    s = re.sub(r'[^A-Z0-9]','', norm(s))[:18]
    if len(s) < 18: return s
    x = list(s)
    def L(i): 
        if x[i].isdigit(): x[i] = MAP_LFROM_D.get(x[i], x[i])
    def D(i):
        if x[i].isalpha(): x[i] = MAP_DFROM_L.get(x[i], x[i])
    for i in range(0,4): L(i)          # 1–4 letras
    for i in range(4,10): D(i)         # 5–10 dígitos
    L(10)                               # 11 H/M
    L(11); L(12)                        # 12–13
    for i in range(13,16): L(i)         # 14–16
    D(17)                               # 18 dígito
    return ''.join(x)

CURP_RX = re.compile(
    r"""(?<![A-Z0-9])
    [A-Z][AEIOUX][A-Z]{2}
    \d{2}(?:0[1-9]|1[0-2])
    (?:0[1-9]|[12]\d|3[01])
    [HM]
    (?:AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)
    [A-Z]{3}
    [0-9A-Z]\d
    (?![A-Z0-9])
    """, re.VERBOSE
)

def validate_curp(s: str) -> str|None:
    m = CURP_RX.search(s)
    return m.group(0) if m else None

# ===== OCR helpers =====
def preprocess(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=2.2, beta=12)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return th

def ocr_df(image: np.ndarray, psm=4) -> pd.DataFrame:
    cfg = f"--oem 3 --psm {psm} -l spa -c preserve_interword_spaces=1"
    df = pytesseract.image_to_data(image, config=cfg, output_type=Output.DATAFRAME)
    df = df.dropna(subset=['text']).copy()
    df['text_norm'] = df['text'].astype(str).apply(norm)
    for c in ("left","top","width","height"):
        if c in df.columns: df[c] = df[c].astype(int)
    return df

def ocr_text(image: np.ndarray, psm: int, whitelist=False) -> str:
    cfg = f"--oem 3 --psm {psm} -l spa -c preserve_interword_spaces=1"
    if whitelist:
        cfg += " -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return norm(pytesseract.image_to_string(image, config=cfg))

# ===== Parámetros clave para anclar “la línea de abajo” =====
X_LEFT_PAD   = 40     # menos ancho hacia la izquierda
X_RIGHT_PAD  = 420    # menos ancho hacia la derecha (evita 2023 de “AÑO DE REGISTRO”)
BAND_PIXELS  = 55     # franja más bajita (evita FECHA/SECCIÓN/VIGENCIA)
Y_START_BIAS = -6     # empieza un poco MÁS ARRIBA para no cortar la parte superior de la CURP

def extract_curp_line_below(path: str) -> str|None:
    img_bgr = cv2.imread(path)
    if img_bgr is None:
        raise FileNotFoundError(path)
    img = preprocess(img_bgr)

    # 1) Localizar el label 'CURP' / 'CURV'
    df = ocr_df(img, psm=4)
    if DEBUG_SAVE_WORDS_CSV:
        Path(path).with_suffix(".curp_words.csv").write_text(df.to_csv(index=False))
    labs = df[df['text_norm'].isin(['CURP','CURV'])]
    if labs.empty:
        # Fallback: todo el documento
        full = re.sub(r'[^A-Z0-9]','', ''.join(df['text_norm'].tolist()))
        m = CURP_RX.search(full)
        return m.group(0) if m else None

    label = labs.sort_values(['top','left']).iloc[0]
    lx, ly, lw, lh = int(label['left']), int(label['top']), int(label['width']), int(label['height'])
    h, w = img.shape[:2]

    # 2) Construir la FRANJA justo debajo (misma columna), de altura limitada
    x1 = max(lx - X_LEFT_PAD, 0)
    x2 = min(lx + lw + X_RIGHT_PAD, w)
    y1 = min(max(ly + lh + Y_START_BIAS, 0), h-1)
    y2 = min(y1 + BAND_PIXELS, h)

    band = img[y1:y2, x1:x2]
    if DEBUG_SAVE_ROI:
        cv2.imwrite(Path(path).with_suffix(".curp_band_roi.png").as_posix(), band)

    # 3) OCR exclusivo de esa franja (línea/pequeño texto)
    texts = []
    for psm in (7, 6, 13):                 # 7: single line, 13: raw line, 6: single uniform block
        texts.append(ocr_text(band, psm, whitelist=True))
        texts.append(ocr_text(band, psm, whitelist=False))

    # 4) Buscar match directo; si no, ventanas con corrección posicional
    for t in texts:
        raw = re.sub(r'[^A-Z0-9]','', t)
        m = CURP_RX.search(raw)
        if m:
            return m.group(0)
        for m2 in re.finditer(r'[A-Z0-9]{16,22}', raw):
            cand = m2.group(0)
            fixed = pos_fix_18(cand)
            val = validate_curp(fixed)
            if val:
                return val

    # 5) Último recurso: primera línea detectada debajo (si Tesseract segmentó)
    cx = lx + lw // 2
    words = df[(df['top'] > ly + lh) & (df['left'].between(cx - 260, cx + 260))].copy()
    if not words.empty:
        words = words.sort_values(['top','left'])
        # tomar palabras con top dentro del band y1..y2
        line = words[(words['top'] >= y1) & (words['top'] <= y2)]
        if not line.empty:
            txt = ' '.join(line['text_norm'].tolist())
            raw = re.sub(r'[^A-Z0-9]','', txt)
            m = CURP_RX.search(raw)
            if m: return m.group(0)
            for m2 in re.finditer(r'[A-Z0-9]{16,22}', raw):
                cand = m2.group(0)
                fixed = pos_fix_18(cand)
                val = validate_curp(fixed)
                if val: return val

    return None

# ===== CLI opcional =====
if __name__ == "__main__":
    img_path = sys.argv[1] if len(sys.argv) > 1 else "frente.jpg"
    curp = extract_curp_line_below(img_path)
    print("CURP detectada:", curp)

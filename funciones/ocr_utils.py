import cv2, re, unicodedata, pandas as pd
from pytesseract import Output
import pytesseract

# Ajusta si tu Tesseract está en otra ruta:
# pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
# pytesseract.pytesseract.tesseract_cmd = r'\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'                                           # Linux / Docker     /

# --------- Texto ---------
def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')

def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', strip_accents(str(s)).upper().strip())

# --------- Imagen / OCR ---------
def preprocess_image(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    return preprocess_array(img)

def preprocess_array(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=2.2, beta=12)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return th

def ocr_df(image_bin, psm: int = 4) -> pd.DataFrame:
    cfg = f"--oem 3 --psm {psm} -l spa -c preserve_interword_spaces=1"
    df = pytesseract.image_to_data(image_bin, config=cfg, output_type=Output.DATAFRAME)
    df = df.dropna(subset=['text']).copy()
    df['text'] = df['text'].astype(str)
    df['text_norm'] = df['text'].apply(norm)
    for c in ("left","top","width","height"):
        if c in df.columns: df[c] = df[c].astype(int)
    return df

# --------- Labels / Layout helpers ---------
LABELS_KNOWN = {
    "APELLIDO PATERNO", "APELLIDO MATERNO",
    "NOMBRE", "NOMBRES",
    "DOMICILIO",
    "CURP", "CURV",
    "FECHA", "FECHA DE NACIMIENTO",
    "SECCION", "SECCIÓN", "VIGENCIA",
    "CLAVE DE ELECTOR", "CLAVE ELECTOR", "CLAVE DEL ELECTOR"
}

def normalize_label_key(t: str) -> str:
    t = norm(t)
    if "CLAVE" in t and "ELECTOR" in t:
        return "CLAVE DE ELECTOR"
    if t.startswith("FECHA"):
        return "FECHA DE NACIMIENTO"
    if t == "SECCIÓN":
        return "SECCION"
    return t

def all_label_rows(df: pd.DataFrame) -> pd.DataFrame:
    cand = df[df['text_norm'].isin(LABELS_KNOWN)].copy()
    if cand.empty:
        return cand
    cand['label_key'] = cand['text_norm'].apply(normalize_label_key)
    return cand.sort_values(['top','left']).reset_index(drop=True)

def collect_below_until_next(df, label_row, all_labels_df,
                             x_tolerance=200, y_min_gap=-4, min_delta_down=8) -> str:
    lx, ly, lw, lh = int(label_row['left']), int(label_row['top']), int(label_row['width']), int(label_row['height'])
    cx = lx + lw // 2

    same_col = all_labels_df[
        (all_labels_df['top'] > ly + max(min_delta_down, int(lh*0.4))) &
        (all_labels_df['left'].between(cx - x_tolerance, cx + x_tolerance))
    ].sort_values('top')
    next_y = int(same_col.iloc[0]['top']) if not same_col.empty else 10**9

    band = df[
        (df['top'] > ly + lh + y_min_gap) &
        (df['top'] < next_y) &
        (df['left'].between(cx - x_tolerance, cx + x_tolerance))
    ].sort_values(['top','left'])

    if band.empty: return ""
    if "line_num" in band.columns:
        text = " ".join([" ".join(g['text'].tolist())
                         for _, g in band.groupby(['page_num','block_num','par_num','line_num'])])
    else:
        text = " ".join(band['text'].tolist())
    return norm(text)

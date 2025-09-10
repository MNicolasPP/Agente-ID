# funciones/direccion.py
import re, cv2, pytesseract, unicodedata, numpy as np, pandas as pd
from pytesseract import Output

# Ajusta si tu Tesseract está en otra ruta
# pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract' # macOS Homebrew
# pytesseract.pytesseract.tesseract_cmd = r'\Program Files\Tesseract-OCR\tesseract.exe' # Windows
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ---------- Helpers de texto ----------
def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')

def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', strip_accents(str(s)).upper().strip())

# ---------- Preproceso / OCR ----------
def preprocess(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=2.2, beta=12)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return th

def ocr_df(image_bin: np.ndarray, psm: int = 4) -> pd.DataFrame:
    cfg = f"--oem 3 --psm {psm} -l spa -c preserve_interword_spaces=1"
    df = pytesseract.image_to_data(image_bin, config=cfg, output_type=Output.DATAFRAME)
    df = df.dropna(subset=['text']).copy()
    df['text'] = df['text'].astype(str)
    df['text_norm'] = df['text'].apply(norm)
    for c in ("left","top","width","height"):
        if c in df.columns: df[c] = df[c].astype(int)
    return df

# ---------- Labels / Layout ----------
KNOWN_LABELS = {
    "DOMICILIO", "CLAVE DE ELECTOR", "CLAVE ELECTOR", "CLAVE DEL ELECTOR",
    "CURP", "CURV", "FECHA", "FECHA DE NACIMIENTO", "SECCION", "SECCIÓN", "VIGENCIA",
    "NOMBRE", "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO"
}
STOP_TOKENS = ("CLAVE", "FECHA", "SECCION", "VIGENCIA", "REGISTRO", "AÑO", "ANO", "CURP", "CURV")

def _normalize_label_key(t: str) -> str:
    t = norm(t)
    if "CLAVE" in t and "ELECTOR" in t:
        return "CLAVE DE ELECTOR"
    if t == "SECCIÓN":
        return "SECCION"
    if t.startswith("FECHA"):
        return "FECHA DE NACIMIENTO"
    return t

def _all_label_rows(df: pd.DataFrame) -> pd.DataFrame:
    cand = df[df['text_norm'].isin(KNOWN_LABELS)].copy()
    if cand.empty:
        return cand
    cand['label_key'] = cand['text_norm'].apply(_normalize_label_key)
    return cand.sort_values(['top','left']).reset_index(drop=True)

def _lines_below_same_column(df: pd.DataFrame, label_row: pd.Series,
                             all_labels: pd.DataFrame,
                             x_tolerance: int = 240,
                             y_min_gap: int = -2):
    """Líneas debajo del label en la MISMA columna; corta antes del siguiente label en la misma columna."""
    lx, ly, lw, lh = int(label_row['left']), int(label_row['top']), int(label_row['width']), int(label_row['height'])
    cx = lx + lw // 2

    same_col = all_labels[
        (all_labels['top'] > ly + max(y_min_gap, int(lh * 0.4))) &
        (all_labels['left'].between(cx - x_tolerance, cx + x_tolerance))
    ].sort_values('top')
    next_y = int(same_col.iloc[0]['top']) if not same_col.empty else 10**9

    band = df[
        (df['top'] > ly + lh + y_min_gap) &
        (df['top'] < next_y) &
        (df['left'].between(cx - x_tolerance, cx + x_tolerance))
    ].sort_values(['top','left'])

    if band.empty:
        return []

    lines, current_top, current_h, current_words = [], None, 0, []
    for _, r in band.iterrows():
        t, h = int(r['top']), int(r['height'])
        if current_top is None:
            current_top, current_h = t, h
        if t > current_top + max(10, int(0.6*current_h)):
            lines.append(' '.join(current_words))
            current_words = [r['text_norm']]
            current_top, current_h = t, h
        else:
            current_words.append(r['text_norm'])
    if current_words:
        lines.append(' '.join(current_words))

    lines = [norm(l) for l in lines if l.strip()]
    return lines

# ---------- Limpieza de dirección ----------
ADDR_KEYWORDS = (
    "CALLE", "AV", "AV.", "AVENIDA", "BLVD", "BLVD.", "BOULEVARD",
    "COL", "COL.", "COLONIA", "MZ", "MANZANA", "LT", "LOTE", "INT", "DEPTO", "DEPTO.",
    "NO", "NO.", "NUM", "#", "C.P", "CP", "C.P.", "EDO", "ESTADO", "MUNICIPIO", "ALCALDIA", "DELEGACION", "DELEGACIÓN"
)

def _clean_address(text: str) -> str:
    # corta si aparecen tokens de otros labels
    for stop in STOP_TOKENS:
        idx = text.find(stop)
        if idx != -1:
            text = text[:idx].strip()
            break
    # espacios y signos redundantes
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'[,:;]{2,}', ',', text)
    text = text.strip(' ,.;-')
    return text or ""

# ---------- Fallback por líneas con pinta de dirección ----------
def _group_lines(df: pd.DataFrame):
    groups = []
    if {'page_num','block_num','par_num','line_num'}.issubset(df.columns):
        for _, g in df.sort_values(['top','left']).groupby(['page_num','block_num','par_num','line_num']):
            txt = ' '.join(g['text_norm'].tolist())
            top = int(g['top'].min())
            groups.append((top, norm(txt)))
    else:
        # Fallback tosco: usa saltos detectando cambios grandes de top
        rows = df.sort_values(['top','left'])
        current_top, current_h, words = None, 0, []
        for _, r in rows.iterrows():
            t, h = int(r['top']), int(r['height'])
            if current_top is None:
                current_top, current_h = t, h
            if t > current_top + max(10, int(0.6*current_h)):
                groups.append((current_top, norm(' '.join(words))))
                words = [r['text_norm']]
                current_top, current_h = t, h
            else:
                words.append(r['text_norm'])
        if words:
            groups.append((current_top, norm(' '.join(words))))
    return sorted(groups, key=lambda x: x[0])

def _looks_like_address(s: str) -> bool:
    if any(k in s for k in ADDR_KEYWORDS):
        return True
    # o bien que tenga un número de calle + palabras
    if re.search(r'\b\d{1,5}\b', s) and len(s.split()) >= 3:
        return True
    return False

# ---------- API ----------
def extract_direccion_desde_path(img_path: str,
                                 max_lines: int = 3,
                                 x_tolerance: int = 240,
                                 y_min_gap: int = -2) -> str | None:
    """
    Devuelve un string con la dirección. Lee debajo de 'DOMICILIO'
    (misma columna) y concatena hasta max_lines líneas, cortando ante
    otros labels. Si no hay label, intenta heurística por palabras clave.
    """
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(img_path)
    img = preprocess(img_bgr)
    df = ocr_df(img, psm=4)

    labels = df[df['text_norm'].isin(["DOMICILIO", "DIRECCION", "DIRECCIÓN"])]
    if not labels.empty:
        label = labels.sort_values(['top','left']).iloc[0]
        all_labels = _all_label_rows(df)
        lines = _lines_below_same_column(df, label, all_labels,
                                         x_tolerance=x_tolerance,
                                         y_min_gap=y_min_gap)
        if lines:
            joined = ' '.join(lines[:max_lines])
            addr = _clean_address(joined)
            return addr or None

    # ---- Fallback heurístico sin label ----
    grouped = _group_lines(df)
    for i, (_, line) in enumerate(grouped):
        if _looks_like_address(line):
            take = [line]
            if i+1 < len(grouped):
                take.append(grouped[i+1][1])
            addr = _clean_address(' '.join(take))
            if addr:
                return addr

    return None

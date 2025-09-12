# funciones/nombres.py
import re, cv2, pytesseract, unicodedata, numpy as np, pandas as pd
from pytesseract import Output
import funciones.ocr_env

# (opcional) ajusta la ruta si tu Tesseract está en otro lugar
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
# pytesseract.pytesseract.tesseract_cmd = r'\Program Files\Tesseract-OCR\tesseract.exe'
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ---------- helpers de texto ----------
def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')

def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', strip_accents(str(s)).upper().strip())

# ---------- preproceso / OCR ----------
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

# ---------- detección de labels / cortes ----------
KNOWN_LABELS = {
    "DOMICILIO", "CLAVE", "CLAVE DE ELECTOR", "CLAVE ELECTOR", "CLAVE DEL ELECTOR",
    "CURP", "CURV", "FECHA", "FECHA DE NACIMIENTO", "SECCION", "SECCIÓN", "VIGENCIA",
    "NOMBRE", "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO"
}

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
    cand['label_key'] = cand['text_norm'] = cand['text_norm'].apply(_normalize_label_key)
    return cand.sort_values(['top','left']).reset_index(drop=True)

# ---------- recoger líneas debajo (misma columna) ----------
def _lines_below_same_column(df: pd.DataFrame, label_row: pd.Series,
                             all_labels: pd.DataFrame,
                             x_tolerance: int = 200,
                             y_min_gap: int = 0):
    lx, ly, lw, lh = int(label_row['left']), int(label_row['top']), int(label_row['width']), int(label_row['height'])
    cx = lx + lw // 2

    # "Siguiente label" en la MISMA columna para cortar el bloque
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

    # Agrupar por líneas por proximidad vertical
    lines = []
    current_top = None
    current_h = 0
    current_words = []
    for _, r in band.iterrows():
        t, h = int(r['top']), int(r['height'])
        if current_top is None:
            current_top, current_h = t, h
        # salto de línea si cambia mucho el "top"
        if t > current_top + max(10, int(0.6*current_h)):
            lines.append(' '.join(current_words))
            current_words = [r['text_norm']]
            current_top, current_h = t, h
        else:
            current_words.append(r['text_norm'])
    if current_words:
        lines.append(' '.join(current_words))

    # Normaliza/limpia líneas
    lines = [norm(l) for l in lines if l.strip()]
    return lines

# ---------- heurística para separar apellidos / nombres ----------
PARTICULAS = {"DE","DEL","DE LA","DE LAS","DE LOS","LA","LOS","LAS","DA","DOS","VON","VAN","MC","MAC","SAN","SANTA"}

def _split_name_lines(lines: list[str]):
    """
    Casos típicos INE moderna:
      L1 = APELLIDO PATERNO
      L2 = APELLIDO MATERNO
      L3.. = NOMBRES
    Fallbacks para 1 o 2 líneas.
    """
    ap_pat = ap_mat = nombre = None

    if len(lines) >= 3:
        ap_pat = lines[0].strip()
        ap_mat = lines[1].strip()
        nombre = ' '.join(lines[2:]).strip()
    elif len(lines) == 2:
        # Si línea 1 es una sola palabra y línea 2 tiene 1+ palabras:
        t1 = lines[0].split()
        t2 = lines[1].split()
        if len(t1) == 1:
            ap_pat = t1[0]
            if len(t2) >= 2:
                ap_mat = t2[0]
                nombre = ' '.join(t2[1:])
            else:
                ap_mat = t2[0]
                nombre = None
        else:
            # Fallback: toma 1º y 2º token como apellidos
            comb = (lines[0] + ' ' + lines[1]).split()
            if len(comb) >= 3:
                ap_pat, ap_mat = comb[0], comb[1]
                nombre = ' '.join(comb[2:])
            else:
                nombre = ' '.join(comb)
    elif len(lines) == 1:
        parts = lines[0].split()
        if len(parts) >= 3:
            ap_pat, ap_mat = parts[0], parts[1]
            nombre = ' '.join(parts[2:])
        else:
            nombre = ' '.join(parts)

    # Limpieza final
    def clean(x):
        x = (x or "").strip()
        x = re.sub(r'\s{2,}', ' ', x)
        return x if x else None

    return clean(ap_pat), clean(ap_mat), clean(nombre)

# ---------- API: usar directo con una ruta de imagen ----------
def extract_nombres_desde_path(img_path: str) -> dict:
    """
    Devuelve dict: {"apellido_paterno", "apellido_materno", "nombre"}
    Lee el bloque inmediatamente debajo de 'NOMBRE'/'NOMBRES' (misma columna),
    y corta antes del siguiente label vertical de la misma columna.
    """
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(img_path)
    img = preprocess(img_bgr)
    df = ocr_df(img, psm=4)

    # Buscar label de NOMBRE/NOMBRES
    labels = df[df['text_norm'].isin(["NOMBRE","NOMBRES"])]
    if labels.empty:
        # Fallback muy básico: línea en mayúsculas con >=3 palabras y sin dígitos
        candidates = [l for l in df['text_norm'].tolist()
                      if l.isupper() and len(l.split()) >= 3 and not any(c.isdigit() for c in l)]
        if candidates:
            parts = candidates[0].split()
            ap_pat, ap_mat, nombre = _split_name_lines([' '.join(parts)])
            return {
                "apellido_paterno": ap_pat,
                "apellido_materno": ap_mat,
                "nombre": nombre
            }
        return {"apellido_paterno": None, "apellido_materno": None, "nombre": None}

    label = labels.sort_values(['top','left']).iloc[0]
    all_labels = _all_label_rows(df)
    lines = _lines_below_same_column(df, label, all_labels, x_tolerance=200, y_min_gap=0)
    ap_pat, ap_mat, nombre = _split_name_lines(lines)

    return {
        "apellido_paterno": ap_pat,
        "apellido_materno": ap_mat,
        "nombre": nombre
    }

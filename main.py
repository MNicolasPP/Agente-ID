import cv2
import numpy as np
import pytesseract
import re
from dataclasses import dataclass, asdict
from dateutil import parser as dateparser
from unidecode import unidecode
from rapidfuzz import fuzz

# ---------- Config ----------
# Ajusta ruta si Tesseract no está en PATH (Windows):
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESS_LANG = "spa+eng"   # añade "+ocrb" si lo tienes instalado
TESS_CONFIG = r'--oem 3 --psm 6'  # o 4/6/7 según layout

@dataclass
class IDFields:
    nombre: str | None = None
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    nombre_completo: str | None = None
    fecha_nacimiento: str | None = None  # ISO yyyy-mm-dd
    curp: str | None = None
    numero_credencial: str | None = None
    domicilio: str | None = None
    sexo: str | None = None
    nacionalidad: str | None = None
    raw_text: str | None = None
    confidence: float | None = None

# ---------- Utilidades ----------
def order_quad(pts):
    # pts: 4x2
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect = np.zeros((4,2), dtype="float32")
    rect[0] = pts[np.argmin(s)]     # top-left
    rect[2] = pts[np.argmax(s)]     # bottom-right
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect

def four_point_warp(image, pts):
    rect = order_quad(pts)
    (tl, tr, br, bl) = rect
    # compute width/height
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxW = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxH = int(max(heightA, heightB))
    dst = np.array([[0,0],[maxW-1,0],[maxW-1,maxH-1],[0,maxH-1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxW, maxH))
    return warped

def find_id_card(bgr):
    # 1) downscale opcional
    img = bgr.copy()
    ratio = 800 / img.shape[1] if img.shape[1] > 800 else 1.0
    if ratio < 1.0:
        img = cv2.resize(img, (int(img.shape[1]*ratio), int(img.shape[0]*ratio)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if area > best_area:
                best = approx.reshape(4,2)
                best_area = area

    if best is None:
        # fallback: no contorno claro → devuelve imagen original
        return bgr
    # re-escalar puntos si hicimos resize
    if ratio < 1.0:
        best = (best / ratio).astype(np.float32)
    return four_point_warp(bgr, best)

def preprocess_for_ocr(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # mejora de contraste local
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # de-ruido suave preservando bordes
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    # binarización adaptativa
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 12)
    return thr

def ocr_with_conf(image_bin):
    data = pytesseract.image_to_data(image_bin, lang=TESS_LANG, config=TESS_CONFIG, output_type=pytesseract.Output.DICT)
    # texto concatenado
    words = [w for w in data["text"] if w.strip()]
    text = " ".join(words)
    # confianza media simple (ignora -1)
    confs = [int(c) for c in data["conf"] if c not in ("-1", -1)]
    mean_conf = float(sum(confs) / len(confs)) if confs else 0.0
    return text, mean_conf

# ---------- Extracción de campos ----------
CURP_RE = r"\b([A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b"
RFC_RE = r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b"
FECHA_RE = r"\b(\d{2}[\/\-\.\s]\d{2}[\/\-\.\s]\d{2,4})\b"  # dd/mm/aaaa

def normalize_text(t):
    t = t.replace("\n"," ").strip()
    t = re.sub(r"\s+", " ", t)
    return t

def parse_date_any(s):
    try:
        d = dateparser.parse(s, dayfirst=True, yearfirst=False, fuzzy=True)
        return d.date().isoformat() if d else None
    except Exception:
        return None

def extract_fields(text):
    t = normalize_text(text)
    t_ascii = unidecode(t).upper()

    fields = IDFields(raw_text=t)

    # CURP (si aplica)
    m = re.search(CURP_RE, t_ascii)
    if m: fields.curp = m.group(1)

    # RFC (por si el ID lo incluye)
    # rfc = re.search(RFC_RE, t_ascii)
    # if rfc: fields.rfc = rfc.group(1)

    # Fecha de nacimiento (heurística)
    fecha = None
    for m in re.finditer(FECHA_RE, t):
        candidate = parse_date_any(m.group(1))
        if candidate:
            fecha = candidate
            break
    fields.fecha_nacimiento = fecha

    # Sexo (heurística simple)
    if re.search(r"\b(M|HOMBRE|H|MASCULINO)\b", t_ascii):
        fields.sexo = "H"
    elif re.search(r"\b(F|MUJER|FEMENINO)\b", t_ascii):
        fields.sexo = "M"

    # Nombre (dos estrategias):
    # A) Por etiqueta común
    nombre = None
    label_hits = re.findall(r"(NOMBRE|NOMBRE(S)?|NAME)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ\s]{3,})", t_ascii)
    if label_hits:
        nombre = label_hits[0][2].strip()

    # B) Fallback: línea más "nombre-like" (mayúsculas con espacios, sin dígitos)
    if not nombre:
        candidates = [s.strip() for s in t_ascii.split() if s.isalpha() and len(s) >= 3]
        # pega ventanas de 2–4 tokens y busca similitud con etiquetas típicas
        joined = " ".join(candidates)
        # esto es muy heurístico; para producción usa layout ROIs
        nombre = None
        for n in re.findall(r"([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,3})", joined):
            if fuzz.partial_ratio(n, "NOMBRE") < 60 and len(n.split()) >= 2:
                nombre = n
                break

    if nombre:
        fields.nombre_completo = " ".join(nombre.split())

    # Número de credencial (heurística: bloques de 8–13 dígitos/letras)
    num = re.search(r"\b([A-Z0-9]{8,13})\b", t_ascii)
    if num:
        fields.numero_credencial = num.group(1)

    return fields

def process_id_image(path):
    bgr = cv2.imread(path)
    if bgr is None:
        raise FileNotFoundError(path)
    card = find_id_card(bgr)
    prep = preprocess_for_ocr(card)
    text, conf = ocr_with_conf(prep)
    fields = extract_fields(text)
    fields.confidence = round(conf, 2)
    return fields

# ---------- Demo CLI ----------
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Uso: python id_ocr.py <imagen_anverso> [imagen_reverso]")
        sys.exit(1)

    front = process_id_image(sys.argv[1])
    result = {"anverso": asdict(front)}

    if len(sys.argv) >= 3:
        back = process_id_image(sys.argv[2])
        result["reverso"] = asdict(back)

    print(json.dumps(result, ensure_ascii=False, indent=2))

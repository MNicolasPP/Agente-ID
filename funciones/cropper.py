# funciones/cropper.py
# Recorta una credencial (ID-1) desde una foto: detecta cuadrilátero,
# corrige perspectiva SIN deformar, aprieta bordes y centra al ratio 1.586.
# Guarda el recorte final y, si debug=True, imágenes auxiliares.

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

# Relación de aspecto estándar ID-1 (85.6 × 53.98 mm)
ID1_RATIO = 85.6 / 53.98  # ≈ 1.586 (ancho / alto)

# ---------------------------- Utilidades geométricas ----------------------------

def _rotate(img: np.ndarray, k: int) -> np.ndarray:
    """Rota 0/90/180/270 en pasos de 90°."""
    if k % 4 == 0: return img
    if k % 4 == 1: return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if k % 4 == 2: return cv2.rotate(img, cv2.ROTATE_180)
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

def _order(pts: np.ndarray) -> np.ndarray:
    """Ordena puntos (tl, tr, br, bl)."""
    pts = np.asarray(pts, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype="float32")

def _edge_map(bgr: np.ndarray) -> np.ndarray:
    """Mapa de bordes robusto (CLAHE + Canny + adaptative)."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(2.0, (8, 8)).apply(gray)
    den = cv2.medianBlur(clahe, 5)
    e1 = cv2.Canny(den, 60, 160)
    th = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 35, 5)
    e2 = cv2.Canny(th, 30, 120)
    edges = cv2.bitwise_or(e1, e2)
    return cv2.dilate(edges, np.ones((3, 3), np.uint8), 1)

def _aspect(quad: np.ndarray) -> float:
    """Aspect ratio del cuadrilátero (mayor/lower)."""
    r = _order(quad)
    w = max(np.linalg.norm(r[1] - r[0]), np.linalg.norm(r[2] - r[3]))
    h = max(np.linalg.norm(r[2] - r[1]), np.linalg.norm(r[3] - r[0]))
    if min(w, h) <= 1: return 1.0
    return float(max(w, h) / min(w, h))

# ---------------------------- Detección de cuadrilátero ----------------------------

def _find_quad(img: np.ndarray,
               ratio_target: float,
               min_area_ratio: float = 0.12,
               top_k: int = 40) -> Optional[np.ndarray]:
    """
    Busca el mejor cuadrilátero tipo tarjeta:
      - 4 vértices convexos
      - área suficiente
      - relación de aspecto cercana a ratio_target (1.586)
    Devuelve 4 puntos (x, y) o None.
    """
    H, W = img.shape[:2]
    edges = _edge_map(img)
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:top_k]

    best, best_score = None, 1e9
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area_ratio * W * H:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        quad = approx.reshape(4, 2).astype("float32")
        ar = _aspect(quad)
        area_norm = area / (W * H)
        # score simple: cercanía al ratio y preferencia por área grande
        score = abs(ar - ratio_target) * 5.0 - area_norm * 2.0
        if score < best_score:
            best_score, best = score, quad

    if best is None and cnts:
        # Último recurso: rectángulo mínimo del contorno mayor
        best = cv2.boxPoints(cv2.minAreaRect(cnts[0])).astype("float32")

    return best

# ---------------------------- Warp, apriete y crop ----------------------------

def _warp_by_measured_size(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """
    Warpea usando el ancho/alto MEDIDOS del quad (no fuerza ratio).
    Evita “aplastar” la tarjeta.
    """
    rect = _order(quad)
    wA = np.linalg.norm(rect[1] - rect[0]); wB = np.linalg.norm(rect[2] - rect[3])
    hA = np.linalg.norm(rect[2] - rect[1]); hB = np.linalg.norm(rect[3] - rect[0])
    W = int(round(max(wA, wB))); H = int(round(max(hA, hB)))
    W = max(W, 50); H = max(H, 50)
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (W, H))
    return warped

def _tighten_borders_axis_aligned(img: np.ndarray, pad: int = 3) -> np.ndarray:
    """
    Apreta bordes tras el warp: detecta el contorno externo y recorta al bounding box.
    Deja 'pad' px de margen para no cortar el borde impreso.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 35, 5)
    edges = cv2.Canny(th, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), 1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return img

    c = max(cnts, key=cv2.contourArea)
    x, y, ww, hh = cv2.boundingRect(c)
    x = max(x - pad, 0); y = max(y - pad, 0)
    ww = min(ww + 2 * pad, w - x); hh = min(hh + 2 * pad, h - y)

    # Sanity check para evitar recorte absurdo
    if ww < w * 0.6 or hh < h * 0.6:
        return img
    return img[y:y + hh, x:x + ww]

def _center_crop_to_ratio(img: np.ndarray, ratio: float) -> np.ndarray:
    """Recorte centrado para ajustar al ratio pedido (sin deformar)."""
    h, w = img.shape[:2]
    curr = w / h
    if abs(curr - ratio) < 0.02:
        return img
    if curr > ratio:
        new_w = int(round(ratio * h))
        x1 = max((w - new_w) // 2, 0); x2 = x1 + new_w
        return img[:, x1:x2]
    else:
        new_h = int(round(w / ratio))
        y1 = max((h - new_h) // 2, 0); y2 = y1 + new_h
        return img[y1:y2, :]

# ---------------------------- API principal ----------------------------

def crop_credencial(img_path: str,
                    save_path: Optional[str] = None,
                    out_width: int = 1200,
                    ratio: float = ID1_RATIO,
                    debug: bool = False) -> str:
    """
    Detecta la credencial en una foto, corrige perspectiva sin deformar,
    aprieta bordes y centra al ratio ID-1. Devuelve la ruta del archivo recortado.

    - img_path: foto original.
    - save_path: ruta de salida; si None → '<original>.cropped.jpg'
    - out_width: ancho final (alto se calcula con el ratio).
    - ratio: relación destino (1.586).
    - debug: si True, guarda '<out>.dbg.jpg' y '<out>.edges.jpg'.
    """
    src = cv2.imread(img_path)
    if src is None:
        raise FileNotFoundError(img_path)

    # Trabajo en “small” para detección (más rápido/estable)
    H0, W0 = src.shape[:2]
    scale = 1000.0 / max(W0, H0)
    small = cv2.resize(src, (int(W0 * scale), int(H0 * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else src.copy()

    best_img = None
    best_dbg = None
    best_edges = None
    best_score = 1e9

    # Probar 4 rotaciones (0/90/180/270)
    for rot in range(4):
        img_r = _rotate(small, rot)
        quad = _find_quad(img_r, ratio_target=ratio, min_area_ratio=0.12)
        if quad is None:
            continue

        # Warp por tamaño medido → apretar → orientar → crop al ratio
        warped = _warp_by_measured_size(img_r, quad)
        warped = _tighten_borders_axis_aligned(warped, pad=3)
        if warped.shape[0] > warped.shape[1]:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
        cropped = _center_crop_to_ratio(warped, ratio)

        # Score: cercanía al ratio + preferencia por ocupar tamaño
        h, w = cropped.shape[:2]
        score = abs((w / h) - ratio) + (1.0 - min(w, h) / max(small.shape[:2])) * 0.5

        if score < best_score:
            best_score = score
            best_img = cropped
            if debug:
                dbg = img_r.copy()
                cv2.polylines(dbg, [quad.astype(np.int32)], True, (0, 255, 0), 3)
                best_dbg = dbg
                best_edges = _edge_map(img_r)

    # Fallback si no hubo buen quad en ninguna rotación
    if best_img is None:
        edges = _edge_map(small)
        cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            box = cv2.boxPoints(cv2.minAreaRect(max(cnts, key=cv2.contourArea))).astype("float32")
            warped = _warp_by_measured_size(small, box)
        else:
            warped = small
        warped = _tighten_borders_axis_aligned(warped, pad=3)
        if warped.shape[0] > warped.shape[1]:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
        best_img = _center_crop_to_ratio(warped, ratio)
        if debug:
            best_edges = edges
            best_dbg = small.copy()
            if cnts:
                cv2.polylines(best_dbg, [box.astype(np.int32)], True, (0, 0, 255), 3)

    # Resize final proporcional al ratio destino
    out_h = int(round(out_width / ratio))
    final = cv2.resize(best_img, (out_width, out_h), interpolation=cv2.INTER_CUBIC)

    # Guardar
    out = save_path or (str(Path(img_path).with_suffix("")) + ".cropped.jpg")
    cv2.imwrite(out, final)

    return out

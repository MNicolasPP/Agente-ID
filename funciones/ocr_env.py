# Centraliza la ruta de tesseract para todos los módulos
import os, platform, shutil, pytesseract

# 1) Permite override por variable de entorno
cmd = os.getenv("TESSERACT_CMD")

# 2) Si no hay env, intenta detectar según SO
if not cmd:
    if platform.system() == "Darwin":  # macOS
        for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(p):
                cmd = p
                break
    elif platform.system() == "Windows":
        for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
            if os.path.exists(p):
                cmd = p
                break
    # 3) Último recurso: lo que haya en PATH
    if not cmd:
        cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

pytesseract.pytesseract.tesseract_cmd = cmd

# (opcional) ruta de datos de idiomas
if platform.system() == "Darwin":
    os.environ.setdefault("TESSDATA_PREFIX", "/opt/homebrew/share/tessdata")

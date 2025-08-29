import cv2
import pytesseract

# Si en algún momento no encuentra Tesseract, descomenta y ajusta esta línea:
# pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"

# Cargar imagen (usa una foto con texto, puede ser cualquier JPG/PNG)
img = cv2.imread("ejemplo.jpg")

# Convertir a escala de grises (mejora el OCR)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Extraer texto con Tesseract
text = pytesseract.image_to_string(gray, lang="spa+eng")

print("Texto detectado:")
print(text)

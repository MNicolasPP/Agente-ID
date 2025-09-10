# Usa una imagen base oficial de Python
FROM python:slim-trixie

# Instala Tesseract OCR y sus dependencias de OpenCV
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-spa libsm6 libxext6 libxrender-dev libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Copia los archivos de tu proyecto al contenedor
WORKDIR /app
COPY . /app

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Comando por defecto para ejecutar tu aplicacion
CMD ["python", "main.py"]

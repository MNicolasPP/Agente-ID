FROM python:3.11

# Instala Tesseract OCR y sus dependencias de OpenCV
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-spa libsm6 libxext6 libxrender-dev libgl1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "python_services/id_service.py"]
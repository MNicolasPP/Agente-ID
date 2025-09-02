import easyocr
import cv2

def escanear_texto(imagen):
    # 1. Instalar librerías (si no las tienes)
    # pip install easyocr opencv-python

    # 2. Inicializar el lector de EasyOCR
    # Puedes especificar los idiomas que quieres soportar. En este caso, inglés y español.
    reader = easyocr.Reader(['en', 'es'], gpu=False)    # Cambiar el valor de gpu a True si tienes una GPU compatible

    # 3. Leer texto de una imagen
    # Reemplaza 'ruta/a/tu/imagen.jpg' con la ruta de tu archivo de imagen
    result = reader.readtext(imagen)

    # 4. Procesar y mostrar los resultados
    for (bbox, text, prob) in result:
        # bbox contiene las coordenadas de los cuadros que rodean el texto
        # text es el texto extraído
        # prob es la probabilidad de la detección (entre 0 y 1)
        print(f"Texto: {text}, Confianza: {prob:.4f}")

        # Opcional: dibuja los cuadros alrededor del texto en la imagen
        # Asegúrate de tener OpenCV instalado
        img = cv2.imread(imagen)
        (top_left, top_right, bottom_right, bottom_left) = bbox
        top_left = tuple(map(int, top_left))
        bottom_right = tuple(map(int, bottom_right))
        cv2.rectangle(img, top_left, bottom_right, (0, 255, 0), 2)
        cv2.putText(img, text, (top_left[0], top_left[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Muestra la imagen (requiere una interfaz gráfica)
        cv2.namedWindow("Imagen con Texto", cv2.WINDOW_NORMAL)
        cv2.imshow("Imagen con Texto", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    imagen = 'INE2.jpg'
    escanear_texto(imagen)


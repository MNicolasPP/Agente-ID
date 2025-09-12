| Variable      | Descripción                                             | Ejemplo                                                 |
| ------------- | ------------------------------------------------------- | ------------------------------------------------------- |
| `TOOL_URL`    | URL del proxy (tool)                                    | `http://localhost:4000`                                 |
| `PY_URL`      | URL del backend Python (puerto donde corre uvicorn)     | `http://127.0.0.1:3000` _(o `3001`)_                    |
| `OUT_JSON`    | Nombre del archivo de salida que guarda Python          | `ine_datos.json`                                        |
| `IMG_PATH` \_ | **Ruta absoluta** a la imagen `.jpg/.png` en tu Mac     | `/Users/tu_usuario/…/Agente-ID/foto_ine.jpg`            |
| `IMG_B64`     | **Contenido base64** de la imagen en **una sola línea** | _(pega el base64 completo; no pongas la ruta del .txt)_ |

si se usa b64 para copiar todo el contenido es:
tr -d '\n\r' < "/ruta/imagen_base64.txt" | pbcopy

body:
{
"input_data": {
"image": "{{IMG_PATH}}",
"out_json": "{{OUT_JSON}}"
},
"config": {
"python_url": "{{PY_URL}}"
}
}

Checks rápidos

Salud del proxy: GET {{TOOL_URL}}/health

Salud de Python: GET {{PY_URL}}/health

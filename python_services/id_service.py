import os
import sys
import base64
from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn
import tempfile
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
app = FastAPI(title="ID Extraction Service", version="1.0.0")

class ImageRequest(BaseModel):
    image_base64: str
    out_json: str = "ine_datos.json"  # nombre de archivo opcional

class ImageResponse(BaseModel):
    curp: str | None = None
    ap_pat: str | None = None
    ap_mat: str | None = None
    nombre: str | None = None
    direccion: str | None = None
    json_file: str | None = None
    error: str | None = None

@app.get("/health")
def health():
    return {"status": "ok", "name": "ID-extractor-agent", "version": "1.0.0"}

@app.post("/execute")
async def execute(request: Request):
    tmp_path = None
    print("Payload recibido en Python:", await request.json())
    try:
        body = await request.json()
        img_b64 = body.get("image_base64")
        if not img_b64:
            return {"error": "No image provided"}
        try:
            content = base64.b64decode(img_b64)
        except Exception as e:
            return {"error": f"Error decoding base64: {str(e)}"}
        out_json = body.get("out_json", "ine_datos.json")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            from funciones.curp import extract_curp_line_below
            from funciones.nombres import extract_nombres_desde_path
            from funciones.direccion import extract_direccion_desde_path
        except Exception as e:
            return {"error": f"Error importing extraction functions: {str(e)}"}
        try:
            curp = extract_curp_line_below(tmp_path)
        except Exception as e:
            return {"error": f"Error extracting CURP: {str(e)}"}
        try:
            nombres = extract_nombres_desde_path(tmp_path)
        except Exception as e:
            return {"error": f"Error extracting names: {str(e)}"}
        try:
            direccion = extract_direccion_desde_path(tmp_path)
        except Exception as e:
            return {"error": f"Error extracting address: {str(e)}"}
        datos = {
            "curp": curp,
            "apellido_paterno": nombres.get("ap_pat") or nombres.get("apellido_paterno"),
            "apellido_materno": nombres.get("ap_mat") or nombres.get("apellido_materno"),
            "nombre": nombres.get("nombre"),
            "direccion": direccion
        }
        try:
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            return {**datos, "error": f"Error saving JSON: {str(e)}"}
        return {**datos, "json_file": out_json}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 3000)))

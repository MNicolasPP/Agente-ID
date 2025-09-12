# main.py
import json
from pathlib import Path

from funciones import (
    extract_curp_line_below,
    extract_nombres_desde_path,
    extract_direccion_desde_path,
)

def main(img_path: str = "frente.jpg", out_json: str = "ine_datos.json"):
    datos = {}
    datos["curp"] = extract_curp_line_below(img_path)
    datos.update(extract_nombres_desde_path(img_path))
    datos["direccion"] = extract_direccion_desde_path(img_path)

    Path(out_json).write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    print("OK →", out_json)

if __name__ == "__main__":
    main()

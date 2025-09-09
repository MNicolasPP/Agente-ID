import json
from pathlib import Path
from .cropper import crop_credencial
from .curp import extraer_curp
from .nombres import extract_nombres_desde_path
from .direccion import extract_direccion_desde_path

def procesar_ine(img_path: str,
                 out_dir: str | None = None,
                 debug: bool = False,
                 save_json: bool = True) -> dict:
    """
    Función central: recibe una foto de una credencial, la recorta,
    y extrae CURP, nombres y dirección.
    """
    # 1. Recorte
    img_path = Path(img_path)
    out_dir = Path(out_dir) if out_dir else img_path.parent
    cropped_path = out_dir / (img_path.stem + ".cropped.jpg")

    crop_credencial(str(img_path),
                    save_path=str(cropped_path),
                    out_width=1200,
                    debug=debug)

    # 2. Extracción de campos
    curp = extraer_curp(str(cropped_path))
    nombres = extract_nombres_desde_path(str(cropped_path))
    direccion = extract_direccion_desde_path(str(cropped_path))

    # 3. Consolidar resultados
    data = {
        "curp": curp,
        "apellido_paterno": nombres.get("apellido_paterno"),
        "apellido_materno": nombres.get("apellido_materno"),
        "nombre": nombres.get("nombre"),
        "direccion": direccion,
        "imagen_recortada": str(cropped_path)
    }

        # --- Validación de coherencia ---
    if not curp or len(curp) < 18 or (
        not data["apellido_paterno"] and
        not data["apellido_materno"] and
        not data["nombre"]
    ):
        return {
            print("Intente tomar la foto de nuevo por favor")
        }

    if save_json:
        json_path = out_dir / "ine_datos.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        data["json_path"] = str(json_path)

    return data

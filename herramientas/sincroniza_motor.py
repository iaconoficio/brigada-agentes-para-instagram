#!/usr/bin/env python3
"""
sincroniza_motor.py · La Brigada (IA con Oficio)

brigada-para-llevar dibuja las imágenes de la semana con el mismo motor que la
Lámina de texto (lamina-de-texto.html): las mismas medidas, los mismos temas,
la misma forma de partir las líneas y el mismo .zip.

La Lámina es una página suelta que funciona sin internet, y cada agente tiene
que poder instalarse por su cuenta, así que el motor va copiado dentro del
agente, en skills/brigada-para-llevar/assets/motor-lamina.js. Este script lo
vuelve a copiar. Ejecútalo cada vez que cambies el dibujo de la Lámina. Las
pruebas avisan si se te olvida.

Uso
  python3 herramientas/sincroniza_motor.py
  python3 herramientas/sincroniza_motor.py --comprobar   # no cambia nada; falla si no coinciden

Solo usa Python estándar y no se conecta a nada.
"""

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "herramientas" / "lamina-de-texto.html"
COPIA = RAIZ / "skills" / "brigada-para-llevar" / "assets" / "motor-lamina.js"

CABECERA = """// motor-lamina.js · La Brigada (IA con Oficio)
//
// El motor de dibujo de la Lámina de texto (herramientas/lamina-de-texto.html),
// copiado tal cual por herramientas/sincroniza_motor.py. No lo cambies a mano:
// cambia la Lámina y vuelve a ejecutar ese script.
//
// Necesita que quien lo use defina antes «estado» (como el de la Lámina) y
// «fotoImg» (la foto ya cargada, o null).
"""

# Trozos de la Lámina, de una línea que empieza así hasta otra.
# (desde, hasta, ¿la línea de «hasta» entra?)
TROZOS = [
    ("var FORMATOS = {", "var AZUL_VERIFICADO", True),
    ("var INVISIBLES", "function limpiarParaDibujar", True),
    ("// ---------- Dibujo ----------", "// ---------- Estado ----------", False),
    ("// ZIP sin compresión", "// Foto:", False),
]


def motor(html):
    """El motor que hay ahora en la Lámina, listo para guardar."""
    lineas = html.splitlines()
    partes = []
    for desde, hasta, incluida in TROZOS:
        inicio = next((i for i, l in enumerate(lineas) if l.strip().startswith(desde)), None)
        if inicio is None:
            raise SystemExit(f"No encuentro en la Lámina la línea que empieza por «{desde}».")
        fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].strip().startswith(hasta)), None)
        if fin is None:
            raise SystemExit(f"No encuentro en la Lámina la línea que empieza por «{hasta}».")
        trozo = lineas[inicio:fin + 1 if incluida else fin]
        while trozo and not trozo[-1].strip():
            trozo.pop()
        partes.append("\n".join(l[2:] if l.startswith("  ") else l for l in trozo))
    return CABECERA + "\n" + "\n\n".join(partes) + "\n"


def main():
    p = argparse.ArgumentParser(description="Copia el motor de dibujo de la Lámina dentro de brigada-para-llevar.")
    p.add_argument("--comprobar", action="store_true", help="solo comprueba que coinciden")
    args = p.parse_args()

    nuevo = motor(PAGINA.read_text(encoding="utf-8"))
    if args.comprobar:
        actual = COPIA.read_text(encoding="utf-8") if COPIA.exists() else ""
        if actual == nuevo:
            print("Coinciden.")
            return 0
        print("No coinciden. Ejecuta: python3 herramientas/sincroniza_motor.py")
        return 1

    COPIA.parent.mkdir(parents=True, exist_ok=True)
    COPIA.write_text(nuevo, encoding="utf-8")
    print("Motor copiado en brigada-para-llevar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

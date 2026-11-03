#!/usr/bin/env python3
"""
sincroniza_muletillas.py · La Brigada (IA con Oficio)

La Lámina de texto (lamina-de-texto.html) avisa de las muletillas de IA con
la misma lista que usa brigada-humano: skills/brigada-humano/scripts/muletillas.json.

La página funciona sin internet y abierta desde el disco, así que no puede
leer ese archivo por su cuenta: la lista va copiada dentro de la página.
Este script la vuelve a copiar. Ejecútalo cada vez que cambies muletillas.json.
Las pruebas avisan si se te olvida.

Uso
  python3 herramientas/sincroniza_muletillas.py
  python3 herramientas/sincroniza_muletillas.py --comprobar   # no cambia nada; falla si no coinciden

Solo usa Python estándar y no se conecta a nada.
"""

import argparse
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LISTA = RAIZ / "skills" / "brigada-humano" / "scripts" / "muletillas.json"
PAGINA = RAIZ / "herramientas" / "lamina-de-texto.html"
BLOQUE = re.compile(r'(<script type="application/json" id="muletillas">)(.*?)(</script>)', re.S)


def lista_en_pagina(html):
    m = BLOQUE.search(html)
    if not m:
        raise SystemExit("No encuentro el bloque de muletillas en la página.")
    return json.loads(m.group(2))


def main():
    p = argparse.ArgumentParser(description="Copia muletillas.json dentro de la Lámina de texto.")
    p.add_argument("--comprobar", action="store_true", help="solo comprueba que coinciden")
    args = p.parse_args()

    lista = json.loads(LISTA.read_text(encoding="utf-8"))
    html = PAGINA.read_text(encoding="utf-8")

    if args.comprobar:
        if lista_en_pagina(html) == lista:
            print("Coinciden.")
            return 0
        print("No coinciden. Ejecuta: python3 herramientas/sincroniza_muletillas.py")
        return 1

    # ensure_ascii: las tildes y las rayas van escapadas, así la página no
    # lleva rayas sueltas ni caracteres invisibles fuera de este bloque.
    texto = json.dumps(lista, ensure_ascii=True, separators=(",", ":"))
    nuevo = BLOQUE.sub(lambda m: m.group(1) + texto + m.group(3), html, count=1)
    PAGINA.write_text(nuevo, encoding="utf-8")
    print("Lista copiada en la página.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

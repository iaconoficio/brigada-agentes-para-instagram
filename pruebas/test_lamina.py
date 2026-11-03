"""
Pruebas de la Lámina de texto (herramientas/lamina-de-texto.html).

Comprueban las dos promesas de la página:
  1. No se conecta a nada: ni scripts, ni estilos, ni imágenes de fuera, ni envíos.
  2. Usa la misma lista de muletillas que brigada-humano.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import json
import pathlib
import re
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "herramientas" / "lamina-de-texto.html"
LISTA = RAIZ / "skills" / "brigada-humano" / "scripts" / "muletillas.json"
SINCRONIZA = RAIZ / "herramientas" / "sincroniza_muletillas.py"
BLOQUE = re.compile(r'<script type="application/json" id="muletillas">(.*?)</script>', re.S)


def pagina():
    return PAGINA.read_text(encoding="utf-8")


def sin_bloque_json(html):
    return BLOQUE.sub("", html)


class LaminaSinConexiones(unittest.TestCase):
    def test_no_carga_nada_de_fuera(self):
        html = sin_bloque_json(pagina())
        prohibido = {
            "script externo": r"<script[^>]*\bsrc\s*=",
            "hoja de estilos externa": r"<link[^>]*\bhref\s*=",
            "import de CSS": r"@import",
            "recurso por url()": r"url\(\s*['\"]?https?:",
            "imagen externa": r"<img[^>]*\bsrc\s*=\s*['\"]https?:",
            "marco incrustado": r"<iframe",
        }
        for nombre, patron in prohibido.items():
            with self.subTest(nombre):
                self.assertIsNone(re.search(patron, html, re.I), nombre)

    def test_no_envia_nada(self):
        html = sin_bloque_json(pagina())
        for llamada in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "EventSource", "importScripts"):
            with self.subTest(llamada):
                self.assertNotIn(llamada, html)

    def test_los_enlaces_son_solo_de_navegacion(self):
        # Los únicos http(s) permitidos son enlaces <a href> del pie de página.
        html = sin_bloque_json(pagina())
        sin_enlaces = re.sub(r'<a\s+href="https://[^"]+">', "", html)
        self.assertIsNone(re.search(r"https?://", sin_enlaces), "hay una dirección web fuera de un enlace")


class LaminaMuletillas(unittest.TestCase):
    def test_lista_sincronizada_con_brigada_humano(self):
        m = BLOQUE.search(pagina())
        self.assertIsNotNone(m, "falta el bloque de muletillas en la página")
        self.assertEqual(
            json.loads(m.group(1)),
            json.loads(LISTA.read_text(encoding="utf-8")),
            "la lista de la página no coincide con muletillas.json: ejecuta herramientas/sincroniza_muletillas.py",
        )

    def test_script_de_sincronia_dice_que_coinciden(self):
        r = subprocess.run([sys.executable, str(SINCRONIZA), "--comprobar"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class LaminaTipografia(unittest.TestCase):
    def test_sin_rayas_ni_invisibles_en_la_pagina(self):
        html = sin_bloque_json(pagina())
        malos = {0x2014: "raya", 0x2013: "semirraya", 0x200B: "invisible", 0x200C: "invisible",
                 0x200D: "invisible", 0xFEFF: "BOM", 0x00A0: "espacio duro"}
        for codigo, nombre in malos.items():
            with self.subTest(nombre):
                self.assertNotIn(chr(codigo), html)


if __name__ == "__main__":
    unittest.main()

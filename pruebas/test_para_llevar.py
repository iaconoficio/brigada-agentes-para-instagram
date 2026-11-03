"""
Pruebas de brigada-para-llevar (skills/brigada-para-llevar/scripts/para_llevar.py).

Comprueban que sin el sí de la persona no se hace nada, que los textos van
tal cual se aprobaron, que el paquete sale con sus carpetas, sus medidas y su
.zip, que no pisa nada, que no carga nada de internet, que las imágenes no
llevan la firma y que el motor de dibujo es el de la Lámina. Si hay Chrome o
Chromium (o la variable BRIGADA_CHROME), también dibujan y miden de verdad.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "brigada-para-llevar"
SCRIPT = SKILL / "scripts" / "para_llevar.py"
EJEMPLO = SKILL / "assets" / "pedido-ejemplo.json"
PLANTILLA = SKILL / "assets" / "pagina-para-llevar.html"
MOTOR = SKILL / "assets" / "motor-lamina.js"


def _carga(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


P = _carga("para_llevar_pruebas", SCRIPT)


def ejemplo():
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


def png(ancho, alto, tipo=6, con_pixeles=False):
    """Una PNG hecha con la biblioteca estándar: solo la cabecera, o de verdad y de un color."""
    def trozo(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, tipo, 0, 0, 0)
    pixeles = b""
    if con_pixeles:
        fila = b"\x00" + bytes([200, 60, 40, 255][:{2: 3, 6: 4}[tipo]]) * ancho
        pixeles = trozo(b"IDAT", zlib.compress(fila * alto))
    return b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", ihdr) + pixeles + trozo(b"IEND", b"")


def jpg(ancho, alto):
    """La cabecera de una JPG: basta para leer sus medidas."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, alto, ancho, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def dato(bytes_, tipo):
    import base64
    return f"data:image/{tipo};base64," + base64.b64encode(bytes_).decode()


def datos_de_la_pagina(html):
    m = re.search(r'<script type="application/json" id="pedido">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def dibujo_falso(trabajo, **cambios):
    """Lo que devolvería el navegador si todo cupiera."""
    imagenes = []
    for img in trabajo["imagenes"]:
        ancho, alto = P.MEDIDAS[img["formato"]]
        cuerpo = dato(png(ancho, alto), "png") if img["clase"] == "cartel" else dato(jpg(ancho, alto), "jpeg")
        h = {"ruta": img["ruta"], "ancho": ancho, "alto": alto, "noCabe": False, "partida": False, "datos": cuerpo}
        h.update(cambios.get(img["ruta"], {}))
        imagenes.append(h)
    return {"imagenes": imagenes, "cortados": cambios.get("cortados", []), "fotoMal": False}


class Carpeta(unittest.TestCase):
    """Cada prueba trabaja en una carpeta temporal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def pedido(self, datos, nombre="pedido.json"):
        ruta = self.dir / nombre
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return ruta

    def lleva(self, datos, **kw):
        kw.setdefault("navegador", False)
        return P.para_llevar(self.pedido(datos), **kw)

    def prepara(self, datos):
        avisos = []
        return P.prepara(datos, self.dir, avisos), avisos

    def falla(self, datos, donde=None):
        avisos = []
        with self.assertRaises(P.Pedido):
            P.prepara(datos, self.dir, avisos)
        arreglas = [a for a in avisos if a["estado"] == "ARREGLA"]
        self.assertTrue(arreglas, avisos)
        if donde:
            self.assertTrue(any(a["donde"] == donde for a in arreglas), arreglas)
        return arreglas

    def con_navegador_falso(self, dibujo=None):
        """Cambia el navegador por uno de mentira que devuelve dibujo (o el de todo bien)."""
        viejos = (P.E.busca_navegador, P.dibuja)
        P.E.busca_navegador = lambda: "navegador-de-prueba"

        def dibuja(nav, ruta):
            self.assertTrue(ruta.exists())
            self.paginas_medidas.append(ruta)
            hecho = dibujo if dibujo is not None else dibujo_falso(self.ultimo_trabajo)
            if hecho is None or "error" in hecho or "nombres" in hecho:
                return hecho
            datos = datos_de_la_pagina(ruta.read_text(encoding="utf-8"))
            nombres = [datos["carpeta"] + "/" + a["ruta"] for a in datos["archivos"]]
            nombres += [datos["carpeta"] + "/" + h["ruta"] for h in hecho["imagenes"]]
            return {**hecho, "nombres": nombres}

        self.paginas_medidas = []

        P.dibuja = dibuja
        self.addCleanup(lambda: (setattr(P.E, "busca_navegador", viejos[0]), setattr(P, "dibuja", viejos[1])))


class ElEjemplo(Carpeta):
    def test_el_ejemplo_es_inventado_y_de_oficios(self):
        texto = EJEMPLO.read_text(encoding="utf-8").lower()
        self.assertIn("ejemplo inventado", texto)
        self.assertIn("radiador", texto)

    def test_sin_navegador_deja_solo_la_pagina(self):
        informe = self.lleva(ejemplo())
        self.assertEqual(informe["veredicto"], "REVÍSALO", informe["avisos"])
        self.assertTrue(pathlib.Path(informe["pagina"]).exists())
        self.assertIsNone(informe["zip"])
        self.assertIsNone(informe["carpeta"])
        self.assertTrue(any(a["donde"] == "MEDIDO" and a["estado"] == "OJO" and "no he dibujado ni medido" in
                            a["detalle"] for a in informe["avisos"]))

    def test_la_pagina_lleva_todas_las_piezas(self):
        t, _ = self.prepara(ejemplo())
        rutas = [img["ruta"] for img in t["imagenes"]]
        self.assertEqual(rutas[0], "1-martes-17-reel/portada-del-reel.jpg")
        self.assertEqual(rutas[1:7], [f"1-martes-17-reel/textos-en-pantalla-opcional/{i:02d}.png" for i in range(1, 7)])
        self.assertEqual(rutas[7:17], [f"2-jueves-19-carrusel/{i:02d}.jpg" for i in range(1, 11)])
        self.assertEqual(rutas[17:], ["3-sabado-21-post/post.jpg"])
        archivos = [r for r, _ in P.archivos(t)]
        self.assertEqual(archivos, ["LEEME.txt", "1-martes-17-reel/guion.txt", "1-martes-17-reel/texto-del-post.txt",
                                    "2-jueves-19-carrusel/texto-del-post.txt", "3-sabado-21-post/texto-del-post.txt"])

    def test_el_leeme_dice_que_va_cada_dia(self):
        t, _ = self.prepara(ejemplo())
        leeme = P.leeme(t)
        self.assertIn("Textos aprobados por Marta Olmo el 28 de octubre de 2026.", leeme)
        self.assertIn("MARTES 17 · REEL · 19:00", leeme)
        self.assertIn("Las 10 láminas, de 01 a 10: súbelas en ese orden.", leeme)
        self.assertIn("sin tu sí, no se publica.", leeme)
        self.assertIn("textos-en-pantalla-opcional", leeme)
        self.assertTrue(leeme.rstrip().endswith(P.E.REPO))


class SinElSiNoHayNada(Carpeta):
    def test_sin_aprobado_no_hace_nada(self):
        datos = ejemplo()
        del datos["aprobado"]
        informe = self.lleva(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertTrue(any(a["donde"] == "APROBADO" for a in informe["avisos"]))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["pedido.json"])

    def test_aprobado_tiene_que_decir_quien_y_cuando(self):
        for malo in ("sí", True, {"por": "Marta"}, {"fecha": "2026-10-28"}, {"por": "", "fecha": "2026-10-28"},
                     {"por": "Marta", "fecha": "28/10/2026"}, {"por": "Marta", "fecha": "2026-02-30"}):
            with self.subTest(malo=malo):
                datos = ejemplo()
                datos["aprobado"] = malo
                self.falla(datos, "APROBADO")

    def test_una_fecha_que_aun_no_ha_llegado_avisa(self):
        datos = ejemplo()
        datos["aprobado"]["fecha"] = "2999-01-01"
        _, avisos = self.prepara(datos)
        self.assertTrue(any(a["donde"] == "APROBADO" and a["estado"] == "OJO" for a in avisos))


class LosTextosVanTalCual(Carpeta):
    def test_el_texto_del_post_no_cambia(self):
        datos = ejemplo()
        raro = "  «Esto» va así:  con dos espacios, un emoji 🔧 y **asteriscos**.\r\n\r\n#caldera  "
        datos["piezas"][2]["texto"] = raro
        t, _ = self.prepara(datos)
        texto = dict(P.archivos(t))["3-sabado-21-post/texto-del-post.txt"]
        self.assertEqual(texto, raro.replace("\r\n", "\n").strip() + "\n")

    def test_el_guion_no_cambia(self):
        t, _ = self.prepara(ejemplo())
        guion = dict(P.archivos(t))["1-martes-17-reel/guion.txt"]
        self.assertEqual(guion, ejemplo()["piezas"][0]["guion"] + "\n")

    def test_las_rayas_avisan_pero_no_se_tocan(self):
        datos = ejemplo()
        raya = chr(0x2014)
        datos["piezas"][2]["texto"] = f"Antes {raya} después"
        t, avisos = self.prepara(datos)
        self.assertTrue(any(a["estado"] == "OJO" and "rayas" in a["detalle"] for a in avisos))
        self.assertIn(raya, dict(P.archivos(t))["3-sabado-21-post/texto-del-post.txt"])

    def test_los_invisibles_avisan(self):
        datos = ejemplo()
        datos["piezas"][2]["texto"] = "Hola" + chr(0x200B) + " mundo"
        _, avisos = self.prepara(datos)
        self.assertTrue(any(a["estado"] == "OJO" and "invisibles" in a["detalle"] for a in avisos))

    def test_textos_desde_un_archivo(self):
        (self.dir / "texto.txt").write_text("Del archivo, tal cual.\n", encoding="utf-8")
        datos = ejemplo()
        datos["piezas"][2]["texto"] = {"archivo": "texto.txt"}
        t, _ = self.prepara(datos)
        self.assertEqual(dict(P.archivos(t))["3-sabado-21-post/texto-del-post.txt"], "Del archivo, tal cual.\n")

    def test_texto_demasiado_largo_para_instagram(self):
        datos = ejemplo()
        datos["piezas"][2]["texto"] = "a" * (P.CAPTION_MAX + 1)
        self.falla(datos, "PIEZA 3")

    def test_los_limites_son_los_de_los_otros_agentes(self):
        caption = _carga("revisa_caption_pruebas_llevar", RAIZ / "skills" / "brigada-caption" / "scripts" /
                         "revisa_caption.py")
        carrusel = _carga("revisa_carrusel_pruebas_llevar", RAIZ / "skills" / "brigada-carrusel" / "scripts" /
                          "revisa_carrusel.py")
        self.assertEqual(P.CAPTION_MAX, caption.LIMITE)
        self.assertEqual(P.LAMINAS_MAX, carrusel.LAMINAS_MAX)


class ElPedido(Carpeta):
    def test_faltan_cosas(self):
        for campo in ("titulo", "para", "cuenta", "piezas"):
            with self.subTest(campo):
                datos = ejemplo()
                del datos[campo]
                self.falla(datos)

    def test_cada_formato_pide_lo_suyo(self):
        for n, campo in ((0, "portada"), (0, "guion"), (0, "texto"), (1, "laminas"), (2, "lamina"), (2, "dia")):
            with self.subTest(campo=campo):
                datos = ejemplo()
                del datos["piezas"][n][campo]
                self.falla(datos, f"PIEZA {n + 1}")

    def test_formato_que_no_existe(self):
        datos = ejemplo()
        datos["piezas"][0]["formato"] = "historia"
        self.falla(datos, "PIEZA 1")

    def test_la_hora(self):
        datos = ejemplo()
        datos["piezas"][0]["hora"] = "19.00"
        t, _ = self.prepara(datos)
        self.assertEqual(t["piezas"][0]["hora"], "19:00")
        datos["piezas"][0]["hora"] = "a las siete"
        self.falla(datos, "PIEZA 1")

    def test_laminas_del_carrusel(self):
        for laminas in (["Solo una"], [f"Lámina {i}" for i in range(P.LAMINAS_MAX + 1)], []):
            with self.subTest(n=len(laminas)):
                datos = ejemplo()
                datos["piezas"][1]["laminas"] = laminas
                self.falla(datos, "PIEZA 2")

    def test_laminas_separadas_como_en_la_lamina(self):
        datos = ejemplo()
        datos["piezas"][1]["laminas"] = "Una\n\n---\n\nDos\n---\nTres"
        t, _ = self.prepara(datos)
        self.assertEqual(t["piezas"][1]["laminas"], ["Una", "Dos", "Tres"])

    def test_sin_numerar(self):
        datos = ejemplo()
        datos["piezas"][1]["numerar"] = "no"
        t, _ = self.prepara(datos)
        self.assertFalse(any(img["numerar"] for img in t["imagenes"] if img["clase"] == "lamina"))

    def test_demasiadas_piezas(self):
        datos = ejemplo()
        datos["piezas"] = datos["piezas"] * 3
        self.falla(datos, "PEDIDO")

    def test_demasiados_carteles(self):
        datos = ejemplo()
        datos["piezas"][0]["carteles"] = [f"Cartel {i}" for i in range(P.CARTELES_MAX + 1)]
        self.falla(datos, "PIEZA 1")

    def test_la_cuenta(self):
        t, _ = self.prepara(ejemplo())
        self.assertEqual(t["usuario"], "calefaccion.olmo")
        datos = ejemplo()
        datos["cuenta"] = "@calefacción olmo"
        self.falla(datos, "PEDIDO")

    def test_nombres_de_carpeta_sin_tildes(self):
        t, _ = self.prepara(ejemplo())
        self.assertEqual([p["carpeta"] for p in t["piezas"]],
                         ["1-martes-17-reel", "2-jueves-19-carrusel", "3-sabado-21-post"])

    def test_archivos_solo_de_la_carpeta_del_pedido(self):
        fuera = self.dir.parent / f"fuera-{self.dir.name}.txt"
        fuera.write_text("no", encoding="utf-8")
        self.addCleanup(fuera.unlink)
        for n, campo in ((2, "texto"), (1, "laminas"), (0, "guion")):
            with self.subTest(campo):
                datos = ejemplo()
                datos["piezas"][n][campo] = {"archivo": f"../{fuera.name}"}
                self.falla(datos, f"PIEZA {n + 1}")

    def test_el_calendario(self):
        (self.dir / "semana.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n", encoding="utf-8")
        datos = ejemplo()
        datos["calendario"] = "semana.ics"
        t, _ = self.prepara(datos)
        self.assertIn(("semana.ics", "BEGIN:VCALENDAR\nEND:VCALENDAR\n"), P.archivos(t))
        self.assertIn("semana.ics", P.leeme(t))
        (self.dir / "otro.ics").write_text("hola", encoding="utf-8")
        datos["calendario"] = "otro.ics"
        self.falla(datos, "CALENDARIO")


class LosColores(Carpeta):
    def test_texto_que_no_se_lee_no_se_prepara(self):
        datos = ejemplo()
        datos["marca"] = {"fondo": "#FFFFFF", "texto": "#DDDDDD"}
        informe = self.lleva(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertTrue(any(a["donde"] == "COLORES" and a["estado"] == "ARREGLA" for a in informe["avisos"]))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["pedido.json"])

    def test_el_gris_de_la_cuenta_se_oscurece_hasta_que_se_lee(self):
        for texto, fondo in (("#6E6E6E", "#FFFFFF"), ("#15314B", "#EEF3F6"), ("#B0B0B0", "#000000")):
            with self.subTest(texto=texto, fondo=fondo):
                self.assertLess(P.E.contraste(P.mezcla(texto, fondo, 0.62), fondo), P.CONTRASTE_GRIS)
                color, t = P.gris(texto, fondo)
                self.assertGreaterEqual(P.E.contraste(color, fondo), P.CONTRASTE_GRIS)
                self.assertGreater(t, 0.62)
                self.assertLessEqual(t, 1.0)
        datos = ejemplo()
        datos["marca"] = {"fondo": "#FFFFFF", "texto": "#6E6E6E"}
        t, _ = self.prepara(datos)
        self.assertEqual(t["marca"]["gris"], P.gris("#6E6E6E", "#FFFFFF")[0])
        informe = self.lleva(datos)
        self.assertTrue(any(a["donde"] == "COLORES" and "más oscuro" in a["detalle"] for a in informe["avisos"]))
        pagina = datos_de_la_pagina(pathlib.Path(informe["pagina"]).read_text(encoding="utf-8"))
        self.assertEqual(pagina["marca"]["gris"], t["marca"]["gris"])

    def test_la_insignia_y_las_iniciales_que_se_ven_poco_avisan(self):
        datos = ejemplo()
        datos["marca"] = {"fondo": "#2A9BEF", "texto": "#000000", "verificado": True}
        informe = self.lleva(datos)
        detalles = " ".join(a["detalle"] for a in informe["avisos"] if a["estado"] == "OJO")
        self.assertIn("insignia azul", detalles)

    def test_fondo_de_color_pide_el_color_del_texto(self):
        datos = ejemplo()
        datos["marca"] = {"fondo": "#EEF3F6"}
        self.falla(datos, "MARCA")

    def test_blanco_y_negro_son_los_de_la_lamina(self):
        for fondo in ("blanco", "negro"):
            with self.subTest(fondo):
                datos = ejemplo()
                datos["marca"] = {"fondo": fondo}
                t, _ = self.prepara(datos)
                self.assertEqual(t["marca"]["fondo"], fondo)
                self.assertEqual(t["marca"]["colorFondo"], P.TEMAS[fondo][0])

    def test_colores_y_letra_mal_escritos(self):
        for marca in ({"fondo": "azul"}, {"fondo": "#EEF3F6", "texto": "marino"}, {"letra": "comic"}, "rojo"):
            with self.subTest(marca=marca):
                datos = ejemplo()
                datos["marca"] = marca
                self.falla(datos, "MARCA")

    def test_la_mezcla_es_la_de_la_lamina(self):
        # mezclar("#000000", "#FFFFFF", 0.62) en la Lámina: rgb(97,97,97). Y redondea 0,5 hacia arriba, como JS.
        self.assertEqual(P.mezcla("#000000", "#FFFFFF", 0.62), "#616161")
        self.assertEqual(P.mezcla("#000000", "#010101", 0.5), "#010101")


class LaFoto(Carpeta):
    def test_foto_buena(self):
        (self.dir / "foto.png").write_bytes(png(4, 4, 2, con_pixeles=True))
        datos = ejemplo()
        datos["marca"]["foto"] = "foto.png"
        t, _ = self.prepara(datos)
        self.assertTrue(t["marca"]["foto"].startswith("data:image/png;base64,"))

    def test_lo_que_no_es_una_foto(self):
        (self.dir / "foto.png").write_text("no soy una foto", encoding="utf-8")
        datos = ejemplo()
        datos["marca"]["foto"] = "foto.png"
        self.falla(datos, "FOTO")

    def test_foto_que_pesa_demasiado(self):
        (self.dir / "grande.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * (P.FOTO_MAX + 1))
        datos = ejemplo()
        datos["marca"]["foto"] = "grande.jpg"
        self.falla(datos, "FOTO")

    def test_foto_fuera_de_la_carpeta(self):
        datos = ejemplo()
        datos["marca"]["foto"] = "../../etc/passwd"
        self.falla(datos, "FOTO")

    def test_sin_foto_van_las_iniciales(self):
        informe = self.lleva(ejemplo())
        self.assertTrue(any(a["donde"] == "FOTO" and "(CO)" in a["detalle"] for a in informe["avisos"]))


class ElPaquete(Carpeta):
    """El trabajo entero, con un navegador de mentira que dibuja bien."""

    def lleva_con_dibujo(self, datos, dibujo=None, **kw):
        self.ultimo_trabajo, _ = self.prepara(datos)
        self.con_navegador_falso(dibujo)
        return P.para_llevar(self.pedido(datos), navegador=True, **kw)

    def test_sale_la_carpeta_el_zip_y_la_pagina(self):
        informe = self.lleva_con_dibujo(ejemplo(), salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])
        carpeta = pathlib.Path(informe["carpeta"])
        self.assertEqual(carpeta, self.dir / "semana-v1")
        self.assertTrue((self.dir / "semana-v1.zip").exists())
        self.assertTrue((self.dir / "semana-v1.html").exists())
        en_disco = sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*") if p.is_file())
        with zipfile.ZipFile(informe["zip"]) as z:
            en_zip = sorted(n.split("/", 1)[1] for n in z.namelist())
            self.assertIsNone(z.testzip())
            self.assertTrue(all(n.startswith("semana-v1/") for n in z.namelist()))
            self.assertEqual(z.read("semana-v1/3-sabado-21-post/texto-del-post.txt").decode("utf-8"),
                             ejemplo()["piezas"][2]["texto"] + "\n")
        self.assertEqual(en_disco, en_zip)
        self.assertEqual(len(en_disco), 18 + 5)

    def test_no_pisa_nada(self):
        (self.dir / "semana-v1").mkdir()
        (self.dir / "semana-v1" / "viejo.txt").write_text("de otra vez", encoding="utf-8")
        informe = self.lleva_con_dibujo(ejemplo(), salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertTrue(any(a["donde"] == "SALIDA" for a in informe["avisos"]))
        self.assertEqual((self.dir / "semana-v1" / "viejo.txt").read_text(encoding="utf-8"), "de otra vez")
        self.assertFalse((self.dir / "semana-v1.zip").exists())

    def test_un_zip_viejo_tampoco_se_pisa(self):
        (self.dir / "semana-v1.zip").write_bytes(b"viejo")
        informe = self.lleva_con_dibujo(ejemplo(), salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertEqual((self.dir / "semana-v1.zip").read_bytes(), b"viejo")

    def test_si_algo_no_cabe_no_entrega_nada(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t, **{"2-jueves-19-carrusel/04.jpg": {"noCabe": True},
                                    "3-sabado-21-post/post.jpg": {"partida": True}})
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        detalles = " ".join(a["detalle"] for a in informe["avisos"] if a["estado"] == "ARREGLA")
        self.assertIn("Lámina 4 de 10", detalles)
        self.assertIn("se partiría por letras", detalles)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["pedido.json"])

    def test_una_imagen_con_otra_medida_no_se_entrega(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t, **{"3-sabado-21-post/post.jpg": {"datos": dato(jpg(1080, 1080), "jpeg")},
                                    "1-martes-17-reel/textos-en-pantalla-opcional/01.png":
                                        {"datos": dato(png(1080, 1920, 2), "png")}})
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        malas = [a["detalle"] for a in informe["avisos"] if a["estado"] == "ARREGLA"]
        self.assertEqual(len(malas), 2, malas)
        self.assertFalse((self.dir / "semana-v1").exists())

    def test_si_falta_una_imagen_no_se_entrega(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t)
        dibujo["imagenes"].pop()
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_si_el_navegador_falla(self):
        informe = self.lleva_con_dibujo(ejemplo(), {"error": "algo"}, salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["pedido.json"])

    def test_el_nombre_cortado_avisa(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t, cortados=["Calefacción Olmo"])
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "REVÍSALO")
        self.assertTrue(any(a["donde"] == "CABECERA" for a in informe["avisos"]))

    def test_dibuja_con_el_navegador_de_brigada_emplatado(self):
        llamadas = []
        viejo = P.E._lanza
        P.E._lanza = lambda nav, args, tiempo=60: llamadas.append(args) or (
            '<body data-listo="si"><pre id="salida">{&quot;imagenes&quot;: []}</pre></body>')
        self.addCleanup(setattr, P.E, "_lanza", viejo)
        ruta = self.dir / "p.html"
        ruta.write_text("<html></html>", encoding="utf-8")
        self.assertEqual(P.dibuja("chrome", ruta), {"imagenes": []})
        self.assertIn("--dump-dom", llamadas[0])
        self.assertTrue(llamadas[0][-1].endswith("p.html#auto"))


class LoQueEncontroLaRevision(Carpeta):
    """Lo que encontró la revisión independiente: que no vuelva."""

    def lleva_con_dibujo(self, datos, dibujo=None, **kw):
        self.ultimo_trabajo, _ = self.prepara(datos)
        self.con_navegador_falso(dibujo)
        return P.para_llevar(self.pedido(datos), navegador=True, **kw)

    def test_la_pagina_entregada_lleva_las_imagenes_del_zip(self):
        informe = self.lleva_con_dibujo(ejemplo(), salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])
        pagina = datos_de_la_pagina(pathlib.Path(informe["pagina"]).read_text(encoding="utf-8"))
        self.assertIsNone(pagina["marca"]["foto"])
        import base64
        with zipfile.ZipFile(informe["zip"]) as z:
            for h in pagina["hechas"]:
                with self.subTest(h["ruta"]):
                    self.assertEqual(base64.b64decode(h["datos"].split(",", 1)[1]), z.read("semana-v1/" + h["ruta"]))
        self.assertEqual([h["ruta"] for h in pagina["hechas"]], [img["ruta"] for img in pagina["imagenes"]])

    def test_se_mide_al_lado_de_la_salida_y_no_queda_nada_a_medias(self):
        informe = self.lleva_con_dibujo(ejemplo(), salida=self.dir / "semana-v1")
        self.assertEqual(self.paginas_medidas[0].parent.parent.resolve(), self.dir.resolve())
        self.assertFalse(self.paginas_medidas[0].parent.name.startswith("."))
        self.assertEqual(sorted(x.name for x in self.dir.iterdir()),
                         ["pedido.json", "semana-v1", "semana-v1.html", "semana-v1.zip"])
        self.assertEqual(informe["veredicto"], "LISTO")

    def test_si_el_navegador_no_arranca_queda_la_pagina(self):
        self.ultimo_trabajo, _ = self.prepara(ejemplo())
        viejos = (P.E.busca_navegador, P.dibuja)
        P.E.busca_navegador = lambda: "navegador-de-prueba"
        P.dibuja = lambda nav, ruta: None
        self.addCleanup(lambda: (setattr(P.E, "busca_navegador", viejos[0]), setattr(P, "dibuja", viejos[1])))
        informe = P.para_llevar(self.pedido(ejemplo()), salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "REVÍSALO")
        self.assertEqual(sorted(x.name for x in self.dir.iterdir()), ["pedido.json", "semana-v1.html"])

    def test_la_pagina_entregada_lleva_los_avisos(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t, cortados=["Calefacción Olmo"])
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        pagina = datos_de_la_pagina(pathlib.Path(informe["pagina"]).read_text(encoding="utf-8"))
        self.assertEqual(len(pagina["notas"]), 1)
        self.assertIn("cortados", pagina["notas"][0])

    def test_si_el_zip_de_la_pagina_no_coincide_no_se_entrega(self):
        t, _ = self.prepara(ejemplo())
        dibujo = dibujo_falso(t)
        dibujo["nombres"] = ["otra-cosa"]
        informe = self.lleva_con_dibujo(ejemplo(), dibujo, salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertEqual(sorted(x.name for x in self.dir.iterdir()), ["pedido.json"])

    def test_el_calendario_va_tal_cual_byte_a_byte(self):
        ics = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nSUMMARY:Reel de la semana con un texto largo que se\r\n  dobla\r\nEND:VCALENDAR\r\n"
        (self.dir / "semana.ics").write_bytes(ics)
        datos = ejemplo()
        datos["calendario"] = "semana.ics"
        informe = self.lleva_con_dibujo(datos, salida=self.dir / "semana-v1")
        self.assertEqual((self.dir / "semana-v1" / "semana.ics").read_bytes(), ics)
        with zipfile.ZipFile(informe["zip"]) as z:
            self.assertEqual(z.read("semana-v1/semana.ics"), ics)

    def test_un_formato_que_no_es_texto_no_rompe_nada(self):
        for raro in (["reel"], {"a": 1}, 3, None, True):
            with self.subTest(formato=raro):
                datos = ejemplo()
                datos["piezas"][0]["formato"] = raro
                self.falla(datos, "PIEZA 1")

    def test_las_iniciales_con_un_emoji_delante(self):
        self.assertEqual(P.iniciales(chr(0x1F527) + " Fontanería Ruiz"), "FR")
        self.assertEqual(P.iniciales("Calefacción Olmo"), "CO")
        self.assertEqual(P.iniciales("Olmo"), "O")
        self.assertEqual(P.iniciales(""), "?")
        self.assertIn('"[\\\\p{L}\\\\p{N}]"', PLANTILLA.read_text(encoding="utf-8"))

    def test_salidas_raras(self):
        for salida in (".", ".."):
            with self.subTest(salida=salida):
                informe = self.lleva(ejemplo(), salida=salida)
                self.assertTrue(any(a["donde"] == "SALIDA" for a in informe["avisos"]), informe["avisos"])
        (self.dir / "vacia").mkdir()
        informe = self.lleva(ejemplo(), salida=self.dir / "vacia")
        self.assertTrue(any(a["donde"] == "SALIDA" for a in informe["avisos"]))
        if hasattr(os, "symlink"):
            try:
                os.symlink(self.dir / "no-existe.zip", self.dir / "roto.zip")
            except OSError:
                return
            informe = self.lleva(ejemplo(), salida=self.dir / "roto")
            self.assertTrue(any(a["donde"] == "SALIDA" for a in informe["avisos"]))
            self.assertFalse((self.dir / "no-existe.zip").exists())

    def test_la_cuenta_solo_con_letras_de_instagram(self):
        datos = ejemplo()
        datos["cuenta"] = "@calefacción"
        self.falla(datos, "PEDIDO")

    def test_los_mensajes_hablan_del_pedido(self):
        datos = ejemplo()
        datos["piezas"][1]["laminas"] = {"archivo": "../fuera.txt"}
        arreglas = self.falla(datos, "PIEZA 2")
        self.assertTrue(all("comanda" not in a["detalle"] for a in arreglas), arreglas)

    def test_lo_que_usa_de_brigada_emplatado_existe(self):
        for nombre in ("busca_navegador", "_lanza", "_dentro", "_laminas", "Lector", "lee_comanda", "contraste",
                       "hex6", "coma", "fuentes", "RAYAS_RE", "INVISIBLES", "COLOR_RE", "CONTRASTE_TEXTO",
                       "HECHO_CON", "FIRMA", "REPO", "ENLACES"):
            with self.subTest(nombre):
                self.assertTrue(hasattr(P.E, nombre))


class LasMedidas(unittest.TestCase):
    def test_lee_las_medidas_de_una_jpg_y_una_png(self):
        self.assertEqual(P.medidas(jpg(1080, 1350)), ("jpg", 1080, 1350, False))
        self.assertEqual(P.medidas(png(1080, 1920)), ("png", 1080, 1920, True))
        self.assertEqual(P.medidas(png(10, 10, 2)), ("png", 10, 10, False))
        self.assertIsNone(P.medidas(b"no es una imagen"))


class LaFirma(Carpeta):
    def test_las_imagenes_no_llevan_la_firma(self):
        plantilla = PLANTILLA.read_text(encoding="utf-8")
        guion_de_la_pagina = plantilla.split("<script>", 1)[1]
        codigo_del_motor = "\n".join(l for l in MOTOR.read_text(encoding="utf-8").splitlines()
                                     if not l.lstrip().startswith("//"))
        for codigo in (guion_de_la_pagina, codigo_del_motor):
            for marca in ("Brigada", "IA con Oficio", "Toni Mont", "github.com"):
                self.assertNotIn(marca, codigo)

    def test_la_firma_va_en_el_leeme_y_en_la_pagina(self):
        informe = self.lleva(ejemplo())
        pagina = pathlib.Path(informe["pagina"]).read_text(encoding="utf-8")
        self.assertIn(P.E.HECHO_CON, pagina)
        self.assertIn(P.E.FIRMA, pagina)
        self.assertIn(P.E.REPO, pagina)
        t, _ = self.prepara(ejemplo())
        self.assertIn(f"{P.E.HECHO_CON} · {P.E.FIRMA}", P.leeme(t))


class SinInternet(Carpeta):
    def pagina(self):
        informe = self.lleva(ejemplo())
        texto = pathlib.Path(informe["pagina"]).read_text(encoding="utf-8")
        return re.sub(r'<script type="application/json" id="pedido">.*?</script>', "", texto, flags=re.S)

    def test_no_carga_nada_de_fuera(self):
        html = self.pagina()
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
        html = self.pagina()
        for llamada in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "EventSource", "importScripts"):
            with self.subTest(llamada):
                self.assertNotIn(llamada, html)

    def test_los_enlaces_son_solo_de_navegacion(self):
        sin_enlaces = re.sub(r'<a href="https://[^"]+">', "", self.pagina())
        self.assertIsNone(re.search(r"https?://", sin_enlaces), "hay una dirección web fuera de un enlace")

    def test_el_script_no_usa_la_red(self):
        codigo = SCRIPT.read_text(encoding="utf-8")
        for modulo in ("urllib", "http.client", "socket", "requests"):
            with self.subTest(modulo):
                self.assertNotRegex(codigo, rf"^\s*(import|from)\s+{re.escape(modulo)}", re.M)

    def test_lo_que_escribe_la_persona_no_rompe_la_pagina(self):
        datos = ejemplo()
        datos["piezas"][2]["texto"] = "</script><script>alert(1)</script> @@MOTOR@@ @@PEDIDO@@"
        datos["titulo"] = "<b>Semana</b>"
        informe = self.lleva(datos)
        html = pathlib.Path(informe["pagina"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn("<b>Semana</b>", html)
        self.assertEqual(html.count("var FORMATOS = {"), 1)
        m = re.search(r'<script type="application/json" id="pedido">(.*?)</script>', html, re.S)
        datos_pagina = json.loads(m.group(1))
        self.assertIn("@@PEDIDO@@", datos_pagina["archivos"][-1]["texto"])

    def test_sin_rayas_ni_invisibles_en_lo_que_se_escribe_a_mano(self):
        for ruta in (PLANTILLA, MOTOR, SKILL / "SKILL.md", SKILL / "references" / "pedido.md", EJEMPLO):
            texto = ruta.read_text(encoding="utf-8")
            for codigo in (0x2014, 0x2013, 0x200B, 0x00A0, 0xFEFF):
                with self.subTest(archivo=ruta.name, caracter=hex(codigo)):
                    self.assertNotIn(chr(codigo), texto)


class ElMotorEsElDeLaLamina(unittest.TestCase):
    def test_la_copia_coincide_con_la_lamina(self):
        r = subprocess.run([sys.executable, str(RAIZ / "herramientas" / "sincroniza_motor.py"), "--comprobar"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_el_motor_trae_lo_que_usa_la_pagina(self):
        motor = MOTOR.read_text(encoding="utf-8")
        for nombre in ("function dibujar(", "function partirLineas(", "function altoTexto(", "function temaActual(",
                       "function recortar(", "function crearZip(", "function limpiarParaDibujar(", "var FORMATOS",
                       "var LETRAS"):
            with self.subTest(nombre):
                self.assertIn(nombre, motor)

    def test_las_medidas_son_las_de_la_lamina(self):
        motor = MOTOR.read_text(encoding="utf-8")
        self.assertIn("feed:     { W: 1080, H: 1350", motor)
        self.assertIn("story:    { W: 1080, H: 1920", motor)
        self.assertEqual(P.MEDIDAS, {"feed": (1080, 1350), "story": (1080, 1920)})

    def test_los_temas_fijos_son_los_de_la_lamina(self):
        motor = MOTOR.read_text(encoding="utf-8")
        for tema, (fondo, texto, sub) in P.TEMAS.items():
            with self.subTest(tema):
                self.assertRegex(motor, rf'{tema}:\s*{{ fondo: "{fondo}", texto: "{texto}", sub: "{sub}"')


class LaLineaDeOrdenes(Carpeta):
    def corre(self, *args, script=SCRIPT):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                              cwd=self.dir, env={**os.environ, "BRIGADA_CHROME": "/no/existe"})

    def test_archivo_que_no_existe(self):
        r = self.corre("no-existe.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no puedo leer «no-existe.json»", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_json_roto(self):
        (self.dir / "roto.json").write_text("{\"titulo\": ", encoding="utf-8")
        r = self.corre("roto.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("el JSON no está bien", r.stderr)

    def test_arregla_sale_con_1(self):
        datos = ejemplo()
        del datos["aprobado"]
        self.pedido(datos, "malo.json")
        r = self.corre("malo.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ARREGLA", r.stdout)

    def test_sin_navegador_deja_la_pagina_y_sale_con_0(self):
        self.pedido(ejemplo(), "semana.json")
        r = self.corre("semana.json", "--salida", "semana-v1", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        informe = json.loads(r.stdout)
        self.assertIsNone(informe["zip"])
        self.assertTrue((self.dir / "semana-v1.html").exists())

    def test_en_windows_con_la_salida_a_un_archivo_no_se_rompe(self):
        datos = ejemplo()
        datos["para"] = chr(0x1F527) + " Calefacción Olmo"
        self.pedido(datos, "semana.json")
        r = subprocess.run([sys.executable, str(SCRIPT), "semana.json", "--salida", "semana-v1"], capture_output=True,
                           cwd=self.dir, env={**os.environ, "BRIGADA_CHROME": "/no/existe", "PYTHONIOENCODING": "cp1252"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(b"Traceback", r.stderr)

    def test_sin_brigada_emplatado_lo_dice_claro(self):
        sola = self.dir / "skills" / "brigada-para-llevar"
        shutil.copytree(SKILL, sola)
        self.pedido(ejemplo(), "semana.json")
        r = self.corre("semana.json", script=sola / "scripts" / "para_llevar.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("necesita a brigada-emplatado", r.stderr)
        self.assertIn("brigada-emplatado.zip", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


def _navegador():
    nav = P.E.busca_navegador() if P.E else None
    return nav


@unittest.skipUnless(_navegador(), "no hay Chrome, Chromium ni Edge (o BRIGADA_CHROME) en este ordenador")
class ConNavegador(Carpeta):
    def test_dibuja_mide_y_empaqueta_de_verdad(self):
        (self.dir / "foto.png").write_bytes(png(40, 40, 2, con_pixeles=True))
        datos = ejemplo()
        datos["marca"]["foto"] = "foto.png"
        informe = P.para_llevar(self.pedido(datos), salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])
        carpeta = pathlib.Path(informe["carpeta"])
        t, _ = self.prepara(datos)
        for img in t["imagenes"]:
            with self.subTest(img["ruta"]):
                medida = P.medidas((carpeta / img["ruta"]).read_bytes())
                ancho, alto = P.MEDIDAS[img["formato"]]
                tipo = "png" if img["clase"] == "cartel" else "jpg"
                self.assertEqual(medida[:3], (tipo, ancho, alto))
                if tipo == "png":
                    self.assertTrue(medida[3], "el texto en pantalla tiene que tener fondo transparente")
        with zipfile.ZipFile(informe["zip"]) as z:
            self.assertEqual(len(z.namelist()), len(t["imagenes"]) + len(P.archivos(t)))

    def test_las_palabras_largas_caben_con_la_letra_mas_pequena(self):
        datos = ejemplo()
        datos["piezas"][0]["carteles"][0] = "Electroencefalografista"
        datos["piezas"][0]["portada"] = "#mantenimientodecalderas"
        datos["piezas"][1]["laminas"][0] = "Todo en calefaccionolmo.es/purgar-radiadores"
        informe = P.para_llevar(self.pedido(datos), salida=self.dir / "semana-v1")
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])

    def test_el_nombre_cortado_y_la_foto_rota_avisan(self):
        (self.dir / "rota.png").write_bytes(png(10, 10)[:30] + b"basura")
        datos = ejemplo()
        datos["para"] = "Calefacción, Fontanería y Climatización Olmo e Hijos"
        datos["marca"]["foto"] = "rota.png"
        informe = P.para_llevar(self.pedido(datos), salida=self.dir / "semana-v1")
        donde = {a["donde"] for a in informe["avisos"] if a["estado"] == "OJO"}
        self.assertIn("CABECERA", donde)
        self.assertIn("FOTO", donde)
        pagina = datos_de_la_pagina(pathlib.Path(informe["pagina"]).read_text(encoding="utf-8"))
        self.assertEqual(len(pagina["notas"]), 2)

    def test_los_textos_en_pantalla_son_transparentes_de_verdad(self):
        informe = P.para_llevar(self.pedido(ejemplo()), salida=self.dir / "semana-v1")
        datos = (pathlib.Path(informe["carpeta"]) / "1-martes-17-reel" / "textos-en-pantalla-opcional" /
                 "01.png").read_bytes()
        i, idat = 8, b""
        while i < len(datos):
            largo, tipo = struct.unpack(">I4s", datos[i:i + 8])
            if tipo == b"IDAT":
                idat += datos[i + 8:i + 8 + largo]
            i += 12 + largo
        pixeles = zlib.decompress(idat)
        self.assertEqual(pixeles[4], 0, "la esquina de arriba a la izquierda tendría que ser transparente")

    def test_la_pagina_marca_lo_que_no_cabe_y_no_deja_descargar(self):
        datos = ejemplo()
        datos["piezas"][1]["laminas"][3] = " ".join(["purgador"] * 260)
        informe = P.para_llevar(self.pedido(datos), navegador=False, salida=self.dir / "mala")
        salida = P.E._lanza(_navegador(), ["--virtual-time-budget=10000", "--dump-dom",
                                          pathlib.Path(informe["pagina"]).resolve().as_uri()])
        self.assertIsNotNone(re.search(r'<figure class="img malo" id="img-10">', salida), "no marca la lámina 4")
        self.assertIsNotNone(re.search(r'<button class="bajar" id="bajar" type="button" disabled="">', salida),
                             "deja descargar")

    def test_la_pagina_entregada_deja_descargar(self):
        informe = P.para_llevar(self.pedido(ejemplo()), salida=self.dir / "semana-v1")
        salida = P.E._lanza(_navegador(), ["--virtual-time-budget=10000", "--dump-dom",
                                          pathlib.Path(informe["pagina"]).resolve().as_uri()])
        self.assertIn('<button class="bajar" id="bajar" type="button">Descargar todo (.zip)</button>', salida)
        self.assertIsNone(re.search(r'class="img[^"]*malo', salida), "hay una imagen marcada en rojo")

    def test_lo_que_no_cabe_se_ve_de_verdad(self):
        datos = ejemplo()
        datos["piezas"][1]["laminas"][3] = " ".join(["purgador"] * 260)
        datos["piezas"][2]["lamina"] = "Supercalifragilisticoespialidosoextraordinariamenteinterminable"
        informe = P.para_llevar(self.pedido(datos), salida=self.dir / "semana-v1")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        detalles = " ".join(a["detalle"] for a in informe["avisos"] if a["estado"] == "ARREGLA")
        self.assertIn("Lámina 4 de 10", detalles)
        self.assertIn("La imagen del post", detalles)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["pedido.json"])


if __name__ == "__main__":
    unittest.main()

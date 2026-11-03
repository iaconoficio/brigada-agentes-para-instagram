"""
Pruebas de brigada-emplatado (skills/brigada-emplatado/scripts/emplata.py).

Comprueban que el documento sale bien, que la firma va en todas las páginas
y no se puede quitar, que no carga nada de internet, que los colores se leen
y que los errores se dicen claros. Si hay Chrome o Chromium (o la variable
BRIGADA_CHROME), también miden de verdad y hacen el PDF.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "brigada-emplatado"
SCRIPT = SKILL / "scripts" / "emplata.py"
EJEMPLO = SKILL / "assets" / "comanda-ejemplo.json"


def _carga(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


E = _carga("emplata_pruebas", SCRIPT)


def ejemplo():
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


class Carpeta(unittest.TestCase):
    """Cada prueba trabaja en una carpeta temporal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def comanda(self, datos, nombre="comanda.json"):
        ruta = self.dir / nombre
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return ruta

    def emplata(self, datos, **kw):
        kw.setdefault("navegador", False)
        return E.emplata(self.comanda(datos), **kw)


class ElEjemplo(Carpeta):
    def test_el_ejemplo_sale_listo(self):
        informe = self.emplata(ejemplo())
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])
        self.assertTrue(pathlib.Path(informe["html"]).exists())
        self.assertTrue(pathlib.Path(informe["copiar"]).exists())
        self.assertTrue(informe["copiar"].endswith("comanda-para-copiar.txt"))

    def test_el_ejemplo_es_inventado_y_de_oficios(self):
        texto = EJEMPLO.read_text(encoding="utf-8").lower()
        self.assertIn("ejemplo inventado", texto)
        self.assertIn("radiador", texto)

    def test_las_cifras_del_ejemplo_salen_del_cronometro(self):
        # Lo que dice tiempos.py de brigada-reel con el guion del ejemplo: segundos, planos y carteles.
        guion = next(p for p in ejemplo()["paginas"] if p["tipo"] == "guion")
        lineas = []
        for plano in guion["planos"]:
            lineas += [f"[{plano['cartel']}]", plano["dices"]]
        r = subprocess.run([sys.executable, str(RAIZ / "skills" / "brigada-reel" / "scripts" / "tiempos.py"), "-"],
                           input="\n".join(lineas), capture_output=True, text=True)
        m = re.search(r"TOTAL\s+([\d.]+)\s*s", r.stdout)
        self.assertIsNotNone(m, r.stdout + r.stderr)
        planos = re.search(r"(\d+) planos", r.stdout)
        cifras = next(p for p in ejemplo()["paginas"] if p["tipo"] == "cifras")["cifras"]
        self.assertEqual(round(float(m.group(1))), int(cifras[0]["numero"]))
        self.assertEqual(int(planos.group(1)), int(cifras[1]["numero"]))
        self.assertEqual(len([p for p in guion["planos"] if p.get("cartel")]), int(cifras[2]["numero"]))


class LaFirma(Carpeta):
    def setUp(self):
        super().setUp()
        informe = self.emplata(ejemplo())
        self.html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.copiar = pathlib.Path(informe["copiar"]).read_text(encoding="utf-8")
        self.total = informe["paginas"]

    def test_la_firma_va_en_todas_las_paginas(self):
        paginas = re.findall(r'<section class="p[^"]*".*?</section>', self.html, re.S)
        self.assertEqual(len(paginas), self.total)
        for i, pagina in enumerate(paginas, 1):
            with self.subTest(pagina=i):
                self.assertIn("Hecho con La Brigada · Toni Mont · IA con Oficio", pagina)
                self.assertIn(f'href="{E.REPO}"', pagina)
                self.assertIn(f"{i} / {self.total}", pagina)

    def test_acaba_con_la_contraportada(self):
        ultima = re.findall(r'<section class="p[^"]*".*?</section>', self.html, re.S)[-1]
        self.assertIn('data-tipo="contraportada"', ultima)
        for _, url, _ in E.ENLACES:
            self.assertIn(f'href="{url}"', ultima)
        self.assertIn("chat.whatsapp.com/F4LVhDev0ahGSJixjCsLc9", ultima)
        self.assertIn("Toni Mont", ultima)

    def test_no_hay_opcion_para_quitarla(self):
        ayuda = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True).stdout
        opciones = set(re.findall(r"--[a-z-]+", ayuda))
        self.assertEqual(opciones, {"--help", "--salida", "--pdf", "--sin-navegador", "--json"})

    def test_no_se_cuela_por_la_comanda(self):
        # Ni con un tipo «contraportada» ni con campos raros se quita o se cambia.
        datos = ejemplo()
        datos["sin_firma"] = True
        datos["firma"] = "otra"
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertEqual(html.count('class="firma"'), informe["paginas"])
        datos = ejemplo()
        datos["paginas"].append({"tipo": "contraportada"})
        informe = self.emplata(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_la_firma_va_tambien_en_el_archivo_para_copiar(self):
        self.assertIn("Hecho con La Brigada · Toni Mont · IA con Oficio", self.copiar)
        self.assertIn(E.REPO, self.copiar)

    def test_en_el_titulo_y_en_los_datos_del_documento(self):
        self.assertRegex(self.html, r"<title>[^<]*Hecho con La Brigada</title>")
        self.assertIn('name="generator" content="La Brigada', self.html)


class SinInternet(Carpeta):
    def test_no_carga_nada_de_fuera(self):
        informe = self.emplata(ejemplo())
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertNotRegex(html, r'src\s*=\s*["\']?(?!data:)', "algo se carga desde fuera")
        self.assertNotRegex(html, r"url\((?!data:)", "algo se carga desde fuera")
        self.assertNotIn("@import", html)
        self.assertNotIn("<link", html)
        self.assertGreaterEqual(html.count("data:font/woff2;base64,"), 5)

    def test_el_script_no_usa_la_red(self):
        codigo = SCRIPT.read_text(encoding="utf-8")
        for modulo in ("urllib", "http.client", "socket", "requests"):
            with self.subTest(modulo):
                self.assertNotRegex(codigo, rf"^\s*(import|from)\s+{re.escape(modulo)}", re.M)

    def test_las_letras_tienen_su_licencia(self):
        for nombre in ("Fraunces", "SpaceMono", "ArchivoBlack", "GreatVibes"):
            with self.subTest(nombre):
                licencia = (SKILL / "assets" / "fuentes" / f"OFL-{nombre}.txt").read_text(encoding="utf-8")
                self.assertIn("SIL Open Font License", licencia)


class LosColores(Carpeta):
    def test_contraste_conocido(self):
        self.assertAlmostEqual(E.contraste("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(E.contraste("#FFFFFF", "#FFFFFF"), 1.0, places=2)
        self.assertEqual(E.hex6("#abc"), "#AABBCC")

    def test_sin_marca_van_los_de_la_brigada(self):
        datos = ejemplo()
        del datos["marca"]
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertIn("--fondo:#F5ECD6", html)
        self.assertTrue(any(a["donde"] == "COLORES" and a["estado"] == "NOTA" for a in informe["avisos"]))

    def test_texto_que_no_se_lee_no_se_emplata(self):
        datos = ejemplo()
        datos["marca"] = {"fondo": "#FFFFFF", "texto": "#DDDDDD"}
        informe = self.emplata(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertIsNone(informe["html"])
        self.assertEqual(list(self.dir.glob("*.html")), [])

    def test_acento_justo_avisa(self):
        datos = ejemplo()
        datos["marca"]["acento"] = "#9FB8C8"
        informe = self.emplata(datos)
        self.assertEqual(informe["veredicto"], "REVÍSALO")

    def test_color_mal_escrito(self):
        datos = ejemplo()
        datos["marca"]["fondo"] = "azul"
        informe = self.emplata(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertTrue(any("#1C2541" in a["detalle"] for a in informe["avisos"]))


class LaComanda(Carpeta):
    def test_faltan_cosas(self):
        informe = self.emplata({"paginas": [{"tipo": "idea"}, {"tipo": "invento"}]})
        detalles = " ".join(a["detalle"] for a in informe["avisos"])
        self.assertIn("«titulo»", detalles)
        self.assertIn("«para»", detalles)
        self.assertIn("«invento» no existe", detalles)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_tabla_con_filas_cojas(self):
        datos = {"titulo": "T", "para": "P", "paginas": [
            {"tipo": "tabla", "columnas": ["A", "B"], "filas": [["1", "2"], ["3"]]}]}
        informe = self.emplata(datos)
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_escapa_lo_que_parece_codigo(self):
        datos = {"titulo": "T", "para": "P", "paginas": [
            {"tipo": "idea", "titulo": "<script>alert(1)</script>", "texto": "a **negrita** & más"}]}
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<b>negrita</b>", html)

    def test_rayas_largas_avisan(self):
        datos = {"titulo": "T", "para": "P", "paginas": [{"tipo": "idea", "titulo": "Una idea — larga"}]}
        informe = self.emplata(datos)
        self.assertEqual(informe["veredicto"], "REVÍSALO")
        self.assertTrue(any("rayas" in a["detalle"] for a in informe["avisos"]))

    def test_mucho_texto_avisa(self):
        datos = {"titulo": "T", "para": "P", "paginas": [{"tipo": "idea", "titulo": "Idea", "texto": "palabra " * 80}]}
        informe = self.emplata(datos)
        self.assertEqual(informe["veredicto"], "REVÍSALO")

    def test_caption_largo_es_una_nota(self):
        datos = {"titulo": "T", "para": "P", "paginas": [{"tipo": "texto", "texto": "Texto largo. " * 80}]}
        informe = self.emplata(datos)
        self.assertEqual(informe["veredicto"], "LISTO")
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertIn("… más", html)
        copiar = pathlib.Path(informe["copiar"]).read_text(encoding="utf-8")
        self.assertIn(("Texto largo. " * 80).strip(), copiar)

    def test_las_laminas_se_parten_como_en_la_lamina(self):
        carrusel = _carga("carrusel_pruebas", RAIZ / "skills" / "brigada-carrusel" / "scripts" / "revisa_carrusel.py")
        self.assertEqual(E.SEPARADOR_RE.pattern, carrusel.SEPARADOR_RE.pattern)
        texto = "Uno\n---\nDos\n\n----\n\nTres \n---"
        self.assertEqual(E.separa_laminas(texto), carrusel.separa(texto))

    def test_laminas_desde_un_archivo(self):
        (self.dir / "carrusel.txt").write_text("Uno\n---\nDos\n---\nTres", encoding="utf-8")
        datos = {"titulo": "T", "para": "P", "paginas": [{"tipo": "laminas", "laminas": {"archivo": "carrusel.txt"}}]}
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertEqual(html.count('class="mini medir"'), 3)

    def test_parte_las_listas_largas_a_partes_iguales(self):
        planos = [{"dices": f"Frase {i}", "cartel": f"C{i}"} for i in range(1, 8)]
        datos = {"titulo": "T", "para": "P", "paginas": [{"tipo": "guion", "antetitulo": "Reel", "planos": planos}]}
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        guiones = re.findall(r'<section class="p[^"]*" data-tipo="guion".*?</section>', html, re.S)
        self.assertEqual([g.count('class="plano"') for g in guiones], [3, 2, 2])
        self.assertIn("1 de 3", guiones[0])
        self.assertIn('<span class="n">7</span>', guiones[2])
        self.assertEqual(informe["paginas"], 4)

    def test_logotipo(self):
        png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                            "1f15c4890000000d49444154789c6360000002000154a24f6e0000000049454e44ae426082")
        (self.dir / "logo.png").write_bytes(png)
        datos = ejemplo()
        datos["marca"]["logo"] = "logo.png"
        informe = self.emplata(datos)
        html = pathlib.Path(informe["html"]).read_text(encoding="utf-8")
        self.assertIn('class="logo" src="data:image/png;base64,', html)
        datos["marca"]["logo"] = "no-existe.png"
        self.assertTrue(self.emplata(datos)["veredicto"].startswith("ARREGLA"))

    def test_el_archivo_para_copiar_trae_todo(self):
        informe = self.emplata(ejemplo())
        copiar = pathlib.Path(informe["copiar"]).read_text(encoding="utf-8")
        pie = next(p for p in ejemplo()["paginas"] if p["tipo"] == "texto")["texto"]
        self.assertIn(pie, copiar)
        self.assertIn("¿Los tuyos se abren con moneda o con llave?", copiar)
        self.assertIn("[En pantalla: Mira la presión]", copiar)


class LaLineaDeOrdenes(Carpeta):
    def corre(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
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
        self.comanda({"titulo": "T", "paginas": []}, "mala.json")
        r = self.corre("mala.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ARREGLA", r.stdout)

    def test_sin_navegador_avisa_y_sale_con_0(self):
        self.comanda(ejemplo(), "semana.json")
        r = self.corre("semana.json", "--pdf", "semana.pdf", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        informe = json.loads(r.stdout)
        self.assertIsNone(informe["pdf"])
        self.assertTrue(any(a["donde"] == "PDF" and a["estado"] == "NOTA" for a in informe["avisos"]))
        self.assertTrue((self.dir / "semana.html").exists())


class LoQueNoSePuedeColar(Carpeta):
    """Lo que encontró la revisión independiente: que no vuelva."""

    def html_de(self, informe):
        return pathlib.Path(informe["html"]).read_text(encoding="utf-8")

    def test_los_campos_internos_no_entran_por_la_comanda(self):
        trampa = "<style>.firma,.contra{display:none!important}</style><img src=https://example.com/x.png>"
        datos = {"titulo": "T", "para": "P", "paginas": [
            {"tipo": "puntos", "antetitulo": "x", "_parte": trampa, "_desde": "a", "puntos": ["a", "b", "c", "d"]}]}
        informe = self.emplata(datos)
        html = self.html_de(informe)
        self.assertNotIn("display:none!important", html)
        self.assertNotIn("example.com", html)
        self.assertIn("1 de 2", html)

    def test_ningun_campo_mete_html(self):
        malo = '<img src=x onerror=alert(1)><style>*{display:none}</style>'
        datos = {"titulo": malo, "para": malo[:59], "cuenta": "@a<b>", "preparado_por": "a<i>b</i>", "fecha": malo[:59],
                 "paginas": [
                     {"tipo": "portada", "titulo": malo, "subtitulo": malo, "antetitulo": malo,
                      "piezas": [{"dia": malo, "formato": malo}]},
                     {"tipo": "semana", "filas": [{"dia": malo, "hora": malo, "formato": malo, "tema": malo}]},
                     {"tipo": "puntos", "puntos": [{"texto": malo, "fuente": malo}]},
                     {"tipo": "guion", "planos": [{"dices": malo, "cartel": malo, "se_ve": malo}]},
                     {"tipo": "texto", "texto": malo, "imagen": malo, "notas": [malo], "nota": malo},
                     {"tipo": "laminas", "laminas": [malo]},
                     {"tipo": "lista", "items": [malo]},
                     {"tipo": "tabla", "columnas": [malo, malo], "filas": [[malo, malo]]},
                     {"tipo": "cifras", "cifras": [{"numero": malo, "texto": malo}, {"numero": "1", "texto": "x"}]},
                     {"tipo": "idea", "titulo": malo, "texto": malo, "nota": malo}]}
        informe = self.emplata(datos)
        html = self.html_de(informe)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<style>*{display", html)
        self.assertNotIn("<i>b</i>", html)
        self.assertEqual(html.count('class="firma"'), informe["paginas"])

    def test_preparado_por_no_tapa_la_contraportada(self):
        datos = ejemplo()
        datos["preparado_por"] = "Ana" + "\n" * 40 + "López"
        self.assertTrue(self.emplata(datos)["veredicto"].startswith("ARREGLA"))
        datos["preparado_por"] = "x" * 61
        self.assertTrue(self.emplata(datos)["veredicto"].startswith("ARREGLA"))
        datos["preparado_por"] = "Ana López, de Calefacción Olmo"
        self.assertFalse(self.emplata(datos)["veredicto"].startswith("ARREGLA"))

    def test_tipos_raros_dan_un_error_claro(self):
        casos = [
            {"tipo": "texto", "texto": "Hola", "notas": {"a": 1}},
            {"tipo": "portada", "titulo": "T", "piezas": 5},
            {"tipo": "semana", "filas": 5},
            {"tipo": "tabla", "columnas": ["a", "b"], "filas": 5},
            {"tipo": "puntos", "puntos": 5},
            {"tipo": "lista", "items": 5},
            {"tipo": ["idea"], "titulo": "T"},
            {"tipo": "idea", "titulo": {"x": 1}},
            {"tipo": "guion", "planos": [5.5, {"dices": ["a"]}]},
            {"tipo": "cifras", "cifras": [1, 2]},
        ]
        for pagina in casos:
            with self.subTest(pagina=pagina):
                informe = self.emplata({"titulo": "T", "para": "P", "paginas": [pagina]})
                self.assertTrue(informe["veredicto"].startswith("ARREGLA"), informe["avisos"])

    def test_una_nota_suelta_vale_como_lista(self):
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [
            {"tipo": "texto", "texto": "Hola", "notas": "Una nota", "nota": "Otra nota"}]})
        html = self.html_de(informe)
        self.assertEqual(re.findall(r'<p class="chico">([^<]*)</p>', html), ["Una nota", "Otra nota"])

    def test_si_y_no(self):
        informe = self.emplata({"titulo": "T", "para": "P", "marca": {"manuscrita": "no"}, "paginas": [
            {"tipo": "lista", "items": ["a"], "casillas": "no"}, {"tipo": "idea", "titulo": "I", "oscura": "sí"}]})
        html = self.html_de(informe)
        self.assertNotIn("font-family:'Great Vibes';src", html)
        self.assertIn('class="bola"', html)
        self.assertIn('class="p oscura"', html)
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [{"tipo": "idea", "titulo": "I", "oscura": "quizá"}]})
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_null_no_escribe_none(self):
        informe = self.emplata({"titulo": None, "para": None, "paginas": [{"tipo": "idea", "titulo": "I"}]})
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [
            {"tipo": "tabla", "columnas": ["A", "B"], "filas": [["x", None]]},
            {"tipo": "semana", "filas": [{"dia": "lunes", "hora": None, "formato": "Reel", "tema": "x"}]}]})
        html = self.html_de(informe)
        self.assertNotIn("None", html)
        self.assertIn("<td></td>", html)

    def test_archivos_solo_de_la_carpeta_de_la_comanda(self):
        fuera = pathlib.Path(self._tmp.name).parent / f"fuera-{os.getpid()}.txt"
        fuera.write_text("secreto", encoding="utf-8")
        try:
            for archivo in (str(fuera), f"../{fuera.name}", "/etc/passwd"):
                with self.subTest(archivo=archivo):
                    informe = self.emplata({"titulo": "T", "para": "P", "paginas": [
                        {"tipo": "laminas", "laminas": {"archivo": archivo}}]})
                    self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
            datos = ejemplo()
            datos["marca"]["logo"] = f"../{fuera.name}"
            self.assertTrue(self.emplata(datos)["veredicto"].startswith("ARREGLA"))
        finally:
            fuera.unlink()
        (self.dir / "datos.json").write_text("{}", encoding="utf-8")
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [
            {"tipo": "laminas", "laminas": {"archivo": "datos.json"}}]})
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_una_pagina_vacia_no_desaparece_en_silencio(self):
        for laminas in (["", " "], "---", "\n---\n"):
            with self.subTest(laminas=laminas):
                informe = self.emplata({"titulo": "T", "para": "P", "paginas": [{"tipo": "laminas", "laminas": laminas}]})
                self.assertTrue(informe["veredicto"].startswith("ARREGLA"))

    def test_la_semana_partida_lleva_su_1_de_2(self):
        filas = [{"dia": f"d{i}", "hora": "9:00", "formato": "Reel", "tema": "t"} for i in range(9)]
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [{"tipo": "semana", "filas": filas}]})
        html = self.html_de(informe)
        self.assertIn('<div class="eti">1 de 2</div>', html)
        self.assertIn('<div class="eti">2 de 2</div>', html)

    def test_acento_que_no_se_lee_sobre_las_tarjetas(self):
        datos = ejemplo()
        datos["marca"] = {"fondo": "#333333", "suave": "#555555", "texto": "#FFFFFF", "acento": "#999999"}
        informe = self.emplata(datos)
        self.assertEqual(informe["veredicto"], "REVÍSALO")
        self.assertTrue(any("tarjetas" in a["detalle"] for a in informe["avisos"]))

    def test_rayas_tambien_en_los_campos_de_arriba(self):
        datos = ejemplo()
        datos["fecha"] = "Lunes — martes"
        self.assertEqual(self.emplata(datos)["veredicto"], "REVÍSALO")
        datos = ejemplo()
        datos["paginas"][1]["filas"][0]["formato"] = "Reel – corto"
        self.assertEqual(self.emplata(datos)["veredicto"], "REVÍSALO")

    def test_el_archivo_para_copiar_lleva_fuentes_cifras_y_notas(self):
        informe = self.emplata({"titulo": "T", "para": "P", "paginas": [
            {"tipo": "puntos", "puntos": [{"texto": "Dato", "fuente": "INE 2025"}]},
            {"tipo": "cifras", "cifras": [{"numero": "19", "texto": "segundos"}, {"numero": "6", "texto": "planos"}]},
            {"tipo": "guion", "planos": [{"dices": "Hola", "cartel": "Hola"}]},
            {"tipo": "texto", "texto": "Post", "notas": ["Ojo a la hora"]}]})
        copiar = pathlib.Path(informe["copiar"]).read_text(encoding="utf-8")
        self.assertIn("(fuente: INE 2025)", copiar)
        self.assertIn("- 19 segundos", copiar)
        self.assertIn("Nota: Ojo a la hora", copiar)
        self.assertIn("1. [En pantalla: Hola] Hola", copiar)

    def test_avisa_de_archivos_viejos(self):
        (self.dir / "comanda.html").write_text("viejo", encoding="utf-8")
        informe = self.emplata({"titulo": "T", "paginas": []})
        self.assertTrue(any(a["donde"] == "ARCHIVO" for a in informe["avisos"]))
        self.assertEqual((self.dir / "comanda.html").read_text(encoding="utf-8"), "viejo")

    def test_el_navegador_va_con_la_red_cortada(self):
        codigo = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"--proxy-server=127.0.0.1:9"', codigo)
        self.assertIn('"--host-resolver-rules=MAP * ~NOTFOUND"', codigo)


class ErroresDeLineaDeOrdenes(Carpeta):
    def corre(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              cwd=self.dir, env={**os.environ, "BRIGADA_CHROME": "/no/existe"})

    def test_json_con_demasiados_niveles(self):
        (self.dir / "hondo.json").write_text("[" * 100000, encoding="utf-8")
        r = self.corre("hondo.json")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_carpeta_de_salida_que_no_existe(self):
        self.comanda(ejemplo(), "semana.json")
        r = self.corre("semana.json", "--salida", str(self.dir / "no" / "existe" / "x.html"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no puedo guardar", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


NAVEGADOR = E.busca_navegador()


@unittest.skipUnless(NAVEGADOR, "no hay Chrome, Chromium ni Edge (o BRIGADA_CHROME) en este ordenador")
class ConNavegador(Carpeta):
    def test_mide_y_hace_el_pdf(self):
        informe = E.emplata(self.comanda(ejemplo()), pdf=self.dir / "semana.pdf")
        self.assertEqual(informe["veredicto"], "LISTO", informe["avisos"])
        self.assertTrue(informe["medido"])
        pdf = (self.dir / "semana.pdf").read_bytes()
        cajas = set(re.findall(rb"/MediaBox\s*\[([^\]]+)\]", pdf))
        self.assertEqual(len(cajas), 1)
        ancho, alto = [float(x) for x in cajas.pop().split()[2:]]
        self.assertAlmostEqual(ancho, 810, delta=1)       # 1080 px a 72/96
        self.assertAlmostEqual(alto, 1012.5, delta=1)     # 1350 px a 72/96
        paginas = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        self.assertEqual(paginas, informe["paginas"])
        self.assertIn(b"/URI", pdf)

    def test_marca_lo_que_se_sale(self):
        datos = {"titulo": "T", "para": "P", "paginas": [
            {"tipo": "idea", "titulo": "Una idea", "texto": "Mucho texto que no cabe. " * 70},
            {"tipo": "idea", "titulo": "Otra que sí cabe"}]}
        informe = E.emplata(self.comanda(datos), pdf=self.dir / "x.pdf")
        self.assertTrue(informe["veredicto"].startswith("ARREGLA"))
        self.assertTrue(any("página 1:" in a["detalle"] for a in informe["avisos"]))
        self.assertIsNone(informe["pdf"])
        self.assertFalse((self.dir / "x.pdf").exists())


if __name__ == "__main__":
    unittest.main()

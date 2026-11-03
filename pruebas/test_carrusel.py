"""
Pruebas de brigada-carrusel: el revisor de carruseles, sus siete estructuras y
el ejemplo, y que corta las láminas igual que la Lámina de texto.

Los carruseles son inventados, de oficios distintos: fontanería, taller,
carpintería y reformas.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "brigada-carrusel"
SCRIPT = SKILL / "scripts" / "revisa_carrusel.py"
spec = importlib.util.spec_from_file_location("revisa_carrusel", SCRIPT)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def carrusel(*laminas):
    return "\n\n---\n\n".join(laminas)


def estado(r, comprobacion):
    return [c["estado"] for c in r["revision"] if c["comprobacion"] == comprobacion]


def detalle(r, comprobacion):
    return " ".join(c["detalle"] for c in r["revision"] if c["comprobacion"] == comprobacion)


# Un carrusel corto y correcto, para variar una cosa cada vez.
PORTADA = "Lo que miro antes de comprar una moto de segunda mano."
SEGUNDA = "Una moto barata puede salir cara si no sabes qué mirar. Esto es lo que reviso yo."
MEDIO = [
    "El aceite\n\nSi está negro y espeso, pregunta cuándo se cambió por última vez.",
    "Los frenos\n\nPasa el dedo por el disco. Si notas un escalón, habrá que cambiarlo.",
    "La cadena\n\nTira de ella hacia atrás en la corona. Si se separa mucho, está gastada.",
]
CIERRE = "¿Y tú qué miras primero cuando vas a ver una?"


def base(**cambios):
    partes = {"portada": PORTADA, "segunda": SEGUNDA, "medio": MEDIO, "cierre": CIERRE}
    partes.update(cambios)
    return carrusel(partes["portada"], partes["segunda"], *partes["medio"], partes["cierre"])


class CortaComoLaLamina(unittest.TestCase):
    def test_tres_guiones_en_su_linea(self):
        self.assertEqual(rc.separa("a\n---\nb"), ["a", "b"])
        self.assertEqual(rc.separa("a\n  -----  \nb"), ["a", "b"])

    def test_separadores_de_mas_no_cuentan(self):
        self.assertEqual(rc.separa("---\na\n---\n---\nb\n---\n"), ["a", "b"])

    def test_guiones_con_texto_no_cortan(self):
        self.assertEqual(len(rc.separa("a\n--- nota\nb")), 1)

    def test_finales_de_linea_de_windows(self):
        self.assertEqual(rc.separa("a\r\n---\r\nb"), ["a", "b"])

    def test_espacio_duro_tras_los_guiones(self):
        # Al pegar desde Notas, Docs o WhatsApp, a veces queda un espacio duro.
        self.assertEqual(rc.separa("a\n---" + chr(0xA0) + "\nb"), ["a", "b"])

    def test_invisibles_alrededor_de_los_guiones(self):
        self.assertEqual(rc.separa("a\n" + chr(0x200B) + "---\nb"), ["a", "b"])
        self.assertEqual(rc.separa("a\n---\n" + chr(0x200B) + "\n---\nb"), ["a", "b"])

    def test_la_lamina_limpia_lo_mismo(self):
        html = (RAIZ / "herramientas" / "lamina-de-texto.html").read_text(encoding="utf-8")
        for nombre, python in (("INVISIBLES", rc.INVISIBLES), ("ESPACIOS_RAROS", rc.ESPACIOS_RAROS)):
            m = re.search(r"var " + nombre + r" = new RegExp\(\"\[\" \+ \[([^\]]+)\]", html)
            with self.subTest(nombre):
                self.assertIsNotNone(m, f"no encuentro {nombre} en la Lámina")
                self.assertEqual({int(c, 16) for c in re.findall(r"0x([0-9A-Fa-f]+)", m.group(1))}, set(python))

    def test_la_lamina_usa_el_mismo_corte(self):
        html = (RAIZ / "herramientas" / "lamina-de-texto.html").read_text(encoding="utf-8")
        m = re.search(r"function separar\(t\) \{\s*return .*?\.split\(/(.+?)/\)", html)
        self.assertIsNotNone(m, "no encuentro cómo corta la Lámina")
        self.assertEqual(m.group(1), rc.SEPARADOR_RE.pattern)


class CuantasLaminas(unittest.TestCase):
    def test_un_carrusel_normal(self):
        self.assertEqual(estado(rc.revisa(base()), "LÁMINAS"), ["BIEN"])

    def test_una_sola_es_un_post(self):
        r = rc.revisa(PORTADA)
        self.assertEqual(estado(r, "LÁMINAS"), ["ARREGLA"])
        self.assertTrue(r["veredicto"].startswith("ARREGLA"))

    def test_mas_de_veinte_no_entra(self):
        laminas = [f"Paso {i}: aprieta la tuerca número {i}." for i in range(1, 22)]
        self.assertEqual(estado(rc.revisa(carrusel(*laminas)), "LÁMINAS"), ["ARREGLA"])

    def test_veinte_si(self):
        laminas = [f"Paso {i}: aprieta la tuerca número {i}." for i in range(1, 21)]
        self.assertEqual(estado(rc.revisa(carrusel(*laminas)), "LÁMINAS"), ["OJO"])

    def test_tres_son_pocas(self):
        self.assertEqual(estado(rc.revisa(carrusel(PORTADA, SEGUNDA, CIERRE)), "LÁMINAS"), ["OJO"])


@unittest.skipUnless(rc.GANCHO, "hace falta brigada-reel al lado")
class LaPortada(unittest.TestCase):
    def test_portada_buena(self):
        r = rc.revisa(base())
        self.assertEqual(estado(r, "PORTADA"), ["BIEN"])
        self.assertGreaterEqual(r["portada"]["total"], 50)

    def test_portada_floja(self):
        r = rc.revisa(base(portada="Consejos."))
        self.assertEqual(estado(r, "PORTADA"), ["OJO"])
        self.assertIn("menos de 50", detalle(r, "PORTADA"))

    def test_portada_con_preambulo(self):
        r = rc.revisa(base(portada="Hoy te traigo lo que miro antes de comprar una moto."))
        self.assertEqual(estado(r, "PORTADA"), ["OJO"])

    def test_portada_con_mucho_texto(self):
        larga = PORTADA + "\n\n" + " ".join(["Una moto de segunda mano tiene historia."] * 5)
        r = rc.revisa(base(portada=larga))
        self.assertIn("en la rejilla del perfil", detalle(r, "PORTADA"))

    def test_portada_partida_en_renglones(self):
        en_una = "¿Radiador frío por arriba? Casi siempre es aire, no la caldera."
        partida = "¿Radiador frío\npor arriba?\nCasi siempre es aire, no la caldera."
        self.assertEqual(rc.revisa(base(portada=partida))["portada"], rc.revisa(base(portada=en_una))["portada"])

    def test_sin_punto_doble_en_la_cita(self):
        self.assertNotIn(".»", detalle(rc.revisa(base()), "PORTADA"))

    def test_solo_puntua_la_primera_frase(self):
        con_subtitulo = PORTADA + "\n\nLas tres cosas que reviso en el taller."
        self.assertEqual(rc.revisa(base(portada=con_subtitulo))["portada"]["total"],
                         rc.revisa(base())["portada"]["total"])


class LaSegundaLamina(unittest.TestCase):
    def test_que_se_entienda_sola(self):
        self.assertEqual(estado(rc.revisa(base()), "LÁMINA 2"), ["BIEN"])

    def test_sin_anunciar_lo_que_viene(self):
        for segunda in ("En este carrusel te cuento lo que miro.", "Sigue deslizando, que te lo enseño."):
            with self.subTest(segunda):
                self.assertEqual(estado(rc.revisa(base(segunda=segunda)), "LÁMINA 2"), ["OJO"])

    def test_lo_que_no_es_anunciar(self):
        for segunda in ("Desliza la mano por el radiador: si está frío arriba, es aire.",
                        "Antes de empezar, apaga la caldera.",
                        "iPhone o Android, da igual: la foto la haces igual.",
                        "Te voy a ser sincero: casi nadie mira la cadena."):
            with self.subTest(segunda):
                self.assertEqual(estado(rc.revisa(base(segunda=segunda)), "LÁMINA 2"), ["BIEN"])

    def test_desliza_dirigido_a_quien_lee(self):
        for segunda in ("Desliza para verlo.", "Desliza " + chr(0x2192), "Te voy a contar lo que miro."):
            with self.subTest(segunda):
                self.assertEqual(estado(rc.revisa(base(segunda=segunda)), "LÁMINA 2"), ["OJO"])

    def test_sin_empezar_a_mitad_de_frase(self):
        for segunda in ("y no te lo dicen en el concesionario.", "...y aquí empieza lo bueno."):
            with self.subTest(segunda):
                self.assertEqual(estado(rc.revisa(base(segunda=segunda)), "LÁMINA 2"), ["OJO"])


class ElLargo(unittest.TestCase):
    def test_lamina_larga(self):
        larga = "El aceite\n\n" + " ".join(["Mira el color y el nivel con la moto en llano."] * 6)
        r = rc.revisa(base(medio=[larga] + MEDIO[1:]))
        self.assertEqual(estado(r, "LARGO"), ["OJO"])
        self.assertIn("3 (", detalle(r, "LARGO"))

    def test_el_limite_se_cambia(self):
        self.assertEqual(estado(rc.revisa(base(), max_palabras=10), "LARGO"), ["OJO"])


class LoQueNoSePuedePulsar(unittest.TestCase):
    def test_hashtags_menciones_y_enlaces(self):
        for cosa in ("#motos", "@taller_pepe", "www.tallerpepe.es", "tallerpepe.com"):
            with self.subTest(cosa):
                r = rc.revisa(base(cierre=f"¿Cuál se te olvida? {cosa}"))
                self.assertEqual(estado(r, "EN LA IMAGEN"), ["OJO"])

    def test_un_numero_no_es_un_hashtag(self):
        r = rc.revisa(base(medio=["Paso #1: el aceite.", "Paso #2: los frenos.", "Paso #3: la cadena."]))
        self.assertEqual(estado(r, "EN LA IMAGEN"), [])

    def test_un_espacio_que_falta_no_es_un_enlace(self):
        for texto in ("Está frío por arriba.Es aire.", "Lo vemos.App aparte, el manual."):
            with self.subTest(texto):
                self.assertEqual(rc.ENLACE_RE.findall(texto), [])
        self.assertTrue(rc.ENLACE_RE.findall("Pide cita en TallerPepe.com"))

    def test_un_correo_no_es_una_mencion(self):
        self.assertEqual(rc.MENCION_RE.findall("hola@taller.es"), [])


class LaminasRepetidas(unittest.TestCase):
    def test_iguales_aunque_cambien_las_mayusculas(self):
        r = rc.revisa(base(medio=[MEDIO[0], MEDIO[0].upper(), MEDIO[2]]))
        self.assertEqual(estado(r, "REPETIDAS"), ["ARREGLA"])

    def test_sin_repetidas_no_dice_nada(self):
        self.assertEqual(estado(rc.revisa(base()), "REPETIDAS"), [])


class LaLaminaParaGuardar(unittest.TestCase):
    def test_carrusel_largo_sin_resumen(self):
        medio = MEDIO + ["Las ruedas\n\nMira la fecha del neumático.", "Los papeles\n\nPide las facturas del taller."]
        self.assertEqual(estado(rc.revisa(base(medio=medio)), "RESUMEN"), ["NOTA"])

    def test_con_resumen(self):
        resumen = "Las cinco, juntas:\n\n- Aceite\n- Frenos\n- Cadena\n- Ruedas\n- Papeles"
        medio = MEDIO + ["Las ruedas\n\nMira la fecha del neumático.", resumen]
        self.assertEqual(estado(rc.revisa(base(medio=medio)), "RESUMEN"), [])

    def test_una_cifra_no_es_una_lista(self):
        self.assertFalse(rc.LISTA_RE.match("1.000 € al año en averías"))
        self.assertTrue(rc.LISTA_RE.match("1. El aceite"))


@unittest.skipUnless(rc.CAPTION, "hace falta brigada-caption al lado")
class ElCierre(unittest.TestCase):
    def test_una_pregunta(self):
        self.assertEqual(estado(rc.revisa(base()), "CIERRE"), ["BIEN"])

    def test_pregunta_con_emoji_detras(self):
        self.assertEqual(estado(rc.revisa(base(cierre="¿Cuál se te olvida siempre? 👇")), "CIERRE"), ["BIEN"])

    def test_una_peticion(self):
        r = rc.revisa(base(cierre="Escríbeme y te digo qué mirar en la tuya."))
        self.assertEqual(estado(r, "CIERRE"), ["BIEN"])
        self.assertIn("escribir", detalle(r, "CIERRE"))

    def test_dos_peticiones_se_pisan(self):
        r = rc.revisa(base(portada=PORTADA + "\n\nGuárdalo para cuando vayas a comprar.",
                           cierre="Escríbeme y te digo qué mirar en la tuya."))
        self.assertEqual(estado(r, "CIERRE"), ["OJO"])
        self.assertIn("la portada", detalle(r, "CIERRE"))

    def test_los_pasos_del_medio_no_son_peticiones(self):
        medio = ["Llama al vendedor\n\nPregunta por las revisiones.", MEDIO[1], MEDIO[2]]
        self.assertEqual(estado(rc.revisa(base(medio=medio)), "CIERRE"), ["BIEN"])

    def test_sin_pedir_nada(self):
        self.assertEqual(estado(rc.revisa(base(cierre="Con esto, ya sabes por dónde empezar.")), "CIERRE"), ["NOTA"])


class OtrosAgentesQueNoRespondenComoSeEspera(unittest.TestCase):
    """Un brigada-reel o un brigada-caption más viejo no rompe la revisión: avisa y sigue."""

    class Roto:
        def puntua(self, *a):
            raise ValueError("formato desconocido: post")

        def peticiones(self, *a):
            raise TypeError("otra forma de llamarlo")

    def setUp(self):
        self.gancho, self.caption = rc.GANCHO, rc.CAPTION
        rc.GANCHO = rc.CAPTION = self.Roto()

    def tearDown(self):
        rc.GANCHO, rc.CAPTION = self.gancho, self.caption

    def test_avisa_y_sigue(self):
        r = rc.revisa(base())
        self.assertEqual(estado(r, "PORTADA"), ["NOTA"])
        self.assertEqual(estado(r, "CIERRE"), ["NOTA"])


class SinLosOtrosAgentes(unittest.TestCase):
    """Si brigada-reel o brigada-caption no están al lado, lo dice y sigue."""

    def setUp(self):
        self.gancho, self.caption = rc.GANCHO, rc.CAPTION
        rc.GANCHO = rc.CAPTION = None

    def tearDown(self):
        rc.GANCHO, rc.CAPTION = self.gancho, self.caption

    def test_avisa_y_sigue(self):
        r = rc.revisa(base())
        self.assertEqual(estado(r, "PORTADA"), ["NOTA"])
        self.assertEqual(estado(r, "CIERRE"), ["NOTA"])
        self.assertEqual(r["veredicto"], "LISTO")

    def test_sin_puntuador_mira_el_largo(self):
        larga = "Lo que miro siempre antes de comprar una moto de segunda mano en cualquier sitio."
        self.assertEqual(estado(rc.revisa(base(portada=larga)), "PORTADA"), ["OJO"])

    def test_sin_puntuador_mira_el_saludo(self):
        self.assertEqual(estado(rc.revisa(base(portada="Hola, hoy hablamos de motos.")), "PORTADA"), ["OJO"])


class ElTextoAlternativo(unittest.TestCase):
    def test_uno_por_lamina(self):
        r = rc.revisa(base())
        self.assertEqual(len(r["texto_alternativo"]), len(r["laminas"]))
        self.assertTrue(r["texto_alternativo"][0].startswith("Lámina 1 de 6. Texto: Lo que miro"))
        self.assertNotIn("\n", r["texto_alternativo"][2])

    def test_titulo_y_texto_no_se_juntan(self):
        alt = rc.texto_alternativo(["1. Apaga la calefacción\n\nEspera a que se enfríe.", "Juntos:\n\n- Aceite\n- Frenos"])
        self.assertIn("Apaga la calefacción. Espera", alt[0])
        self.assertIn("Juntos: Aceite. Frenos.", alt[1])


class ElEjemploDelRepo(unittest.TestCase):
    def test_el_ejemplo_esta_listo(self):
        if not (rc.GANCHO and rc.CAPTION):
            self.skipTest("hacen falta brigada-reel y brigada-caption al lado")
        r = rc.revisa((SKILL / "assets" / "carrusel-ejemplo.txt").read_text(encoding="utf-8"))
        self.assertEqual(r["veredicto"], "LISTO", r["revision"])

    def test_la_lamina_para_guardar_tiene_todos_los_pasos(self):
        laminas = rc.separa((SKILL / "assets" / "carrusel-ejemplo.txt").read_text(encoding="utf-8"))
        pasos = [l for l in laminas if re.match(r"\d+\. ", l)]
        resumen = [l for l in laminas if rc.es_resumen(l)]
        self.assertEqual(len(resumen), 1)
        self.assertEqual(sum(1 for l in resumen[0].splitlines() if rc.LISTA_RE.match(l)), len(pasos))


@unittest.skipUnless(rc.GANCHO, "hace falta brigada-reel al lado")
class LasSieteEstructuras(unittest.TestCase):
    """Cada portada de ejemplo de references/estructuras.md tiene 12 palabras o menos y saca 50 o más como post."""

    def estructuras(self):
        texto = (SKILL / "references" / "estructuras.md").read_text(encoding="utf-8")
        partes = re.split(r"^## \d+\. ", texto, flags=re.M)[1:]
        partes[-1] = partes[-1].split("## Las que no")[0]
        return partes

    def test_son_siete(self):
        self.assertEqual(len(self.estructuras()), 7)

    def test_cada_portada_pasa_su_propio_corte(self):
        for parte in self.estructuras():
            nombre = parte.splitlines()[0]
            ejemplo = re.search(r"\*\*Ejemplo de portada:\*\* «(.+)»\.?\s*$", parte, re.M).group(1)
            with self.subTest(nombre):
                self.assertLessEqual(len(rc.GANCHO.tokens(ejemplo)), 12)
                self.assertGreaterEqual(rc.GANCHO.puntua(ejemplo, "post")[1], 50)

    def test_cada_una_tiene_todos_sus_campos(self):
        campos = ("Para qué", "Pata", "Portada", "Ejemplo de portada", "Lámina 2", "El medio", "Cierre",
                  "Se estropea si")
        for parte in self.estructuras():
            for campo in campos:
                with self.subTest(estructura=parte.splitlines()[0], campo=campo):
                    self.assertIn(f"**{campo}:**", parte)


class LaLineaDeOrdenes(unittest.TestCase):
    def corre(self, *args, entrada=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=entrada, capture_output=True,
                              text=True, encoding="utf-8")

    def test_archivo_que_no_existe(self):
        r = self.corre("no-existe.txt")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no puedo leer", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_texto_vacio(self):
        self.assertEqual(self.corre("-", entrada="\n---\n\n").returncode, 2)

    def test_arregla_sale_con_uno(self):
        self.assertEqual(self.corre("-", entrada=PORTADA).returncode, 1)

    def test_listo_sale_con_cero_y_enseña_el_mapa(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = pathlib.Path(tmp) / "carrusel.txt"
            ruta.write_text(base(), encoding="utf-8")
            r = self.corre(str(ruta), "--alt")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PORTADA", r.stdout)
        self.assertIn("TEXTO ALTERNATIVO", r.stdout)

    def test_json(self):
        import json
        r = self.corre("-", "--json", entrada=base())
        datos = json.loads(r.stdout)
        self.assertEqual(len(datos["mapa"]), 6)
        self.assertEqual(datos["mapa"][0]["papel"], "PORTADA")
        self.assertEqual(datos["mapa"][-1]["papel"], "CIERRE")

    def test_palabras_tiene_que_ser_positivo(self):
        self.assertEqual(self.corre("-", "--palabras", "0", entrada=base()).returncode, 2)


class LosOtrosScriptsNoSeRompenConUnArchivoQueNoExiste(unittest.TestCase):
    SCRIPTS = [
        ("brigada-reel", "puntua_gancho.py"),
        ("brigada-reel", "tiempos.py"),
        ("brigada-caption", "revisa_caption.py"),
        ("brigada-humano", "humaniza.py"),
        ("brigada-humano", "detecta.py"),
        ("brigada-plan", "semana.py"),
    ]

    def test_dicen_que_no_lo_encuentran(self):
        for skill, script in self.SCRIPTS:
            with self.subTest(script):
                r = subprocess.run([sys.executable, str(RAIZ / "skills" / skill / "scripts" / script), "no-existe.txt"],
                                   capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)

    def test_ficha_y_lista_que_no_existen(self):
        humano = RAIZ / "skills" / "brigada-humano" / "scripts"
        ejemplo = str(SKILL / "assets" / "carrusel-ejemplo.txt")
        for script, opcion in (("humaniza.py", "--ficha"), ("humaniza.py", "--lexico"),
                               ("detecta.py", "--ficha"), ("detecta.py", "--lexico")):
            with self.subTest(script=script, opcion=opcion):
                r = subprocess.run([sys.executable, str(humano / script), ejemplo, opcion, "no-existe.md"],
                                   capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)

    def test_puntua_gancho_sugiere_la_opcion_de_frase(self):
        r = subprocess.run([sys.executable, str(RAIZ / "skills" / "brigada-reel" / "scripts" / "puntua_gancho.py"),
                            "Una frase suelta"], capture_output=True, text=True, encoding="utf-8")
        self.assertIn("--gancho", r.stderr)


if __name__ == "__main__":
    unittest.main()

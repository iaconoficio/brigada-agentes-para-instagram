"""
Pruebas de lo que brigada-humano hace con la ficha de cada persona.

  1. humaniza.py no toca las «Palabras que usas», aunque estén en la lista.
  2. humaniza.py avisa de las «Palabras que no dirías nunca».
  3. Lee bien esos dos campos de FICHA-BRIGADA.md.
  4. detecta.py avisa cuando el texto es demasiado corto para juzgarlo.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "skills" / "brigada-humano" / "scripts"


def carga(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


humaniza = carga(SCRIPTS / "humaniza.py", "humaniza_ficha")
detecta = carga(SCRIPTS / "detecta.py", "detecta_ficha")
LEX = json.loads((SCRIPTS / "muletillas.json").read_text(encoding="utf-8"))

FICHA = """# FICHA-BRIGADA.md

## Tu voz

- **Palabras que usas** (no se tocan, aunque parezcan de IA): «optimizar», «Asimismo», «Al grano y sin vueltas»
- **Palabras que no dirías nunca:** «sin compromiso, sin sorpresas», «experiencia única» `[PENDIENTE]` alguna más
"""


class RespetaTusPalabras(unittest.TestCase):
    TEXTO = "Vamos a optimizar el presupuesto. Asimismo, hay que potenciar la revisión."

    def test_sin_ficha_cambia_la_muletilla(self):
        limpio, _ = humaniza.humaniza(self.TEXTO, LEX)
        self.assertNotIn("optimizar", limpio)

    def test_con_ficha_respeta_tus_palabras(self):
        limpio, informe = humaniza.humaniza(self.TEXTO, LEX, respetar=["optimizar", "Asimismo"])
        self.assertIn("optimizar", limpio)
        self.assertIn("Asimismo", limpio)
        self.assertIn("optimizar", informe["respetadas"])

    def test_respetar_no_frena_lo_demas(self):
        limpio, _ = humaniza.humaniza(self.TEXTO, LEX, respetar=["optimizar"])
        self.assertNotIn("potenciar", limpio)

    def test_respeta_sin_mirar_tildes_ni_mayusculas(self):
        limpio, _ = humaniza.humaniza("Por consiguiente, cuesta.", LEX, respetar=["POR CONSIGUIENTE"])
        self.assertIn("Por consiguiente", limpio)

    def test_respeta_frases_de_la_lista_que_acaban_en_coma(self):
        limpio, _ = humaniza.humaniza("En resumen, hay que revisar la caldera.", LEX, respetar=["En resumen"])
        self.assertTrue(limpio.startswith("En resumen"))

    def test_solo_protege_la_expresion_entera(self):
        # «crucial» está en la lista. Dentro de su expresión se queda; suelto, no.
        texto = "Es crucial purgar los radiadores. Para mí esto es crucial, de verdad."
        limpio, informe = humaniza.humaniza(texto, LEX, respetar=["esto es crucial, de verdad"])
        self.assertIn("esto es crucial, de verdad", limpio)
        self.assertTrue(limpio.startswith("Es importante") or "crucial" in informe["para_revisar"])

    def test_avisa_de_lo_que_no_dirias(self):
        _, informe = humaniza.humaniza("Sin compromiso, sin sorpresas. Así de fácil.", LEX,
                                        evitar=["sin compromiso, sin sorpresas"])
        self.assertEqual(informe["evitar"].get("sin compromiso, sin sorpresas"), 1)

    def test_no_mete_palabras_que_no_dirias(self):
        limpio, informe = humaniza.humaniza("Esto va a potenciar el negocio.", LEX, evitar=["mejorar"])
        self.assertIn("potenciar", limpio)
        self.assertIn("potenciar", informe["para_revisar"])
        self.assertNotIn("mejorar", limpio)

    def test_su_cierre_no_es_una_pregunta_retorica(self):
        texto = "Esto me pasa cada lunes en el taller.\n¿Me sigues?"
        _, sin = humaniza.humaniza(texto, LEX)
        _, con = humaniza.humaniza(texto, LEX, respetar=["¿Me sigues?"])
        self.assertLessEqual(len(con["estructuras"]), len(sin["estructuras"]))
        self.assertFalse(any("retórica" in s["nombre"].lower() for s in con["estructuras"]))


class GuionesYChats(unittest.TestCase):
    def test_no_rompe_los_tiempos_del_guion(self):
        texto = "0:00 " + chr(0x2013) + " 0:03 Gancho del reel.\n0:03-0:08 Lo que está en juego."
        limpio, _ = humaniza.humaniza(texto, LEX)
        # El tramo sigue entero (no pasa a «0:00, 0:03») y la semirraya pasa a guion.
        self.assertIn("0:00 - 0:03", limpio)
        self.assertIn("0:03-0:08", limpio)

    def test_los_horarios_pierden_la_semirraya(self):
        texto = "Abrimos de 9:00 " + chr(0x2013) + " 14:00 y de 20:00" + chr(0x2013) + "23:30."
        limpio, _ = humaniza.humaniza(texto, LEX)
        self.assertNotIn(chr(0x2013), limpio)
        self.assertIn("9:00 - 14:00", limpio)
        self.assertIn("20:00-23:30", limpio)

    def test_lo_pendiente_no_se_respeta(self):
        ficha = "- **Palabras que usas** (no se tocan): «mira» `[PENDIENTE]` confirmar si dice «vale», «venga»"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que usas"), ["mira"])

    def test_quita_el_formato_de_chat(self):
        limpio, informe = humaniza.humaniza("### Título\n**Ojo** con esto. #taller", LEX)
        self.assertEqual(limpio, "Título\nOjo con esto. #taller")
        self.assertTrue(informe["tipografia"])


class LeeLaFicha(unittest.TestCase):
    def test_lee_las_citas_entre_comillas(self):
        self.assertEqual(humaniza.campo_lista(FICHA, "Palabras que usas"),
                         ["optimizar", "Asimismo", "Al grano y sin vueltas"])

    def test_ignora_lo_pendiente(self):
        self.assertEqual(humaniza.campo_lista(FICHA, "Palabras que no dirías nunca"),
                         ["sin compromiso, sin sorpresas", "experiencia única"])

    def test_sin_comillas_parte_por_comas(self):
        ficha = "- **Palabras que usas** (no se tocan): mira, sin rollos *(observado)*, vamos al lío"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que usas"), ["mira", "sin rollos", "vamos al lío"])

    def test_lee_subvinetas(self):
        ficha = "- **Palabras que usas** (no se tocan):\n  - «mira»\n  - «sin rollos»\n- **Otro campo:** nada"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que usas"), ["mira", "sin rollos"])

    def test_lee_comillas_rectas_y_curvas(self):
        ficha = "- **Palabras que no dirías nunca:** \"experiencia única\", “somos pasión”"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que no dirías nunca"),
                         ["experiencia única", "somos pasión"])

    def test_parte_por_ni(self):
        ficha = "- **Palabras que no dirías nunca:** gurú ni magia"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que no dirías nunca"), ["gurú", "magia"])

    def test_marca_de_origen_con_dos_puntos(self):
        ficha = "- **Palabras que usas** (no se tocan) *(de otra fuente: agencia)*: mira, sin rollos"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que usas"), ["mira", "sin rollos"])

    def test_ejemplos_entre_parentesis_no_cuentan(self):
        ficha = "- **Palabras que no dirías nunca:** «sin compromiso»; frases de folleto («líderes del sector»)"
        self.assertEqual(humaniza.campo_lista(ficha, "Palabras que no dirías nunca"), ["sin compromiso"])

    def test_campo_vacio_o_que_no_existe(self):
        self.assertEqual(humaniza.campo_lista("- **Palabras que usas** (no se tocan):", "Palabras que usas"), [])
        self.assertEqual(humaniza.campo_lista("nada", "Palabras que usas"), [])

    def test_la_linea_de_ordenes_usa_la_ficha(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ficha = pathlib.Path(carpeta) / "FICHA-BRIGADA.md"
            ficha.write_text(FICHA, encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "humaniza.py"), "-", "--ficha", str(ficha), "--json"],
                               input="Vamos a optimizar esto. Sin compromiso, sin sorpresas.", capture_output=True,
                               text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            salida = json.loads(r.stdout)
            self.assertIn("optimizar", salida["texto"])
            self.assertIn("sin compromiso, sin sorpresas", salida["informe"]["evitar"])


class DetectaRespetaTusPalabras(unittest.TestCase):
    TEXTO = ("Vamos a optimizar cómo trabajamos cada lunes en el taller. Asimismo, "
             "yo te lo explico rápido: la batería se descarga si la moto no se mueve. "
             "Arráncala una vez al mes, diez minutos. Así de simple. ¿Lo haces?")

    def test_sus_palabras_no_restan(self):
        sin = detecta.analiza(self.TEXTO, LEX)[0]["MULETILLAS"][0]
        con = detecta.analiza(self.TEXTO, LEX, ["optimizar", "Asimismo"])[0]["MULETILLAS"][0]
        self.assertGreater(con, sin)


class AvisoDeTextoCorto(unittest.TestCase):
    def test_frases_sueltas_llevan_aviso(self):
        self.assertIn("orientativa", detecta.aviso_longitud("Una moto parada también se estropea."))

    def test_un_post_entero_no_lleva_aviso(self):
        texto = " ".join(["Llevo veinte años en el taller y cada semana aprendo algo nuevo de mis clientes."] * 6)
        self.assertEqual(detecta.aviso_longitud(texto), "")


class SusPreguntasRetoricas(unittest.TestCase):
    TEXTO = "Llevo años viendo lo mismo en el taller.\n¿El resultado?\nMotos paradas todo el invierno."

    def test_la_ficha_dice_si_son_suyas(self):
        self.assertEqual(humaniza.estructuras_propias("  - Preguntas retóricas: sí, son mías"), {"pregunta-retorica"})
        self.assertEqual(humaniza.estructuras_propias("  - **Preguntas retóricas:** sí *(observado)*"),
                         {"pregunta-retorica"})

    def test_sin_rellenar_o_que_no_cuenta_como_no(self):
        for ficha in ("  - Preguntas retóricas: [sí, son mías | no]", "  - Preguntas retóricas: no",
                      "  - Preguntas retóricas: `[PENDIENTE]` confirmar", "  - Preguntas retóricas:", "",
                      "  - Preguntas retóricas: Sin preguntas retóricas", "  - Preguntas retóricas: Simplemente no"):
            with self.subTest(ficha):
                self.assertEqual(humaniza.estructuras_propias(ficha), set())

    def test_otras_formas_de_escribirlo(self):
        for ficha in ("  - Preguntas retoricas: si", "  - Preguntas retóricas: [sí, son mías]",
                      "  - Preguntas retóricas:\n    - sí, muchas", "- **Preguntas retóricas:** SÍ"):
            with self.subTest(ficha):
                self.assertEqual(humaniza.estructuras_propias(ficha), {"pregunta-retorica"})

    def test_humaniza_no_las_senala_si_son_suyas(self):
        _, sin = humaniza.humaniza(self.TEXTO, LEX)
        _, con = humaniza.humaniza(self.TEXTO, LEX, propias={"pregunta-retorica"})
        self.assertTrue(any("retórica" in s["nombre"].lower() for s in sin["estructuras"]))
        self.assertFalse(any("retórica" in s["nombre"].lower() for s in con["estructuras"]))

    def test_detecta_no_las_cuenta_si_son_suyas(self):
        texto = (self.TEXTO + " Arráncala una vez al mes, diez minutos, y ya está. Te lo digo yo, que lo veo "
                 "cada semana: la batería se descarga sola si la moto no se mueve. ¿Y luego? La grúa.")
        sin = detecta.mira_voz(texto, LEX)[0]
        con = detecta.mira_voz(texto, LEX, {"pregunta-retorica"})[0]
        self.assertGreater(con, sin)

    def test_la_linea_de_ordenes_las_respeta_con_la_ficha(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ficha = pathlib.Path(carpeta) / "FICHA-BRIGADA.md"
            ficha.write_text(FICHA + "- **Cómo escribes**:\n  - Preguntas retóricas: sí, son mías\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "humaniza.py"), "-", "--ficha", str(ficha), "--json"],
                               input=self.TEXTO, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            nombres = [s["nombre"].lower() for s in json.loads(r.stdout)["informe"]["estructuras"]]
            self.assertFalse(any("retórica" in n for n in nombres))


class BorrarSinDejarRastro(unittest.TestCase):
    def test_no_queda_un_punto_huerfano(self):
        casos = {
            "Síguenos para más. Corre a revisar los frenos.": "Corre a revisar los frenos.",
            "Frenos nuevos. Síguenos para más. Hasta el lunes.": "Frenos nuevos. Hasta el lunes.",
            "Bueno... ya veremos.": "Bueno... ya veremos.",
            "Bueno.. ya veremos.": "Bueno.. ya veremos.",
            "¿En serio?.. Pues sí.": "¿En serio?.. Pues sí.",
            "Hasta el lunes\n:)": "Hasta el lunes\n:)",
            "Tornillos, tuercas, etc. Todo en su caja.": "Tornillos, tuercas, etc. Todo en su caja.",
        }
        for entrada, salida in casos.items():
            with self.subTest(entrada):
                self.assertEqual(humaniza.humaniza(entrada, LEX)[0], salida)


if __name__ == "__main__":
    unittest.main()

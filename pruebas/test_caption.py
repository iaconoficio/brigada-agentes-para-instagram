"""
Pruebas de revisa_caption.py, la revisión del texto del post de brigada-caption.

Los textos son inventados, de oficios distintos.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RUTA = RAIZ / "skills" / "brigada-caption" / "scripts" / "revisa_caption.py"
spec = importlib.util.spec_from_file_location("revisa_caption", RUTA)
caption = importlib.util.module_from_spec(spec)
spec.loader.exec_module(caption)

BUENO = """¿Cada cuánto cambias el aceite? Casi nadie acierta.

En el taller lo vemos cada semana: motos con el aceite negro porque «aún no tocaba».

Mira el libro de mantenimiento de tu moto y, si haces mucha ciudad, adelántalo un poco.

¿Tú cada cuánto lo cambias?

#mecanica #motos"""


def estado(texto, comprobacion, **kw):
    r = caption.revisa(texto, **kw)
    return [c["estado"] for c in r["revision"] if c["comprobacion"] == comprobacion]


class LoQueSeVe(unittest.TestCase):
    def test_un_texto_corto_se_ve_entero(self):
        r = caption.revisa("Otra vez sin luz.")
        self.assertFalse(r["hay_mas"])
        self.assertEqual(r["visible"], "Otra vez sin luz.")

    def test_el_corte_no_parte_palabras(self):
        texto = "Frenas en la rotonda y la moto hace un ruido que no hacía. " * 4
        r = caption.revisa(texto)
        self.assertTrue(r["hay_mas"])
        self.assertLessEqual(len(r["visible"]), caption.VENTANA)
        self.assertTrue(texto.startswith(r["visible"]))
        self.assertEqual(texto[len(r["visible"])], " ")

    def test_la_primera_frase_que_no_cabe(self):
        texto = ("Cuando una reforma se alarga y nadie te explica por qué, lo normal es pensar que te están "
                 "tomando el pelo, y muchas veces no es así. Te cuento.")
        self.assertEqual(estado(texto, "ANTES DEL MÁS"), ["OJO"])

    def test_empezar_saludando(self):
        for texto in ("Hola, familia. Hoy toca hablar de frenos.", "Hoy quiero contaros algo del taller."):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "ANTES DEL MÁS"), ["OJO"])

    def test_buenas_noticias_no_es_un_saludo(self):
        self.assertEqual(estado("Buenas noticias: ya abrimos los sábados.", "ANTES DEL MÁS"), ["BIEN"])

    def test_la_ventana_no_corta_una_palabra_que_cabe(self):
        frase = ("Llevo veinte años arreglando motos en el taller y la avería más cara casi siempre "
                 "empezó con un ruido pequeño que nadie quiso oír.")
        frase = frase[:caption.VENTANA - 1] + "."
        r = caption.revisa(frase + " Y sigue el texto.")
        self.assertEqual(r["visible"], frase)

    def test_empezar_con_hashtag_o_mencion(self):
        for texto in ("#taller Hoy cambiamos frenos.", "@vecino Mira esto.", "⭐ Hoy abrimos el taller."):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "ANTES DEL MÁS"), ["OJO"])

    def test_la_ventana_se_puede_cambiar(self):
        r = caption.revisa(BUENO, ventana=40)
        self.assertLessEqual(len(r["visible"]), 40)


class Limites(unittest.TestCase):
    def test_mas_de_2200_caracteres(self):
        self.assertEqual(estado("Palabra " * 300, "LARGO"), ["ARREGLA"])

    def test_seis_hashtags_son_demasiados(self):
        texto = "Cambio de pastillas.\n\n#a1 #b2 #c3 #d4 #e5 #f6"
        self.assertEqual(estado(texto, "HASHTAGS"), ["ARREGLA"])

    def test_cinco_hashtags_valen(self):
        texto = "Cambio de pastillas de freno en una tarde.\n\n#frenos #motos #taller #mataro #mecanica"
        self.assertEqual(estado(texto, "HASHTAGS"), ["BIEN"])

    def test_hashtags_genericos_o_repetidos(self):
        for texto in ("Cambio de frenos.\n\n#viral #frenos", "Cambio de frenos.\n\n#ParaTi #frenos",
                      "Cambio de frenos.\n\n#Taller #taller"):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "HASHTAGS"), ["OJO"])

    def test_hashtags_en_la_parte_que_se_ve(self):
        self.assertEqual(estado("Cambio de #frenos en una tarde.", "HASHTAGS"), ["OJO"])

    def test_mas_de_veinte_menciones(self):
        # 20 es el límite de la API de Meta (lo que usan las herramientas para programar).
        texto = "Gracias a " + " ".join(f"@persona{i}" for i in range(21))
        self.assertEqual(estado(texto, "MENCIONES"), ["OJO"])

    def test_hashtags_pegados_a_la_ultima_linea_no_estan_en_la_parte_que_se_ve(self):
        for texto in ("Frenos nuevos en una tarde.\n#frenos #motos", "Frenos nuevos en una tarde. #frenos #motos"):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "HASHTAGS"), ["BIEN"])

    def test_repetidos_sin_mirar_mayusculas(self):
        self.assertEqual(estado("Cambio de frenos.\n\n#Taller #taller", "HASHTAGS"), ["OJO"])


class Enlaces(unittest.TestCase):
    def test_un_enlace_en_el_texto_no_se_pulsa(self):
        for texto in ("Pide cita en tallerdemotos.es/cita", "Todo en https://ejemplo.com", "Mira www.ejemplo.es"):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "ENLACES"), ["OJO"])

    def test_enlaces_acortados(self):
        for texto in ("Todo en linktr.ee/tallerdemotos", "La guía: bit.ly/guia-frenos"):
            with self.subTest(texto):
                self.assertEqual(estado(texto, "ENLACES"), ["OJO"])

    def test_un_espacio_que_falta_no_es_un_enlace(self):
        self.assertEqual(estado("Estaba frío por arriba.Es aire, no la caldera.", "ENLACES"), ["BIEN"])

    def test_un_correo_no_es_un_enlace(self):
        self.assertEqual(estado("Escríbeme a hola@tallerdemotos.es si quieres cita.", "ENLACES"), ["BIEN"])


class ElCierre(unittest.TestCase):
    def test_dos_peticiones_se_pisan(self):
        texto = "Tres cosas que miro antes de comprar una moto usada.\n\nGuárdalo y compártelo con quien la busque."
        r = caption.revisa(texto)
        self.assertEqual(estado(texto, "CIERRE"), ["OJO"])
        self.assertEqual(set(r["peticiones"]), {"guardar", "compartir"})

    def test_una_peticion_vale(self):
        self.assertEqual(estado("Pastillas nuevas en una tarde.\n\nPide cita por WhatsApp.", "CIERRE"), ["BIEN"])

    def test_acabar_con_una_pregunta_vale(self):
        self.assertEqual(estado(BUENO, "CIERRE"), ["BIEN"])

    def test_no_pedir_nada_es_una_nota_no_un_fallo(self):
        texto = "Una casa vieja con humedad tiene arreglo.\n\nCasi siempre empieza por una tubería que nadie mira."
        r = caption.revisa(texto)
        self.assertEqual(estado(texto, "CIERRE"), ["NOTA"])
        self.assertEqual(r["veredicto"], "LISTO")

    def test_cada_cierre_de_la_ficha_cuenta(self):
        for texto, tipo in (("Ven a vernos el sábado.", "venir"), ("Pásate por el taller.", "venir"),
                            ("Mándame un WhatsApp.", "escribir"), ("Pide presupuesto.", "llamar o reservar"),
                            ("Haz tu reserva por teléfono.", "llamar o reservar"),
                            ("Escribe «FRENOS» en los comentarios.", "comentar"),
                            ("Contadme qué haríais.", "comentar"),
                            ("La guía completa está en mi perfil.", "ir al enlace del perfil"),
                            ("Y ahora, guárdalo para la próxima vez.", "guardar")):
            with self.subTest(texto):
                self.assertEqual(caption.revisa("Frenos nuevos en una tarde.\n\n" + texto)["peticiones"], [tipo])

    def test_una_pregunta_con_emoji_detras_sigue_siendo_pregunta(self):
        for final in ("¿Tú cada cuánto los cambias? 👇", "¿Tú cada cuánto los cambias? @tallerdemotos",
                      "(¿Tú cada cuánto los cambias?)"):
            with self.subTest(final):
                self.assertEqual(estado("Frenos nuevos en una tarde.\n\n" + final, "CIERRE"), ["BIEN"])

    def test_contar_algo_no_es_pedirlo(self):
        for texto in ("Un cliente me comenta que la moto tira a la derecha.",
                      "Mi vecino comparte piso con dos mecánicos.",
                      "Una descarga eléctrica no avisa.",
                      "Mi abuela guarda las recetas en una libreta.",
                      "Mi cuñado comenta siempre lo mismo.",
                      "Reservar con tiempo es clave.",
                      "Sigue siendo caro.",
                      "Llama la atención que nadie lo revise.",
                      "Descarga eléctrica: ojo con los enchufes viejos.",
                      "Guarda relación con el aceite.",
                      "Llevo veinte años en el taller. Comparte piso con mi socio."):
            with self.subTest(texto):
                self.assertEqual(caption.revisa(texto)["peticiones"], [])


class PalabraClave(unittest.TestCase):
    def test_una_palabra_en_mayusculas(self):
        self.assertEqual(estado("La lista de revisión de tu moto.\n\nComenta ACEITE y te la mando.",
                                "PALABRA CLAVE"), ["BIEN"])

    def test_con_tilde_conviene_comprobarla(self):
        self.assertEqual(estado("La lista.\n\nComenta GUÍA y te la mando.", "PALABRA CLAVE"), ["OJO"])

    def test_varias_palabras_cuestan_de_escribir(self):
        self.assertEqual(estado("La lista de revisión.\n\nComenta «la lista completa» y te la mando.",
                                "PALABRA CLAVE"), ["OJO"])


class Busqueda(unittest.TestCase):
    def test_sin_tildes_ni_mayusculas(self):
        texto = "Taller de motos en Mataró desde hace veinte años."
        self.assertEqual(estado(texto, "BÚSQUEDA", buscar=["taller de motos", "Mataro"]), ["BIEN", "BIEN"])

    def test_en_un_hashtag_no_cuenta(self):
        self.assertEqual(estado("Frenos nuevos en una tarde.\n\n#Mataró", "BÚSQUEDA", buscar=["Mataró"]), ["OJO"])

    def test_lo_que_no_esta(self):
        self.assertEqual(estado("Frenos nuevos en una tarde.", "BÚSQUEDA", buscar=["taller de motos"]), ["OJO"])


class Emojis(unittest.TestCase):
    def test_se_cuentan_enteros(self):
        mecanico = chr(0x1F468) + chr(0x200D) + chr(0x1F527)
        pulgar = chr(0x1F44D) + chr(0x1F3FD)
        bandera = chr(0x1F1EA) + chr(0x1F1F8)
        uno = "1" + chr(0xFE0F) + chr(0x20E3)
        self.assertEqual(caption.cuenta_emojis(f"Hoy {mecanico} y {pulgar}"), 2)
        self.assertEqual(caption.cuenta_emojis(f"{bandera} {uno}"), 2)


class LineaDeOrdenes(unittest.TestCase):
    def ejecuta(self, texto, *extra):
        return subprocess.run([sys.executable, str(RUTA), "-", *extra], input=texto,
                              capture_output=True, text=True, encoding="utf-8")

    def test_texto_bueno(self):
        r = self.ejecuta(BUENO)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("LO QUE SE VE ANTES DEL «MÁS»", r.stdout)

    def test_si_hay_que_arreglar_sale_con_error(self):
        self.assertEqual(self.ejecuta("Palabra " * 300).returncode, 1)

    def test_vacio(self):
        self.assertEqual(self.ejecuta("   ").returncode, 2)

    def test_json_y_bom(self):
        r = self.ejecuta(chr(0xFEFF) + BUENO, "--json", "--buscar", "aceite")
        self.assertEqual(r.returncode, 0, r.stderr)
        datos = json.loads(r.stdout)
        self.assertTrue(datos["visible"].startswith("¿Cada"))
        self.assertIn(datos["veredicto"], ("LISTO", "REVÍSALO"))


if __name__ == "__main__":
    unittest.main()

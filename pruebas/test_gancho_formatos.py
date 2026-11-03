"""
Pruebas del puntuador de ganchos con los dos formatos (reel y post), y de los
ejemplos del recetario de brigada-reel.

Los ganchos son inventados, de oficios distintos: taller, obra, peluquería y
electricidad.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "brigada-reel"
spec = importlib.util.spec_from_file_location("gancho_formatos", SKILL / "scripts" / "puntua_gancho.py")
gancho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gancho)


def veredicto(texto, formato="reel"):
    return gancho.puntua(texto, formato)[2]


def avisos(texto, formato="reel"):
    return gancho.puntua(texto, formato)[3]


class LaEscenaEsConcreta(unittest.TestCase):
    def test_dos_detalles_hacen_una_escena(self):
        nota, detalle = gancho.mira_concrecion("Frenas y la rueda de delante hace un ruido raro")
        self.assertGreaterEqual(nota, 60)
        self.assertIn("ruido", detalle)

    def test_un_detalle_y_alguien_dentro_tambien(self):
        self.assertGreaterEqual(gancho.mira_concrecion("¿Cuánto hace que no purgas tu caldera?")[0], 60)

    def test_la_escena_tambien_en_plural(self):
        self.assertGreaterEqual(gancho.mira_concrecion("Enchufes quemados detrás del sofá")[0], 60)

    def test_un_cartel_en_mayusculas_no_son_nombres_propios(self):
        self.assertEqual(gancho.mira_concrecion("LA IMPORTANCIA DE LA COMUNICACIÓN")[0], 15)
        self.assertEqual(gancho.puntua("LA IMPORTANCIA DE LA COMUNICACIÓN", "post")[2], "FLOJO")

    def test_una_palabra_suelta_no_basta(self):
        nota, detalle = gancho.mira_concrecion("La importancia de la cocina")
        self.assertEqual(nota, 15)
        self.assertIn("suelto", detalle)

    def test_nombrar_el_oficio_no_es_concreto(self):
        self.assertEqual(gancho.mira_concrecion("Lo que pasa con los clientes en la obra")[0], 15)

    def test_lo_abstracto_sigue_siendo_flojo(self):
        self.assertEqual(gancho.mira_concrecion("La importancia de la comunicación")[0], 15)

    def test_numeros_dichos_del_veintiuno_al_veintinueve(self):
        self.assertGreaterEqual(gancho.mira_concrecion("Veintidós años en el taller")[0], 60)


class LaEmocionEsTension(unittest.TestCase):
    def test_la_rabia_pone_algo_en_juego(self):
        self.assertGreaterEqual(gancho.mira_tension("Qué rabia me dio aquella factura")[0], 70)

    def test_sin_tildes_tambien(self):
        self.assertGreaterEqual(gancho.mira_tension("Que verguenza el presupuesto")[0], 70)

    def test_vale_la_pena_no_es_emocion(self):
        self.assertEqual(gancho.mira_tension("Vale la pena una sola visita")[0], 20)

    def test_tampoco_pone_algo_en_juego(self):
        self.assertGreaterEqual(gancho.mira_tension("Tampoco es para tanto")[0], 70)


class PrimeraLineaDePost(unittest.TestCase):
    def test_la_verdad_que_duele_funciona_en_post(self):
        self.assertEqual(veredicto("Lo que te ahorras en tinte de caja lo pagas en la peluquería.", "post"),
                         "FUERTE")

    def test_el_hartazgo_funciona_en_post(self):
        self.assertEqual(veredicto("Estoy harto de ver enchufes quemados detrás del sofá.", "post"), "FUERTE")

    def test_corta_y_con_tension_no_basta_para_fuerte(self):
        # Sin nada que se vea y sin hablarle de tú a quien lo lee, sirve para cualquier cuenta.
        for texto in ("Nadie habla de esto nunca.", "Estoy harto de todo esto, de verdad.",
                      "Yo no hago esto nunca."):
            with self.subTest(texto):
                self.assertEqual(veredicto(texto, "post"), "VALE")

    def test_un_post_vacio_no_puntua(self):
        self.assertEqual(gancho.mira_duracion("...", "post")[0], 0)

    def test_la_frase_golpe_no_se_castiga_por_corta(self):
        self.assertNotEqual(veredicto("Otra vez sin luz.", "post"), "FLOJO")
        self.assertTrue(gancho.nota_de_formato("Otra vez sin luz.", "post"))

    def test_lo_flojo_sigue_flojo_en_post(self):
        for texto in ("La importancia de la comunicación en las empresas",
                      "Consejos para tu negocio",
                      "Hoy os traigo cinco consejos para mejorar tu marca"):
            with self.subTest(texto):
                self.assertEqual(veredicto(texto, "post"), "FLOJO")


class GanchoDeReel(unittest.TestCase):
    def test_la_escena_funciona_en_reel(self):
        self.assertEqual(veredicto("Frenas en la rotonda y la moto hace un ruido que no hacía."), "FUERTE")

    def test_el_reel_pide_mas_que_una_frase_golpe(self):
        self.assertEqual(veredicto("Otra vez sin luz."), "FLOJO")
        self.assertEqual(gancho.nota_de_formato("Otra vez sin luz.", "reel"), "")

    def test_reel_es_el_formato_por_defecto(self):
        self.assertEqual(gancho.puntua("Perdí 18.000 € por no firmar un papel.")[1],
                         gancho.puntua("Perdí 18.000 € por no firmar un papel.", "reel")[1])

    def test_formato_desconocido(self):
        with self.assertRaises(ValueError):
            gancho.puntua("Hola", "tiktok")


class LoQueSiempreResta(unittest.TestCase):
    def test_las_frases_gastadas(self):
        for texto in ("Nadie te cuenta esto sobre los frenos.", "El secreto que usan los pintores.",
                      "Esto lo cambia todo en tu baño."):
            with self.subTest(texto):
                self.assertTrue(avisos(texto))
                self.assertNotEqual(veredicto(texto), "FUERTE")

    def test_no_es_solo_x_es_y(self):
        texto = "No es solo un corte de pelo, es una forma de cuidarte."
        self.assertTrue(avisos(texto, "post"))
        self.assertNotEqual(veredicto(texto, "post"), "FUERTE")

    def test_diagnosticar_a_quien_lo_ve(self):
        for texto in ("Si te duele aquí, tienes una hernia.", "Te cruje la rodilla: lo tuyo es artrosis.",
                      "Si te pasa esto al levantarte, tienes una lumbalgia."):
            with self.subTest(texto):
                self.assertTrue(avisos(texto))
                self.assertNotEqual(veredicto(texto), "FUERTE")

    def test_lo_que_no_es_eliminatorio(self):
        for texto in ("Tres cosas que hago cuando un cliente llega con prisa.",
                      "Si tienes tendinitis, no cargues así la caja de herramientas.",
                      "¿Tienes una hernia? Así se levanta peso sin hacerte daño.",
                      "Si nadie te explica la factura de la luz, pregunta esto.",
                      "Si nadie te dice el precio antes, desconfía.",
                      "No es solo por el precio. Es que no me fío del material."):
            with self.subTest(texto):
                self.assertFalse(avisos(texto))

    def test_buenas_practicas_no_es_un_saludo(self):
        self.assertFalse(avisos("Buenas prácticas para pedir presupuesto de una reforma", "post"))
        self.assertTrue(avisos("Buenas, hoy os hablo de reformas", "post"))

    def test_nadie_me_lo_conto_tambien_es_gastada(self):
        self.assertTrue(avisos("Llevo 26 años en hostelería y nadie me contó esto"))


class ElRecetarioPasaSuPropioCorte(unittest.TestCase):
    """Cada ejemplo de references/ganchos.md saca 50 o más en el formato que dice."""

    def formas(self):
        texto = (SKILL / "references" / "ganchos.md").read_text(encoding="utf-8")
        formas = re.split(r"^## \d+\. ", texto, flags=re.M)[1:]
        formas[-1] = formas[-1].split("## Las que no")[0]
        return formas

    def test_los_doce_ejemplos(self):
        formas = self.formas()
        self.assertEqual(len(formas), 12)
        for forma in formas:
            nombre = forma.splitlines()[0]
            ejemplo = re.search(r"\*\*Ejemplo:\*\* «(.+)»\.?\s*$", forma, re.M).group(1)
            formato = re.search(r"\*\*Se puntúa como:\*\* (reel|post)", forma).group(1)
            with self.subTest(nombre):
                total = gancho.puntua(ejemplo, formato)[1]
                self.assertGreaterEqual(total, 50, f"«{ejemplo}» saca {total:.0f} como {formato}")

    def test_los_carteles_del_recetario_caben(self):
        for forma in self.formas():
            cartel = re.search(r"\*\*En pantalla:\*\* (.+)$", forma, re.M).group(1)
            with self.subTest(cartel):
                self.assertLessEqual(len(re.findall(r"[^\W_]+", cartel)), 6)


if __name__ == "__main__":
    unittest.main()

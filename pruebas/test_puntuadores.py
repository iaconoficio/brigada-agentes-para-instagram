"""Pruebas de los puntuadores en español. Se lanzan con:

    python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import json
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def carga(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


gancho = carga("skills/brigada-reel/scripts/puntua_gancho.py", "puntua_gancho")
humaniza = carga("skills/brigada-humano/scripts/humaniza.py", "humaniza")
detecta = carga("skills/brigada-humano/scripts/detecta.py", "detecta")
LEX = json.loads((RAIZ / "skills/brigada-humano/scripts/muletillas.json").read_text(encoding="utf-8"))


class Gancho(unittest.TestCase):
    def test_nadie_cuenta_como_tension(self):
        nota, detalle = gancho.mira_tension("Llevo 26 años en hostelería y nadie me contó esto")
        self.assertGreaterEqual(nota, 70)
        self.assertIn("nadie", detalle)

    def test_tension_sin_tildes(self):
        self.assertGreaterEqual(gancho.mira_tension("Jamas pierdas una reserva")[0], 70)
        self.assertGreaterEqual(gancho.mira_tension("Jamás pierdas una reserva")[0], 70)

    def test_cifra_en_euros(self):
        nota, detalle = gancho.mira_concrecion("Perdí 18.000 € por no firmar un papel")
        self.assertGreaterEqual(nota, 75)
        self.assertIn("18.000", detalle)

    def test_verbo_en_segunda_persona_sin_pronombre(self):
        self.assertEqual(gancho.mira_a_quien("¿Sabes cuánto pierdes cada semana?")[0], 100)

    def test_saludo_y_preambulo_son_eliminatorios(self):
        _, total, veredicto, avisos = gancho.puntua("Hola chicos, hoy os voy a enseñar un truco")
        self.assertEqual(veredicto, "FLOJO")
        self.assertEqual(len(avisos), 2)

    def test_gancho_bueno_es_fuerte(self):
        _, total, veredicto, _ = gancho.puntua("Nunca subas el precio sin hacer esto antes")
        self.assertEqual(veredicto, "FUERTE")


class Humaniza(unittest.TestCase):
    def limpia(self, texto, **kw):
        return humaniza.humaniza(texto, LEX, **kw)

    def test_conserva_emoji_compuesto(self):
        texto, informe = self.limpia("La chef 👩\u200d🍳 de la casa")
        self.assertIn("👩\u200d🍳", texto)
        self.assertEqual(informe["invisibles"], 0)

    def test_quita_invisibles_sueltos(self):
        texto, informe = self.limpia("Hola\u200b mundo\ufeff")
        self.assertEqual(texto, "Hola mundo")
        self.assertEqual(informe["invisibles"], 2)

    def test_raya_a_coma(self):
        texto, _ = self.limpia("Lo probé — y funcionó.")
        self.assertEqual(texto, "Lo probé, y funcionó.")

    def test_raya_de_dialogo(self):
        texto, _ = self.limpia("— ¿Vienes mañana?")
        self.assertEqual(texto, "¿Vienes mañana?")

    def test_cambia_muletillas_con_mayuscula(self):
        texto, _ = self.limpia("En el mundo actual todo va rápido.")
        self.assertEqual(texto, "Hoy todo va rápido.")

    def test_no_toca_enlaces_ni_hashtags(self):
        entrada = "Mira https://ejemplo.com/potenciar y #potenciar"
        texto, _ = self.limpia(entrada)
        self.assertEqual(texto, entrada)

    def test_no_deja_conjunciones_huerfanas(self):
        texto, _ = self.limpia("Gracias. Sígueme para más contenido y no olvides darle like.")
        self.assertEqual(texto.strip(), "Gracias.")

    def test_puntos_suspensivos_siguen_en_minuscula(self):
        texto, _ = self.limpia("Y entonces... pasó lo que pasó.")
        self.assertEqual(texto, "Y entonces... pasó lo que pasó.")

    def test_mantener_comillas(self):
        texto, _ = self.limpia("Dijo “vale”.", mantener_comillas=True)
        self.assertIn("“vale”", texto)

    def test_las_comillas_curvas_se_quedan_por_defecto(self):
        texto, _ = self.limpia("Dijo “vale” y se fue.")
        self.assertIn("“vale”", texto)

    def test_comillas_rectas_si_se_piden(self):
        texto, _ = self.limpia("Dijo “vale”.", mantener_comillas=False)
        self.assertIn('"vale"', texto)


class Detecta(unittest.TestCase):
    HUMANO = ("Llevo 26 años en La Tasqueta y te digo una cosa: el martes pasado perdí tres mesas "
              "por no contestar un WhatsApp. Tres. Eran 12 personas.\nDesde entonces apunto las "
              "reservas por voz. Tardo dos minutos. Mi libreta de papel lleva veinte años diciéndome "
              "lo mismo, pero vale, a veces uno no escucha.\n¿Lo mejor? Que ya no se me escapa "
              "ninguna. Si tienes un bar en Caldes o donde sea, pruébalo esta semana y me cuentas.")
    IA = ("En el mundo actual, la inteligencia artificial juega un papel crucial en los negocios. "
          "No es solo una herramienta, es una revolución que permite potenciar tu marca y "
          "desbloquear infinitas posibilidades. Cabe destacar que la creatividad, la estrategia y "
          "la constancia son fundamentales. Asimismo, resulta clave optimizar cada proceso de la "
          "empresa para maximizar resultados de forma sostenible.")

    def test_texto_humano_pasa(self):
        _, total, veredicto = detecta.analiza(self.HUMANO, LEX)
        self.assertEqual(veredicto, "PASA")

    def test_texto_de_ia_no_pasa(self):
        _, total, veredicto = detecta.analiza(self.IA, LEX)
        self.assertEqual(veredicto, "SUENA A IA")

    def test_comillas_curvas_no_restan(self):
        nota, _ = detecta.mira_huella("Me dijo “vale” y se fue.")
        self.assertEqual(nota, 100.0)

    def test_humanizar_mejora_la_nota(self):
        limpio, _ = humaniza.humaniza(self.IA, LEX)
        self.assertGreater(detecta.analiza(limpio, LEX)[1], detecta.analiza(self.IA, LEX)[1])


if __name__ == "__main__":
    unittest.main()

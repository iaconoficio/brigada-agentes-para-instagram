"""
Pruebas de tiempos.py, el cronómetro del guion de brigada-reel.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import pathlib
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RUTA = RAIZ / "skills/brigada-reel/scripts/tiempos.py"
spec = importlib.util.spec_from_file_location("tiempos", RUTA)
tiempos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tiempos)

GUION = """# Reel de ejemplo, taller inventado
Llevo 22 años de taller y esto lo veo cada semana. [plano: manos con grasa]
Llega alguien con la moto parada desde el verano.
La batería, muerta.
Y nadie le dijo que bastaba con arrancarla una vez al mes.
Arráncala una vez al mes. Diez minutos. Ya está.
"""


class Cronometro(unittest.TestCase):
    def test_las_indicaciones_no_cuentan(self):
        self.assertEqual(tiempos.hablado("Hola. [plano: manos] (sonríe) Adiós."), "Hola. Adiós.")

    def test_comentarios_y_lineas_vacias_fuera(self):
        self.assertEqual(len(tiempos.planos(GUION)), 5)

    def test_tiempo_por_palabras(self):
        r = tiempos.cronometra("uno dos tres cuatro cinco seis siete ocho", ppm=160)
        self.assertAlmostEqual(r["total"], 3.0, places=1)

    def test_las_cifras_cuentan_mas(self):
        self.assertGreater(tiempos.palabras_dichas("Perdí 18.000 euros"), 3)

    def test_avisa_del_gancho_largo(self):
        r = tiempos.cronometra("Esto es un gancho larguísimo que nadie va a escuchar hasta el final de verdad.\nFin.")
        self.assertTrue(any(a.startswith("GANCHO LARGO") for a in r["avisos"]))

    def test_avisa_del_plano_largo(self):
        largo = " ".join(["palabra"] * 14)
        r = tiempos.cronometra("Gancho corto.\n" + largo)
        self.assertTrue(any(a.startswith("PLANO LARGO") for a in r["avisos"]))

    def test_avisa_del_tramo_plano(self):
        r = tiempos.cronometra("Mira esto.\nEs importante.\nPiénsalo bien.\nDe verdad que sí.")
        self.assertTrue(any(a.startswith("TRAMO PLANO") for a in r["avisos"]))

    def test_la_escena_corta_el_tramo_plano(self):
        r = tiempos.cronometra("Mira esto.\nEs importante.\nToca la rueda de delante.\nDe verdad que sí.")
        self.assertFalse(any(a.startswith("TRAMO PLANO") for a in r["avisos"]))

    def test_avisa_si_se_aleja_del_objetivo(self):
        r = tiempos.cronometra(GUION, objetivo=60)
        self.assertTrue(any(a.startswith("DURACIÓN") for a in r["avisos"]))

    def test_una_indicacion_sola_no_es_un_plano(self):
        r = tiempos.cronometra("Gancho corto.\n[plano: manos en el motor]\nY sigue.")
        self.assertEqual(len(r["planos"]), 2)

    def test_una_indicacion_corta_el_tramo_plano(self):
        r = tiempos.cronometra("Mira esto.\nEs importante.\n[plano: el motor abierto]\nPiénsalo bien.\nDe verdad.")
        self.assertFalse(any(a.startswith("TRAMO PLANO") for a in r["avisos"]))

    def test_los_carteles_no_cuentan_como_tiempo(self):
        con = tiempos.cronometra("> CARTEL DEL GANCHO\nUno dos tres cuatro.")
        sin = tiempos.cronometra("Uno dos tres cuatro.")
        self.assertEqual(con["total"], sin["total"])
        self.assertEqual(con["carteles"], ["CARTEL DEL GANCHO"])

    def test_avisa_del_cartel_largo(self):
        r = tiempos.cronometra("> ESTO ES UN CARTEL DEMASIADO LARGO PARA LEERLO\nHola.")
        self.assertTrue(any(a.startswith("CARTEL LARGO") for a in r["avisos"]))

    def test_el_ritmo_por_defecto_es_el_del_puntuador(self):
        self.assertEqual(tiempos.PPM, 165)

    def test_un_ritmo_de_cero_no_vale(self):
        with self.assertRaises(ValueError):
            tiempos.cronometra("Hola.", ppm=0)
        r = subprocess.run([sys.executable, str(RUTA), "-", "--ppm", "0"], input="Hola.",
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_linea_de_ordenes(self):
        r = subprocess.run([sys.executable, str(RUTA), "-", "--objetivo", "15"], input=GUION,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("TIEMPOS DEL REEL", r.stdout)


class CifrasDichas(unittest.TestCase):
    def test_cada_cifra_cuenta_lo_que_se_tarda_en_decir(self):
        casos = {
            "22": 1,          # veintidós
            "45": 3,          # cuarenta y cinco
            "600": 1,         # seiscientos
            "18.000": 2,      # dieciocho mil
            "1.250": 3,       # mil doscientos cincuenta
            "2026": 3,        # dos mil veintiséis
            "18,5": 3,        # dieciocho coma cinco
            "3,05": 4,        # tres coma cero cinco
            "9:30": 3,        # nueve y treinta
            "9:30.5": 3,      # no se cae con décimas
        }
        for cifra, esperado in casos.items():
            with self.subTest(cifra):
                self.assertEqual(tiempos.palabras_de_cifra(cifra), esperado)

    def test_los_simbolos_tambien_se_dicen(self):
        self.assertEqual(tiempos.palabras_dichas("50 %"), 3)      # cincuenta por ciento
        self.assertEqual(tiempos.palabras_dichas("300 €"), 2)     # trescientos euros
        self.assertEqual(tiempos.palabras_dichas("1º"), 1)        # primero


class MarcasYEtiquetas(unittest.TestCase):
    def test_las_marcas_de_tiempo_no_se_dicen(self):
        for linea in ("0:00-0:03 No siempre es la rueda.", "[0:03] No siempre es la rueda.",
                      "00:03 No siempre es la rueda.", "0:00 " + chr(0x2013) + " 0:03 No siempre es la rueda.",
                      "1:03.5 No siempre es la rueda.", "00:00:03 No siempre es la rueda.",
                      "1:05 - No siempre es la rueda."):
            with self.subTest(linea):
                self.assertEqual(tiempos.clasifica(linea), ("dicho", "No siempre es la rueda."))

    def test_una_hora_dicha_se_queda(self):
        self.assertEqual(tiempos.clasifica("9:30 y la moto no arranca."), ("dicho", "9:30 y la moto no arranca."))

    def test_las_etiquetas_no_se_dicen(self):
        self.assertEqual(tiempos.clasifica("GANCHO: No siempre es la rueda."), ("dicho", "No siempre es la rueda."))
        self.assertEqual(tiempos.clasifica("VOZ EN OFF: Mira esto."), ("dicho", "Mira esto."))

    def test_lo_que_parece_etiqueta_pero_se_dice(self):
        self.assertEqual(tiempos.clasifica("IVA: lo pagas tú."), ("dicho", "IVA: lo pagas tú."))

    def test_un_cartel_entre_corchetes_es_cartel(self):
        r = tiempos.cronometra("[EN PANTALLA: 600 € DE GRÚA] Seiscientos euros de grúa.")
        self.assertEqual(r["carteles"], ["600 € DE GRÚA"])
        self.assertEqual(r["planos"][0]["dicho"], "Seiscientos euros de grúa.")

    def test_sin_nada_no_avisa_de_duracion(self):
        self.assertEqual(tiempos.cronometra("# solo una nota", objetivo=30)["avisos"], [])

    def test_las_etiquetas_de_cartel_son_carteles(self):
        for linea in ("EN PANTALLA: NO SIEMPRE ES LA RUEDA", "Cartel: NO SIEMPRE ES LA RUEDA",
                      "0:00 > NO SIEMPRE ES LA RUEDA", "CARTEL 1: NO SIEMPRE ES LA RUEDA",
                      "TEXTO EN PANTALLA 2: NO SIEMPRE ES LA RUEDA", "SUPER: NO SIEMPRE ES LA RUEDA"):
            with self.subTest(linea):
                self.assertEqual(tiempos.clasifica(linea), ("cartel", "NO SIEMPRE ES LA RUEDA"))

    def test_un_guion_con_marcas_dura_lo_mismo_que_sin_ellas(self):
        con = tiempos.cronometra("0:00-0:03 GANCHO: Uno dos tres.\n0:03-0:06 Cuatro cinco seis.")
        sin = tiempos.cronometra("Uno dos tres.\nCuatro cinco seis.")
        self.assertEqual(con["total"], sin["total"])


class LecturaDelGuion(unittest.TestCase):
    def test_no_se_cae_con_un_tiempo_con_decimas(self):
        r = tiempos.cronometra("Gancho corto.\n1:03.5 Y aquí cambio el filtro.")
        self.assertEqual(r["planos"][1]["dicho"], "Y aquí cambio el filtro.")

    def test_un_archivo_con_bom(self):
        r = tiempos.cronometra(chr(0xFEFF) + "# nota\nGancho corto.\nY sigue.")
        self.assertEqual(r["planos"][0]["dicho"], "Gancho corto.")

    def test_una_pausa_no_es_una_imagen(self):
        r = tiempos.cronometra("Mira esto.\n(pausa)\nEs importante.\nPiénsalo bien.")
        self.assertTrue(any(a.startswith("TRAMO PLANO") for a in r["avisos"]))

    def test_el_tramo_plano_se_avisa_entero(self):
        r = tiempos.cronometra("Mira esto.\nEs importante.\nPiénsalo bien.\nDe verdad.\nY ahora qué.")
        tramos = [a for a in r["avisos"] if a.startswith("TRAMO PLANO")]
        self.assertEqual(len(tramos), 1)
        self.assertIn("del plano 1 al 5", tramos[0])


class ReelSinVoz(unittest.TestCase):
    GUION = "> NO SIEMPRE ES LA RUEDA\n[plano: manos en el manillar]\n> MIRA LA DIRECCIÓN\n> 22 AÑOS DE TALLER\n"

    def test_solo_carteles_tambien_se_cronometra(self):
        r = tiempos.cronometra(self.GUION)
        self.assertEqual(r["modo"], "carteles")
        self.assertEqual(len(r["planos"]), 3)
        self.assertGreaterEqual(min(p["segundos"] for p in r["planos"]), tiempos.CARTEL_MIN)
        self.assertGreater(r["total"], 0)

    def test_la_linea_de_ordenes_no_falla_sin_voz(self):
        r = subprocess.run([sys.executable, str(RUTA), "-"], input=self.GUION,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sin voz", r.stdout)


if __name__ == "__main__":
    unittest.main()

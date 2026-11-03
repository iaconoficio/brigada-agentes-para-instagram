"""
Pruebas de semana.py, la tabla y el calendario de brigada-plan.

Los planes son inventados (un taller de motos).

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import datetime as dt
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HOY = dt.date(2026, 10, 28)
RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "brigada-plan"
RUTA = SKILL / "scripts" / "semana.py"
EJEMPLO = SKILL / "assets" / "semana-ejemplo.json"
spec = importlib.util.spec_from_file_location("semana", RUTA)
semana = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semana)


def plan(*piezas, **extra):
    return {"semana": "2026-11-04", **extra, "piezas": list(piezas)}


def tipos(avisos):
    return [t for t, _ in avisos]


class Fechas(unittest.TestCase):
    def test_cualquier_dia_lleva_a_su_lunes(self):
        piezas, _ = semana.lee_plan(plan({"dia": "martes", "tema": "Frenos"}))
        self.assertEqual(piezas[0]["fecha"], dt.date(2026, 11, 3))

    def test_dias_con_y_sin_tilde(self):
        for dia, esperado in (("miércoles", 4), ("miercoles", 4), ("Sábado", 7), ("sabado", 7)):
            with self.subTest(dia):
                self.assertEqual(semana.lee_plan(plan({"dia": dia, "tema": "x"}))[0][0]["fecha"].day, esperado)

    def test_se_ordenan_por_dia_y_hora(self):
        piezas, _ = semana.lee_plan(plan({"dia": "jueves", "tema": "b"}, {"dia": "martes", "tema": "a"}))
        self.assertEqual([p["tema"] for p in piezas], ["a", "b"])

    def test_preparar_siempre_va_antes(self):
        piezas, avisos = semana.lee_plan(plan({"dia": "lunes", "tema": "a", "hora": "9:00", "preparar": "domingo"}), HOY)
        self.assertEqual(piezas[0]["preparar"], dt.date(2026, 11, 1))
        self.assertNotIn("ANTES", tipos(avisos))

    def test_lo_que_no_se_entiende_se_dice(self):
        for mal in (plan({"dia": "lunes2", "tema": "x"}), plan({"dia": "lunes", "tema": "x", "hora": "25:00"}),
                    plan({"dia": "lunes", "tema": "x", "formato": "tiktok"}), plan({"dia": "lunes"}),
                    plan({"dia": "lunes", "tema": "   "}), plan({"dia": "lunes", "tema": "x", "vende": "quizá"}),
                    plan({"dia": "lunes", "tema": "x", "pata": "vender"}), plan({"dia": "lunes", "tema": "x"}, venta_cada=True),
                    plan({"dia": "lunes", "tema": "x"}, version=0), {"piezas": [{"dia": "lunes", "tema": "x"}]},
                    {"semana": "mañana", "piezas": [{"dia": "lunes", "tema": "x"}]}, {"piezas": []}):
            with self.subTest(mal), self.assertRaises(semana.PlanMal):
                semana.lee_plan(mal)


class LoQueSeEscribeAMano(unittest.TestCase):
    def test_vende_si_o_no(self):
        for valor, esperado in (("no", False), ("false", False), ("sí", True), ("si", True), (True, True), (None, False)):
            with self.subTest(valor):
                self.assertEqual(semana.lee_plan(plan({"dia": "lunes", "tema": "x", "vende": valor}), HOY)[0][0]["vende"],
                                 esperado)

    def test_venta_con_el_texto_de_la_ficha(self):
        for texto, n in (("uno de cada tres", 3), ("En todos los posts", 1), ("solo cuando haya algo que ofrecer", 0)):
            with self.subTest(texto):
                self.assertEqual(semana.venta_de(texto), n)

    def test_un_salto_de_linea_no_rompe_la_tabla(self):
        piezas, avisos = semana.lee_plan(plan({"dia": "lunes", "hora": "9:00", "tema": "Frenos\ny discos"}), HOY)
        self.assertIn("| Frenos y discos |", semana.tabla(piezas, avisos))


class Avisos(unittest.TestCase):
    def test_dos_el_mismo_dia(self):
        _, avisos = semana.lee_plan(plan({"dia": "martes", "tema": "a", "hora": "10:00"},
                                         {"dia": "martes", "tema": "b", "hora": "19:00", "formato": "reel"}))
        self.assertIn("MISMO DÍA", tipos(avisos))

    def test_las_historias_no_cuentan_como_mismo_dia_ni_seguidas(self):
        _, avisos = semana.lee_plan(plan({"dia": "martes", "tema": "a", "hora": "19:00", "formato": "reel"},
                                         {"dia": "martes", "tema": "b", "hora": "10:00", "formato": "historia"},
                                         {"dia": "jueves", "tema": "c", "hora": "19:00", "formato": "carrusel"}), HOY)
        self.assertNotIn("MISMO DÍA", tipos(avisos))
        _, avisos = semana.lee_plan(plan({"dia": "martes", "tema": "a", "hora": "19:00", "formato": "reel"},
                                         {"dia": "miércoles", "tema": "b", "hora": "10:00", "formato": "historia"},
                                         {"dia": "jueves", "tema": "c", "hora": "19:00", "formato": "reel"}), HOY)
        self.assertIn("SEGUIDAS", tipos(avisos))

    def test_pocas_piezas_y_vender_una_de_cada_tres(self):
        piezas = [{"dia": "lunes", "tema": "a", "hora": "9:00"}, {"dia": "jueves", "tema": "b", "hora": "9:00", "vende": True}]
        self.assertIn("VENTA", tipos(semana.lee_plan(plan(*piezas, venta_cada=3), HOY)[1]))

    def test_fechas_pasadas(self):
        self.assertIn("PASADO", tipos(semana.lee_plan(plan({"dia": "lunes", "tema": "a", "hora": "9:00"}),
                                                       dt.date(2026, 11, 20))[1]))

    def test_mas_ventas_de_las_que_pide_la_ficha(self):
        piezas = [{"dia": d, "tema": d, "hora": "19:00", "vende": True} for d in ("lunes", "miércoles", "viernes")]
        self.assertIn("VENTA", tipos(semana.lee_plan(plan(*piezas, venta_cada=3))[1]))
        self.assertNotIn("VENTA", tipos(semana.lee_plan(plan(*piezas, venta_cada=1))[1]))
        self.assertNotIn("VENTA", tipos(semana.lee_plan(plan(*piezas, venta_cada=0))[1]))

    def test_sin_hora(self):
        self.assertIn("SIN HORA", tipos(semana.lee_plan(plan({"dia": "martes", "tema": "a"}))[1]))

    def test_preparar_tarde(self):
        _, avisos = semana.lee_plan(plan({"dia": "martes", "tema": "a", "hora": "19:00", "preparar": "martes"}), HOY)
        self.assertIn("ANTES", tipos(avisos))

    def test_dos_seguidas_del_mismo_formato_es_una_nota(self):
        _, avisos = semana.lee_plan(plan({"dia": "martes", "tema": "a", "hora": "19:00", "formato": "reel"},
                                         {"dia": "jueves", "tema": "b", "hora": "19:00", "formato": "reel"}))
        self.assertIn("SEGUIDAS", tipos(avisos))

    def test_el_ejemplo_no_tiene_avisos(self):
        _, avisos = semana.lee_plan(json.loads(EJEMPLO.read_text(encoding="utf-8")), HOY)
        self.assertEqual(avisos, [])


class Calendario(unittest.TestCase):
    AHORA = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc)

    def ics(self, repaso=False, cambio=None, version=1):
        datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        if cambio:
            datos["piezas"][1]["tema"] = cambio
        piezas, _ = semana.lee_plan(datos, HOY)
        return semana.calendario(piezas, repaso=repaso, ahora=self.AHORA, version=version)

    def test_estructura(self):
        texto = self.ics()
        self.assertTrue(texto.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(texto.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(texto.count("BEGIN:VEVENT"), texto.count("END:VEVENT"))
        self.assertNotIn("\n", texto.replace("\r\n", ""))

    def test_preparar_y_publicar(self):
        texto = self.ics()
        self.assertEqual(texto.count("BEGIN:VEVENT"), 5)        # 3 publicar + 2 preparar
        self.assertIn("DTSTART:20261103T190000", texto)
        self.assertIn("DTSTART;VALUE=DATE:20261102", texto)       # preparar el lunes
        self.assertEqual(texto.count("BEGIN:VALARM"), 5)          # todos avisan
        self.assertIn("TRIGGER:PT9H", texto)                       # los de todo el día, a las 9
        self.assertIn("TRIGGER:-PT30M", texto)

    def test_repaso_a_las_48_horas(self):
        texto = self.ics(repaso=True)
        self.assertEqual(texto.count("BEGIN:VEVENT"), 8)
        self.assertIn("DTSTART;VALUE=DATE:20261105", texto)

    def test_lineas_de_75_bytes_como_mucho(self):
        largo = {"semana": "2026-11-02", "piezas": [{"dia": "martes", "hora": "19:00", "tema": "ñ" * 120}]}
        texto = semana.calendario(semana.lee_plan(largo, HOY)[0], ahora=self.AHORA)
        for linea in texto.split("\r\n"):
            self.assertLessEqual(len(linea.encode("utf-8")), 75)
        desdoblado = texto.replace("\r\n ", "")
        self.assertIn("ñ" * 120, desdoblado)

    def test_comas_y_puntos_y_coma_escapados(self):
        p = {"semana": "2026-11-02", "piezas": [{"dia": "martes", "hora": "19:00", "tema": "Frenos, pastillas; discos"}]}
        texto = semana.calendario(semana.lee_plan(p, HOY)[0], ahora=self.AHORA).replace("\r\n ", "")
        self.assertIn("Frenos\\, pastillas\\; discos", texto)

    def test_mismo_plan_mismos_identificadores(self):
        self.assertEqual(self.ics(), self.ics())

    def test_corregir_el_tema_no_duplica_el_evento(self):
        uids = lambda t: sorted(l for l in t.split("\r\n") if l.startswith("UID:"))
        v1, v2 = self.ics(), self.ics(cambio="Otro tema", version=2)
        self.assertEqual(uids(v1), uids(v2))
        self.assertIn("SEQUENCE:1", v2)

    def test_un_retorno_de_carro_se_escapa(self):
        p = {"semana": "2026-11-02", "piezas": [{"dia": "martes", "hora": "19:00", "tema": "a", "nota": "uno\rdos"}]}
        texto = semana.calendario(semana.lee_plan(p, HOY)[0], ahora=self.AHORA)
        self.assertNotIn("\r", texto.replace("\r\n", ""))


class LineaDeOrdenes(unittest.TestCase):
    def test_tabla_y_calendario(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ics = pathlib.Path(carpeta) / "semana.ics"
            r = subprocess.run([sys.executable, str(RUTA), str(EJEMPLO), "--ics", str(ics), "--repaso"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("| martes 03/11 | 19:00 | reel |", r.stdout)
            self.assertTrue(ics.read_text(encoding="utf-8").startswith("BEGIN:VCALENDAR"))

    def test_plan_mal_escrito(self):
        r = subprocess.run([sys.executable, str(RUTA), "-"], input="{no es json",
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_errores_de_archivo_sin_traceback(self):
        with tempfile.TemporaryDirectory() as carpeta:
            latin = pathlib.Path(carpeta) / "latin.json"
            latin.write_bytes('{"semana": "2026-11-02", "piezas": [{"dia": "sábado", "tema": "x"}]}'.encode("latin-1"))
            casos = ([str(pathlib.Path(carpeta) / "no-existe.json")], [str(latin)],
                     [str(EJEMPLO), "--ics", str(pathlib.Path(carpeta) / "no" / "existe.ics")])
            for args in casos:
                with self.subTest(args):
                    r = subprocess.run([sys.executable, str(RUTA), *args], capture_output=True, text=True,
                                       encoding="utf-8")
                    self.assertEqual(r.returncode, 2)
                    self.assertNotIn("Traceback", r.stderr)

    def test_json(self):
        r = subprocess.run([sys.executable, str(RUTA), str(EJEMPLO), "--json"],
                           capture_output=True, text=True, encoding="utf-8")
        datos = json.loads(r.stdout)
        self.assertEqual(datos["piezas"][0]["fecha"], "2026-11-03")
        self.assertEqual(datos["piezas"][2]["pata"], "ofrecer")


if __name__ == "__main__":
    unittest.main()

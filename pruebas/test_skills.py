"""
Pruebas de los agentes de La Brigada (skills/*/SKILL.md).

Comprueban que cada agente está bien formado y que la ficha cumple su
contrato con el resto de la brigada:
  1. Cabecera válida: nombre igual que la carpeta, descripción de 200 caracteres como mucho y sin < >.
  2. Los archivos que cita cada SKILL.md existen.
  3. Sin rayas largas ni caracteres invisibles en los textos.
  4. La plantilla de la ficha tiene todas las secciones que promete el contrato.

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILLS = RAIZ / "skills"
FICHA = SKILLS / "brigada-ficha"


def agentes():
    return sorted(p for p in SKILLS.glob("*/SKILL.md"))


def cabecera(texto):
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        return None
    datos = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()
    return datos


class CabeceraDeLosAgentes(unittest.TestCase):
    def test_hay_al_menos_un_agente(self):
        self.assertTrue(agentes(), "no hay ningún skills/*/SKILL.md")

    def test_cabecera_valida(self):
        for ruta in agentes():
            with self.subTest(ruta.parent.name):
                datos = cabecera(ruta.read_text(encoding="utf-8"))
                self.assertIsNotNone(datos, "falta la cabecera entre --- y ---")
                self.assertEqual(datos.get("name"), ruta.parent.name, "el nombre no coincide con la carpeta")
                self.assertRegex(datos["name"], r"^[a-z0-9-]{1,64}$")
                descripcion = datos.get("description", "")
                self.assertTrue(descripcion, "falta la descripción")
                # La ayuda de Claude pone 200 caracteres como máximo para la descripción de una skill subida a la app.
                self.assertLessEqual(len(descripcion), 200, "la descripción pasa de 200 caracteres (máximo de la app de Claude)")
                self.assertNotRegex(descripcion, r"[<>]", "la descripción no puede llevar < ni >")

    def test_los_archivos_citados_existen(self):
        for ruta in agentes():
            texto = ruta.read_text(encoding="utf-8")
            for citado in sorted(set(re.findall(r"`((?:references|assets|scripts)/[^`\s]+)`", texto))):
                with self.subTest(agente=ruta.parent.name, archivo=citado):
                    self.assertTrue((ruta.parent / citado).exists(), f"{citado} no existe")


class TipografiaDeLosTextos(unittest.TestCase):
    MALOS = {0x2014: "raya", 0x2013: "semirraya", 0x200B: "invisible", 0x200C: "invisible",
             0x200D: "invisible", 0x2060: "invisible", 0xFEFF: "BOM", 0x00A0: "espacio duro"}

    def test_sin_rayas_ni_invisibles(self):
        for ruta in sorted(SKILLS.rglob("*.md")):
            texto = ruta.read_text(encoding="utf-8")
            for codigo, nombre in self.MALOS.items():
                with self.subTest(archivo=str(ruta.relative_to(RAIZ)), caracter=nombre):
                    self.assertNotIn(chr(codigo), texto)


class ContratoDeLaFicha(unittest.TestCase):
    def setUp(self):
        if not (FICHA / "SKILL.md").exists():
            self.skipTest("brigada-ficha todavía no existe")
        self.skill = (FICHA / "SKILL.md").read_text(encoding="utf-8")
        self.plantilla = (FICHA / "assets" / "plantilla-ficha.md").read_text(encoding="utf-8")

    def secciones_del_contrato(self):
        m = re.search(r"Secciones que existen siempre[^:]*:\s*(.+)", self.skill)
        self.assertIsNotNone(m, "el SKILL.md no lista las secciones del contrato")
        return re.findall(r"`([^`]+)`", m.group(1))

    def test_la_plantilla_tiene_todas_las_secciones(self):
        encabezados = set(re.findall(r"^## (.+?)\s*$", self.plantilla, re.M))
        secciones = self.secciones_del_contrato()
        self.assertGreaterEqual(len(secciones), 8)
        for seccion in secciones:
            with self.subTest(seccion):
                self.assertIn(seccion, encabezados)

    def test_la_plantilla_no_tiene_secciones_fuera_del_contrato(self):
        encabezados = set(re.findall(r"^## (.+?)\s*$", self.plantilla, re.M))
        self.assertEqual(encabezados, set(self.secciones_del_contrato()))

    def test_los_campos_que_usan_otros_agentes_existen(self):
        # Los «Usos concretos» del SKILL.md citan campos de la plantilla entre « ».
        m = re.search(r"Usos concretos:(.*?)(?:\n## |\Z)", self.skill, re.S)
        self.assertIsNotNone(m, "falta la lista de usos concretos")
        for campo in re.findall(r"«([^»]+)»", m.group(1)):
            with self.subTest(campo):
                self.assertIn(f"**{campo}", self.plantilla, f"la plantilla no tiene el campo «{campo}»")


if __name__ == "__main__":
    unittest.main()

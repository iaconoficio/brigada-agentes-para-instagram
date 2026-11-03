"""
Pruebas de los .zip para la app de Claude (para-la-app-de-claude/).

Comprueban que hay un .zip por agente, que cada uno lleva la carpeta del agente
dentro con su SKILL.md, y que su contenido es el mismo que skills/. Si fallan,
ejecuta:  python3 herramientas/empaqueta_agentes.py

Solo Python estándar:  python3 -m unittest discover -s pruebas -v
"""

import importlib.util
import pathlib
import unittest
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "herramientas" / "empaqueta_agentes.py"
spec = importlib.util.spec_from_file_location("empaqueta_agentes", SCRIPT)
emp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emp)


class LosZipDeLaApp(unittest.TestCase):
    def test_estan_al_dia(self):
        self.assertEqual(emp.diferencias(), [], "ejecuta python3 herramientas/empaqueta_agentes.py")

    def test_cada_zip_lleva_su_carpeta_y_su_skill(self):
        for agente in emp.agentes():
            with self.subTest(agente.name):
                ruta = emp.DESTINO / (agente.name + ".zip")
                self.assertTrue(ruta.is_file(), f"falta {ruta.name}")
                with zipfile.ZipFile(ruta) as z:
                    nombres = z.namelist()
                self.assertIn(f"{agente.name}/SKILL.md", nombres)
                self.assertTrue(all(n.startswith(agente.name + "/") for n in nombres), "todo tiene que ir dentro de la carpeta del agente")
                self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in nombres))
                self.assertFalse(any(parte.startswith(".") for n in nombres for parte in n.split("/") if parte),
                                 "no puede ir ningún archivo ni carpeta oculta")
                with zipfile.ZipFile(ruta) as z:
                    self.assertTrue(all(i.create_system == 3 for i in z.infolist()), "los .zip se hacen como Unix")

    def test_el_readme_enlaza_los_ocho(self):
        readme = (RAIZ / "README.md").read_text(encoding="utf-8")
        for agente in emp.agentes():
            with self.subTest(agente.name):
                self.assertIn(f"para-la-app-de-claude/{agente.name}.zip", readme)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
empaqueta_agentes.py · La Brigada (IA con Oficio)

La app de Claude instala cada agente desde su propio .zip, con la carpeta del
agente dentro. Para que nadie tenga que comprimir carpetas a mano, los ocho
.zip van ya hechos en para-la-app-de-claude/. Este script los vuelve a hacer.
Ejecútalo cada vez que cambies algo en skills/. Las pruebas avisan si se te
olvida. Solo empaqueta lo que está en git (haz git add de lo nuevo antes), y
nunca archivos ocultos, cachés ni enlaces simbólicos.

Uso
  python3 herramientas/empaqueta_agentes.py
  python3 herramientas/empaqueta_agentes.py --comprobar   # no cambia nada; falla si no coinciden

Solo usa Python estándar y no se conecta a nada.
"""

import argparse
import pathlib
import subprocess
import sys
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILLS = RAIZ / "skills"
DESTINO = RAIZ / "para-la-app-de-claude"
FECHA = (2026, 1, 1, 0, 0, 0)  # fija, para que el mismo agente dé siempre el mismo .zip
BASURA = {"__pycache__", "Thumbs.db", "desktop.ini"}


def _en_git(agente):
    """Los archivos del agente que están en git, o None si no hay git a mano."""
    try:
        r = subprocess.run(["git", "-C", str(RAIZ), "ls-files", "-z", "--", str(agente.relative_to(RAIZ))],
                           capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return {RAIZ / n.decode("utf-8") for n in r.stdout.split(b"\0") if n}


def _vale(ruta):
    """Fuera ocultos, basura del sistema, cachés y enlaces simbólicos."""
    relativa = ruta.relative_to(SKILLS)
    if any(parte.startswith(".") or parte in BASURA for parte in relativa.parts):
        return False
    if ruta.suffix in (".pyc", ".tmp") or ruta.name.endswith("~"):
        return False
    return ruta.is_file() and not ruta.is_symlink()


def agentes():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def archivos_de(agente):
    """Lo que tiene que ir en el .zip: {ruta dentro del zip: bytes}.

    Solo lo que está en git (si hay git), y nunca ocultos, basura ni enlaces.
    """
    en_git = _en_git(agente)
    dentro = {}
    for ruta in sorted(agente.rglob("*")):
        if any(parte.is_symlink() for parte in [ruta, *ruta.parents] if agente in parte.parents or parte == agente):
            continue
        if en_git is not None and ruta not in en_git:
            continue
        if _vale(ruta):
            dentro[ruta.relative_to(SKILLS).as_posix()] = ruta.read_bytes()
    return dentro


def empaqueta(agente, destino):
    dentro = archivos_de(agente)
    carpetas = sorted({p.rsplit("/", i)[0] + "/" for p in dentro for i in range(1, p.count("/") + 1)})
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta in carpetas:
            info = zipfile.ZipInfo(carpeta, FECHA)
            info.create_system = 3  # como Unix, también si se rehace en Windows
            info.external_attr = (0o40755 << 16) | 0x10
            z.writestr(info, b"")
        for nombre, datos in dentro.items():
            info = zipfile.ZipInfo(nombre, FECHA)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, datos)


def diferencias():
    """Lista de avisos: .zip que faltan, sobran o no coinciden con skills/."""
    avisos = []
    esperados = {a.name + ".zip": a for a in agentes()}
    presentes = {p.name for p in DESTINO.glob("*.zip")} if DESTINO.is_dir() else set()
    for nombre in sorted(set(esperados) - presentes):
        avisos.append(f"falta {nombre}")
    for nombre in sorted(presentes - set(esperados)):
        avisos.append(f"sobra {nombre}: no hay ningún agente con ese nombre")
    for nombre in sorted(set(esperados) & presentes):
        esperado = archivos_de(esperados[nombre])
        with zipfile.ZipFile(DESTINO / nombre) as z:
            hay = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
        if hay != esperado:
            distintos = sorted(set(hay) ^ set(esperado) | {k for k in set(hay) & set(esperado) if hay[k] != esperado[k]})
            avisos.append(f"{nombre} no coincide con skills/: {', '.join(distintos[:5])}")
    return avisos


def main():
    p = argparse.ArgumentParser(description="Hace un .zip por agente para subirlo a la app de Claude.")
    p.add_argument("--comprobar", action="store_true", help="no cambia nada; falla si los .zip no están al día")
    args = p.parse_args()
    if args.comprobar:
        avisos = diferencias()
        for a in avisos:
            print("ARREGLA:", a)
        if avisos:
            print("Ejecuta: python3 herramientas/empaqueta_agentes.py")
            sys.exit(1)
        print("Coinciden.")
        return
    DESTINO.mkdir(exist_ok=True)
    for viejo in DESTINO.glob("*.zip"):
        viejo.unlink()
    for agente in agentes():
        empaqueta(agente, DESTINO / (agente.name + ".zip"))
        print("hecho:", agente.name + ".zip")


if __name__ == "__main__":
    main()

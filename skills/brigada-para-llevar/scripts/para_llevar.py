#!/usr/bin/env python3
"""
para_llevar.py · La Brigada (IA con Oficio)

Prepara la semana para llevar: coge los textos que la persona ya ha aprobado
(un pedido en JSON) y lo deja todo listo para subir a Instagram, con las
imágenes hechas, una carpeta por pieza y un .zip:

  LEEME.txt                        qué subir, qué día y a qué hora
  1-martes-17-reel/
    portada-del-reel.jpg           1080x1920
    guion.txt
    texto-del-post.txt
    textos-en-pantalla-opcional/   01.png, 02.png... con fondo transparente
  2-jueves-19-carrusel/
    01.jpg ... 10.jpg              1080x1350, en el orden en que se suben
    texto-del-post.txt
  3-sabado-21-post/
    post.jpg                       1080x1350
    texto-del-post.txt
  semana.ics                       si el pedido trae el calendario de brigada-plan

Deja también una página (.html) para verlo todo en el móvil, copiar los textos
y descargar el .zip.

Las imágenes se dibujan con el motor de la Lámina de texto
(assets/motor-lamina.js): aspecto de tuit, con los colores de la persona y su
foto o sus iniciales. La firma de La Brigada va en el LEEME y en la página,
nunca en las imágenes que se publican.

Los textos no se tocan: van tal cual se aprobaron. Si algo no está bien, se
arregla con el agente que lo escribió y se vuelve a aprobar.

Lo que mira antes:

  APROBADO   que los textos estén aprobados: quién y qué día. Sin eso, nada
  PEDIDO     que cada pieza tenga lo suyo y cada campo sea del tipo que toca
  COLORES    que el texto se lea sobre el fondo (contraste WCAG: 4,5 como
             mínimo; 3 para la cuenta y los números del carrusel)
  FOTO       que esté en la carpeta del pedido, sea PNG, JPG o WEBP y no pese
             más de 2 MB
  TEXTO      rayas largas y caracteres invisibles (avisa, no cambia nada), y
             los límites de Instagram: 2.200 caracteres por texto y de 2 a 20
             láminas por carrusel, como revisa_caption.py y revisa_carrusel.py
  MEDIDO     con el navegador, dibuja cada imagen y comprueba que el texto cabe
             entero, que ninguna palabra se parte y que cada archivo sale con
             su medida. Si algo no cabe, no entrega nada

El navegador es el de brigada-emplatado, con lo mismo: Chrome, Chromium o
Edge sin ventana, con un perfil temporal y la red cortada. Por eso esta skill
va con brigada-emplatado instalada a su lado. Sin navegador (pasa a menudo
dentro de Claude en la web), deja solo la página: la persona la abre, la
página dibuja y mide en su navegador, y el .zip se descarga desde ahí.

El script solo usa Python estándar, no se conecta a internet ni envía nada.

Uso
  python3 para_llevar.py pedido.json
  python3 para_llevar.py pedido.json --salida semana-16-nov-v1
  python3 para_llevar.py pedido.json --sin-navegador
  python3 para_llevar.py pedido.json --json

Salida: 0 hecho (puede haber OJO o NOTA), 1 hay que arreglar algo,
2 no puedo leer el pedido o falta brigada-emplatado.
"""

import argparse
import base64
import datetime
import html
import importlib.util
import json
import math
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import unicodedata
import zipfile

AQUI = pathlib.Path(__file__).resolve().parent
SKILL = AQUI.parent
MOTOR = SKILL / "assets" / "motor-lamina.js"
PAGINA = SKILL / "assets" / "pagina-para-llevar.html"
EMPLATA = SKILL.parent / "brigada-emplatado" / "scripts" / "emplata.py"


def _carga_emplatado():
    """brigada-emplatado, la de al lado: su navegador, sus colores y sus letras."""
    if not EMPLATA.is_file():
        return None
    spec = importlib.util.spec_from_file_location("brigada_emplatado_para_llevar", EMPLATA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


E = _carga_emplatado()

# Límites de Instagram: los mismos que revisa_caption.py y revisa_carrusel.py (las pruebas lo comprueban).
CAPTION_MAX = 2200       # caracteres por texto (Meta, documentación de la API)
LAMINAS_MIN = 2          # un carrusel lleva al menos dos
LAMINAS_MAX = 20         # fotos o vídeos por carrusel (Instagram, agosto de 2024)

# Opinión, no un dato.
PIEZAS_MAX = 7           # una semana
CARTELES_MAX = 15        # textos en pantalla por reel
TEXTO_MAX_BYTES = 200 * 1024
CALENDARIO_MAX_BYTES = 200 * 1024
TIEMPO = 120             # segundos como mucho para dibujarlo todo en el navegador

FOTO_MAX = 2 * 1024 * 1024
# WCAG 2.x: la cuenta y los números del carrusel son letra pequeña en el móvil (4,5, como un texto normal);
# las iniciales y la insignia azul son grandes (3).
CONTRASTE_GRIS = 4.5
CONTRASTE_GRANDE = 3.0
AZUL_VERIFICADO = "#1D9BF0"   # el de la Lámina
FORMATOS = {"reel": "Reel", "carrusel": "Carrusel", "post": "Post"}
LETRAS = ("sans", "serif", "mono")
# Los temas fijos de la Lámina (motor-lamina.js): fondo, texto y gris de la cuenta.
TEMAS = {"blanco": ("#FFFFFF", "#0F1419", "#536471"), "negro": ("#000000", "#E7E9EA", "#8B98A5")}
MEDIDAS = {"feed": (1080, 1350), "story": (1080, 1920)}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
CUENTA_RE = re.compile(r"^@?([A-Za-z0-9._]{1,30})$")
HORA_RE = re.compile(r"^([01]?\d|2[0-3])[:.h]([0-5]\d)$")
FECHA_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
BOM = chr(0xFEFF)
MARCADOR_RE = re.compile(r"@@(FUENTES|TITULO|MOTOR|CUERPO|PEDIDO)@@")


class Pedido(Exception):
    """Un fallo del pedido que hay que arreglar antes de preparar nada."""


class NoPuedoEscribir(Exception):
    """No se puede guardar el resultado donde se ha pedido."""


class FaltaEmplatado(Exception):
    """brigada-emplatado no está instalada al lado."""


# ---------------------------------------------------------------- utilidades

def slug(texto, largo=40):
    t = unicodedata.normalize("NFD", str(texto).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:largo].strip("-")


def tal_cual(texto):
    """El texto aprobado, sin tocar: solo los saltos de línea de Windows y los espacios de los extremos."""
    return str(texto).replace("\r\n", "\n").replace("\r", "\n").strip()


def fecha_legible(iso):
    a, m, d = (int(x) for x in iso.split("-"))
    return f"{d} de {MESES[m - 1]} de {a}"


def mezcla(a, b, t):
    """Como mezclar() de la Lámina: el gris de la cuenta sale de mezclar el texto con el fondo.
    Redondea como Math.round de JavaScript (0,5 hacia arriba), no como round() de Python."""
    x, y = E.hex6(a).lstrip("#"), E.hex6(b).lstrip("#")
    canales = [math.floor(int(x[i:i + 2], 16) * t + int(y[i:i + 2], 16) * (1 - t) + 0.5) for i in (0, 2, 4)]
    return "#" + "".join(f"{c:02X}" for c in canales)


def gris(texto, fondo):
    """El gris de la cuenta y de los números, como lo pinta la página: el de la Lámina (62 % del texto) o, si
    no se lee bien en el móvil, un poco más oscuro, hasta que se lea. Devuelve (color, proporción de texto)."""
    pasos = 0
    while pasos <= 19:
        t = (62 + 2 * pasos) / 100
        color = mezcla(texto, fondo, t)
        if E.contraste(color, fondo) >= CONTRASTE_GRIS:
            return color, t
        pasos += 1
    return E.hex6(texto), 1.0


def iniciales(nombre):
    """Como iniciales() de la página: la primera letra (o cifra) de la primera palabra y de la última.
    Las palabras sin letras (un emoji, un guion) no cuentan."""
    p = [m.group(0) for m in (re.search(r"[^\W_]", w) for w in nombre.split()) if m]
    return ((p[0] if p else "?") + (p[-1] if len(p) > 1 else "")).upper()


def tipo_de_imagen(datos):
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if datos[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def medidas(datos):
    """(tipo, ancho, alto, ¿con transparencia?) de una PNG o una JPG, leyendo su cabecera."""
    if datos[:8] == b"\x89PNG\r\n\x1a\n" and len(datos) >= 26:
        ancho, alto = struct.unpack(">II", datos[16:24])
        return "png", ancho, alto, datos[25] in (4, 6)
    if datos[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 <= len(datos):
            if datos[i] != 0xFF:
                i += 1
                continue
            marca = datos[i + 1]
            if marca in (0xD8, 0x01) or 0xD0 <= marca <= 0xD7 or marca == 0xFF:
                i += 1 if marca == 0xFF else 2
                continue
            if 0xC0 <= marca <= 0xCF and marca not in (0xC4, 0xC8, 0xCC):
                alto, ancho = struct.unpack(">HH", datos[i + 5:i + 9])
                return "jpg", ancho, alto, False
            i += 2 + struct.unpack(">H", datos[i + 2:i + 4])[0]
    return None


def _lee_archivo(valor, base, donde, lee, campo, sufijos=(".txt", ".md"), maximo=TEXTO_MAX_BYTES, exacto=False):
    """Un texto que viene de un archivo de la carpeta del pedido. None si hay que arreglar algo.
    Con exacto, tal cual está en el disco: sin cambiar los saltos de línea (el .ics los necesita así)."""
    nombre = valor.get("archivo") if isinstance(valor, dict) else valor
    if not isinstance(nombre, str) or not nombre.strip():
        lee.arregla(donde, f"«{campo}» tiene que ser la ruta del archivo, desde la carpeta del pedido")
        return None
    ruta = E._dentro(base, nombre)
    if ruta is None:
        lee.arregla(donde, f"«{nombre}» tiene que estar dentro de la carpeta del pedido")
        return None
    if ruta.suffix.lower() not in sufijos:
        lee.arregla(donde, f"«{ruta.name}» tiene que ser un archivo {' o '.join(sufijos)}")
        return None
    try:
        if ruta.stat().st_size > maximo:
            lee.arregla(donde, f"«{ruta.name}» es demasiado grande")
            return None
        if exacto:
            return ruta.read_bytes().decode("utf-8")
        return ruta.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        lee.arregla(donde, f"no puedo leer «{nombre}» (la ruta es desde la carpeta del pedido)")
        return None


def _texto_aprobado(valor, base, donde, lee, campo, obligatorio=True):
    """Un texto aprobado: escrito en el pedido o en un archivo. Vacío si no hay; None si está mal."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            lee.arregla(donde, f"falta «{campo}»")
        return ""
    if isinstance(valor, dict):
        bruto = _lee_archivo(valor, base, donde, lee, campo)
        return None if bruto is None else tal_cual(bruto)
    if isinstance(valor, str):
        return tal_cual(valor)
    lee.arregla(donde, f"«{campo}» tiene que ser un texto o {{\"archivo\": \"...\"}}")
    return None


# ---------------------------------------------------------------- el pedido

def prepara(datos, base, avisos):
    """Valida el pedido y lo deja listo para dibujar. Lanza Pedido si hay que arreglar algo."""
    lee = E.Lector(avisos)
    base = pathlib.Path(base)

    cab = {}
    for campo, maximo, obligatorio in (("titulo", 90, True), ("para", 60, True), ("cuenta", 40, True),
                                       ("preparado_por", 60, False)):
        valor = lee.texto(datos.get(campo), campo, "PEDIDO")
        if valor is None:
            continue
        if obligatorio and not valor:
            explica = {"titulo": "el nombre de la semana, por ejemplo «Tu semana del 16 de noviembre»",
                       "para": "el nombre del negocio o de la persona, como en «Nombre» de su ficha",
                       "cuenta": "su cuenta de Instagram, con @. Sale en la cabecera de cada imagen"}[campo]
            lee.arregla("PEDIDO", f"falta «{campo}»: {explica}")
        elif "\n" in valor:
            lee.arregla("PEDIDO", f"«{campo}» va en una sola línea")
        elif len(valor) > maximo:
            lee.arregla("PEDIDO", f"«{campo}» tiene {len(valor)} caracteres: como mucho {maximo}")
        cab[campo] = valor or ""
    usuario = ""
    if cab.get("cuenta"):
        m = CUENTA_RE.match(cab["cuenta"])
        if m:
            usuario = m.group(1)
        else:
            lee.arregla("PEDIDO", "«cuenta» tiene que ser la cuenta de Instagram: solo letras sin tilde, números, "
                                  "puntos y guiones bajos, como @calefaccion.olmo")

    aprobado = _aprobado(datos.get("aprobado"), lee)
    marca = _marca(datos.get("marca"), base, lee)
    calendario = None
    if datos.get("calendario") is not None:
        calendario = _lee_archivo(datos["calendario"], base, "CALENDARIO", lee, "calendario", (".ics",),
                                  CALENDARIO_MAX_BYTES, exacto=True)
        if calendario is not None and not calendario.lstrip(BOM + " \r\n\t").startswith("BEGIN:VCALENDAR"):
            lee.arregla("CALENDARIO", "el archivo no es un calendario (.ics). Sácalo con brigada-plan: "
                                      "semana.py --ics")
            calendario = None

    piezas = lee.lista(datos.get("piezas"), "piezas", "PEDIDO", obligatoria=True) or []
    if len(piezas) > PIEZAS_MAX:
        lee.arregla("PEDIDO", f"hay {len(piezas)} piezas: como mucho {PIEZAS_MAX}, una semana")
    limpias = []
    for n, pieza in enumerate(piezas, 1):
        limpia = _pieza(pieza, n, base, lee)
        if limpia is not None:
            limpias.append(limpia)

    if any(a["estado"] == "ARREGLA" for a in avisos):
        raise Pedido()

    for p in limpias:
        _mira_textos(p, lee)
    trabajo = {**cab, "usuario": usuario, "aprobado": aprobado, "marca": marca, "piezas": limpias,
               "calendario": calendario}
    trabajo["imagenes"] = _imagenes(limpias)
    return trabajo


def _aprobado(valor, lee):
    explica = ("Las imágenes se hacen solo con los textos aprobados. Enséñale los textos, espera su sí y apunta "
               "quién y qué día: \"aprobado\": {\"por\": \"su nombre\", \"fecha\": \"AAAA-MM-DD\"}")
    if valor is None:
        lee.arregla("APROBADO", f"falta «aprobado». {explica}")
        return None
    if not isinstance(valor, dict):
        lee.arregla("APROBADO", f"«aprobado» tiene que llevar quién y qué día. {explica}")
        return None
    por = lee.texto(valor.get("por"), "aprobado.por", "APROBADO")
    fecha = lee.texto(valor.get("fecha"), "aprobado.fecha", "APROBADO")
    if por is not None and (not por or "\n" in por or len(por) > 60):
        lee.arregla("APROBADO", "«aprobado.por» es el nombre de quien ha dado el sí, en una línea")
        por = None
    dia = None
    if fecha is not None:
        m = FECHA_RE.match(fecha)
        try:
            dia = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
        except ValueError:
            dia = None
        if dia is None:
            lee.arregla("APROBADO", f"«aprobado.fecha» tiene que ser un día como 2026-11-14 (has puesto «{fecha}»)")
        elif dia > datetime.date.today():
            lee.ojo("APROBADO", f"la fecha del sí ({fecha}) es de un día que aún no ha llegado: ¿es correcta?")
    if por and dia:
        return {"por": por, "fecha": dia.isoformat()}
    return None


def _marca(valor, base, lee):
    marca = {"fondo": "blanco", "colorFondo": "#FFFFFF", "colorTexto": "#0F1419", "letra": "sans",
             "verificado": False, "foto": None, "propia": False, "gris": None, "gris_t": 0.62}
    if valor is None:
        return marca
    if not isinstance(valor, dict):
        lee.arregla("MARCA", "«marca» tiene que ser un objeto con fondo, texto, letra y foto")
        return marca
    fondo = valor.get("fondo", "blanco")
    texto = valor.get("texto")
    if isinstance(fondo, str) and fondo.strip().lower() in TEMAS:
        marca["fondo"] = fondo.strip().lower()
        marca["colorFondo"], marca["colorTexto"] = TEMAS[marca["fondo"]][:2]
        if texto is not None:
            lee.ojo("MARCA", f"con fondo {marca['fondo']}, el color del texto lo pone la Lámina: «texto» no se usa")
    elif isinstance(fondo, str) and E.COLOR_RE.match(fondo.strip()):
        if not isinstance(texto, str) or not E.COLOR_RE.match(texto.strip()):
            lee.arregla("MARCA", f"con un fondo de color, «texto» tiene que ser un color en código, como #1C2541 "
                                 f"(has puesto «{texto}»)")
        else:
            marca.update({"fondo": "propio", "colorFondo": E.hex6(fondo.strip()), "colorTexto": E.hex6(texto.strip()),
                          "propia": True})
            marca["gris"], marca["gris_t"] = gris(marca["colorTexto"], marca["colorFondo"])
    else:
        lee.arregla("MARCA", f"«fondo» tiene que ser blanco, negro o un color en código, como #F5ECD6 "
                             f"(has puesto «{fondo}»)")
    letra = valor.get("letra", "sans")
    if letra not in LETRAS:
        lee.arregla("MARCA", f"«letra» tiene que ser sans, serif o mono (has puesto «{letra}»)")
    else:
        marca["letra"] = letra
    marca["verificado"] = lee.si_no(valor.get("verificado"), "verificado", "MARCA", False)
    if valor.get("foto") is not None:
        marca["foto"] = _foto(valor["foto"], base, lee)
    return marca


def _foto(nombre, base, lee):
    if not isinstance(nombre, str) or not nombre.strip():
        lee.arregla("FOTO", "«foto» tiene que ser la ruta del archivo, desde la carpeta del pedido")
        return None
    ruta = E._dentro(base, nombre)
    if ruta is None:
        lee.arregla("FOTO", f"«{nombre}» tiene que estar dentro de la carpeta del pedido")
        return None
    if not ruta.is_file():
        lee.arregla("FOTO", f"no encuentro «{nombre}» (la ruta es desde la carpeta del pedido)")
        return None
    if ruta.stat().st_size > FOTO_MAX:
        lee.arregla("FOTO", f"«{ruta.name}» pesa más de 2 MB: guárdala más pequeña")
        return None
    datos = ruta.read_bytes()
    tipo = tipo_de_imagen(datos)
    if tipo is None:
        lee.arregla("FOTO", f"«{ruta.name}» tiene que ser una foto PNG, JPG o WEBP")
        return None
    return f"data:{tipo};base64," + base64.b64encode(datos).decode()


def _pieza(pieza, n, base, lee):
    donde = f"PIEZA {n}"
    if not isinstance(pieza, dict):
        lee.arregla(donde, "cada pieza tiene que ser un objeto con dia, formato y texto")
        return None
    antes = sum(1 for a in lee.avisos if a["estado"] == "ARREGLA")
    formato = pieza.get("formato")
    formato = formato.strip().lower() if isinstance(formato, str) else None
    if formato not in FORMATOS:
        lee.arregla(donde, f"el formato «{pieza.get('formato')}» no existe. Los formatos son: {', '.join(FORMATOS)}")
        return None
    p = {"n": n, "formato": formato}
    dia = lee.texto(pieza.get("dia"), "dia", donde)
    if dia is not None and (not dia or "\n" in dia or len(dia) > 30):
        lee.arregla(donde, "«dia» es el día de publicarla, en una línea corta, como «martes 17»")
    p["dia"] = dia or ""
    hora = lee.texto(pieza.get("hora"), "hora", donde)
    p["hora"] = ""
    if hora:
        m = HORA_RE.match(hora)
        if m:
            p["hora"] = f"{int(m.group(1)):02d}:{m.group(2)}"
        else:
            lee.arregla(donde, f"«hora» tiene que ser como 19:00 (has puesto «{hora}»)")
    p["texto"] = _texto_aprobado(pieza.get("texto"), base, donde, lee, "texto")

    if formato == "reel":
        p["portada"] = _texto_aprobado(pieza.get("portada"), base, donde, lee, "portada")
        p["guion"] = _texto_aprobado(pieza.get("guion"), base, donde, lee, "guion")
        carteles = lee.lista(pieza.get("carteles"), "carteles", donde) or []
        p["carteles"] = []
        for c in carteles:
            t = lee.texto(c, "carteles", donde)
            if t:
                p["carteles"].append(t)
        if len(p["carteles"]) > CARTELES_MAX:
            lee.arregla(donde, f"hay {len(p['carteles'])} textos en pantalla: como mucho {CARTELES_MAX}")
    elif formato == "carrusel":
        if pieza.get("laminas") is None:
            lee.arregla(donde, "falta «laminas»: las láminas del carrusel, en orden")
            p["laminas"] = []
        else:
            desde = len(lee.avisos)
            p["laminas"] = E._laminas(pieza.get("laminas"), base, donde, lee)
            for aviso in lee.avisos[desde:]:   # los mensajes de brigada-emplatado hablan de la comanda
                aviso["detalle"] = aviso["detalle"].replace("de la comanda", "del pedido")
        p["numerar"] = lee.si_no(pieza.get("numerar"), "numerar", donde, True)
        n_lam = len(p["laminas"])
        if pieza.get("laminas") is not None and n_lam < LAMINAS_MIN:
            lee.arregla(donde, f"el carrusel tiene {n_lam} lámina(s): un carrusel lleva {LAMINAS_MIN} o más")
        elif n_lam > LAMINAS_MAX:
            lee.arregla(donde, f"el carrusel tiene {n_lam} láminas: Instagram admite {LAMINAS_MAX} como mucho")
    else:
        p["lamina"] = _texto_aprobado(pieza.get("lamina"), base, donde, lee, "lamina")

    if sum(1 for a in lee.avisos if a["estado"] == "ARREGLA") > antes:
        return None
    if len(p["texto"]) > CAPTION_MAX:
        lee.arregla(donde, f"el texto del post tiene {len(p['texto'])} caracteres: Instagram admite {CAPTION_MAX}")
        return None
    p["carpeta"] = f"{n}-{slug(p['dia']) or 'dia'}-{formato}"
    return p


def _mira_textos(p, lee):
    donde = f"PIEZA {p['n']}"
    textos = [p["texto"], p.get("portada", ""), p.get("guion", ""), p.get("lamina", "")]
    textos += p.get("laminas", []) + p.get("carteles", [])
    if any(E.RAYAS_RE.search(t) for t in textos if t):
        lee.ojo(donde, "hay rayas largas en los textos aprobados. No las cambio: si no las quiere, que las quite "
                       "el agente que lo escribió y que lo vuelva a aprobar")
    if any(c in t for t in textos if t for c in E.INVISIBLES):
        lee.ojo(donde, "hay caracteres invisibles en los textos (los deja a veces la IA). En las imágenes no salen; "
                       "en los textos para copiar, sí. Pásalos por brigada-humano y que los vuelva a aprobar")


def _imagenes(piezas):
    """La lista de imágenes que hay que dibujar, con su ruta dentro del paquete."""
    imagenes = []
    for p in piezas:
        c = p["carpeta"]
        if p["formato"] == "reel":
            imagenes.append({"ruta": f"{c}/portada-del-reel.jpg", "clase": "lamina", "formato": "story",
                             "texto": p["portada"], "indice": 0, "total": 1, "numerar": False,
                             "etiqueta": "La portada del reel"})
            for i, cartel in enumerate(p["carteles"], 1):
                imagenes.append({"ruta": f"{c}/textos-en-pantalla-opcional/{i:02d}.png", "clase": "cartel",
                                 "formato": "story", "texto": cartel, "etiqueta": f"Texto en pantalla {i}"})
        elif p["formato"] == "carrusel":
            total = len(p["laminas"])
            for i, lamina in enumerate(p["laminas"], 1):
                imagenes.append({"ruta": f"{c}/{i:02d}.jpg", "clase": "lamina", "formato": "feed", "texto": lamina,
                                 "indice": i - 1, "total": total, "numerar": p["numerar"],
                                 "etiqueta": f"Lámina {i} de {total}"})
        else:
            imagenes.append({"ruta": f"{c}/post.jpg", "clase": "lamina", "formato": "feed", "texto": p["lamina"],
                             "indice": 0, "total": 1, "numerar": False, "etiqueta": "La imagen del post"})
    for img in imagenes:
        img["pieza"] = img["ruta"].split("/")[0]
    return imagenes


# ---------------------------------------------------------------- los textos del paquete

def leeme(t):
    cuando = fecha_legible(t["aprobado"]["fecha"])
    lineas = [f"{t['titulo'].upper()} · LISTA PARA SUBIR", f"{t['para']} · @{t['usuario']}",
              f"Textos aprobados por {t['aprobado']['por']} el {cuando}.", "",
              "Revísalo con calma antes de subir nada: sin tu sí, no se publica.", ""]
    for p in t["piezas"]:
        cabeza = f"{p['dia'].upper()} · {FORMATOS[p['formato']].upper()}"
        lineas.append(cabeza + (f" · {p['hora']}" if p["hora"] else ""))
        lineas.append(f"  Carpeta {p['carpeta']}:")
        if p["formato"] == "reel":
            lineas.append("  portada-del-reel.jpg, la portada. guion.txt, lo que dices y lo que se ve.")
            lineas.append("  texto-del-post.txt, el texto para copiar. El vídeo lo grabas tú.")
            if p["carteles"]:
                lineas.append(f"  Opcional: en textos-en-pantalla-opcional, {len(p['carteles'])} textos sin fondo,")
                lineas.append("  para colocarlos sobre el vídeo si te apetece, siguiendo el guion.")
        elif p["formato"] == "carrusel":
            total = len(p["laminas"])
            lineas.append(f"  Las {total} láminas, de 01 a {total:02d}: súbelas en ese orden.")
            lineas.append("  texto-del-post.txt, el texto para copiar.")
        else:
            lineas.append("  post.jpg, la imagen. texto-del-post.txt, el texto para copiar.")
        lineas.append("")
    if t["calendario"]:
        lineas += ["semana.ics: ábrelo y te pone la semana en el calendario, con sus avisos.", ""]
    lineas += ["--"]
    if t.get("preparado_por"):
        lineas.append(f"Preparado por {t['preparado_por']} con La Brigada")
    lineas += [f"{E.HECHO_CON} · {E.FIRMA}", E.REPO, ""]
    return "\n".join(lineas)


def archivos(t):
    """Los archivos de texto del paquete, en orden: (ruta, texto)."""
    lista = [("LEEME.txt", leeme(t))]
    for p in t["piezas"]:
        if p["formato"] == "reel":
            lista.append((f"{p['carpeta']}/guion.txt", p["guion"] + "\n"))
        lista.append((f"{p['carpeta']}/texto-del-post.txt", p["texto"] + "\n"))
    if t["calendario"]:
        lista.append(("semana.ics", t["calendario"]))
    return lista


# ---------------------------------------------------------------- la página

def _cuerpo(t):
    e = html.escape
    aprobado = f"Textos aprobados por {t['aprobado']['por']} el {fecha_legible(t['aprobado']['fecha'])}"
    partes = [
        '<header class="cab">',
        '<div class="eti"><span class="sello"></span>La Brigada · Para llevar</div>',
        f'<h1>{e(t["titulo"])}</h1>',
        f'<p class="para">{e(t["para"])} · <span class="cuenta">@{e(t["usuario"])}</span></p>',
        f'<p class="aprobado">{e(aprobado)}</p>',
        '</header>',
        '<div class="accion">',
        '<button class="bajar" id="bajar" type="button" disabled>Preparando las imágenes...</button>',
        '<p class="estado" id="estado" role="status">Un momento: estoy preparando las imágenes. Si no aparecen, '
        'abre esta página con Chrome, Safari o Edge.</p>',
        '<noscript><p class="estado mal">Esta página necesita JavaScript para enseñar las imágenes. Ábrela con '
        'Chrome, Safari o Edge.</p></noscript>',
        '</div>',
        '<p class="nota">Revísalo con calma antes de subir nada: sin tu sí, no se publica. Desliza para ver cada pieza.</p>',
    ]
    numeradas = list(enumerate(t["imagenes"]))
    for p in t["piezas"]:
        cuando = p["dia"] + (f" · {p['hora']}" if p["hora"] else "")
        que = {"reel": "La portada, el guion y el texto", "carrusel": f"Las {len(p.get('laminas', []))} láminas, "
               "en orden", "post": "La imagen y su texto"}[p["formato"]]
        partes += ['<section class="pieza">',
                   f'<div class="chips"><span class="chip">{e(cuando)}</span>'
                   f'<span class="chip linea">{FORMATOS[p["formato"]]}</span></div>',
                   f'<h2>{que}</h2>', f'<p class="carpeta">Carpeta {e(p["carpeta"])}</p>']
        suyas = [(k, img) for k, img in numeradas if img["pieza"] == p["carpeta"]]
        normales = [(k, img) for k, img in suyas if img["clase"] == "lamina"]
        carteles = [(k, img) for k, img in suyas if img["clase"] == "cartel"]
        partes.append('<div class="tira">' + "".join(_figura(k, img) for k, img in normales) + "</div>")
        if carteles:
            partes += ['<p class="sub">Opcional · textos en pantalla</p>',
                       '<p class="nota">Sin fondo, para colocarlos sobre el vídeo siguiendo el guion.</p>',
                       '<div class="tira">' + "".join(_figura(k, img) for k, img in carteles) + "</div>"]
        if p["formato"] == "reel":
            partes.append(_texto_plegable(f"g-{p['n']}", "El guion", p["guion"], "Copiar el guion", abierto=False))
        partes.append(_texto_plegable(f"t-{p['n']}", "El texto del post", p["texto"], "Copiar el texto"))
        partes.append("</section>")
    enlaces = " · ".join(f'<a href="{e(url)}">{e(que)}</a>' for que, url, _ in E.ENLACES)
    partes += ['<footer class="pie">', f'<div class="eti"><span class="sello"></span>{e(E.HECHO_CON)}</div>',
               f'<p class="firma">{e(E.FIRMA)}</p>']
    if t.get("preparado_por"):
        partes.append(f'<p>Preparado por {e(t["preparado_por"])}.</p>')
    partes += ['<p>Las imágenes son tuyas: no llevan la firma de La Brigada.</p>', f"<p>{enlaces}</p>", "</footer>"]
    return "\n".join(partes)


def _figura(k, img):
    e = html.escape
    ancho, alto = MEDIDAS[img["formato"]]
    clases = "img" + (" alta" if img["formato"] == "story" else "") + (" cartel" if img["clase"] == "cartel" else "")
    return (f'<figure class="{clases}" id="img-{k}"><img alt="{e(img["texto"])}" width="{ancho}" height="{alto}">'
            f'<figcaption class="pie-img">{e(img["etiqueta"])}</figcaption></figure>')


def _texto_plegable(ident, titulo, texto, boton, abierto=True):
    e = html.escape
    return (f'<details{" open" if abierto else ""}><summary>{titulo}</summary>'
            f'<div class="texto" id="{ident}">{e(texto)}</div>'
            f'<button class="copiar" type="button" data-de="{ident}">{boton}</button></details>')


def _json_para_html(datos):
    """JSON que se puede meter dentro de <script>: sin «<» que pueda cerrar la etiqueta."""
    menor = "\\" + "u003c"
    return json.dumps(datos, ensure_ascii=True, separators=(",", ":")).replace("<", menor)


def pagina(t, carpeta, hechas=None, notas=None):
    """La página. Con «hechas» (las imágenes que ya ha dibujado y medido el navegador) las lleva dentro y no
    vuelve a dibujar: lo que se ve en el móvil y lo que se descarga son las mismas imágenes del .zip."""
    marca = {k: t["marca"][k] for k in ("fondo", "colorFondo", "colorTexto", "letra", "verificado", "foto", "gris")}
    datos = {"para": t["para"], "usuario": t["usuario"], "carpeta": carpeta, "marca": marca,
             "imagenes": [{k: v for k, v in img.items() if k != "etiqueta"} for img in t["imagenes"]],
             "archivos": [{"ruta": r, "texto": x} for r, x in archivos(t)]}
    if hechas is not None:
        datos["hechas"] = hechas
        datos["notas"] = notas or []
        datos["marca"]["foto"] = None   # ya va dentro de las imágenes
    valores = {"FUENTES": E.fuentes(False), "TITULO": html.escape(t["titulo"]),
               "MOTOR": MOTOR.read_text(encoding="utf-8"), "CUERPO": _cuerpo(t), "PEDIDO": _json_para_html(datos)}
    # Una sola pasada: lo que escribe la persona no puede colar ningún marcador.
    return MARCADOR_RE.sub(lambda m: valores[m.group(1)], PAGINA.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- el navegador

def dibuja(navegador, ruta_html):
    """Abre la página sin ventana y con la red cortada, y devuelve lo que ha dibujado, o None."""
    try:
        salida = E._lanza(navegador, ["--virtual-time-budget=10000", "--dump-dom",
                                      ruta_html.resolve().as_uri() + "#auto"], tiempo=TIEMPO)
    except (OSError, subprocess.SubprocessError):
        return None
    if 'data-listo="si"' not in salida:
        return None
    m = re.search(r'<pre id="salida"[^>]*>(.*?)</pre>', salida, re.S)
    if not m:
        return None
    try:
        dibujo = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    return dibujo if isinstance(dibujo, dict) else None


def revisa_dibujo(t, dibujo, avisos):
    """Comprueba lo que ha dibujado el navegador. Devuelve [(ruta, bytes)] o None si algo no está bien."""
    esperadas = {img["ruta"]: img for img in t["imagenes"]}
    hechas = {h.get("ruta"): h for h in dibujo.get("imagenes") or [] if isinstance(h, dict)}
    if set(hechas) != set(esperadas):
        avisos.append({"estado": "ARREGLA", "donde": "MEDIDO", "detalle": "el navegador no ha dibujado todas las "
                                                                          "imágenes: vuelve a probar"})
        return None
    malas, lista = [], []
    for ruta, img in esperadas.items():
        h = hechas[ruta]
        donde = f"{img['pieza']}"
        if h.get("noCabe"):
            malas.append(ruta)
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": f"{img['etiqueta']} ({donde}): el texto no cabe. Hay que acortarlo o partirlo "
                                      "en dos con el agente que lo escribió, y que lo vuelva a aprobar"})
        if h.get("partida"):
            malas.append(ruta)
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": f"{img['etiqueta']} ({donde}): hay una palabra más ancha que la línea, incluso "
                                      "con la letra más pequeña, y se partiría por letras. Hay que cambiarla con el "
                                      "agente que lo escribió"})
        try:
            datos = base64.b64decode(str(h.get("datos", "")).split(",", 1)[1], validate=True)
        except (IndexError, ValueError):
            datos = b""
        medida = medidas(datos)
        ancho, alto = MEDIDAS[img["formato"]]
        tipo = "png" if img["clase"] == "cartel" else "jpg"
        if not medida or medida[:3] != (tipo, ancho, alto) or (tipo == "png" and not medida[3]):
            malas.append(ruta)
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": f"{img['etiqueta']} ({donde}) no ha salido como tiene que salir "
                                      f"({tipo.upper()} de {ancho}x{alto}): vuelve a probar"})
        lista.append((ruta, datos))
    for t_cortado in dibujo.get("cortados") or []:
        avisos.append({"estado": "OJO", "donde": "CABECERA",
                       "detalle": f"«{t_cortado}» no cabe entero en la cabecera de las imágenes y sale cortado con "
                                  "«...». Acórtalo en el pedido si quieres que se vea entero"})
    if dibujo.get("fotoMal"):
        avisos.append({"estado": "OJO", "donde": "FOTO", "detalle": "el navegador no ha podido abrir la foto: "
                                                                     "van las iniciales"})
    return None if malas else lista


# ---------------------------------------------------------------- todo junto

def _escribe_nuevo(ruta, texto):
    """Escribe un archivo que no existía. Si ya existe (aunque sea un enlace roto), no lo toca."""
    try:
        with open(ruta, "x", encoding="utf-8") as archivo:
            archivo.write(texto)
    except OSError:
        raise NoPuedoEscribir(str(ruta))


def _zip(ruta_zip, carpeta, entradas):
    ahora = time.localtime()[:6]
    with zipfile.ZipFile(ruta_zip, "x") as z:
        for ruta, datos_archivo, comprimir in entradas:
            info = zipfile.ZipInfo(f"{carpeta}/{ruta}", date_time=ahora)
            info.compress_type = zipfile.ZIP_DEFLATED if comprimir else zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            z.writestr(info, datos_archivo)


def _sin_arreglar(informe):
    informe["veredicto"] = "ARREGLA: NO HE PREPARADO NADA"
    return informe


def para_llevar(ruta_pedido, salida=None, navegador=True):
    """Hace el trabajo y devuelve el informe.

    Lanza FaltaEmplatado si no está brigada-emplatado, FileNotFoundError o
    ValueError si no puede leer el pedido, y NoPuedoEscribir si no puede
    guardar el resultado."""
    if E is None:
        raise FaltaEmplatado(str(EMPLATA))
    ruta_pedido = pathlib.Path(ruta_pedido)
    datos = E.lee_comanda(ruta_pedido)
    avisos = []
    informe = {"avisos": avisos, "carpeta": None, "zip": None, "pagina": None, "imagenes": 0, "piezas": 0}
    try:
        t = prepara(datos, ruta_pedido.parent, avisos)
    except Pedido:
        return _sin_arreglar(informe)

    carpeta = pathlib.Path(salida) if salida else ruta_pedido.parent / (slug(t["titulo"], 50) or "semana")
    if carpeta.name in ("", ".", ".."):
        avisos.append({"estado": "ARREGLA", "donde": "SALIDA",
                       "detalle": f"«{salida}» no vale: --salida es el nombre de una carpeta nueva, como "
                                  "semana-16-nov-v1"})
        return _sin_arreglar(informe)
    ruta_zip = carpeta.with_name(carpeta.name + ".zip")
    ruta_html = carpeta.with_name(carpeta.name + ".html")
    ocupados = [r.name for r in (carpeta, ruta_zip, ruta_html) if os.path.lexists(r)]
    if ocupados:
        avisos.append({"estado": "ARREGLA", "donde": "SALIDA",
                       "detalle": f"ya hay {', '.join(ocupados)} y no lo piso. Usa --salida con otro nombre, por "
                                  f"ejemplo {carpeta.name}-v2"})
        return _sin_arreglar(informe)
    if not carpeta.parent.is_dir():
        raise NoPuedoEscribir(str(carpeta.parent))
    informe.update({"para": t["para"], "piezas": len(t["piezas"]), "imagenes": len(t["imagenes"])})

    marca = t["marca"]
    if marca["propia"]:
        texto, fondo = marca["colorTexto"], marca["colorFondo"]
        texto_fondo = E.contraste(texto, fondo)
        if texto_fondo < E.CONTRASTE_TEXTO:
            avisos.append({"estado": "ARREGLA", "donde": "COLORES",
                           "detalle": f"el texto no se lee bien sobre el fondo: contraste {E.coma(texto_fondo)}, y "
                                      f"hace falta {E.coma(E.CONTRASTE_TEXTO)} como mínimo. Oscurece el texto o "
                                      "aclara el fondo, con ella"})
            return _sin_arreglar(informe)
        avisos.append({"estado": "BIEN", "donde": "COLORES",
                       "detalle": f"los de {t['para']}: el texto se lee sobre el fondo (contraste "
                                  f"{E.coma(texto_fondo)})"})
        if marca["gris_t"] > 0.62:
            avisos.append({"estado": "NOTA", "donde": "COLORES",
                           "detalle": "la cuenta y los números del carrusel van en un gris algo más oscuro que en la "
                                      "Lámina, para que se lean bien en el móvil"})
        circulo = mezcla(texto, fondo, 0.18)
        if not marca["foto"] and E.contraste(texto, circulo) < CONTRASTE_GRANDE:
            avisos.append({"estado": "OJO", "donde": "COLORES",
                           "detalle": "las iniciales se leen justo sobre su círculo: con su foto quedará mejor"})
        if marca["verificado"] and E.contraste(AZUL_VERIFICADO, fondo) < CONTRASTE_GRANDE:
            avisos.append({"estado": "OJO", "donde": "COLORES",
                           "detalle": "la insignia azul de verificado se ve poco sobre este fondo"})
    else:
        avisos.append({"estado": "NOTA", "donde": "COLORES", "detalle": f"fondo {marca['fondo']}, como en la Lámina"})
    if not marca["foto"]:
        avisos.append({"estado": "NOTA", "donde": "FOTO",
                       "detalle": f"sin foto: en la cabecera van sus iniciales ({iniciales(t['para'])})"})
    if marca["verificado"]:
        avisos.append({"estado": "NOTA", "donde": "VERIFICADO",
                       "detalle": "lleva la insignia azul: solo si su cuenta está verificada de verdad"})
    avisos.append({"estado": "BIEN", "donde": "APROBADO",
                   "detalle": f"por {t['aprobado']['por']} el {fecha_legible(t['aprobado']['fecha'])}. Los textos "
                              "van tal cual"})

    texto_pagina = pagina(t, carpeta.name)
    sin_medir = ("Que la persona abra {} en su navegador: allí se dibujan las imágenes, se mide que todo cabe y, "
                 "si cabe, se descarga el .zip").format(ruta_html.name)
    nav = E.busca_navegador() if navegador else None
    if not nav:
        _escribe_nuevo(ruta_html, texto_pagina)
        informe["pagina"] = str(ruta_html)
        motivo = "sin navegador" if not navegador else "no he encontrado Chrome, Chromium ni Edge"
        avisos.append({"estado": "OJO", "donde": "MEDIDO",
                       "detalle": f"{motivo}: no he dibujado ni medido nada. {sin_medir}"})
        return _veredicto(informe)

    # Todo se prepara en una carpeta de trabajo al lado de la salida (no en la carpeta temporal del sistema,
    # que algunos Chromium no pueden leer). Solo al final pasa a su sitio: si algo falla, no queda nada a medias.
    try:
        trabajo = tempfile.TemporaryDirectory(dir=carpeta.parent, prefix=f"{carpeta.name}-a-medias-")
    except OSError:
        raise NoPuedoEscribir(str(carpeta.parent))
    with trabajo as temporal:
        temporal = pathlib.Path(temporal)
        prueba = temporal / "para-llevar.html"
        prueba.write_text(texto_pagina, encoding="utf-8")
        dibujo = dibuja(nav, prueba)
        if dibujo is None:
            _escribe_nuevo(ruta_html, texto_pagina)
            informe["pagina"] = str(ruta_html)
            avisos.append({"estado": "OJO", "donde": "MEDIDO",
                           "detalle": f"el navegador de este ordenador no ha podido dibujar: no he medido nada. "
                                      f"{sin_medir}"})
            return _veredicto(informe)
        if dibujo.get("error"):
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": f"la página no ha podido dibujar las imágenes ({dibujo['error']}). Así no se "
                                      "puede entregar"})
            return _veredicto(informe)
        imagenes = revisa_dibujo(t, dibujo, avisos)
        if imagenes is None:
            return _veredicto(informe)
        entradas = [(r, x.encode("utf-8"), True) for r, x in archivos(t)] + [(r, d, False) for r, d in imagenes]
        if dibujo.get("nombres") != [f"{carpeta.name}/{r}" for r, _, _ in entradas]:
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": "el .zip de la página no saldría igual que el del script. No lo entrego: avisa "
                                      "a quien mantiene La Brigada"})
            return _veredicto(informe)
        avisos.append({"estado": "BIEN", "donde": "MEDIDO",
                       "detalle": f"dibujadas y medidas en el navegador: {len(imagenes)} imágenes, todo cabe"})
        por_ruta = {h["ruta"]: h["datos"] for h in dibujo["imagenes"]}
        notas = []
        if dibujo.get("cortados"):
            notas.append("El nombre o la cuenta no caben enteros en la cabecera y salen cortados con «...».")
        if dibujo.get("fotoMal"):
            notas.append("No se ha podido abrir la foto: van las iniciales.")
        final = pagina(t, carpeta.name, [{"ruta": img["ruta"], "datos": por_ruta[img["ruta"]]}
                                         for img in t["imagenes"]], notas)
        obra = temporal / carpeta.name
        try:
            for ruta, datos_archivo, _ in entradas:
                destino = obra / ruta
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(datos_archivo)
            _zip(temporal / ruta_zip.name, carpeta.name, entradas)
            _escribe_nuevo(temporal / ruta_html.name, final)
            for origen, destino in ((obra, carpeta), (temporal / ruta_zip.name, ruta_zip),
                                    (temporal / ruta_html.name, ruta_html)):
                if os.path.lexists(destino):
                    raise NoPuedoEscribir(str(destino))
                os.rename(origen, destino)
        except OSError:
            raise NoPuedoEscribir(str(carpeta))
    informe.update({"carpeta": str(carpeta), "zip": str(ruta_zip), "pagina": str(ruta_html)})
    avisos.append({"estado": "BIEN", "donde": "PAQUETE",
                   "detalle": f"{ruta_zip.name}: {len(t['piezas'])} piezas, {len(imagenes)} imágenes y los textos. "
                              "La página lleva dentro las mismas imágenes. Sin la firma de La Brigada en ellas"})
    return _veredicto(informe)


def _veredicto(informe):
    estados = [a["estado"] for a in informe["avisos"]]
    informe["veredicto"] = ("ARREGLA" if "ARREGLA" in estados else "REVÍSALO" if "OJO" in estados else "LISTO")
    return informe


def pinta(informe, out=sys.stdout):
    cabeza = "PARA LLEVAR"
    if informe.get("piezas"):
        cabeza += f" · {informe['piezas']} pieza(s), {informe['imagenes']} imagen(es)"
    if informe.get("para"):
        cabeza += f" · {informe['para']}"
    print(f"\n{cabeza}", file=out)
    print("=" * 70, file=out)
    for a in informe["avisos"]:
        lineas = textwrap.wrap(a["detalle"], 47) or [""]
        print(f"  {a['estado']:<8} {a['donde']:<12} {lineas[0]}", file=out)
        for resto in lineas[1:]:
            print(f"  {'':<8} {'':<12} {resto}", file=out)
    print("-" * 70, file=out)
    print(f"  {informe['veredicto']}", file=out)
    for clave, nombre in (("zip", "El paquete"), ("carpeta", "La carpeta"), ("pagina", "La página")):
        if informe.get(clave):
            print(f"  {nombre}: {informe[clave]}", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Prepara la semana para llevar: las imágenes hechas y los textos "
                                             "aprobados, una carpeta por pieza y un .zip, listo para subir.")
    ap.add_argument("pedido", help="archivo JSON con el pedido (mira references/pedido.md)")
    ap.add_argument("--salida", help="la carpeta del paquete (por defecto, al lado del pedido, con el nombre del "
                                     "título). Al lado deja el .zip y la página .html")
    ap.add_argument("--sin-navegador", action="store_true", help="no abre el navegador: deja solo la página")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:   # en Windows, con la salida a un archivo, que un emoji no lo pare todo
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        informe = para_llevar(args.pedido, args.salida, navegador=not args.sin_navegador)
    except FaltaEmplatado:
        ap.error("brigada-para-llevar necesita a brigada-emplatado. En la app de Claude, sube también brigada-emplatado.zip; en Claude Code, instala el plugin brigada entero. Después, vuelve a pedirlo")
    except NoPuedoEscribir as fallo:
        ap.error(f"no puedo guardar «{fallo}»: mira que la carpeta exista y se pueda escribir en ella")
    except FileNotFoundError:
        ap.error(f"no puedo leer «{args.pedido}»: no existe o no es un archivo de texto")
    except ValueError as fallo:
        ap.error(f"no puedo leer «{args.pedido}»: {str(fallo).replace('la comanda', 'el pedido')}")
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        pinta(informe)
    sys.exit(1 if informe["veredicto"].startswith("ARREGLA") else 0)


if __name__ == "__main__":
    main()

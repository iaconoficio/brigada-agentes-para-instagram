#!/usr/bin/env python3
"""
emplata.py · La Brigada (IA con Oficio)

Emplata el trabajo de la brigada: convierte una comanda (un archivo JSON con
las páginas) en un documento para el cliente, en formato móvil (1080x1350,
una idea por página), con los colores de su marca y la firma de La Brigada.

Deja tres cosas al lado de la comanda:

  semana.html              el documento: se abre sin internet en un navegador
                           actualizado (las letras van dentro)
  semana-para-copiar.txt   todos los textos en limpio, para copiar y pegar
  semana.pdf               solo con --pdf y si encuentra Chrome, Chromium o
                           Edge en el ordenador

La firma va en todas las páginas («Hecho con La Brigada · Toni Mont · IA con
Oficio», con enlace a La Brigada) y el documento acaba siempre con la
contraportada de La Brigada. No hay ninguna opción para quitarlas. El código
es abierto (licencia MIT) y cada cual puede cambiar su copia, pero esta
herramienta siempre firma.

Lo que mira antes de emplatar:

  COMANDA     que el JSON esté bien, cada página tenga lo que necesita y cada
              campo sea del tipo que toca. Lo que no conoce, lo deja fuera
  COLORES     que el texto se lea sobre el fondo (contraste de las pautas de
              accesibilidad WCAG: 4,5 como mínimo para el texto, 3 para el
              color de acento, que va en letra grande o en negrita)
  LOGOTIPO    que esté en la carpeta de la comanda, sea PNG, JPG, WEBP o SVG y
              no pese demasiado
  TEXTO       páginas con demasiado texto y rayas largas
  MEDIDO      si encuentra el navegador, comprueba de verdad que nada se sale
              de su página; si no, solo cuenta palabras

Con un navegador basado en Chromium abre el HTML en local, sin ventana, con
un perfil temporal y la red cortada (aunque el navegador intente conectarse,
no sale nada del ordenador), solo para medir y para imprimir el PDF. El
script no se conecta a internet ni envía nada.

Lo que es opinión, no un dato: cuántas palabras caben en cada tipo de página
y cuántos planos o láminas van por página. Están en las constantes de abajo.

Las letras (Fraunces, Space Mono, Archivo Black y Great Vibes) tienen
licencia SIL Open Font License 1.1; las licencias están en assets/fuentes.

Uso
  python3 emplata.py comanda.json
  python3 emplata.py comanda.json --salida semana-v1.html --pdf semana-v1.pdf
  python3 emplata.py comanda.json --sin-navegador
  python3 emplata.py comanda.json --json

Salida: 0 hecho (puede haber OJO o NOTA), 1 hay que arreglar algo,
2 no puedo leer la comanda.
"""

import argparse
import base64
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap

AQUI = pathlib.Path(__file__).resolve().parent
FUENTES = AQUI.parent / "assets" / "fuentes"

# La firma. No hay opción para quitarla.
HECHO_CON = "Hecho con La Brigada"
FIRMA = "Toni Mont · IA con Oficio"
REPO = "https://github.com/iaconoficio/brigada-agentes-para-instagram"
ENLACES = [
    ("La Brigada, gratis", REPO, "github.com/iaconoficio/brigada-agentes-para-instagram"),
    ("La comunidad", "https://chat.whatsapp.com/F4LVhDev0ahGSJixjCsLc9", "Comunidad de IA con Oficio en WhatsApp"),
    ("En Instagram", "https://www.instagram.com/soytonimont/", "@soytonimont"),
]

# Los colores de IA con Oficio: van en la firma, en la contraportada y, si el
# cliente no tiene marca, en todo el documento.
CREMA, MARINO, TOMATE, PAPEL = "#F5ECD6", "#1C2541", "#E0442A", "#FFFBF2"
MARCA_POR_DEFECTO = {"fondo": CREMA, "texto": MARINO, "acento": TOMATE, "suave": PAPEL}

CONTRASTE_TEXTO = 4.5    # WCAG 2.x, texto normal (nivel AA)
CONTRASTE_ACENTO = 3.0   # WCAG 2.x, texto grande o en negrita (nivel AA)
LOGO_MAX = 2 * 1024 * 1024
LOGO_TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".svg": "image/svg+xml"}
PAGINAS_MAX = 40
LAMINAS_MAX_BYTES = 200 * 1024

# Opinión: cuánto cabe en cada página. Lo que pase, avisa (OJO).
POR_PAGINA = {"guion": 3, "laminas": 6, "puntos": 3, "lista": 7, "tabla": 8, "semana": 7}
LIMITES = {
    ("portada", "titulo"): 12, ("portada", "subtitulo"): 30,
    ("idea", "titulo"): 16, ("idea", "texto"): 60,
    ("semana", "tema"): 14, ("puntos", "texto"): 40,
    ("guion", "dices"): 35, ("guion", "cartel"): 8, ("guion", "se_ve"): 16,
    ("lista", "item"): 18, ("laminas", "lamina"): 40, ("tabla", "celda"): 12,
    ("cifras", "texto"): 6, ("texto", "nota"): 25,
}
CAPTION_EN_MAQUETA = 700   # caracteres del texto del post que se ven en la maqueta

TIPOS = {
    "portada": "la primera página: título, subtítulo y las piezas de la semana",
    "idea": "una idea grande: un título y unas pocas frases",
    "semana": "la semana en una mirada: día, hora, formato y tema",
    "puntos": "puntos numerados, cada uno con su fuente si la tiene",
    "guion": "el guion de un reel, plano a plano",
    "texto": "el texto de un post, en una maqueta de móvil",
    "laminas": "las láminas de un carrusel, en pequeño",
    "lista": "una lista para ir marcando",
    "tabla": "una tabla, por ejemplo la del repaso de las 48 horas",
    "cifras": "dos a cuatro números grandes, cada uno con lo que significa",
}
OBLIGATORIOS = {
    "portada": ["titulo"], "idea": ["titulo"], "semana": ["filas"], "puntos": ["puntos"],
    "guion": ["planos"], "texto": ["texto"], "laminas": ["laminas"], "lista": ["items"],
    "tabla": ["columnas", "filas"], "cifras": ["cifras"],
}

# Igual que la Lámina de texto y que revisa_carrusel.py: una lámina por bloque,
# separadas por una línea con tres guiones o más.
SEPARADOR_RE = re.compile(r"(?:^|\n)[ \t]*-{3,}[ \t]*(?=\n|$)")
INVISIBLES = "\u200b\u200c\u200d\u2060\ufeff\u00ad"
ESPACIOS_RAROS = "\u00a0\u202f\u2009\u2007"
_LIMPIEZA = {**{ord(c): None for c in INVISIBLES}, **{ord(c): " " for c in ESPACIOS_RAROS}}
RAYAS_RE = re.compile("[\u2014\u2013]")
COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
HASHTAG_RE = re.compile(r"(?<![\w#&])#(?=\w*[^\W\d_])[^\W_]\w*")


class Comanda(Exception):
    """Un fallo de la comanda que hay que arreglar antes de emplatar."""


# ---------------------------------------------------------------- utilidades

def limpia(texto):
    if texto is None:
        return ""
    return str(texto).replace("\r\n", "\n").replace("\r", "\n").translate(_LIMPIEZA).strip()


def palabras(texto):
    return len(re.findall(r"[^\W_]+(?:[-'’][^\W_]+)*", str(texto)))


def e(texto):
    """Escapa el texto y deja pasar **negrita** y los saltos de línea."""
    seguro = html.escape(limpia(texto))
    seguro = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", seguro)
    return seguro.replace("\n", "<br>")


def separa_laminas(texto):
    trozos = SEPARADOR_RE.split(limpia(texto))
    return [t.strip() for t in trozos if t.strip()]


def hex6(color):
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    return "#" + c.upper()


def luminancia(color):
    c = hex6(color).lstrip("#")
    canales = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        canales.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def coma(numero, decimales=1):
    return f"{numero:.{decimales}f}".replace(".", ",")


def iniciales(nombre):
    trozos = [t for t in re.findall(r"[^\W\d_]+", nombre) if len(t) > 2] or re.findall(r"[^\W\d_]+", nombre)
    return "".join(t[0].upper() for t in trozos[:2]) or "LB"


def cadenas(valor):
    """Todos los textos que hay dentro de un valor JSON."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from cadenas(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from cadenas(v)


# ---------------------------------------------------------------- la comanda

class Lector:
    """Comprueba los tipos de la comanda y deja solo lo que se conoce, ya limpio."""

    SI = {"sí", "si", "true", "yes"}
    NO = {"no", "false"}

    def __init__(self, avisos):
        self.avisos = avisos

    def arregla(self, donde, texto):
        self.avisos.append({"estado": "ARREGLA", "donde": donde, "detalle": texto})

    def ojo(self, donde, texto):
        self.avisos.append({"estado": "OJO", "donde": donde, "detalle": texto})

    def nota(self, donde, texto):
        self.avisos.append({"estado": "NOTA", "donde": donde, "detalle": texto})

    def texto(self, valor, campo, donde):
        """Un texto: vale un texto o un número. Vacío si no hay; None si está mal."""
        if valor is None:
            return ""
        if isinstance(valor, bool) or not isinstance(valor, (str, int, float)):
            self.arregla(donde, f"«{campo}» tiene que ser un texto")
            return None
        return limpia(valor)

    def si_no(self, valor, campo, donde, defecto):
        if valor is None:
            return defecto
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, str) and valor.strip().lower() in self.SI | self.NO:
            return valor.strip().lower() in self.SI
        self.arregla(donde, f"«{campo}» tiene que ser true o false (has puesto «{valor}»)")
        return defecto

    def lista(self, valor, campo, donde, obligatoria=False):
        if valor is None or valor == []:
            if obligatoria:
                self.arregla(donde, f"falta «{campo}», con al menos un elemento")
            return []
        if not isinstance(valor, list):
            self.arregla(donde, f"«{campo}» tiene que ser una lista, entre corchetes [ ]")
            return None
        return valor

    def objeto(self, valor, claves, campo, donde, principal=None):
        """Un objeto con esas claves de texto. Si es un texto suelto y hay clave principal, va ahí."""
        if principal and isinstance(valor, (str, int, float)) and not isinstance(valor, bool):
            valor = {principal: valor}
        if not isinstance(valor, dict):
            self.arregla(donde, f"cada elemento de «{campo}» tiene que ser un objeto con {', '.join(claves)}")
            return None
        limpio = {}
        for clave in claves:
            t = self.texto(valor.get(clave), f"{campo}.{clave}", donde)
            if t is None:
                return None
            limpio[clave] = t
        return limpio


def lee_comanda(ruta):
    try:
        texto = pathlib.Path(ruta).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        raise FileNotFoundError(ruta)
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as fallo:
        raise ValueError(f"el JSON no está bien en la línea {fallo.lineno}, columna {fallo.colno}: {fallo.msg}")
    except RecursionError:
        raise ValueError("el JSON tiene demasiados niveles, uno dentro de otro")
    if not isinstance(datos, dict):
        raise ValueError("la comanda tiene que ser un objeto JSON, entre llaves { }")
    return datos


def _dentro(base, relativa):
    """La ruta, si está dentro de la carpeta de la comanda; si no, None."""
    try:
        ruta = (base / str(relativa)).resolve()
        ruta.relative_to(base.resolve())
    except (ValueError, OSError):
        return None
    return ruta


def prepara(datos, base, avisos):
    """Valida la comanda y la deja lista para pintar. Lanza Comanda si hay que arreglar algo."""
    lee = Lector(avisos)
    base = pathlib.Path(base)

    cabecera = {}
    for campo, maximo, obligatorio in (("titulo", 90, True), ("para", 60, True), ("cuenta", 40, False),
                                       ("preparado_por", 60, False), ("fecha", 60, False)):
        valor = lee.texto(datos.get(campo), campo, "COMANDA")
        if valor is None:
            continue
        if obligatorio and not valor:
            explica = ("el nombre del documento, por ejemplo «Tu semana del 16 de noviembre»" if campo == "titulo"
                       else "el nombre del negocio o de la persona que lo recibe")
            lee.arregla("COMANDA", f"falta «{campo}»: {explica}")
        elif "\n" in valor:
            lee.arregla("COMANDA", f"«{campo}» va en una sola línea")
        elif len(valor) > maximo:
            lee.arregla("COMANDA", f"«{campo}» tiene {len(valor)} caracteres: como mucho {maximo}")
        cabecera[campo] = valor or ""
    for valor in cadenas({k: cabecera.get(k) for k in cabecera}):
        if RAYAS_RE.search(valor):
            lee.ojo("COMANDA", "hay rayas largas (— o –). La Brigada no las usa: cámbialas por un punto, una coma "
                               "o dos puntos")
            break

    paginas = lee.lista(datos.get("paginas"), "paginas", "COMANDA", obligatoria=True) or []
    if len(paginas) > PAGINAS_MAX:
        lee.arregla("COMANDA", f"hay {len(paginas)} páginas: como mucho {PAGINAS_MAX}. Parte el documento en dos")

    # La marca: la del cliente, o la de La Brigada si no tiene.
    marca = dict(MARCA_POR_DEFECTO)
    propia = datos.get("marca")
    if propia is None:
        propia = {}
    if not isinstance(propia, dict):
        lee.arregla("MARCA", "«marca» tiene que ser un objeto con fondo, texto, acento y suave")
        propia = {}
    for clave in ("fondo", "texto", "acento", "suave"):
        valor = propia.get(clave)
        if valor is None:
            continue
        if not isinstance(valor, str) or not COLOR_RE.match(valor.strip()):
            lee.arregla("MARCA", f"«{clave}» tiene que ser un color en código, como #1C2541 (has puesto «{valor}»)")
            continue
        marca[clave] = hex6(valor.strip())
    marca["propia"] = any(propia.get(k) is not None for k in ("fondo", "texto", "acento", "suave"))
    marca["manuscrita"] = lee.si_no(propia.get("manuscrita"), "manuscrita", "MARCA", False)

    logo = None
    if propia.get("logo") is not None:
        if not isinstance(propia["logo"], str) or not propia["logo"].strip():
            lee.arregla("LOGOTIPO", "«logo» tiene que ser la ruta del archivo, desde la carpeta de la comanda")
        else:
            ruta = _dentro(base, propia["logo"])
            tipo = LOGO_TIPOS.get(ruta.suffix.lower()) if ruta else None
            if ruta is None:
                lee.arregla("LOGOTIPO", f"«{propia['logo']}» tiene que estar dentro de la carpeta de la comanda")
            elif not ruta.is_file():
                lee.arregla("LOGOTIPO", f"no encuentro «{propia['logo']}» (la ruta es desde la carpeta de la comanda)")
            elif not tipo:
                lee.arregla("LOGOTIPO", f"«{ruta.name}» tiene que ser PNG, JPG, WEBP o SVG")
            elif ruta.stat().st_size > LOGO_MAX:
                lee.arregla("LOGOTIPO", f"«{ruta.name}» pesa más de 2 MB: guárdalo más pequeño")
            else:
                logo = f"data:{tipo};base64," + base64.b64encode(ruta.read_bytes()).decode()

    limpias = []
    for n, pagina in enumerate(paginas, 1):
        limpia_pagina = _valida_pagina(pagina, base, f"PÁGINA {n}", lee)
        if limpia_pagina is not None:
            limpias.append(limpia_pagina)

    if any(a["estado"] == "ARREGLA" for a in avisos):
        raise Comanda()

    # Contraste: el texto se tiene que leer.
    texto_fondo = contraste(marca["texto"], marca["fondo"])
    texto_suave = contraste(marca["texto"], marca["suave"])
    acento_fondo = contraste(marca["acento"], marca["fondo"])
    acento_suave = contraste(marca["acento"], marca["suave"])
    if texto_fondo < CONTRASTE_TEXTO:
        lee.arregla("COLORES", f"el texto no se lee bien sobre el fondo: contraste {coma(texto_fondo)}, "
                               f"y hace falta {coma(CONTRASTE_TEXTO)} como mínimo. Oscurece el texto o aclara el fondo")
    if texto_suave < CONTRASTE_TEXTO:
        lee.arregla("COLORES", f"el texto no se lee bien sobre el color suave de las tarjetas: contraste "
                               f"{coma(texto_suave)}, y hace falta {coma(CONTRASTE_TEXTO)}")
    if any(a["estado"] == "ARREGLA" for a in avisos):
        raise Comanda()
    if acento_fondo < CONTRASTE_ACENTO:
        lee.ojo("COLORES", f"el color de acento se lee justo sobre el fondo (contraste {coma(acento_fondo)}; "
                           f"mejor {coma(CONTRASTE_ACENTO)} o más). Va en los antetítulos")
    if acento_suave < CONTRASTE_ACENTO:
        lee.ojo("COLORES", f"el color de acento se lee justo sobre las tarjetas (contraste {coma(acento_suave)}; "
                           f"mejor {coma(CONTRASTE_ACENTO)} o más). Va en los números grandes")
    blanco, ink = "#FFFFFF", marca["texto"]
    marca["sobre_acento"] = blanco if contraste(marca["acento"], blanco) >= contraste(marca["acento"], ink) else ink
    if contraste(marca["acento"], marca["sobre_acento"]) < CONTRASTE_ACENTO:
        lee.ojo("COLORES", "las etiquetas de color (días y formatos) se leen justo: prueba un acento más oscuro "
                           "o más claro")
    return {**cabecera, "marca": marca, "logo": logo, "paginas": limpias,
            "contrastes": {"texto": texto_fondo, "acento": acento_fondo}}


def _valida_pagina(pagina, base, donde, lee):
    """Devuelve la página limpia, solo con los campos que se conocen, o None si hay que arreglarla."""
    if not isinstance(pagina, dict):
        lee.arregla(donde, "cada página tiene que ser un objeto con su «tipo»")
        return None
    tipo = pagina.get("tipo")
    if tipo == "contraportada":
        lee.arregla(donde, "la contraportada la pone el script al final; quítala de la comanda")
        return None
    if not isinstance(tipo, str) or tipo not in TIPOS:
        lee.arregla(donde, f"el tipo «{tipo}» no existe. Los tipos son: {', '.join(TIPOS)}")
        return None
    antes = sum(1 for a in lee.avisos if a["estado"] == "ARREGLA")
    p = {"tipo": tipo}
    for campo in ("antetitulo", "titulo", "subtitulo", "texto", "nota", "imagen"):
        valor = lee.texto(pagina.get(campo), campo, donde)
        if valor:
            p[campo] = valor
    for campo, defecto in (("oscura", False), ("casillas", True)):
        p[campo] = lee.si_no(pagina.get(campo), campo, donde, defecto)
    if tipo == "portada":
        p.pop("nota", None)   # la portada no lleva nota: abajo va para quién es

    if tipo in ("portada", "idea") and not p.get("titulo"):
        lee.arregla(donde, f"a la página de tipo «{tipo}» le falta «titulo»")
    if tipo == "texto" and not p.get("texto"):
        lee.arregla(donde, "a la página de tipo «texto» le falta «texto»: el texto del post entero")

    if tipo == "portada":
        piezas = lee.lista(pagina.get("piezas"), "piezas", donde) or []
        p["piezas"] = [x for x in (lee.objeto(v, ("dia", "formato"), "piezas", donde) for v in piezas) if x]
        if len(p["piezas"]) > 4:
            lee.ojo(donde, "en la portada caben 4 piezas: las demás no salen")
            p["piezas"] = p["piezas"][:4]
    elif tipo == "semana":
        filas = lee.lista(pagina.get("filas"), "filas", donde, obligatoria=True) or []
        p["filas"] = [x for x in (lee.objeto(v, ("dia", "hora", "formato", "tema"), "filas", donde) for v in filas)
                      if x]
    elif tipo == "puntos":
        puntos = lee.lista(pagina.get("puntos"), "puntos", donde, obligatoria=True) or []
        p["puntos"] = [x for x in (lee.objeto(v, ("texto", "fuente"), "puntos", donde, "texto") for v in puntos) if x]
    elif tipo == "guion":
        planos = lee.lista(pagina.get("planos"), "planos", donde, obligatoria=True) or []
        p["planos"] = [x for x in (lee.objeto(v, ("dices", "cartel", "se_ve"), "planos", donde, "dices")
                                   for v in planos) if x]
    elif tipo == "texto":
        notas = pagina.get("notas")
        if isinstance(notas, (str, int, float)) and not isinstance(notas, bool):
            notas = [notas]
        notas = lee.lista(notas, "notas", donde) or []
        p["notas"] = [t for t in (lee.texto(v, "notas", donde) for v in notas) if t]
    elif tipo == "laminas":
        p["laminas"] = _laminas(pagina.get("laminas"), base, donde, lee)
    elif tipo == "lista":
        items = lee.lista(pagina.get("items"), "items", donde, obligatoria=True) or []
        p["items"] = [t for t in (lee.texto(v, "items", donde) for v in items) if t]
    elif tipo == "tabla":
        columnas = lee.lista(pagina.get("columnas"), "columnas", donde, obligatoria=True) or []
        p["columnas"] = [t for t in (lee.texto(v, "columnas", donde) for v in columnas) if t is not None]
        if p["columnas"] and not 2 <= len(p["columnas"]) <= 5:
            lee.arregla(donde, "una tabla lleva de 2 a 5 columnas")
        filas = lee.lista(pagina.get("filas"), "filas", donde, obligatoria=True) or []
        p["filas"] = []
        for fila in filas:
            if not isinstance(fila, list) or len(fila) != len(p["columnas"]):
                lee.arregla(donde, f"cada fila de la tabla tiene que tener {len(p['columnas'])} celdas, "
                                   "como las columnas")
                break
            celdas = [lee.texto(v, "filas", donde) for v in fila]
            if None in celdas:
                break
            p["filas"].append(celdas)
    elif tipo == "cifras":
        cifras = lee.lista(pagina.get("cifras"), "cifras", donde, obligatoria=True) or []
        p["cifras"] = [x for x in (lee.objeto(v, ("numero", "texto"), "cifras", donde) for v in cifras) if x]
        if cifras and not 2 <= len(cifras) <= 4:
            lee.arregla(donde, "una página de cifras lleva de 2 a 4 números")

    if sum(1 for a in lee.avisos if a["estado"] == "ARREGLA") > antes:
        return None
    campo = TROCEABLES.get(tipo)
    if campo and not p.get(campo):
        lee.arregla(donde, f"la página de tipo «{tipo}» está vacía: no tiene nada en «{campo}»")
        return None
    _mira_textos(p, donde, lee)
    return p


def _laminas(valor, base, donde, lee):
    if isinstance(valor, dict) and "archivo" in valor:
        if not isinstance(valor["archivo"], str) or not valor["archivo"].strip():
            lee.arregla(donde, "«archivo» tiene que ser la ruta del carrusel, desde la carpeta de la comanda")
            return []
        ruta = _dentro(base, valor["archivo"])
        if ruta is None:
            lee.arregla(donde, f"«{valor['archivo']}» tiene que estar dentro de la carpeta de la comanda")
            return []
        if ruta.suffix.lower() not in (".txt", ".md"):
            lee.arregla(donde, f"«{ruta.name}» tiene que ser un archivo de texto (.txt o .md)")
            return []
        try:
            if ruta.stat().st_size > LAMINAS_MAX_BYTES:
                lee.arregla(donde, f"«{ruta.name}» es demasiado grande para ser un carrusel")
                return []
            return separa_laminas(ruta.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError):
            lee.arregla(donde, f"no puedo leer «{valor['archivo']}» (la ruta es desde la carpeta de la comanda)")
            return []
    if isinstance(valor, str):
        return separa_laminas(valor)
    if isinstance(valor, list) and all(isinstance(x, str) for x in valor):
        return [limpia(x) for x in valor if limpia(x)]
    lee.arregla(donde, "«laminas» tiene que ser una lista de textos, un texto con las láminas separadas por --- "
                       "o {\"archivo\": \"carrusel.txt\"}")
    return []


def _textos_de(p):
    """Los textos de una página ya limpia, con la etiqueta de su límite."""
    tipo = p["tipo"]
    for campo in ("titulo", "subtitulo"):
        yield (tipo, campo), p.get(campo, "")
    if tipo != "texto":
        yield (tipo, "texto"), p.get("texto", "")
    for fila in p.get("filas") or []:
        if tipo == "semana":
            yield ("semana", "tema"), fila["tema"]
        else:
            for celda in fila:
                yield ("tabla", "celda"), celda
    for punto in p.get("puntos") or []:
        yield ("puntos", "texto"), punto["texto"]
    for plano in p.get("planos") or []:
        for campo in ("dices", "cartel", "se_ve"):
            yield ("guion", campo), plano[campo]
    for item in p.get("items") or []:
        yield ("lista", "item"), item
    for lamina in p.get("laminas") or []:
        yield ("laminas", "lamina"), lamina
    for cifra in p.get("cifras") or []:
        yield ("cifras", "texto"), cifra["texto"]
    for nota in p.get("notas") or []:
        yield ("texto", "nota"), nota


def _mira_textos(p, donde, lee):
    largos = []
    for clave, valor in _textos_de(p):
        limite = LIMITES.get(clave)
        if valor and limite and palabras(valor) > limite:
            largos.append((clave[1], palabras(valor), limite))
    if any(RAYAS_RE.search(t) for t in cadenas(p)):
        lee.ojo(donde, "hay rayas largas (— o –). La Brigada no las usa: cámbialas por un punto, una coma o dos puntos")
    for campo, n, limite in largos[:3]:
        lee.ojo(donde, f"«{campo}» tiene {n} palabras y puede no caber (mejor {limite} o menos)")
    if p["tipo"] == "texto" and len(p["texto"]) > CAPTION_EN_MAQUETA:
        p["corte"] = True
        lee.nota(donde, f"el texto del post pasa de {CAPTION_EN_MAQUETA} caracteres: en la maqueta se corta con "
                        "«más», como en Instagram. Entero va en el archivo para copiar")


# ---------------------------------------------------------------- el diseño

def css(marca):
    return """
:root{--fondo:%(fondo)s;--texto:%(texto)s;--acento:%(acento)s;--suave:%(suave)s;--sobre-acento:%(sobre_acento)s;
--crema:%(crema)s;--marino:%(marino)s;--tomate:%(tomate)s}
@page{size:1080px 1350px;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html{background:#D8D4CB}
body{font-family:'Fraunces',Georgia,'Times New Roman',serif;color:var(--texto);-webkit-print-color-adjust:exact;
print-color-adjust:exact;text-rendering:optimizeLegibility}
.p{position:relative;overflow:hidden;width:min(1080px,calc(100vw - 20px));aspect-ratio:1080/1350;
container-type:inline-size;background:var(--fondo);color:var(--texto);margin:0 auto 22px;
background-image:linear-gradient(165deg,color-mix(in srgb,var(--acento) 7%%,var(--fondo)) 0%%,var(--fondo) 48%%)}
.deco{position:absolute;border-radius:50%%;pointer-events:none}
.deco.sol{right:-20cqw;top:-22cqw;width:66cqw;height:66cqw;background:var(--acento);opacity:.1}
.deco.aro{right:-7cqw;top:-9cqw;width:36cqw;height:36cqw;border:.35cqw solid var(--acento);opacity:.35}
.cuerpo .centro{margin-top:auto;margin-bottom:auto}
@media screen{body{padding:22px 0}.p{border-radius:min(26px,2.4vw);box-shadow:0 14px 40px -22px rgba(0,0,0,.5)}
.p.desborda{outline:6px dashed #D11;outline-offset:-6px}
.p.desborda::after{content:'Esta página se sale: corta el texto o pártela en dos';position:absolute;top:2cqw;left:2cqw;
background:#D11;color:#fff;font:700 1.8cqw/1.3 'Space Mono',monospace;padding:.8cqw 1.4cqw;border-radius:1cqw}}
@media print{html{background:none}body{padding:0}.p{width:1080px;height:1350px;margin:0;break-after:page;
border-radius:0;box-shadow:none}.p:last-child{break-after:auto}}
.cuerpo{position:absolute;left:8.5cqw;right:8.5cqw;top:8.6cqw;bottom:12.4cqw;overflow:hidden;display:flex;
flex-direction:column}
.firma{position:absolute;left:8.5cqw;right:8.5cqw;bottom:4.5cqw;display:flex;align-items:center;gap:1.3cqw;
font-family:'Space Mono',monospace;font-weight:700;font-size:1.72cqw;letter-spacing:.12em;text-transform:uppercase;
color:var(--texto);text-decoration:none}
.firma .sello{flex:none;width:1.35cqw;height:1.35cqw;background:var(--tomate)}
.firma .num{margin-left:auto;font-weight:400}
.oscura{background:var(--texto);background-image:none;color:var(--fondo)}
.oscura .firma{color:var(--fondo)}
.oscura .eti{color:var(--fondo)}
.eti{font-family:'Space Mono',monospace;font-weight:700;font-size:2.05cqw;letter-spacing:.14em;
text-transform:uppercase;color:var(--acento)}
.raya{flex:none;width:5.6cqw;height:.42cqw;background:var(--acento);margin-top:2cqw}
h1{font-weight:650;font-size:10.8cqw;line-height:1.02;letter-spacing:-.012em;margin-top:3.2cqw;
font-variation-settings:'opsz' 144}
h1.manuscrita{font-family:'Great Vibes',cursive;font-weight:400;font-size:13.5cqw;line-height:1;letter-spacing:0;
color:var(--acento)}
h2{font-weight:650;font-size:6.1cqw;line-height:1.06;letter-spacing:-.01em;margin-top:2.4cqw}
h2.grande{font-size:7.6cqw}
.lead{font-size:3.3cqw;line-height:1.42;margin-top:3cqw}
.txt{font-size:2.7cqw;line-height:1.45}
.chico{font-size:2.25cqw;line-height:1.45}
.suave{font-style:italic}
.empuja{margin-top:auto}
.tarjeta{background:var(--suave);border-radius:2.5cqw;padding:3.1cqw 3.5cqw;
box-shadow:0 .2cqw 0 rgba(0,0,0,.04),0 2.2cqw 4.6cqw -3cqw rgba(0,0,0,.28)}
.oscura .tarjeta{background:rgba(255,255,255,.08);box-shadow:none}
.chip{display:inline-block;font-family:'Space Mono',monospace;font-weight:700;font-size:1.7cqw;letter-spacing:.1em;
text-transform:uppercase;padding:.72cqw 1.45cqw;border-radius:999px;background:var(--acento);color:var(--sobre-acento);
white-space:nowrap}
.chip.linea{background:transparent;border:.22cqw solid currentColor;color:var(--texto)}
.logo{max-height:9cqw;max-width:34cqw;object-fit:contain;align-self:flex-start;margin-bottom:4cqw}
.para{font-size:2.35cqw;line-height:1.45}
.para .cuenta{font-family:'Space Mono',monospace;font-size:1.9cqw;letter-spacing:.04em}
.piezas{display:flex;gap:2.2cqw;margin-top:5.4cqw}
.pieza{flex:1;text-align:center;padding:3.6cqw 1.5cqw}
.pieza .dia{font-style:italic;font-weight:500;font-size:5.2cqw;line-height:1.05}
.pieza .chip{margin-top:1.3cqw}
.fila-semana{display:grid;grid-template-columns:19cqw 11cqw 16cqw 1fr;gap:2cqw;align-items:center;margin-top:2.4cqw;
padding:3.4cqw 3.2cqw}
.fila-semana .dia{font-style:italic;font-weight:500;font-size:4.4cqw;line-height:1.05}
.fila-semana .hora{font-family:'Space Mono',monospace;font-weight:700;font-size:2.5cqw}
.fila-semana .tema{font-size:2.75cqw;line-height:1.32}
.punto{display:flex;gap:3cqw;margin-top:2.4cqw;align-items:flex-start}
.n-grande{flex:none;font-family:'Archivo Black',sans-serif;font-size:5.4cqw;line-height:1;color:var(--acento)}
.fuente{display:inline-block;margin-top:1.4cqw;font-family:'Space Mono',monospace;font-size:1.55cqw;letter-spacing:.06em;
text-transform:uppercase;border:.18cqw solid currentColor;border-radius:999px;padding:.5cqw 1.3cqw}
.plano{display:flex;gap:3.2cqw;align-items:flex-start;margin-top:2.6cqw}
.marco{flex:none;width:12.6cqw;height:22.4cqw;border-radius:2cqw;background:var(--texto);color:var(--fondo);
display:flex;align-items:center;justify-content:center;text-align:center;padding:1.3cqw;position:relative;
font-family:'Archivo Black',sans-serif;font-size:1.75cqw;line-height:1.12;overflow:hidden}
.oscura .marco{background:var(--fondo);color:var(--texto)}
.marco .n{position:absolute;top:1cqw;left:1.2cqw;font-family:'Space Mono',monospace;font-size:1.4cqw}
.dices{font-size:2.9cqw;line-height:1.4}
.se-ve{font-family:'Space Mono',monospace;font-size:1.6cqw;letter-spacing:.04em;text-transform:uppercase;
color:var(--acento);margin-top:1.1cqw}
.oscura .se-ve{color:var(--fondo)}
.movil-y-notas{display:flex;gap:4.4cqw;margin-top:3.2cqw;align-items:flex-start}
.movil{flex:none;width:50cqw;background:#fff;border-radius:4.2cqw;border:1.1cqw solid var(--texto);overflow:hidden;
box-shadow:0 2.8cqw 5.6cqw -2.8cqw rgba(0,0,0,.5)}
.ig-cab{display:flex;align-items:center;gap:1.3cqw;padding:1.7cqw 2cqw;font-family:-apple-system,'Helvetica Neue',
Arial,sans-serif;font-weight:700;font-size:1.95cqw;color:#0F1419}
.ava{flex:none;width:4.3cqw;height:4.3cqw;border-radius:50%%;background:var(--acento);color:var(--sobre-acento);display:flex;
align-items:center;justify-content:center;font-family:'Fraunces',serif;font-weight:650;font-size:1.6cqw}
.ig-img{height:27cqw;background:var(--suave);display:flex;align-items:center;justify-content:center;
font-family:'Space Mono',monospace;font-weight:700;font-size:1.7cqw;letter-spacing:.1em;text-transform:uppercase;
color:var(--texto);border-top:.12cqw solid rgba(0,0,0,.06);border-bottom:.12cqw solid rgba(0,0,0,.06);text-align:center;
padding:2cqw}
.ig-txt{padding:1.9cqw 2.4cqw 2.4cqw;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;font-size:1.92cqw;
line-height:1.42;color:#0F1419;word-wrap:break-word}
.ig-txt .h{color:#00376B}
.ig-txt .mas{color:#737373}
.notas{flex:1}
.notas p{margin-top:2cqw}
.notas p:first-child{margin-top:0}
.rejilla{display:grid;grid-template-columns:repeat(3,1fr);gap:2.3cqw;margin-top:3.2cqw}
.mini{aspect-ratio:4/5;background:var(--suave);border-radius:1.8cqw;padding:2.2cqw 2cqw;position:relative;overflow:hidden;
box-shadow:0 1.4cqw 3cqw -2cqw rgba(0,0,0,.35);display:flex;flex-direction:column;justify-content:center}
.mini .n{position:absolute;top:1.3cqw;left:1.6cqw;font-family:'Space Mono',monospace;font-weight:700;font-size:1.35cqw;
color:var(--acento);letter-spacing:.06em}
.mini .l1{font-weight:650;font-size:2.05cqw;line-height:1.16}
.mini .resto{font-size:1.45cqw;line-height:1.36;margin-top:1cqw}
.check{display:flex;gap:2.8cqw;align-items:flex-start;margin-top:3.4cqw}
.check .txt{font-size:3.15cqw;line-height:1.38}
.caja{flex:none;width:4.2cqw;height:4.2cqw;border:.36cqw solid var(--acento);border-radius:1cqw;margin-top:.3cqw}
.bola{flex:none;width:1.6cqw;height:1.6cqw;border-radius:50%%;background:var(--acento);margin-top:1.15cqw}
table{width:100%%;border-collapse:separate;border-spacing:0;margin-top:3.2cqw;font-size:2.6cqw;line-height:1.35;
background:var(--suave);border-radius:2.2cqw;overflow:hidden}
th{font-family:'Space Mono',monospace;font-weight:700;font-size:1.6cqw;letter-spacing:.08em;text-transform:uppercase;
text-align:left;padding:2.2cqw 2cqw;background:var(--texto);color:var(--fondo)}
td{padding:3.4cqw 2cqw;border-top:.14cqw solid rgba(0,0,0,.1);vertical-align:top}
td:empty::after{content:'';display:block;height:2.6cqw;border-bottom:.18cqw dashed rgba(0,0,0,.28)}
.cifras{display:flex;gap:2.4cqw;margin-top:4cqw}
.cifra{flex:1;text-align:center;padding:5.4cqw 1.6cqw}
.cifra .numero{font-family:'Archivo Black',sans-serif;font-size:12cqw;line-height:1;color:var(--acento)}
.cifra .que{font-family:'Space Mono',monospace;font-weight:700;font-size:1.75cqw;letter-spacing:.08em;
text-transform:uppercase;margin-top:1.4cqw;line-height:1.35}
.contra{background:var(--marino);background-image:none;color:var(--crema)}
.contra .deco.aro{border-color:var(--tomate)}
.contra .eti{color:var(--tomate)}
.contra .raya{background:var(--tomate)}
.contra .firma{color:var(--crema)}
.contra h2{font-size:8cqw}
.enlaces{margin-top:4.4cqw;display:flex;flex-direction:column;gap:1.9cqw}
.enlace{display:block;text-decoration:none;color:var(--crema);border:.2cqw solid rgba(245,236,214,.35);
border-radius:2.2cqw;padding:2.3cqw 2.8cqw}
.enlace .que{display:block;font-family:'Space Mono',monospace;font-weight:700;font-size:1.6cqw;letter-spacing:.12em;
text-transform:uppercase;color:var(--tomate)}
.enlace .donde{display:block;font-size:2.7cqw;line-height:1.3;margin-top:.6cqw;word-break:break-word}
.firma-grande{font-size:4.2cqw;font-weight:650;margin-top:auto}
.firma-grande i{font-weight:400}
""" % {**marca, "crema": CREMA, "marino": MARINO, "tomate": TOMATE}


def _fuente(familia, archivo, peso, estilo="normal"):
    datos = base64.b64encode((FUENTES / archivo).read_bytes()).decode()
    return (f"@font-face{{font-family:'{familia}';src:url(data:font/woff2;base64,{datos}) format('woff2');"
            f"font-weight:{peso};font-style:{estilo};font-display:block}}")


def fuentes(manuscrita):
    lista = [
        _fuente("Fraunces", "fraunces-latin-wght-normal.woff2", "100 900"),
        _fuente("Fraunces", "fraunces-latin-wght-italic.woff2", "100 900", "italic"),
        _fuente("Space Mono", "space-mono-latin-400-normal.woff2", "400"),
        _fuente("Space Mono", "space-mono-latin-700-normal.woff2", "700"),
        _fuente("Archivo Black", "archivo-black-latin-400-normal.woff2", "400"),
    ]
    if manuscrita:
        lista.append(_fuente("Great Vibes", "great-vibes-latin-400-normal.woff2", "400"))
    return "\n".join(lista)


MEDIDOR = """
(function(){function mide(){var malas=[];var ps=document.querySelectorAll('.p');
for(var i=0;i<ps.length;i++){var cajas=ps[i].querySelectorAll('.medir');for(var j=0;j<cajas.length;j++){
var c=cajas[j];if(c.scrollHeight>c.clientHeight+2||c.scrollWidth>c.clientWidth+2){ps[i].classList.add('desborda');
malas.push(i+1);break;}}}document.documentElement.setAttribute('data-desbordes',malas.join(','));
document.documentElement.setAttribute('data-medido','si');}
function listas(){return !document.fonts||(document.fonts.check('700 20px "Space Mono"')&&document.fonts.check('600 20px Fraunces'));}
function intenta(n){if(listas()||n<=0){document.documentElement.setAttribute('data-letras',listas()?'si':'no');mide();}
else{setTimeout(function(){intenta(n-1);},100);}}
window.addEventListener('load',function(){intenta(30);});})();
"""


def _cab(pagina, extra=""):
    """El antetítulo con su raya. Si la página viene partida, lleva «1 de 2» aunque no tenga antetítulo."""
    partes = [e(pagina["antetitulo"])] if pagina.get("antetitulo") else []
    if extra:
        partes.append(html.escape(extra))
    if not partes:
        return ""
    return f'<div class="eti">{" · ".join(partes)}</div><div class="raya"></div>'


def _con_hashtags(texto):
    seguro = e(texto)
    return HASHTAG_RE.sub(lambda m: f'<span class="h">{m.group(0)}</span>', seguro)


def pinta_portada(p, doc):
    partes = []
    if doc["logo"]:
        partes.append(f'<img class="logo" src="{doc["logo"]}" alt="Logotipo de {html.escape(doc["para"])}">')
    partes.append(_cab(p))
    clase = ' class="manuscrita"' if doc["marca"]["manuscrita"] else ""
    partes.append(f'<h1{clase}>{e(p["titulo"])}</h1>')
    if p.get("subtitulo"):
        partes.append(f'<p class="lead">{e(p["subtitulo"])}</p>')
    piezas = [x for x in (p.get("piezas") or []) if isinstance(x, dict)][:4]
    if piezas:
        celdas = "".join(f'<div class="tarjeta pieza"><div class="dia">{e(x.get("dia", ""))}</div>'
                         f'<div class="chip">{e(x.get("formato", ""))}</div></div>' for x in piezas)
        partes.append(f'<div class="piezas">{celdas}</div>')
    pie = [f'<b>{e(doc["para"])}</b>']
    if doc["cuenta"]:
        pie.append(f'<span class="cuenta">{e(doc["cuenta"])}</span>')
    linea = " · ".join(pie)
    quien = (f'Preparado por {e(doc["preparado_por"])} con La Brigada' if doc["preparado_por"]
             else "Preparado con La Brigada")
    fecha = f' · {e(doc["fecha"])}' if doc["fecha"] else ""
    partes.append(f'<p class="para empuja">{linea}<br><span class="suave">{quien}{fecha}</span></p>')
    return "".join(partes), ""


def pinta_idea(p, doc):
    texto = f'<p class="lead">{e(p["texto"])}</p>' if p.get("texto") else ""
    partes = [_cab(p), f'<div class="centro"><h2 class="grande">{e(p["titulo"])}</h2>{texto}</div>']
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), "oscura" if p.get("oscura") else ""


def pinta_semana(p, doc):
    partes = [_cab(p, p.get("_parte", ""))]
    if p.get("titulo"):
        partes.append(f'<h2>{e(p["titulo"])}</h2>')
    filas = []
    for f in p["filas"]:
        filas.append(f'<div class="tarjeta fila-semana"><div class="dia">{e(f.get("dia", ""))}</div>'
                     f'<div class="hora">{e(f.get("hora", ""))}</div><div><span class="chip">{e(f.get("formato", ""))}'
                     f'</span></div><div class="tema">{e(f.get("tema", ""))}</div></div>')
    partes.append(f'<div class="centro">{"".join(filas)}</div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), ""


def pinta_puntos(p, doc):
    partes = [_cab(p, p.get("_parte", ""))]
    if p.get("titulo"):
        partes.append(f'<h2>{e(p["titulo"])}</h2>')
    inicio = p.get("_desde", 1)
    for i, punto in enumerate(p["puntos"], inicio):
        texto = punto.get("texto", "") if isinstance(punto, dict) else punto
        fuente = punto.get("fuente", "") if isinstance(punto, dict) else ""
        extra = f'<span class="fuente">{e(fuente)}</span>' if fuente else ""
        partes.append(f'<div class="tarjeta punto"><div class="n-grande">{i:02d}</div><div><p class="txt">{e(texto)}</p>'
                      f'{extra}</div></div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), ""


def pinta_guion(p, doc):
    partes = [_cab(p, p.get("_parte", ""))]
    if p.get("titulo"):
        partes.append(f'<h2>{e(p["titulo"])}</h2>')
    inicio = p.get("_desde", 1)
    for i, plano in enumerate(p["planos"], inicio):
        if not isinstance(plano, dict):
            plano = {"dices": plano}
        cartel = e(plano.get("cartel", "")) or "&nbsp;"
        se_ve = f'<div class="se-ve">Se ve: {e(plano["se_ve"])}</div>' if plano.get("se_ve") else ""
        partes.append(f'<div class="plano"><div class="marco medir"><span class="n">{i}</span>{cartel}</div>'
                      f'<div><p class="dices">{e(plano.get("dices", ""))}</p>{se_ve}</div></div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), "oscura" if p.get("oscura") else ""


def pinta_texto(p, doc):
    partes = [_cab(p)]
    if p.get("titulo"):
        partes.append(f'<h2>{e(p["titulo"])}</h2>')
    cuenta = (doc["cuenta"] or doc["para"]).lstrip("@")
    texto = limpia(p["texto"])
    corto = texto
    if len(texto) > CAPTION_EN_MAQUETA:
        corto = texto[:CAPTION_EN_MAQUETA].rsplit(" ", 1)[0]
    cuerpo = _con_hashtags(corto) + ('<span class="mas">… más</span>' if corto != texto else "")
    imagen = e(p.get("imagen", "")) or "La imagen"
    movil = (f'<div class="movil"><div class="ig-cab"><span class="ava">{iniciales(doc["para"])}</span>'
             f'{html.escape(cuenta)}</div><div class="ig-img">{imagen}</div>'
             f'<div class="ig-txt"><b>{html.escape(cuenta)}</b> {cuerpo}</div></div>')
    notas = [x for x in (p.get("notas") or []) if x]
    if p.get("nota"):
        notas.append(p["nota"])
    if p.get("corte"):
        notas.append("En la maqueta se corta como en Instagram. El texto entero está en el archivo para copiar.")
    lado = "".join(f'<p class="chico">{e(x)}</p>' for x in notas)
    partes.append(f'<div class="movil-y-notas">{movil}<div class="notas">{lado}</div></div>')
    return "".join(partes), ""


def pinta_laminas(p, doc):
    partes = [_cab(p, p.get("_parte", ""))]
    if p.get("titulo"):
        partes.append(f'<h2>{e(p["titulo"])}</h2>')
    inicio = p.get("_desde", 1)
    minis = []
    for i, lamina in enumerate(p["laminas"], inicio):
        trozos = [t.strip() for t in re.split(r"\n\s*\n", lamina) if t.strip()]
        primera = e(trozos[0]) if trozos else ""
        resto = "".join(f'<p class="resto">{e(t)}</p>' for t in trozos[1:])
        minis.append(f'<div class="mini medir"><span class="n">{i:02d}</span><p class="l1">{primera}</p>{resto}</div>')
    partes.append(f'<div class="rejilla">{"".join(minis)}</div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), ""


def pinta_lista(p, doc):
    partes = [_cab(p, p.get("_parte", "")), f'<h2>{e(p.get("titulo", ""))}</h2>' if p.get("titulo") else ""]
    marca = '<span class="caja"></span>' if p.get("casillas", True) else '<span class="bola"></span>'
    filas = "".join(f'<div class="check">{marca}<p class="txt">{e(item)}</p></div>' for item in p["items"])
    partes.append(f'<div class="centro">{filas}</div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), ""


def pinta_tabla(p, doc):
    partes = [_cab(p, p.get("_parte", "")), f'<h2>{e(p.get("titulo", ""))}</h2>' if p.get("titulo") else ""]
    cabeza = "".join(f"<th>{e(c)}</th>" for c in p["columnas"])
    filas = "".join("<tr>" + "".join(f"<td>{e(c) if str(c).strip() else ''}</td>" for c in f) + "</tr>"
                    for f in p["filas"])
    partes.append(f'<table class="centro"><thead><tr>{cabeza}</tr></thead><tbody>{filas}</tbody></table>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja">{e(p["nota"])}</p>')
    return "".join(partes), ""


def pinta_cifras(p, doc):
    partes = [_cab(p), f'<h2>{e(p.get("titulo", ""))}</h2>' if p.get("titulo") else ""]
    celdas = "".join(f'<div class="tarjeta cifra"><div class="numero">{e(c.get("numero", ""))}</div>'
                     f'<div class="que">{e(c.get("texto", ""))}</div></div>' for c in p["cifras"] if isinstance(c, dict))
    partes.append(f'<div class="cifras centro">{celdas}</div>')
    if p.get("nota"):
        partes.append(f'<p class="chico suave empuja" style="margin-top:3cqw">{e(p["nota"])}</p>')
    return "".join(partes), ""


PINTORES = {"portada": pinta_portada, "idea": pinta_idea, "semana": pinta_semana, "puntos": pinta_puntos,
            "guion": pinta_guion, "texto": pinta_texto, "laminas": pinta_laminas, "lista": pinta_lista,
            "tabla": pinta_tabla, "cifras": pinta_cifras}
TROCEABLES = {"guion": "planos", "laminas": "laminas", "puntos": "puntos", "lista": "items", "tabla": "filas",
              "semana": "filas"}


def trocea(paginas):
    """Parte en varias las páginas con más planos, láminas o filas de los que caben."""
    salida = []
    for p in paginas:
        campo = TROCEABLES.get(p["tipo"])
        cabe = POR_PAGINA.get(p["tipo"])
        lista = p.get(campo) if campo else None
        if not campo or not isinstance(lista, list) or len(lista) <= cabe:
            salida.append(p)
            continue
        # Reparto parejo: 7 planos de 3 en 3 son 3, 2 y 2, no 3, 3 y 1.
        partes = -(-len(lista) // cabe)
        base, sobra = divmod(len(lista), partes)
        trozos, desde = [], 0
        for k in range(partes):
            largo = base + (1 if k < sobra else 0)
            trozos.append((desde, lista[desde:desde + largo]))
            desde += largo
        for k, (inicio, trozo) in enumerate(trozos):
            nueva = dict(p)
            nueva[campo] = trozo
            nueva["_parte"] = f"{k + 1} de {len(trozos)}"
            nueva["_desde"] = inicio + 1
            if k:
                nueva.pop("nota", None)
            salida.append(nueva)
    return salida


def firma_html(n, total):
    return (f'<a class="firma" href="{REPO}"><span class="sello"></span><span>{HECHO_CON} · {FIRMA}</span>'
            f'<span class="num">{n} / {total}</span></a>')


def contraportada(doc, n, total):
    quien = (f"Lo ha preparado {e(doc['preparado_por'])} con La Brigada: agentes de IA, gratis y en español, "
             if doc["preparado_por"] else "La Brigada son agentes de IA, gratis y en español, ")
    lead = (quien + "que preparan la semana de Instagram de un negocio con su propia voz. "
            "La persona revisa, decide y publica.")
    enlaces = "".join(f'<a class="enlace" href="{url}"><span class="que">{que}</span><span class="donde">{donde}</span></a>'
                      for que, url, donde in ENLACES)
    cuerpo = (f'<div class="eti">Cómo se ha hecho</div><div class="raya"></div><h2>{HECHO_CON}.</h2>'
              f'<p class="lead">{lead}</p><div class="enlaces">{enlaces}</div>'
              f'<p class="firma-grande">Toni Mont · <i>IA con Oficio</i></p>')
    return (f'<section class="p contra" data-tipo="contraportada"><div class="deco aro"></div>'
            f'<div class="cuerpo medir">{cuerpo}</div>'
            f'{firma_html(n, total)}</section>')


def documento(doc):
    paginas = trocea(doc["paginas"])
    total = len(paginas) + 1
    secciones = []
    for n, p in enumerate(paginas, 1):
        interior, clase = PINTORES[p["tipo"]](p, doc)
        clases = "p" + (f" {clase}" if clase else "")
        adorno = '<div class="deco sol"></div><div class="deco aro"></div>' if p["tipo"] == "portada" else ""
        secciones.append(f'<section class="{clases}" data-tipo="{p["tipo"]}">{adorno}<div class="cuerpo medir">{interior}</div>'
                         f'{firma_html(n, total)}</section>')
    secciones.append(contraportada(doc, total, total))
    titulo = f'{doc["titulo"]} · {doc["para"]} · {HECHO_CON}'
    cabeza = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
              f'<meta name="viewport" content="width=device-width,initial-scale=1">'
              f'<title>{html.escape(titulo)}</title>'
              f'<meta name="generator" content="La Brigada · brigada-emplatado · {FIRMA}">'
              f'<meta name="author" content="{html.escape(doc["preparado_por"] or doc["para"])} · {HECHO_CON}">'
              f'<style>{fuentes(doc["marca"]["manuscrita"])}\n{css(doc["marca"])}</style></head><body>')
    return cabeza + "\n".join(secciones) + f"<script>{MEDIDOR}</script></body></html>", total


def para_copiar(doc):
    """Todos los textos en limpio, en el orden del documento, con la firma al final."""
    lineas = [f"{doc['titulo']} · {doc['para']}", "Los textos, para copiar y pegar.", ""]
    for p in doc["paginas"]:
        cabecera = p.get("antetitulo") or p.get("titulo") or TIPOS[p["tipo"]]
        lineas += [f"== {cabecera}", ""]
        for clave in ("titulo", "subtitulo"):
            if p.get(clave) and p[clave] != cabecera:
                lineas.append(p[clave])
        if p["tipo"] == "texto":
            lineas += ["", p["texto"]]
            if p.get("notas"):
                lineas += [""] + [f"Nota: {x}" for x in p["notas"]]
        elif p["tipo"] == "laminas":
            lineas += ["", "\n---\n".join(p["laminas"])]
        elif p["tipo"] == "guion":
            for i, plano in enumerate(p["planos"], 1):
                partes = [f"{i}."]
                if plano["cartel"]:
                    partes.append(f"[En pantalla: {plano['cartel']}]")
                partes.append(plano["dices"])
                lineas.append(" ".join(partes))
                if plano["se_ve"]:
                    lineas.append(f"   Se ve: {plano['se_ve']}")
        else:
            if p.get("texto"):
                lineas.append(p["texto"])
            for punto in p.get("puntos") or []:
                lineas.append("- " + punto["texto"] + (f" (fuente: {punto['fuente']})" if punto["fuente"] else ""))
            for item in p.get("items") or []:
                lineas.append("- " + item)
            if p["tipo"] == "semana":
                for fila in p["filas"]:
                    lineas.append(" · ".join(fila[k] for k in ("dia", "hora", "formato", "tema") if fila[k]))
            if p["tipo"] == "tabla":
                lineas.append(" | ".join(p["columnas"]))
                for fila in p["filas"]:
                    lineas.append(" | ".join(c or "...." for c in fila))
            for cifra in p.get("cifras") or []:
                lineas.append(f"- {cifra['numero']} {cifra['texto']}".rstrip())
        if p.get("nota"):
            lineas += ["", p["nota"]]
        lineas.append("")
    lineas += ["--", f"{HECHO_CON} · {FIRMA}", REPO, ""]
    return "\n".join(lineas)


# ---------------------------------------------------------------- el navegador

NAVEGADORES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
               "microsoft-edge", "microsoft-edge-stable", "msedge"]
RUTAS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
         "/Applications/Chromium.app/Contents/MacOS/Chromium",
         "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
         r"C:\Program Files\Google\Chrome\Application\chrome.exe",
         r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
         r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
         os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe")]


def busca_navegador():
    propio = os.environ.get("BRIGADA_CHROME")
    if propio:
        return propio if (pathlib.Path(propio).is_file() or shutil.which(propio)) else None
    for nombre in NAVEGADORES:
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    for ruta in RUTAS:
        if pathlib.Path(ruta).is_file():
            return ruta
    return None


TIEMPO_NAVEGADOR = 60   # segundos como mucho por cada vez que se abre el navegador


def _lanza(navegador, argumentos, tiempo=TIEMPO_NAVEGADOR):
    """Abre el navegador sin ventana y devuelve lo que escribe.

    Sin ventana, el navegador usa un perfil temporal propio: no toca el tuyo,
    ni tus pestañas, ni tus contraseñas. No se le pasa --user-data-dir porque
    con un perfil nuevo algunas versiones se quedan colgadas."""
    orden = [navegador, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--disable-background-networking", "--disable-component-update", "--disable-extensions",
             "--disable-sync", "--disable-default-apps", "--metrics-recording-only", "--mute-audio",
             # La red, cortada: todo lo que intente salir va a un puerto cerrado y ningún nombre se resuelve.
             "--proxy-server=127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
             "--host-resolver-rules=MAP * ~NOTFOUND"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        orden.append("--no-sandbox")
    aparte = {"start_new_session": True} if os.name == "posix" else {}
    proceso = subprocess.Popen(orden + argumentos, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding="utf-8", errors="replace", **aparte)
    try:
        salida, _ = proceso.communicate(timeout=tiempo)
    except subprocess.TimeoutExpired:
        # Si se cuelga, se cierra entero: el navegador y todo lo que haya abierto.
        if os.name == "posix":
            try:
                os.killpg(proceso.pid, 9)
            except OSError:
                pass
        proceso.kill()
        proceso.communicate()
        raise
    return salida


def mide(navegador, ruta_html):
    """Devuelve (páginas que se salen, letras cargadas), o None si no se ha podido medir."""
    try:
        salida = _lanza(navegador, ["--virtual-time-budget=5000", "--dump-dom", ruta_html.resolve().as_uri()])
    except (OSError, subprocess.SubprocessError):
        return None
    if 'data-medido="si"' not in salida:
        return None
    m = re.search(r'data-desbordes="([\d,]*)"', salida)
    paginas = [int(x) for x in m.group(1).split(",") if x] if m else []
    return paginas, 'data-letras="si"' in salida


def imprime(navegador, ruta_html, ruta_pdf):
    try:
        if ruta_pdf.exists():
            ruta_pdf.unlink()
        _lanza(navegador, ["--virtual-time-budget=5000", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                           f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()])
    except (OSError, subprocess.SubprocessError):
        return False
    return ruta_pdf.exists() and ruta_pdf.stat().st_size > 0


# ---------------------------------------------------------------- todo junto

class NoPuedoEscribir(Exception):
    """No se puede guardar el resultado donde se ha pedido."""


def _viejo(avisos, ruta):
    """Si de otra vez queda un archivo con el mismo nombre, que se sepa: no se borra nada."""
    if ruta and pathlib.Path(ruta).exists():
        avisos.append({"estado": "NOTA", "donde": "ARCHIVO",
                       "detalle": f"«{pathlib.Path(ruta).name}» es de una vez anterior, no de esta: no lo mandes"})


def emplata(ruta_comanda, salida=None, pdf=None, navegador=True):
    """Hace el trabajo y devuelve el informe.

    Lanza FileNotFoundError o ValueError si no puede leer la comanda, y
    NoPuedoEscribir si no puede guardar el resultado."""
    ruta_comanda = pathlib.Path(ruta_comanda)
    datos = lee_comanda(ruta_comanda)
    avisos = []
    informe = {"avisos": avisos, "html": None, "copiar": None, "pdf": None, "paginas": 0, "medido": False}
    ruta_html = pathlib.Path(salida) if salida else ruta_comanda.with_suffix(".html")
    ruta_copiar = ruta_html.with_name(ruta_html.stem + "-para-copiar.txt")
    try:
        doc = prepara(datos, ruta_comanda.parent, avisos)
    except Comanda:
        for ruta in (ruta_html, ruta_copiar, pdf):
            _viejo(avisos, ruta)
        informe["veredicto"] = "ARREGLA: NO HE EMPLATADO NADA"
        return informe

    texto_html, total = documento(doc)
    try:
        ruta_html.write_text(texto_html, encoding="utf-8")
        ruta_copiar.write_text(para_copiar(doc), encoding="utf-8")
    except OSError:
        raise NoPuedoEscribir(str(ruta_html))
    informe.update({"html": str(ruta_html), "copiar": str(ruta_copiar), "paginas": total, "para": doc["para"]})

    marca = doc["marca"]
    if marca["propia"]:
        avisos.insert(0, {"estado": "BIEN", "donde": "COLORES",
                          "detalle": f"los de {doc['para']}: el texto se lee sobre el fondo "
                                     f"(contraste {coma(doc['contrastes']['texto'])})"})
    else:
        avisos.insert(0, {"estado": "NOTA", "donde": "COLORES",
                          "detalle": "sin marca en la comanda: van los colores de La Brigada"})
    avisos.append({"estado": "BIEN", "donde": "FIRMA",
                   "detalle": f"en las {total} páginas, con la contraportada de La Brigada al final"})

    nav = None
    if not navegador:
        avisos.append({"estado": "NOTA", "donde": "MEDIDO", "detalle": "sin navegador: solo he contado palabras"})
    else:
        nav = busca_navegador()
        if not nav:
            avisos.append({"estado": "NOTA", "donde": "MEDIDO",
                           "detalle": "no he encontrado Chrome, Chromium ni Edge: no he podido comprobar que todo "
                                      "cabe. Ábrelo y mira cada página"})
    medida = mide(nav, ruta_html) if nav else None
    desbordes = medida[0] if medida else None
    if nav and medida is None:
        avisos.append({"estado": "NOTA", "donde": "MEDIDO", "detalle": "el navegador no ha podido medir las páginas"})
    elif medida and not medida[1]:
        avisos.append({"estado": "NOTA", "donde": "MEDIDO", "detalle": "he medido antes de que cargaran las letras: "
                                                                     "mira cada página por si algo se sale"})
    if desbordes:
        normales = [x for x in desbordes if x != total]
        if normales:
            lista = ", ".join(str(x) for x in normales)
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": f"se sale el contenido de la página {lista}: corta el texto o pártela en dos. "
                                      "En el HTML sale señalada en rojo"})
        if total in desbordes:
            avisos.append({"estado": "ARREGLA", "donde": "MEDIDO",
                           "detalle": "no cabe la contraportada: acorta «preparado_por» o «para»"})
    elif medida is not None and medida[1]:
        informe["medido"] = True
        avisos.append({"estado": "BIEN", "donde": "MEDIDO", "detalle": "comprobado en el navegador: todo cabe"})

    if pdf:
        ruta_pdf = pathlib.Path(pdf)
        if desbordes:
            avisos.append({"estado": "NOTA", "donde": "PDF", "detalle": "no lo hago hasta que todo quepa"})
            _viejo(avisos, ruta_pdf)
        elif not nav:
            avisos.append({"estado": "NOTA", "donde": "PDF",
                           "detalle": "sin navegador no puedo hacerlo: abre el HTML en Chrome y usa Imprimir, "
                                      "Guardar como PDF"})
            _viejo(avisos, ruta_pdf)
        elif imprime(nav, ruta_html, ruta_pdf):
            informe["pdf"] = str(ruta_pdf)
            avisos.append({"estado": "BIEN", "donde": "PDF", "detalle": f"{ruta_pdf.name}, {total} páginas de 1080x1350"})
        else:
            avisos.append({"estado": "NOTA", "donde": "PDF",
                           "detalle": "el navegador no lo ha hecho: abre el HTML en Chrome y usa Imprimir, "
                                      "Guardar como PDF"})

    estados = [a["estado"] for a in avisos]
    informe["veredicto"] = ("ARREGLA" if "ARREGLA" in estados else "REVÍSALO" if "OJO" in estados else "LISTO")
    return informe


def pinta(informe, out=sys.stdout):
    cabeza = f"EMPLATADO · {informe['paginas']} página(s)" if informe["paginas"] else "EMPLATADO"
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
    for clave, nombre in (("html", "El documento"), ("copiar", "Los textos"), ("pdf", "El PDF")):
        if informe.get(clave):
            print(f"  {nombre}: {informe[clave]}", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Emplata el trabajo de la brigada en un documento con diseño para el "
                                             "cliente, en formato móvil, con la firma de La Brigada.")
    ap.add_argument("comanda", help="archivo JSON con la comanda (mira references/comanda.md)")
    ap.add_argument("--salida", help="dónde guardar el HTML (por defecto, al lado de la comanda)")
    ap.add_argument("--pdf", help="hace también el PDF, si encuentra Chrome, Chromium o Edge")
    ap.add_argument("--sin-navegador", action="store_true", help="no abre el navegador: ni mide ni hace el PDF")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        informe = emplata(args.comanda, args.salida, args.pdf, navegador=not args.sin_navegador)
    except NoPuedoEscribir as fallo:
        ap.error(f"no puedo guardar «{fallo}»: mira que la carpeta exista y se pueda escribir en ella")
    except FileNotFoundError:
        ap.error(f"no puedo leer «{args.comanda}»: no existe o no es un archivo de texto")
    except ValueError as fallo:
        ap.error(f"no puedo leer «{args.comanda}»: {fallo}")
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        pinta(informe)
    sys.exit(1 if informe["veredicto"].startswith("ARREGLA") else 0)


if __name__ == "__main__":
    main()

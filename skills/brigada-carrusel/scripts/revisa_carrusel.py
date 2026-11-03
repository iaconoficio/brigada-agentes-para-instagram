#!/usr/bin/env python3
"""
revisa_carrusel.py · La Brigada (IA con Oficio)

Revisa el texto de un carrusel de Instagram antes de hacer las imágenes y te lo
enseña lámina a lámina, para leerlo de un vistazo.

El texto va en el formato de la Lámina de texto del repo
(herramientas/lamina-de-texto.html): una lámina por bloque, separadas por una
línea que solo tenga tres guiones (---). Lo que pasa esta revisión se pega tal
cual en la Lámina y salen las imágenes.

Lo que mira:

  LÁMINAS       cuántas hay: Instagram admite 20 como mucho
  PORTADA       que la primera frase sea corta, que enganche (con el puntuador
                de brigada-reel, si está instalado) y que no lleve demasiado
                texto
  LÁMINA 2      que se entienda sola, sin «en este carrusel...» ni a mitad de
                frase
  LARGO         láminas con demasiadas palabras para leerlas en el móvil
  REPETIDAS     láminas iguales
  EN LA IMAGEN  hashtags, enlaces y menciones dentro de una lámina
  RESUMEN       si hay una lámina que junta todo (solo informa)
  CIERRE        cuántas cosas pides en la portada y en la última lámina (con el
                detector de brigada-caption, si está instalado)

Con --alt, propone el texto alternativo de cada lámina: como son láminas de
texto, es su propio texto.

Los datos de Instagram, y de dónde salen:
  - Hasta 20 fotos o vídeos por carrusel: Instagram lo amplió en agosto de
    2024.
  - La lámina 2: según contó Adam Mosseri, responsable de Instagram, en
    octubre de 2024, si alguien ve un carrusel y no desliza, se lo puede
    volver a enseñar mostrando la segunda lámina.
  - En una imagen, un hashtag, un enlace o una @ son dibujos: no se pueden
    pulsar ni buscar.
Si algo de esto cambia, se cambia arriba, en las constantes.

Lo demás (cuántas palabras caben en una lámina, cuántas láminas son pocas o
muchas) es opinión, no un dato. Las palabras por lámina se cambian con
--palabras.

Funciona sin internet y no envía nada a ningún sitio.

Las reglas que revisa (una portada que engancha, una lámina 2 que se sostiene
sola, una idea por lámina, entre unas seis y diez láminas, una lámina para
guardar y una sola petición) parten de ig-carousel, de Jake Schincariol
(licencia MIT): github.com/Jakeschincariol/instagram-agent-skill
El script, las comprobaciones en español y el texto alternativo son nuestros.

Uso
  python3 revisa_carrusel.py carrusel.txt
  python3 revisa_carrusel.py carrusel.txt --alt
  python3 revisa_carrusel.py carrusel.txt --palabras 30
  python3 revisa_carrusel.py carrusel.txt --json
"""

import argparse
import importlib.util
import json
import pathlib
import re
import sys
import textwrap
import unicodedata

LAMINAS_MAX = 20         # fotos o vídeos por carrusel (Instagram, agosto de 2024)
POCAS = 3                # con 2 o 3 láminas, casi no hay nada que deslizar (opinión)
MUCHAS = 10              # a partir de 11, cuesta llegar al final (opinión)
PALABRAS_LAMINA = 40     # más palabras que esto no se leen bien en el móvil (opinión)
PALABRAS_PORTADA = 30    # la portada se ve pequeña en la rejilla del perfil (opinión)
PALABRAS_GANCHO = 12     # la primera frase de la portada (lo mismo que el puntuador de brigada-reel)
LISTA_MIN = 3            # renglones de lista para que una lámina cuente como resumen
BOM = chr(0xFEFF)
# Lo mismo que limpia la Lámina antes de cortar y dibujar: los invisibles fuera
# y los espacios raros (el duro de Notas, Docs o WhatsApp), espacios normales.
INVISIBLES = (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD)
ESPACIOS_RAROS = (0x00A0, 0x202F, 0x2009, 0x2007)
_LIMPIEZA = {**{c: None for c in INVISIBLES}, **{c: " " for c in ESPACIOS_RAROS}}

# El mismo corte que la Lámina: una línea que solo tiene tres guiones o más.
SEPARADOR_RE = re.compile(r"(?:^|\n)[ \t]*-{3,}[ \t]*(?=\n|$)")
PALABRA_RE = re.compile(r"[^\W_]+")
# Un hashtag tiene al menos una letra: «paso #1» no es un hashtag.
HASHTAG_RE = re.compile(r"(?<![\w#&])#(?=\w*[^\W\d_])([^\W_]\w*)")
MENCION_RE = re.compile(r"(?<![\w@])@([\w.]{2,30})")
# La terminación del dominio va en minúsculas: «radiador.Es aire» es un espacio que falta, no un enlace.
ENLACE_RE = re.compile(
    r"(?i:https?://)\S+|(?i:\bwww\.)\S+"
    r"|(?<![@\w.])[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)*\.(?:com|es|cat|eus|gal|net|org|eu|io|co|app|ai|info|me|link|shop)"
    r"\b(?:/\S*)?")
# Lo que gasta la portada o la lámina 2 en anunciar en vez de decir. Unas frases
# solo cuentan al empezar la lámina («Te voy a contar...»); otras, en cualquier
# sitio, porque solo pueden hablar del carrusel («en este carrusel», «sigue deslizando»).
PREAMBULO_RE = re.compile(
    r"(?i)^\W*(?:(?:hoy )?(?:te|os) (?:voy|vamos) a (?:contar|explicar|ense[nñ]ar|dar|decir|hablar)"
    r"|hoy (?:te|os) (?:traigo|cuento|hablo)|vamos (?:all[aá]|a (?:ver|verlo|empezar))|empecemos)\b"
    r"|\b(?:en (?:este|el) carrusel|en (?:las )?(?:siguientes|pr[oó]ximas) l[aá]minas"
    r"|sigue (?:deslizando|leyendo)|desliza(?:d)?(?=[ \t]*(?:$|\n|[.!" + chr(0x2192) + r"]|para\b|y\b|hacia\b)))")
SALUDO_RE = re.compile(r"(?i)^\W*(?:hola|holi|buenas(?=\s*[!,.]|\s*$)|buenos d[ií]as|buenas tardes|buenas noches"
                       r"|qu[ée] tal|hey|bienvenid[oa]s?)\b")
# Una lámina que empieza a mitad de frase: con puntos suspensivos, o con una palabra
# toda en minúsculas («iPhone» o «pH» no cuentan, que llevan mayúscula dentro).
A_MEDIAS_RE = re.compile(r"^(?:\.\.\.|" + chr(0x2026) + r"|[a-záéíóúñü]+(?![\w]))")
# Renglón de lista: una viñeta, o un número de una o dos cifras seguido de punto y espacio («1.000 €» no lo es).
VINETAS = "-*·" + "".join(chr(c) for c in (0x2022, 0x25AA, 0x25CF, 0x2713, 0x2714, 0x2705, 0x2192))
LISTA_RE = re.compile(r"^\s*(?:[" + re.escape(VINETAS) + r"]\s*|\d{1,2}[.)º]\s+)\S")

AQUI = pathlib.Path(__file__).resolve().parent
SKILLS = AQUI.parent.parent


def _carga(nombre, ruta):
    """Carga un script de otro agente de la brigada, si está instalado al lado."""
    try:
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    except (OSError, ImportError, SyntaxError, AttributeError):
        return None


GANCHO = _carga("brigada_puntua_gancho", SKILLS / "brigada-reel" / "scripts" / "puntua_gancho.py")
CAPTION = _carga("brigada_revisa_caption", SKILLS / "brigada-caption" / "scripts" / "revisa_caption.py")


def normaliza(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def limpia_entrada(texto):
    return texto.replace("\r\n", "\n").replace("\r", "\n").translate(_LIMPIEZA)


def separa(texto):
    """Las láminas, como las corta la Lámina: los bloques vacíos no cuentan."""
    trozos = SEPARADOR_RE.split(limpia_entrada(texto))
    return [t.strip() for t in trozos if t.strip()]


def palabras(texto):
    return PALABRA_RE.findall(texto)


def primera_linea(lamina):
    return next((l.strip() for l in lamina.splitlines() if l.strip()), "")


def primer_parrafo(lamina):
    """El primer bloque hasta la línea en blanco, en un solo renglón: la portada se parte a veces para que quepa."""
    return en_una_linea(re.split(r"\n\s*\n", lamina.strip(), maxsplit=1)[0])


def en_una_linea(lamina):
    return re.sub(r"\s*\n\s*", " ", lamina).strip()


def huella(lamina):
    """Para comparar láminas sin mirar tildes, mayúsculas ni signos."""
    return " ".join(palabras(normaliza(lamina)))


def acaba_en_pregunta(lamina):
    """Si lo último que se dice es una pregunta, aunque detrás haya un emoji o unas comillas."""
    cola = re.search(r"[^\W_][^\w]*$", lamina.strip())
    return bool(cola) and "?" in cola.group(0)


def es_resumen(lamina):
    return sum(1 for l in lamina.splitlines() if LISTA_RE.match(l)) >= LISTA_MIN


def puntua_portada(texto):
    """(nota, veredicto, avisos) con el puntuador de brigada-reel, o None si no está o no responde como se espera."""
    if not GANCHO:
        return None
    try:
        _, total, veredicto, avisos = GANCHO.puntua(texto, "post")
        return float(total), str(veredicto), [str(a) for a in avisos]
    except (TypeError, ValueError, AttributeError, KeyError, IndexError):
        return None


def peticiones(texto):
    """Lo que se pide, con el detector de brigada-caption, o None si no está o no responde como se espera."""
    if not CAPTION:
        return None
    try:
        return [str(p) for p in CAPTION.peticiones(texto)]
    except (TypeError, ValueError, AttributeError, KeyError, IndexError):
        return None


FINAL_DE_FRASE = ".!?:;" + chr(0x2026) + chr(0xBB) + '"' + ")"


def texto_alternativo(laminas):
    """Como son láminas de texto, su texto alternativo es su propio texto, en frases y sin viñetas."""
    total, salida = len(laminas), []
    for i, lamina in enumerate(laminas, 1):
        frases = []
        for linea in lamina.splitlines():
            linea = re.sub(r"^\s*[" + re.escape(VINETAS) + r"]\s*", "", linea).strip()
            if linea:
                frases.append(linea if linea[-1] in FINAL_DE_FRASE else linea + ".")
        salida.append(f"Lámina {i} de {total}. Texto: {' '.join(frases)}")
    return salida


def revisa(texto, max_palabras=PALABRAS_LAMINA):
    laminas = separa(texto)
    n = len(laminas)
    revision = []

    def anota(nombre, estado, detalle):
        revision.append({"comprobacion": nombre, "estado": estado, "detalle": detalle})

    # LÁMINAS
    if n == 1:
        anota("LÁMINAS", "ARREGLA", "una sola lámina es un post, no un carrusel. Si quieres carrusel, sepáralo en "
                                    "láminas con una línea que solo tenga ---.")
    elif n > LAMINAS_MAX:
        anota("LÁMINAS", "ARREGLA", f"{n} láminas: Instagram admite {LAMINAS_MAX} como mucho. Sobran {n - LAMINAS_MAX}; "
                                    f"mejor dos carruseles.")
    elif n <= POCAS:
        anota("LÁMINAS", "OJO", f"{n} láminas: casi no hay nada que deslizar. ¿No será mejor un post?")
    elif n > MUCHAS:
        anota("LÁMINAS", "OJO", f"{n} láminas: cuesta llegar al final. Mira si hay alguna que sobre o si son dos carruseles.")
    else:
        anota("LÁMINAS", "BIEN", f"{n} láminas")

    # PORTADA
    portada = laminas[0]
    gancho = primer_parrafo(portada)
    puntos, problemas = None, []
    nota = puntua_portada(gancho)
    if nota:
        total, veredicto, gastadas = nota
        puntos = {"total": round(total, 1), "veredicto": veredicto}
        problemas += gastadas
        if total < 50:
            problemas.append("Con menos de 50 no engancha: mira qué le falta con puntua_gancho.py --formato post.")
    if not problemas and (SALUDO_RE.search(gancho) or PREAMBULO_RE.search(gancho)):
        problemas.append("Empieza saludando o anunciando lo que viene: empieza por lo que importa.")
    # Con el puntuador, el largo de la primera frase ya cuenta en su nota (DURACIÓN).
    if not puntos and len(palabras(gancho)) > PALABRAS_GANCHO:
        problemas.append(f"La primera frase tiene {len(palabras(gancho))} palabras: en la rejilla se lee mejor con "
                         f"{PALABRAS_GANCHO} o menos.")
    if len(palabras(portada)) > PALABRAS_PORTADA:
        problemas.append(f"La portada lleva {len(palabras(portada))} palabras y en la rejilla del perfil se ve "
                         f"pequeña: déjala en {PALABRAS_PORTADA} o menos.")
    # El punto va fuera de las comillas: «... es aire».
    cita = f"«{gancho.rstrip('.')}»"
    resumen = cita + (f" saca {puntos['total']:.0f} ({puntos['veredicto']}) con el puntuador de ganchos"
                      if puntos else "")
    if problemas:
        anota("PORTADA", "OJO", resumen + ". " + " ".join(problemas))
    elif puntos:
        anota("PORTADA", "BIEN", resumen)
    else:
        anota("PORTADA", "NOTA", resumen + ". No la he podido puntuar: para eso hace falta brigada-reel instalado "
                                           "junto a esta skill.")

    # LÁMINA 2
    if n >= 2:
        segunda = laminas[1]
        if PREAMBULO_RE.search(segunda):
            anota("LÁMINA 2", "OJO", "anuncia lo que viene en vez de decirlo. Instagram puede volver a enseñar el "
                                     "carrusel empezando por esta lámina: que diga algo por sí sola.")
        elif A_MEDIAS_RE.match(segunda):
            anota("LÁMINA 2", "OJO", "empieza a mitad de frase. Si alguien la ve sin la portada, no se entiende: "
                                     "que se sostenga sola.")
        else:
            anota("LÁMINA 2", "BIEN", "se entiende sola")

    # LARGO (la portada ya se ha mirado arriba)
    largas = [(i, len(palabras(l))) for i, l in enumerate(laminas[1:], 2) if len(palabras(l)) > max_palabras]
    if largas:
        lista = ", ".join(f"{i} ({p} palabras)" for i, p in largas)
        anota("LARGO", "OJO", f"lámina(s) {lista}. Con tanto texto, la letra sale pequeña y en el móvil cuesta "
                              f"leerla: parte cada una en dos o quédate con lo importante.")
    elif n >= 2:
        anota("LARGO", "BIEN", f"ninguna lámina pasa de {max_palabras} palabras")

    # REPETIDAS
    vistas, repetidas = {}, []
    for i, lamina in enumerate(laminas, 1):
        h = huella(lamina)
        if not h:
            continue
        if h in vistas:
            repetidas.append(f"la {i} es igual que la {vistas[h]}")
        else:
            vistas[h] = i
    if repetidas:
        anota("REPETIDAS", "ARREGLA", "; ".join(repetidas) + ".")

    # EN LA IMAGEN
    dentro = []
    for i, lamina in enumerate(laminas, 1):
        cosas = ([f"#{h}" for h in HASHTAG_RE.findall(lamina)] + [f"@{m}" for m in MENCION_RE.findall(lamina)]
                 + ENLACE_RE.findall(lamina))
        if cosas:
            dentro.append(f"lámina {i}: {', '.join(cosas[:3])}")
    if dentro:
        anota("EN LA IMAGEN", "OJO", "; ".join(dentro) + ". En una imagen no se pueden pulsar ni buscar: los hashtags "
                                     "van en el texto del post, y si nombras a alguien, etiquétalo en la publicación.")

    # RESUMEN (solo en carruseles largos: en uno corto no hace falta)
    if n >= 6 and not any(es_resumen(l) for l in laminas[1:]):
        anota("RESUMEN", "NOTA", "no hay una lámina que lo junte todo. Si son pasos o una lista, la penúltima "
                                 "puede resumirlos: es la que la gente se guarda o manda.")

    # CIERRE
    ultima = laminas[-1]
    donde_mirar = ([("la portada", portada)] if n > 1 else []) + [("el final", ultima)]
    encontradas = [(peticiones(lamina), donde) for donde, lamina in donde_mirar]
    if any(lista is None for lista, _ in encontradas):
        anota("CIERRE", "NOTA", "no he podido contar lo que pides: para eso hace falta brigada-caption instalado "
                                "junto a esta skill. Mira a mano que pidas una sola cosa.")
    else:
        pedidas = []
        for lista, donde in encontradas:
            for p in lista:
                if p not in [x for x, _ in pedidas]:
                    pedidas.append((p, donde))
        if len(pedidas) > 1:
            lista = ", ".join(f"{p} ({d})" for p, d in pedidas)
            anota("CIERRE", "OJO", f"pides {len(pedidas)} cosas: {lista}. Se pisan: deja una.")
        elif pedidas:
            anota("CIERRE", "BIEN", f"una petición: {pedidas[0][0]}")
        elif acaba_en_pregunta(ultima):
            anota("CIERRE", "BIEN", "acaba con una pregunta: abre conversación sin vender")
        else:
            anota("CIERRE", "NOTA", "no pide nada ni acaba con una pregunta. Si quieres que se quede pensando, vale; "
                                    "si no, decide qué quieres que pase al terminar.")

    estados = [r["estado"] for r in revision]
    veredicto = ("ARREGLA ANTES DE HACER LAS LÁMINAS" if "ARREGLA" in estados
                 else "REVÍSALO" if "OJO" in estados else "LISTO")
    mapa = [{"lamina": i, "papel": "PORTADA" if i == 1 else ("CIERRE" if i == n and n > 1 else ""),
             "palabras": len(palabras(l)), "empieza": primera_linea(l)} for i, l in enumerate(laminas, 1)]
    return {"laminas": laminas, "mapa": mapa, "portada": puntos, "revision": revision, "veredicto": veredicto,
            "texto_alternativo": texto_alternativo(laminas)}


def pinta(r, alt=False, out=sys.stdout):
    print(f"\nCARRUSEL · {len(r['laminas'])} lámina(s)", file=out)
    print("=" * 70, file=out)
    for fila in r["mapa"]:
        empieza = textwrap.shorten(fila["empieza"], 44, placeholder="...")
        print(f"  {fila['lamina']:>2}  {fila['papel']:<8} {fila['palabras']:>3} pal.  {empieza}", file=out)
    print("\nREVISIÓN", file=out)
    print("=" * 70, file=out)
    for c in r["revision"]:
        print(f"  {c['estado']:<8} {c['comprobacion']:<13} {c['detalle']}", file=out)
    print("-" * 70, file=out)
    print(f"  {r['veredicto']}", file=out)
    print("  Antes de hacer las imágenes, pasa el texto por brigada-humano.\n", file=out)
    if alt:
        print("TEXTO ALTERNATIVO (uno por lámina)", file=out)
        print("=" * 70, file=out)
        for linea in r["texto_alternativo"]:
            print(textwrap.fill(linea, 70, initial_indent="  ", subsequent_indent="    "), file=out)
        print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Revisa el texto de un carrusel de Instagram antes de hacer las láminas.")
    ap.add_argument("entrada", nargs="?", default="-",
                    help="archivo con el carrusel (láminas separadas por una línea con ---), o - para leerlo de la entrada")
    ap.add_argument("--palabras", type=int, default=PALABRAS_LAMINA,
                    help=f"palabras por lámina a partir de las que avisa (por defecto, {PALABRAS_LAMINA})")
    ap.add_argument("--alt", action="store_true", help="propone el texto alternativo de cada lámina")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.palabras <= 0:
        ap.error("--palabras tiene que ser mayor que cero")

    try:
        texto = sys.stdin.read() if args.entrada == "-" else open(args.entrada, encoding="utf-8-sig").read()
    except (OSError, UnicodeDecodeError):
        ap.error(f"no puedo leer «{args.entrada}»: no existe o no es un archivo de texto")
    if not separa(texto):
        print("no hay texto que revisar", file=sys.stderr)
        sys.exit(2)
    r = revisa(texto, args.palabras)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        pinta(r, args.alt)
    sys.exit(1 if r["veredicto"].startswith("ARREGLA") else 0)


if __name__ == "__main__":
    main()

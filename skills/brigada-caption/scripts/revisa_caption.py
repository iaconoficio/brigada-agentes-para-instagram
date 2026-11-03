#!/usr/bin/env python3
"""
revisa_caption.py · La Brigada (IA con Oficio)

Revisa el texto de un post de Instagram antes de publicarlo y te enseña lo que
se ve en el feed antes del «más».

Lo que mira:

  ANTES DEL MÁS   lo que cabe en la parte visible, y si la primera frase se
                  corta o empieza con un saludo, un hashtag, una mención o un
                  emoji
  LARGO           Instagram admite 2.200 caracteres como mucho
  PÁRRAFOS        bloques demasiado largos para leerlos en el móvil
  HASHTAGS        cinco como mucho, repetidos, genéricos (#viral, #parati...)
                  o metidos en la parte visible
  MENCIONES       veinte como mucho si lo programas con una herramienta
  ENLACES         en el texto de un post no se pueden pulsar
  CIERRE          cuántas cosas pides (comentar, guardar, escribirte...): más
                  de una se pisan. Si no pides nada, mira si acabas con una
                  pregunta. No pedir nada también puede valer.
  PALABRA CLAVE   en «comenta X», que X sea una sola palabra fácil de escribir
  BÚSQUEDA        con --buscar, si las palabras con las que te buscaría un
                  cliente están en el texto

Los datos de Instagram, y de dónde salen:
  - 2.200 caracteres y 20 menciones: es lo que acepta la API de Meta, la que
    usan las herramientas para programar posts (documentación de Meta para
    desarrolladores, códigos de error). Para la app, Meta no publica la cifra.
  - Cinco hashtags: Instagram lo anunció en diciembre de 2025 para posts y
    reels, con una implantación gradual.
  - Unos 125 caracteres antes del «más»: es la cifra que dan herramientas de
    terceros, no Instagram. Mira tu post en la vista previa; si en tu móvil se
    lee menos, bájala con --ventana.
  - Enlaces que no se pueden pulsar: lo explican las ayudas de las
    herramientas que publican en Instagram.
Si algo de esto cambia, se cambia arriba, en las constantes.

Funciona sin internet y no envía nada a ningún sitio.

La idea de enseñar la parte visible y revisar el texto con un script parte de
caption.py, de Jake Schincariol (licencia MIT):
github.com/Jakeschincariol/instagram-agent-skill

Uso
  python3 revisa_caption.py texto.txt
  python3 revisa_caption.py texto.txt --buscar "taller de motos,Mataró"
  python3 revisa_caption.py texto.txt --ventana 100
  python3 revisa_caption.py texto.txt --json
"""

import argparse
import json
import re
import sys
import textwrap
import unicodedata

LIMITE = 2200            # caracteres por texto (Meta, documentación de la API)
MENCIONES_MAX = 20       # menciones por texto (Meta, documentación de la API)
HASHTAGS_MAX = 5         # por post o reel (Instagram, diciembre de 2025)
VENTANA = 125            # caracteres que suelen verse antes del «más» (estimación)
PARRAFO_LARGO = 350      # caracteres seguidos sin línea en blanco: un muro en el móvil
BOM = chr(0xFEFF)

HASHTAG_RE = re.compile(r"(?<![\w#&])#([^\W_][\w]*)")
MENCION_RE = re.compile(r"(?<![\w@])@([\w.]{2,30})")
# La terminación del dominio va en minúsculas: «radiador.Es aire» es un espacio que falta, no un enlace.
ENLACE_RE = re.compile(
    r"(?i:https?://)\S+|(?i:\bwww\.)\S+"
    r"|(?<![@\w.])[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)*\.(?:com|es|cat|eus|gal|net|org|eu|io|co|app|ai|info|me|link|shop)"
    r"\b(?:/\S*)?"
    r"|(?<![@\w.])[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}/\S+")       # cualquier dominio con ruta: bit.ly/..., linktr.ee/...
_EMOJIS = ("[" + chr(0x1F300) + "-" + chr(0x1FAFF) + chr(0x2600) + "-" + chr(0x27BF) + chr(0x2B00) + "-"
           + chr(0x2BFF) + chr(0x1F1E6) + "-" + chr(0x1F1FF) + "]")
_TECLA = "[0-9#*]" + chr(0xFE0F) + "?" + chr(0x20E3)          # 1️⃣
EMOJI_RE = re.compile(_EMOJIS + "|" + _TECLA)
ZWJ, VARIANTE = chr(0x200D), chr(0xFE0F)
TONOS = {chr(c) for c in range(0x1F3FB, 0x1F400)}               # tonos de piel
BANDERA = {chr(c) for c in range(0x1F1E6, 0x1F200)}             # letras de las banderas
SALUDO_RE = re.compile(
    r"(?i)^\W*(?:hola|holi|buenas(?=\s*[!,.]|\s*$)|buenos d[ií]as|buenas tardes|buenas noches|qu[ée] tal|hey"
    r"|hoy (?:quiero|os|te|vengo|traigo)|bienvenid[oa]s?)\b")

# Hashtags que no dicen de qué va el post. Se comparan sin tildes ni mayúsculas.
GENERICOS = {
    "viral", "fyp", "foryou", "foryoupage", "parati", "paratii", "explore", "explorepage",
    "explorar", "instagood", "instadaily", "reels", "reel", "reelsinstagram", "trending",
    "tendencia", "tendencias", "like4like", "likeforlike", "follow", "followme", "sigueme",
    "photooftheday", "picoftheday", "instagram",
}

# Lo que se le pide a quien lee. Cada tipo cuenta una vez.
# Muchos verbos se dicen igual al contar algo que al pedirlo («mi abuela guarda
# las recetas», «reserva tu mesa»). Por eso hay dos listas: la primera solo
# cuenta al principio de una frase, que es donde va una petición; la segunda
# son formas que solo pueden ser petición («guárdalo», «escríbeme»).
AL_EMPEZAR = {
    "comentar": r"com[ée]nta(?:me|lo|nos)?\b|escr[ií]be\b.{0,40}\bcomentarios?\b|cont[aá]d(?:me|nos)\b"
                r"|cu[ée]nta(?:me|nos)\b|d[ií](?:me|nos)\b|dec[ií]d(?:me|nos)\b|d[ée]ja(?:me|nos)?\b.{0,20}\bcomentario",
    "guardar": r"gu[aá]rda(?:lo|la|te|telo|tela)\b|guarda (?:este|esta|el|la|tu)\b|guardad(?:lo|la)?\b",
    "compartir": r"comp[aá]rte(?:lo|la)\b|comparte (?:esto|este|esta|el post|con)\b|compartid(?:lo|la)?\b"
                 r"|env[ií]a(?:selo|sela)\b|m[aá]nda(?:selo|sela)\b",
    "seguir": r"s[ií]gue(?:me|nos)\b|sigue (?:la cuenta|mi cuenta|a @)",
    "escribir": r"escr[ií]be(?:me|nos)\b|m[aá]nda(?:me|nos)\b|h[aá]bla(?:me|nos)\b",
    "llamar o reservar": r"ll[aá]ma(?:me|nos)\b|llama (?:al|ya|hoy|ahora|para)\b|reserva\b|res[ée]rva(?:lo|la)\b"
                         r"|haz (?:tu|una) reserva\b"
                         r"|pide (?:tu |una )?(?:cita|presupuesto|hora|mesa)\b",
    "venir": r"ven(?:te|id)?\b|p[aá]sate\b|pasaos\b|ac[ée]rcate\b",
    "etiquetar": r"etiqueta a\b",
    "apuntarse o descargar": r"ap[uú]ntate\b|inscr[ií]bete\b|desc[aá]rga(?:te|lo|la)\b"
                             r"|descarga (?:la|el|mi|nuestra|nuestro|gratis|aqu[ií])\b",
}
EN_CUALQUIER_SITIO = {
    "guardar": r"gu[aá]rda(?:lo|la|telo|tela)\b",
    "compartir": r"comp[aá]rte(?:lo|la)\b|comparte con alguien\b",
    "seguir": r"s[ií]gue(?:me|nos)\b",
    "escribir": r"escr[ií]be(?:me|nos)\b|m[aá]nda(?:me|nos) un (?:md|dm|mensaje|whatsapp|wasap)\b"
                r"|por (?:md|dm|privado)\b",
    "llamar o reservar": r"ll[aá]ma(?:me|nos)\b|res[ée]rva(?:lo|la)\b",
    "ir al enlace del perfil": r"(?:enlace|link) (?:en|de) (?:la|mi|nuestra) (?:bio|biograf[ií]a)\b"
                               r"|\ben (?:mi|la|nuestra) (?:bio|biograf[ií]a)\b|\ben (?:mi|nuestro) perfil\b",
    "apuntarse o descargar": r"ap[uú]ntate\b|inscr[ií]bete\b|desc[aá]rga(?:te|lo|la)\b",
}
# Lo que puede ir delante de una petición sin dejar de serlo: «Y ahora, guárdalo».
ENLACE_DE_FRASE = re.compile(r"(?i)^(?:[\W_]+|y\b|e\b|pues\b|as[ií] que\b|ahora\b|venga\b|anda\b"
                             r"|si (?:quieres|te apetece|te interesa|te ha servido|te sirve|lo necesitas)\b)\s*,?\s*")
_AL_EMPEZAR = {k: re.compile(r"(?i)^(?:" + v + r")") for k, v in AL_EMPEZAR.items()}
_EN_CUALQUIER_SITIO = {k: re.compile(r"(?i)\b(?:" + v + r")") for k, v in EN_CUALQUIER_SITIO.items()}
CLAVE_CITADA_RE = re.compile(r"(?i)\bcom[ée]nta(?:me)?(?:\s+la\s+palabra)?\s+[«\"“']([^»\"”']{1,40})[»\"”']")
CLAVE_MAYUS_RE = re.compile(r"\b[Cc]om[ée]nta(?:me)?(?:\s+la\s+palabra)?\s+([A-ZÁÉÍÓÚÑ0-9]{2,})\b")


def normaliza(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def limpia_entrada(texto):
    return texto.lstrip(BOM).replace("\r\n", "\n").strip()


def parte_visible(texto, ventana=VENTANA):
    """Lo que cabe antes del «más» y si queda algo detrás."""
    if len(texto) <= ventana:
        return texto, False
    corte = texto[:ventana]
    if not texto[ventana].isspace():              # la última palabra no cabe entera
        espacio = corte.rfind(" ")
        if espacio > ventana * 0.6:
            corte = corte[:espacio]
    return corte.rstrip(), True


def primera_frase(texto):
    m = re.search(r"[.!?…](?=\s|$)|\n", texto)
    return texto[:m.end()].strip() if m else texto.strip()


def parrafos(texto):
    return [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]


BLOQUE_FINAL_RE = re.compile(r"(?:\s*(?<![\w#&])#[^\W_]\w*)+\s*$")


def sin_bloque_final(texto):
    """El texto sin los hashtags del final, vayan en su párrafo o pegados a la última línea."""
    return BLOQUE_FINAL_RE.sub("", texto).rstrip()


def sin_hashtags(texto):
    return HASHTAG_RE.sub("", texto).strip()


def frases_sueltas(texto):
    return [f.strip() for f in re.split(r"(?<=[.!?…:;])\s+|\n+", texto) if f.strip()]


def peticiones(texto):
    encontradas = []
    for frase in frases_sueltas(texto):
        inicio = frase
        while True:
            recortado = ENLACE_DE_FRASE.sub("", inicio, count=1)
            if recortado == inicio:
                break
            inicio = recortado
        for nombre, patron in _AL_EMPEZAR.items():
            if patron.search(inicio) and nombre not in encontradas:
                encontradas.append(nombre)
        for nombre, patron in _EN_CUALQUIER_SITIO.items():
            if patron.search(frase) and nombre not in encontradas:
                encontradas.append(nombre)
    return encontradas


def cuenta_emojis(texto):
    """Emojis completos: uno compuesto (persona con herramienta) o con tono de piel cuenta como uno, y una bandera también."""
    n, banderas, anterior = 0, 0, ""
    for c in texto:
        if c in BANDERA:
            banderas += 1
        elif EMOJI_RE.match(c) and c not in TONOS and anterior != ZWJ:
            n += 1
        anterior = c
    return n + (banderas + 1) // 2 + len(re.findall(_TECLA, texto))


def acaba_en_pregunta(parrafo):
    """Si el último párrafo acaba en pregunta, aunque detrás haya un emoji, una @ o un cierre."""
    final = MENCION_RE.sub("", parrafo)
    final = re.sub(_EMOJIS + "|" + _TECLA + "|[" + ZWJ + VARIANTE + "]", "", final)
    return final.rstrip(" \t.!)»\"”'" + chr(0x2026)).endswith("?")


def revisa(texto, ventana=VENTANA, buscar=None):
    texto = limpia_entrada(texto)
    visible, hay_mas = parte_visible(texto, ventana)
    revision = []

    def anota(nombre, estado, detalle):
        revision.append({"comprobacion": nombre, "estado": estado, "detalle": detalle})

    # ANTES DEL MÁS
    frase = primera_frase(texto)
    if not texto:
        anota("ANTES DEL MÁS", "ARREGLA", "el texto está vacío")
    elif SALUDO_RE.search(texto):
        anota("ANTES DEL MÁS", "OJO", "empieza con un saludo o un «hoy quiero»: gasta la parte que se ve. "
                                      "Empieza por lo que importa.")
    elif HASHTAG_RE.match(texto) or MENCION_RE.match(texto) or EMOJI_RE.match(texto):
        anota("ANTES DEL MÁS", "OJO", "empieza con un hashtag, una mención o un emoji. La primera palabra, "
                                      "que diga algo.")
    elif len(frase) > ventana:
        anota("ANTES DEL MÁS", "OJO", f"la primera frase tiene {len(frase)} caracteres y no cabe: se corta en "
                                      f"«...{visible[-25:]}». Acórtala o pon delante lo fuerte.")
    else:
        anota("ANTES DEL MÁS", "BIEN", f"la primera frase cabe entera ({len(frase)} de unos {ventana} caracteres)")

    # LARGO
    n = len(texto)
    if n > LIMITE:
        anota("LARGO", "ARREGLA", f"{n} caracteres: la API de Meta, la que usan las herramientas para programar, "
                                  f"no admite más de {LIMITE}. Sobran {n - LIMITE}.")
    else:
        anota("LARGO", "BIEN", f"{n} de {LIMITE} caracteres")

    # PÁRRAFOS
    largos = [i for i, p in enumerate(parrafos(texto), 1) if len(p) > PARRAFO_LARGO]
    if largos:
        anota("PÁRRAFOS", "OJO", f"párrafo(s) {', '.join(map(str, largos))} con más de {PARRAFO_LARGO} caracteres "
                                 f"seguidos. En el móvil es un muro: pártelo con una línea en blanco.")
    else:
        anota("PÁRRAFOS", "BIEN", f"{len(parrafos(texto))} párrafo(s), ninguno es un muro")

    # HASHTAGS
    etiquetas = HASHTAG_RE.findall(texto)
    # Repetidos: sin mirar mayúsculas (#Taller y #taller). Con tilde y sin tilde
    # se cuentan como distintos, porque no sabemos si Instagram los junta.
    minusculas = [e.lower() for e in etiquetas]
    repetidas = sorted({e for e in minusculas if minusculas.count(e) > 1})
    genericas = sorted({e for e in minusculas if normaliza(e) in GENERICOS})
    # Un bloque de hashtags al final no molesta aunque el texto sea corto y se vea
    # entero; lo que molesta es un hashtag en mitad de lo que se lee primero.
    cuerpo = sin_bloque_final(texto)
    en_visible = HASHTAG_RE.findall(cuerpo[:len(visible)])
    if len(etiquetas) > HASHTAGS_MAX:
        anota("HASHTAGS", "ARREGLA", f"{len(etiquetas)} hashtags: Instagram los está limitando a {HASHTAGS_MAX} "
                                     f"por post y por reel. Quédate con los que digan de qué va de verdad.")
    elif repetidas or genericas or en_visible:
        partes = []
        if repetidas:
            partes.append("repetidos: #" + ", #".join(repetidas))
        if genericas:
            partes.append("no dicen de qué va el post: #" + ", #".join(genericas))
        if en_visible:
            partes.append("hay hashtags en la parte que se ve; mejor al final")
        anota("HASHTAGS", "OJO", f"{len(etiquetas)} hashtag(s); " + "; ".join(partes))
    else:
        anota("HASHTAGS", "BIEN", f"{len(etiquetas)} hashtag(s)" + ("" if etiquetas else ": ninguno también vale"))

    # MENCIONES
    menciones = MENCION_RE.findall(texto)
    if len(menciones) > MENCIONES_MAX:
        anota("MENCIONES", "OJO", f"{len(menciones)} menciones: la API de Meta, la que usan las herramientas para "
                                  f"programar, no admite más de {MENCIONES_MAX}. Si lo programas, quita alguna.")
    else:
        anota("MENCIONES", "BIEN", f"{len(menciones)} mención(es)")

    # ENLACES
    enlaces = ENLACE_RE.findall(texto)
    if enlaces:
        anota("ENLACES", "OJO", f"{', '.join(enlaces[:3])}: en el texto de un post no se puede pulsar. Pon el "
                                f"enlace en tu perfil y di dónde está.")
    else:
        anota("ENLACES", "BIEN", "ningún enlace en el texto")

    # CIERRE
    pedidas = peticiones(sin_bloque_final(texto))
    cuerpo = sin_bloque_final(texto)
    final = parrafos(cuerpo)[-1] if parrafos(cuerpo) else ""
    if len(pedidas) > 1:
        anota("CIERRE", "OJO", f"{len(pedidas)} peticiones ({', '.join(pedidas)}): se pisan. Deja una.")
    elif pedidas:
        anota("CIERRE", "BIEN", f"una petición: {pedidas[0]}")
    elif acaba_en_pregunta(final):
        anota("CIERRE", "BIEN", "acaba con una pregunta: abre conversación sin vender")
    else:
        anota("CIERRE", "NOTA", "no pide nada ni acaba con una pregunta. Si quieres que se quede pensando, vale; "
                                "si no, decide qué quieres que pase al terminar de leer.")

    # PALABRA CLAVE
    citadas = CLAVE_CITADA_RE.findall(texto)
    malas = [c for c in citadas if re.search(r"\s", c.strip()) or EMOJI_RE.search(c)]
    if malas:
        anota("PALABRA CLAVE", "OJO", f"«{malas[0]}» tiene espacios o emojis: cuesta escribirlo igual en un "
                                      f"comentario. Mejor algo como ACEITE o CITA.")
    elif citadas or CLAVE_MAYUS_RE.search(texto):
        clave = (citadas or [CLAVE_MAYUS_RE.search(texto).group(1)])[0].strip()
        if normaliza(clave) != clave.lower():
            anota("PALABRA CLAVE", "OJO", f"«{clave}» lleva tilde. Si usas respuestas automáticas, comprueba que "
                                          f"la reconocen escrita con y sin tilde, o elige una sin.")
        else:
            anota("PALABRA CLAVE", "BIEN", f"«{clave}» se escribe con el pulgar en un segundo")

    # BÚSQUEDA
    # Se busca en el texto sin hashtags: la idea es que esté escrita como frase.
    texto_sin_tags, visible_sin_tags = normaliza(sin_hashtags(texto)), normaliza(sin_hashtags(visible))
    for frase_busqueda in [b.strip() for b in (buscar or []) if b.strip()]:
        clave = normaliza(frase_busqueda)
        if clave in visible_sin_tags:
            anota("BÚSQUEDA", "BIEN", f"«{frase_busqueda}» está, y en la parte que se ve")
        elif clave in texto_sin_tags:
            anota("BÚSQUEDA", "BIEN", f"«{frase_busqueda}» está en el texto")
        else:
            anota("BÚSQUEDA", "OJO", f"«{frase_busqueda}» no está. Escríbela como una frase normal, no como hashtag.")

    estados = [r["estado"] for r in revision]
    veredicto = ("ARREGLA ANTES DE PUBLICAR" if "ARREGLA" in estados
                 else "REVÍSALO" if "OJO" in estados else "LISTO")
    return {"visible": visible, "hay_mas": hay_mas, "detras": max(0, len(texto) - len(visible)),
            "caracteres": n, "ventana": ventana, "hashtags": etiquetas, "peticiones": pedidas,
            "emojis": cuenta_emojis(texto), "revision": revision, "veredicto": veredicto}


def pinta(r, out=sys.stdout, ancho=48):
    print(f"\nLO QUE SE VE ANTES DEL «MÁS» (unos {r['ventana']} caracteres)", file=out)
    print("+" + "-" * (ancho + 2) + "+", file=out)
    for linea in r["visible"].split("\n"):
        for trozo in textwrap.wrap(linea, ancho) or [""]:
            print(f"| {trozo:<{ancho}} |", file=out)
    print("+" + "-" * (ancho + 2) + "+", file=out)
    if r["hay_mas"]:
        print(f"  ... y {r['detras']} caracteres más detrás del «más».", file=out)
    print(f"\nREVISIÓN DEL TEXTO · {r['caracteres']} caracteres · {r['emojis']} emoji(s)", file=out)
    print("=" * 70, file=out)
    for c in r["revision"]:
        print(f"  {c['estado']:<8} {c['comprobacion']:<14} {c['detalle']}", file=out)
    print("-" * 70, file=out)
    print(f"  {r['veredicto']}\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="Revisa el texto de un post de Instagram antes de publicarlo.")
    ap.add_argument("entrada", nargs="?", default="-", help="archivo con el texto, o - para leerlo de la entrada")
    ap.add_argument("--buscar", default="", help="palabras con las que te buscarían, separadas por comas")
    ap.add_argument("--ventana", type=int, default=VENTANA, help="caracteres visibles antes del «más»")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.ventana <= 0:
        ap.error("--ventana tiene que ser mayor que cero")

    try:
        texto = sys.stdin.read() if args.entrada == "-" else open(args.entrada, encoding="utf-8-sig").read()
    except (OSError, UnicodeDecodeError):
        ap.error(f"no puedo leer «{args.entrada}»: no existe o no es un archivo de texto")
    if not limpia_entrada(texto):
        print("no hay texto que revisar", file=sys.stderr)
        sys.exit(2)
    r = revisa(texto, args.ventana, args.buscar.split(",") if args.buscar else None)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        pinta(r)
    sys.exit(1 if r["veredicto"].startswith("ARREGLA") else 0)


if __name__ == "__main__":
    main()

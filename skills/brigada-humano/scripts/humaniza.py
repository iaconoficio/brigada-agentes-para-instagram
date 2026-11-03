#!/usr/bin/env python3
"""
humaniza.py · La Brigada (IA con Oficio)

Limpia un borrador de las huellas mecánicas que deja la IA en español y te
dice qué frases tienes que reescribir tú.

Lo que arregla solo:
  1. Caracteres invisibles (espacios de ancho cero, marcas de orden, guiones
     blandos...). Respeta los que forman emojis compuestos, como 👩\u200d🍳, que
     sin ellos se partirían en dos.
  2. Tipografía: la raya (—) pasa a coma, los puntos suspensivos de un
     carácter a tres puntos y los espacios duros a espacios normales. Las
     comillas curvas (“ ”) se quedan: en castellano son correctas. Si las
     quieres rectas, usa --comillas-rectas.
  3. Muletillas de IA en castellano («potenciar», «en el mundo actual»,
     «cabe destacar que»...), cambiadas por palabras normales o borradas.

Lo que solo señala, porque cambiarlo pide criterio:
  muletillas sin sustituto seguro y estructuras como «No es solo X, es Y».

Funciona sin internet y no envía nada a ningún sitio. Enlaces, @menciones y
#hashtags no se tocan.

Uso
  python3 humaniza.py borrador.txt                 # texto limpio por pantalla
  python3 humaniza.py borrador.txt -o limpio.txt --informe
  python3 humaniza.py borrador.txt --comillas-rectas
  python3 humaniza.py borrador.txt --ficha FICHA-BRIGADA.md --informe
  python3 humaniza.py borrador.txt --respetar "asimismo" --respetar optimizar
  cat borrador.txt | python3 humaniza.py -

Con --ficha, las «Palabras que usas» de tu ficha no se tocan aunque estén en
la lista de muletillas, y las «Palabras que no dirías nunca» se avisan.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
LEXICO = os.path.join(AQUI, "muletillas.json")

PROTEGER_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+|[@#][\w.áéíóúñÁÉÍÓÚÑ]+")
VOCALES = {
    "a": "aáà", "e": "eéè", "i": "iíì", "o": "oóò", "u": "uúüù",
    "á": "aáà", "é": "eéè", "í": "iíì", "ó": "oóò", "ú": "uúüù",
}


def carga_lexico(ruta=LEXICO):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def normaliza(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


CITA_RE = re.compile(r"«([^»]+)»|“([^”]+)”|\"([^\"]+)\"")
NOTA_RE = re.compile(r"\*?\([^)]*\)\*?")
PENDIENTE_RE = re.compile(r"`?\[PENDIENTE\].*")


def campo_lista(ficha, campo):
    """Saca la lista de un campo de FICHA-BRIGADA.md, por ejemplo «Palabras que usas».

    Vale «**Campo** (nota): valor» y «**Campo:** valor», con el valor en la misma
    línea o en subviñetas debajo. Si hay expresiones entre comillas (« », “ ” o
    " "), se quedan esas. Si no, se parte por comas, punto y coma o «ni». Las
    notas entre paréntesis, las marcas de origen y lo que está en [PENDIENTE]
    no cuentan.
    """
    lineas = ficha.splitlines()
    rotulo = re.compile(r"\*\*" + re.escape(campo) + r"(:\*\*|\*\*)(.*)")
    for i, linea in enumerate(lineas):
        m = rotulo.search(linea)
        if not m:
            continue
        # Lo que va detrás de [PENDIENTE] en una línea es una nota, no una palabra suya.
        valor = PENDIENTE_RE.sub(" ", m.group(2))
        valor = NOTA_RE.sub(" ", valor).strip()
        valor = valor.lstrip(":* ").strip()
        sangria = len(linea) - len(linea.lstrip())
        for siguiente in lineas[i + 1:]:
            if not siguiente.strip() or len(siguiente) - len(siguiente.lstrip()) <= sangria:
                break
            valor += ", " + PENDIENTE_RE.sub(" ", siguiente.strip().lstrip("->* ")).strip()
        citas = [next(g for g in grupos if g).strip() for grupos in CITA_RE.findall(valor)]
        citas = [c for c in citas if c]
        if citas:
            return citas
        partes = re.split(r"[,;]|\s+ni\s+", NOTA_RE.sub(" ", valor))
        return [p.strip(" .;:*") for p in partes if p.strip(" .;:*")]
    return []


def lee_ficha(ruta):
    """Devuelve (palabras que la persona usa, palabras que no diría nunca)."""
    with open(ruta, encoding="utf-8") as fh:
        ficha = fh.read()
    return campo_lista(ficha, "Palabras que usas"), campo_lista(ficha, "Palabras que no dirías nunca")


def estructuras_propias(ficha):
    """Estructuras de la lista que la persona usa a propósito, según su ficha.

    Hoy solo una: si en «Preguntas retóricas» pone que sí, que son suyas, no se
    señalan. Si el campo está sin rellenar («[sí, son mías | no]»), no cuenta."""
    rotulo = re.search(r"(?mi)^([ \t]*)-\s*(?:\*\*)?Preguntas ret[oó]ricas(?:\*\*)?\s*:(?:\*\*)?([^\n]*)", ficha)
    if not rotulo:
        return set()
    valor = rotulo.group(2)
    if not PENDIENTE_RE.sub(" ", valor).strip(" :*"):
        # El valor puede ir en una subviñeta debajo.
        resto = ficha[rotulo.end():].lstrip("\n").split("\n", 1)[0]
        if len(resto) - len(resto.lstrip()) > len(rotulo.group(1)):
            valor = resto.strip().lstrip("-* ")
    valor = PENDIENTE_RE.sub(" ", valor).strip(" :*")
    if "|" in valor:                                   # la plantilla sin rellenar
        return set()
    valor = valor.strip("[] ")
    return {"pregunta-retorica"} if re.match(r"s[ií]\b", valor, re.IGNORECASE) else set()


def lee_propias(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return estructuras_propias(fh.read())


def sin_puntuacion(termino):
    return normaliza(termino).strip(" ,.;:¿?¡!")


# Marcas propias para lo que no se toca: las expresiones de la persona y los
# tiempos de un guion («0:00 a 0:03»), que la semirraya convertiría en coma.
FIJO_A, FIJO_B = chr(0xE002), chr(0xE003)
FIJO_RE = re.compile(FIJO_A + r"(\d+)" + FIJO_B)
TIEMPO_RE = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?:[.,]\d)?(?:\s*[-" + chr(0x2013) + chr(0x2014)
                       + r"]\s*\d{1,2}:\d{2}(?:[.,]\d)?)?")


def fija(texto, respetar):
    """Aparta las expresiones de la persona y los tiempos para que no se toquen.
    Solo se aparta la expresión entera, no las palabras sueltas que contiene.
    En los tiempos y horarios («9:00 a 14:00»), la semirraya pasa a guion."""
    fijos, vistas = [], []

    def guarda(m):
        fijos.append(m.group(0))
        return f"{FIJO_A}{len(fijos) - 1}{FIJO_B}"

    def guarda_tiempo(m):
        fijos.append(m.group(0).replace(chr(0x2013), "-").replace(chr(0x2014), "-"))
        return f"{FIJO_A}{len(fijos) - 1}{FIJO_B}"

    texto = TIEMPO_RE.sub(guarda_tiempo, texto)
    for expresion in sorted({r.strip() for r in respetar if r.strip()}, key=len, reverse=True):
        nuevo, n = patron(expresion).subn(guarda, texto)
        if n:
            vistas.append(expresion)
            texto = nuevo
    return texto, fijos, vistas


def suelta(texto, fijos):
    return FIJO_RE.sub(lambda m: fijos[int(m.group(1))], texto)


FORMATO_CHAT = [
    (re.compile(r"\*\*([^*\n]+)\*\*"), r"\1", "negrita de chat (**)"),
    (re.compile(r"__([^_\n]+)__"), r"\1", "negrita de chat (__)"),
    (re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+"), "", "título de chat (#)"),
    (re.compile(r"(?m)^([ \t]*)\*[ \t]+"), r"\1- ", "viñeta de chat (*)"),
]


def patron(termino):
    """Regex que encuentra el término con o sin tildes y en cualquier caja."""
    partes = []
    for c in termino:
        baja = c.lower()
        if baja in VOCALES:
            partes.append("[" + VOCALES[baja] + "]")
        elif c == " ":
            partes.append(r"\s+")
        else:
            partes.append(re.escape(c))
    cuerpo = "".join(partes)
    if termino[:1].isalnum():
        cuerpo = r"(?<!\w)" + cuerpo
    if termino[-1:].isalnum():
        cuerpo = cuerpo + r"(?!\w)"
    return re.compile(cuerpo, re.IGNORECASE)


def es_emoji(c):
    cp = ord(c)
    return (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
            or unicodedata.category(c) == "So")


def quita_invisibles(texto):
    """Borra los caracteres de formato salvo los que forman parte de un emoji."""
    salida, quitados = [], 0
    n = len(texto)
    for i, c in enumerate(texto):
        if unicodedata.category(c) != "Cf":
            salida.append(c)
            continue
        cp = ord(c)
        if cp == 0x200D:  # unión de ancho cero: la conservamos entre emojis
            j = len(salida) - 1
            # saltamos el selector de emoji y los tonos de piel para llegar al emoji
            while j >= 0 and (salida[j] == "\ufe0f" or 0x1F3FB <= ord(salida[j]) <= 0x1F3FF):
                j -= 1
            siguiente = texto[i + 1] if i + 1 < n else ""
            if j >= 0 and es_emoji(salida[j]) and siguiente and es_emoji(siguiente):
                salida.append(c)
                continue
        if 0xE0020 <= cp <= 0xE007F:  # etiquetas de las banderas de Escocia, Gales e Inglaterra
            if "\U0001F3F4" in texto[max(0, i - 8):i]:
                salida.append(c)
                continue
        quitados += 1
    return "".join(salida), quitados


def protege(texto):
    guardados = []

    def guarda(m):
        guardados.append(m.group(0))
        return f"\ue000{len(guardados) - 1}\ue001"

    return PROTEGER_RE.sub(guarda, texto), guardados


def restaura(texto, guardados):
    return re.sub(r"\ue000(\d+)\ue001", lambda m: guardados[int(m.group(1))], texto)


def con_misma_caja(original, nuevo):
    if nuevo and original[:1].isupper():
        return nuevo[0].upper() + nuevo[1:]
    return nuevo


def escribe_con_mayusculas(texto):
    """¿Esta persona empieza las frases con mayúscula? Solo entonces las arreglamos."""
    inicios = re.findall(r"(?:^|[.!?]\s+)[¿¡\"']?(\w)", texto, re.MULTILINE)
    if len(inicios) < 2:
        return True
    return sum(1 for c in inicios if c.isupper()) / len(inicios) >= 0.6


def limpia_puntuacion(texto, mayusculas):
    # Al borrar una frase entera queda un punto suelto entre espacios
    # («Hola. . Adiós»). Solo ese: «Bueno..», «¿En serio?..» o «etc.» no se tocan.
    texto = re.sub(r"(?<!\.)([.!?])[ \t]+\.(?![.\w])", r"\1", texto)
    texto = re.sub(r"[ \t]+([,.;:!?])", r"\1", texto)
    texto = re.sub(r",\s*,", ",", texto)
    texto = re.sub(r",\s*([.!?;:])", r"\1", texto)
    texto = re.sub(r"(?m)^[ \t]*(?:[,;]|[.:](?=[ \t]|$))[ \t]*", "", texto)
    # Si al borrar muletillas una frase se queda en «Y.» o «Pero.», fuera.
    texto = re.sub(r"(^|[.!?]|\n)[ \t]*(?:[YyEeOo]|[Pp]ero)[ \t]*[.!?](?=\s|$)", r"\1", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"(?m)^[ \t]+|[ \t]+$", "", texto)
    if mayusculas:
        # tras unos puntos suspensivos se sigue en minúscula, así que no se tocan
        texto = re.sub(r"(^|(?<!\.\.)[.!?]\s+|\n)([¿¡\"']?)([a-záéíóúñ])",
                       lambda m: m.group(1) + m.group(2) + m.group(3).upper(), texto)
    return texto


def humaniza(texto, lexico, mantener_comillas=True, respetar=None, evitar=None, propias=None):
    """Limpia el texto.

    `respetar`: palabras o expresiones de la persona. Donde aparecen enteras, no
    se tocan, aunque estén en la lista de muletillas.
    `evitar`: palabras que la persona no diría nunca. Se avisan, y el script no
    las mete como sustituto de nada.
    `propias`: estructuras que la persona usa a propósito (por su id, como
    «pregunta-retorica»). No se señalan.
    """
    propias = set(propias or ())
    informe = {"invisibles": 0, "tipografia": {}, "cambios": {}, "para_revisar": {}, "estructuras": [],
               "respetadas": [], "evitar": {}}
    evitar = [t.strip() for t in (evitar or []) if t and t.strip()]
    no_meter = {sin_puntuacion(t) for t in evitar}
    mayusculas = escribe_con_mayusculas(texto)

    texto, informe["invisibles"] = quita_invisibles(texto)
    texto, guardados = protege(texto)
    texto, fijos, informe["respetadas"] = fija(texto, respetar or [])

    for regla, cambio, nombre in FORMATO_CHAT:
        texto, n = regla.subn(cambio, texto)
        if n:
            informe["tipografia"][nombre] = n

    # Raya de diálogo a principio de línea: se quita sin dejar coma.
    texto, n = re.subn(r"(?m)^([ \t]*)—[ \t]*", r"\1", texto)
    if n:
        informe["tipografia"]["raya de diálogo"] = n
    for regla in lexico["tipografia"]:
        if mantener_comillas and "comilla" in regla["nombre"]:
            continue
        n = texto.count(regla["de"])
        if n:
            texto = texto.replace(regla["de"], regla["a"])
            informe["tipografia"][regla["nombre"]] = informe["tipografia"].get(regla["nombre"], 0) + n

    entradas = sorted(lexico["frases"] + lexico["palabras"], key=lambda e: -len(e["buscar"]))
    for e in entradas:
        p = patron(e["buscar"])
        sustituto_vetado = bool(e["cambiar"]) and sin_puntuacion(e["cambiar"]) in no_meter
        if e["cambiar"] is None or sustituto_vetado:
            # Sin sustituto seguro, o el sustituto es una palabra que no diría: se avisa.
            n = len(p.findall(texto))
            if n:
                informe["para_revisar"][e["buscar"]] = n
            continue
        texto, n = p.subn(lambda m: con_misma_caja(m.group(0), e["cambiar"]), texto)
        if n:
            informe["cambios"][e["buscar"]] = (e["cambiar"] or "(borrado)", n)

    texto = limpia_puntuacion(texto, mayusculas)
    texto = restaura(texto, guardados)

    # Las estructuras se buscan con sus expresiones apartadas: un cierre suyo
    # como «¿Me sigues?» no es una pregunta retórica de IA.
    for s in lexico["estructuras"]:
        if s.get("id") in propias:
            continue
        try:
            encontrados = re.compile(s["regex"]).findall(texto)
        except re.error:
            continue
        if encontrados:
            informe["estructuras"].append({"nombre": s["nombre"], "veces": len(encontrados),
                                           "arreglo": s["arreglo"]})
    texto = suelta(texto, fijos)

    for termino in evitar:
        n = len(patron(termino).findall(texto))
        if n:
            informe["evitar"][termino] = n
    return texto, informe


def pinta_informe(informe, out=sys.stderr):
    total = (informe["invisibles"] + sum(informe["tipografia"].values())
             + sum(v[1] for v in informe["cambios"].values()))
    print(f"\n{total} huellas mecánicas quitadas, "
          f"{len(informe['estructuras'])} estructuras señaladas para reescribir a mano", file=out)
    print("=" * 62, file=out)
    if informe["invisibles"]:
        print(f"  1. INVISIBLES        {informe['invisibles']} borrados", file=out)
    if informe["tipografia"]:
        print("  2. TIPOGRAFÍA", file=out)
        for nombre, n in informe["tipografia"].items():
            print(f"     {nombre}: {n}", file=out)
    if informe["cambios"]:
        print("  3. MULETILLAS CAMBIADAS", file=out)
        for buscar, (cambiar, n) in informe["cambios"].items():
            print(f"     «{buscar}» → «{cambiar}» ({n})", file=out)
    if informe["para_revisar"]:
        print("  4. MULETILLAS PARA REVISAR (no se han tocado)", file=out)
        for buscar, n in informe["para_revisar"].items():
            print(f"     «{buscar}» ({n})", file=out)
    if informe["estructuras"]:
        print("  5. ESTRUCTURAS (reescríbelas tú)", file=out)
        for s in informe["estructuras"]:
            print(f"     {s['nombre']} ×{s['veces']}: {s['arreglo']}", file=out)
    if informe.get("respetadas"):
        print("  6. TUS PALABRAS (son tuyas: no se han tocado)", file=out)
        for buscar in informe["respetadas"]:
            print(f"     «{buscar}»", file=out)
    if informe.get("evitar"):
        print("  7. PALABRAS QUE NO DIRÍAS (según tu ficha: cámbialas tú)", file=out)
        for termino, n in informe["evitar"].items():
            print(f"     «{termino}» ({n})", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Quita las huellas mecánicas de un borrador en español.")
    ap.add_argument("entrada", nargs="?", default="-", help="archivo, o - para leer de la entrada")
    ap.add_argument("-o", "--salida", help="guarda aquí el texto limpio en vez de mostrarlo")
    ap.add_argument("--informe", action="store_true", help="explica qué se ha cambiado y qué falta")
    ap.add_argument("--json", action="store_true", help="devuelve texto e informe en JSON")
    ap.add_argument("--comillas-rectas", action="store_true",
                    help="cambia las comillas curvas por rectas (por defecto se quedan)")
    ap.add_argument("--lexico", default=LEXICO)
    ap.add_argument("--ficha", help="tu FICHA-BRIGADA.md: respeta tus «Palabras que usas», avisa de las que "
                                    "no dirías nunca y no señala tus preguntas retóricas si son tuyas")
    ap.add_argument("--respetar", action="append", default=[], help="palabra o expresión tuya que no se toca (se puede repetir)")
    args = ap.parse_args()

    respetar, evitar, propias = list(args.respetar), [], set()
    if args.ficha:
        try:
            propias = lee_propias(args.ficha)
            usa, nunca = lee_ficha(args.ficha)
        except (OSError, UnicodeDecodeError):
            ap.error(f"no puedo leer la ficha «{args.ficha}»: no existe o no es un archivo de texto")
        if not usa and not nunca:
            print("Aviso: no encuentro tus «Palabras que usas» ni tus «Palabras que no dirías nunca» "
                  "en la ficha. Sigo sin ellas.", file=sys.stderr)
        respetar += usa
        evitar += nunca

    try:
        bruto = sys.stdin.read() if args.entrada == "-" else open(args.entrada, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        ap.error(f"no puedo leer «{args.entrada}»: no existe o no es un archivo de texto")
    try:
        lexico = carga_lexico(args.lexico)
    except (OSError, UnicodeDecodeError, ValueError):
        ap.error(f"no puedo leer la lista de muletillas «{args.lexico}»")
    limpio, informe = humaniza(bruto, lexico, not args.comillas_rectas, respetar, evitar, propias)

    if args.json:
        print(json.dumps({"texto": limpio, "informe": informe}, ensure_ascii=False, indent=2))
        return
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as fh:
            fh.write(limpio)
    else:
        sys.stdout.write(limpio)
    if args.informe:
        pinta_informe(informe)


if __name__ == "__main__":
    main()

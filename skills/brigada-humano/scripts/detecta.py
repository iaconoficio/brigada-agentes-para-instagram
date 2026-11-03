#!/usr/bin/env python3
"""
detecta.py · La Brigada (IA con Oficio)

Puntúa de 0 a 100 cinco señales que delatan un texto escrito por IA en
español. Cuanto más alto, más humano.

  RITMO       ¿las frases cambian de largo? Las personas sí; la IA, poco.
  CONCRECIÓN  cifras, nombres, sitios. La paja es abstracta.
  MULETILLAS  cuántas expresiones de IA hay por cada 100 palabras.
  HUELLA      caracteres que un móvil no escribe: invisibles, rayas.
  VOZ         primera y segunda persona, tono de conversación y las
              estructuras típicas de la IA («No es solo X, es Y»).

Dilo con honestidad: son cinco comprobaciones locales, pensadas a partir de
las señales en las que se fijan los detectores públicos. No son GPTZero,
Originality ni ningún otro, no llaman a ninguno y no pueden prometer lo que
diría cualquiera de ellos. Los umbrales son iniciales y están pendientes de
calibrar con textos reales en español. Nunca digas que un texto es
«indetectable».

Nota sobre las comillas curvas: el iPhone las escribe solas (puntuación
inteligente), así que aquí no cuentan como huella de IA. Se informa de ellas,
pero no restan.

Funciona sin internet y no envía nada a ningún sitio.

Uso
  python3 detecta.py borrador.txt
  python3 detecta.py antes.txt despues.txt       # compara las dos versiones
  python3 detecta.py borrador.txt --ficha FICHA-BRIGADA.md
  python3 detecta.py borrador.txt --json

Con --ficha (o --respetar), tus «Palabras que usas» no cuentan como muletillas.
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
LEXICO = os.path.join(AQUI, "muletillas.json")

FRASE_RE = re.compile(r"[^.!?\n]+[.!?]*")
PALABRA_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
CIFRA_RE = re.compile(r"[€$]\s?\d|\b\d[\d.,]*\s?(?:%|€)?")
VOCALES = {
    "a": "aáà", "e": "eéè", "i": "iíì", "o": "oóò", "u": "uúüù",
    "á": "aáà", "é": "eéè", "í": "iíì", "ó": "oóò", "ú": "uúüù",
}

PERSONA = {
    "yo", "me", "mi", "mis", "conmigo", "nosotros", "nosotras", "nos",
    "nuestro", "nuestra", "nuestros", "nuestras", "tu", "tus", "te", "ti",
    "contigo", "usted", "ustedes", "vosotros", "vosotras", "os", "vuestro",
    "vuestra", "vuestros", "vuestras", "tengo", "llevo", "hice", "hago", "fui",
    "soy", "estoy", "creo", "pienso", "digo", "vi", "aprendi", "probe", "tienes",
    "haces", "eres", "estas", "sabes", "puedes", "quieres", "vas", "llevas",
}
# Marcas de conversación. Algunas son de España y otras de Latinoamérica.
COLOQUIAL = {
    "vale", "oye", "mira", "pues", "eh", "bueno", "venga", "fijate", "ojo",
    "uf", "vaya", "hombre", "tio", "tia", "che", "orale", "ostras", "hostia",
}
COLOQUIAL_FRASES = ["o sea", "a ver", "la verdad", "en plan", "ni de cona", "madre mia"]


def limita(n):
    return max(0.0, min(100.0, n))


def escala(valor, humano, maquina):
    """Lleva un valor a 0-100: `humano` da 100 y `maquina` da 0."""
    if humano == maquina:
        return 50.0
    return limita((valor - maquina) / (humano - maquina) * 100)


def normaliza(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def patron(termino):
    partes = []
    for c in termino:
        baja = c.lower()
        partes.append("[" + VOCALES[baja] + "]" if baja in VOCALES else
                      (r"\s+" if c == " " else re.escape(c)))
    cuerpo = "".join(partes)
    if termino[:1].isalnum():
        cuerpo = r"(?<!\w)" + cuerpo
    if termino[-1:].isalnum():
        cuerpo = cuerpo + r"(?!\w)"
    return re.compile(cuerpo, re.IGNORECASE)


def frases(texto):
    return [f.strip() for f in FRASE_RE.findall(texto) if len(f.split()) > 2]


def palabras(texto):
    return PALABRA_RE.findall(texto)


def nombres_propios(texto):
    vistos = set()
    for f in re.split(r"[.!?¡¿\n]+", texto):
        ps = palabras(f)
        for p in ps[1:]:
            if len(p) >= 3 and p[0].isupper():
                vistos.add(p)
    return vistos


def mira_ritmo(texto):
    """Las personas alternan frases cortas y largas. Los modelos escriben parejo."""
    largos = [len(f.split()) for f in frases(texto)]
    if len(largos) < 4:
        return 50.0, "demasiado corto para juzgarlo"
    media = statistics.mean(largos)
    cv = statistics.pstdev(largos) / media if media else 0
    return escala(cv, humano=0.70, maquina=0.22), f"variación {cv:.2f} en {len(largos)} frases (mejor 0,55 o más)"


def mira_concrecion(texto):
    ps = palabras(texto)
    if len(ps) < 25:
        return 50.0, "demasiado corto para juzgarlo"
    datos = len(CIFRA_RE.findall(texto)) + len(nombres_propios(texto))
    densidad = datos * 100 / len(ps)
    return escala(densidad, humano=6.0, maquina=0.5), f"{datos} datos concretos, {densidad:.1f} por cada 100 palabras (mejor 4 o más)"


def mira_muletillas(texto, lex):
    ps = palabras(texto)
    if not ps:
        return 50.0, "vacío"
    total, vistas = 0, []
    for e in lex["palabras"] + lex["frases"]:
        n = len(patron(e["buscar"]).findall(texto))
        if n:
            total += n
            vistas.append(e["buscar"])
    densidad = total * 100 / len(ps)
    detalle = f"{total} muletillas, {densidad:.1f} por cada 100 palabras"
    if vistas:
        detalle += " (" + ", ".join(sorted(vistas)[:4]) + (", ..." if len(vistas) > 4 else "") + ")"
    return escala(densidad, humano=0.0, maquina=4.0), detalle


def mira_huella(texto):
    """Caracteres que un móvil no escribe solo."""
    invisibles = sum(1 for c in texto if unicodedata.category(c) == "Cf" and c != "\u200d")
    rayas = texto.count("—")
    duros = sum(texto.count(c) for c in "\u00a0\u202f\u2009")
    curvas = sum(texto.count(c) for c in "‘’“”")
    total = invisibles * 4 + rayas * 2 + duros
    por_mil = total * 1000 / max(len(texto), 1)
    detalle = (f"{invisibles} invisibles, {rayas} rayas, {duros} espacios duros"
               f" ({curvas} comillas curvas, que no cuentan: el iPhone las pone solo)")
    return escala(por_mil, humano=0.0, maquina=12.0), detalle


def mira_voz(texto, lex, propias=()):
    ps = palabras(texto)
    if len(ps) < 25:
        return 50.0, "demasiado corto para juzgarlo"
    por100 = 100 / len(ps)
    bajas = [normaliza(p) for p in ps]
    persona = sum(1 for b in bajas if b in PERSONA) * por100
    plano = " " + " ".join(bajas) + " "
    coloquial = (sum(1 for b in bajas if b in COLOQUIAL)
                 + sum(plano.count(f" {f} ") for f in COLOQUIAL_FRASES)) * por100
    tics, nombres = 0, []
    for s in lex["estructuras"]:
        if s.get("id") in propias:
            continue                   # la persona la usa a propósito
        try:
            n = len(re.compile(s["regex"]).findall(texto))
        except re.error:
            continue
        if s["id"] == "tres-de-golpe":
            n = max(0, n - 1)          # un trío lo escribe cualquiera; varios, no
        if n:
            tics += n
            nombres.append(s["id"])
    vinetas = [len(v.split()) for v in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", texto)]
    uniformes = len(vinetas) >= 3 and statistics.pstdev(vinetas) < 1.6
    nota = (escala(persona, humano=8.0, maquina=1.0) * 0.45
            + escala(coloquial, humano=1.5, maquina=0.0) * 0.20
            + limita(100 - tics * 22) * 0.35)
    if uniformes:
        nota -= 12
        nombres.append("vinetas-iguales")
    detalle = (f"{persona:.1f} marcas de persona y {coloquial:.1f} de conversación por cada 100 palabras, "
               f"{tics} estructura(s) de IA")
    if nombres:
        detalle += " [" + ", ".join(nombres[:4]) + "]"
    return limita(nota), detalle


COMPROBACIONES = ["RITMO", "CONCRECIÓN", "MULETILLAS", "HUELLA", "VOZ"]
CORTO = 60


def aviso_longitud(texto):
    """detecta.py mide un texto entero. Con pocas palabras, la nota orienta poco."""
    n = len(palabras(texto))
    if n < CORTO:
        return (f"Texto corto ({n} palabras): la nota es orientativa. Mide un texto entero, "
                f"como un caption o un guion, no frases sueltas.")
    return ""


def sin_respetadas(texto, respetar):
    """Quita las expresiones de la persona antes de contar muletillas y tics:
    si son suyas, no delatan a la IA."""
    for expresion in sorted({r.strip() for r in (respetar or []) if r.strip()}, key=len, reverse=True):
        texto = patron(expresion).sub(" ", texto)
    return texto


def analiza(texto, lex, respetar=None, propias=None):
    suyo = sin_respetadas(texto, respetar)
    propias = set(propias or ())
    r = {
        "RITMO": mira_ritmo(texto),
        "CONCRECIÓN": mira_concrecion(texto),
        "MULETILLAS": mira_muletillas(suyo, lex),
        "HUELLA": mira_huella(texto),
        "VOZ": mira_voz(suyo, lex, propias),
    }
    notas = [r[c][0] for c in COMPROBACIONES]
    # La señal más débil arrastra el resultado: a un detector le basta una.
    total = statistics.mean(notas) * 0.6 + min(notas) * 0.4
    veredicto = "PASA" if total >= 70 and min(notas) >= 55 else (
        "REVISAR" if total >= 50 else "SUENA A IA")
    return r, total, veredicto


def barra(nota, ancho=24):
    llenas = round(nota / 100 * ancho)
    return "#" * llenas + "." * (ancho - llenas)


def pinta(r, total, veredicto, etiqueta=None, out=sys.stdout):
    titulo = "PANEL DE DETECCIÓN" + (f"  ·  {etiqueta}" if etiqueta else "")
    print("\n" + titulo, file=out)
    print("=" * max(len(titulo), 62), file=out)
    for c in COMPROBACIONES:
        nota, detalle = r[c]
        print(f"  {c:<11} {barra(nota)} {nota:5.1f}", file=out)
        print(f"  {'':<11} {detalle}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HUMANO':<11} {barra(total)} {total:5.1f}   {veredicto}", file=out)
    if veredicto != "PASA":
        floja = min(COMPROBACIONES, key=lambda c: r[c][0])
        print(f"\n  Lo más flojo: {floja}. Arregla eso primero.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Puntúa cuánto suena a IA un borrador en español.")
    ap.add_argument("entrada", nargs="?", default="-", help="archivo, o - para leer de la entrada")
    ap.add_argument("comparar", nargs="?", help="segundo archivo, para ver el antes y el después")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lexico", default=LEXICO)
    ap.add_argument("--ficha", help="tu FICHA-BRIGADA.md: tus «Palabras que usas» no cuentan como muletillas, "
                                    "ni tus preguntas retóricas si son tuyas")
    ap.add_argument("--respetar", action="append", default=[], help="palabra o expresión tuya (se puede repetir)")
    args = ap.parse_args()

    try:
        with open(args.lexico, encoding="utf-8") as fh:
            lex = json.load(fh)
    except (OSError, UnicodeDecodeError, ValueError):
        ap.error(f"no puedo leer la lista de muletillas «{args.lexico}»")

    def lee(ruta):
        try:
            return sys.stdin.read() if ruta == "-" else open(ruta, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            ap.error(f"no puedo leer «{ruta}»: no existe o no es un archivo de texto")

    respetar, propias = list(args.respetar), set()
    if args.ficha:
        sys.path.insert(0, AQUI)
        from humaniza import lee_ficha, lee_propias
        try:
            usa = lee_ficha(args.ficha)[0]
            propias = lee_propias(args.ficha)
        except (OSError, UnicodeDecodeError):
            ap.error(f"no puedo leer la ficha «{args.ficha}»: no existe o no es un archivo de texto")
        if not usa:
            print("Aviso: no encuentro tus «Palabras que usas» en la ficha. Sigo sin ellas.", file=sys.stderr)
        respetar += usa

    if args.comparar:
        texto_antes, texto_despues = lee(args.entrada), lee(args.comparar)
        antes, despues = analiza(texto_antes, lex, respetar, propias), analiza(texto_despues, lex, respetar, propias)
        if args.json:
            print(json.dumps({"antes": antes[1], "despues": despues[1],
                              "aviso": aviso_longitud(texto_despues)}, ensure_ascii=False, indent=2))
            return
        pinta(*antes, etiqueta="ANTES")
        pinta(*despues, etiqueta="DESPUÉS")
        print(f"  Diferencia: {despues[1] - antes[1]:+.1f} puntos\n")
        aviso = aviso_longitud(texto_despues)
        if aviso:
            print(f"  {aviso}\n")
        return

    texto = lee(args.entrada)
    r, total, veredicto = analiza(texto, lex, respetar, propias)
    aviso = aviso_longitud(texto)
    if args.json:
        print(json.dumps({"comprobaciones": {k: {"nota": round(v[0], 1), "detalle": v[1]} for k, v in r.items()},
                          "total": round(total, 1), "veredicto": veredicto, "aviso": aviso},
                         ensure_ascii=False, indent=2))
        return
    pinta(r, total, veredicto)
    if aviso:
        print(f"  {aviso}\n")


if __name__ == "__main__":
    main()

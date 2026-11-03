#!/usr/bin/env python3
"""
tiempos.py · La Brigada (IA con Oficio)

Antes de grabar, te dice cuánto dura tu guion y dónde se va a hacer largo.

Lee el guion línea a línea. Cada línea es un plano: lo que dices mientras se ve
una misma imagen. Calcula los segundos de cada plano, los pone en fila con su
minuto y segundo, y marca estos avisos:

  GANCHO LARGO   el primer plano pasa de 4,5 segundos (unas 12 palabras)
  PLANO LARGO    un plano pasa de 4 segundos con la misma imagen
  TRAMO PLANO    tres planos seguidos sin nada que se vea: ni cifra, ni nombre,
                 ni escena, ni indicación de plano. Es una pista, no un error:
                 no conoce todas las palabras de cada oficio.
  DURACIÓN       el total se aleja más de un 20 % de lo que querías
  CARTEL LARGO   un cartel en pantalla pasa de 6 palabras

Cómo calcula: cuenta las palabras y las divide por tu ritmo al hablar, 165
palabras por minuto si no le dices otro. Las cifras cuentan como se dicen:
«45» son tres palabras («cuarenta y cinco») y «18.000 €», tres («dieciocho mil
euros»). Es una estimación para preparar la grabación. Tu ritmo real lo sabrás
leyendo un guion tuyo en voz alta con el cronómetro del móvil; ponlo con --ppm.

Si el guion no tiene nada dicho, solo carteles (un reel sin voz), calcula
cuánto tiempo necesita cada cartel en pantalla para que dé tiempo a leerlo.
También es una estimación.

Cómo se escribe el guion:
  una línea por plano          lo que dices en ese plano
  [plano: manos en el motor]   lo que se ve: no se dice
  (sonríe)                     indicación: tampoco se dice
  > NO SIEMPRE ES LA RUEDA     cartel en pantalla; también valen «EN PANTALLA:»,
                               «CARTEL:» o «TEXTO:» al principio de la línea
  # nota                       se ignora
  0:03-0:08 o GANCHO:          marcas de tiempo y etiquetas de guion (GANCHO,
                               PLANO 2, VOZ EN OFF, CIERRE...) al principio de
                               la línea: se quitan, no se dicen

Funciona sin internet y no envía nada a ningún sitio.

La idea parte de beats.py, de Jake Schincariol (licencia MIT):
github.com/Jakeschincariol/instagram-agent-skill

Uso
  python3 tiempos.py guion.txt
  python3 tiempos.py guion.txt --objetivo 30
  python3 tiempos.py guion.txt --ppm 150 --objetivo 45
  python3 tiempos.py guion.txt --json
"""

import argparse
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from puntua_gancho import (CIFRA_RE, ESCENA, NUMEROS_HABLADOS, PALABRAS_DE_DINERO,  # noqa: E402
                           nombres_propios, normaliza)

PPM = 165                # ritmo por defecto, el mismo que usa puntua_gancho.py
GANCHO_MAX = 4.5         # segundos: unas 12 palabras, lo que acepta puntua_gancho.py
PLANO_MAX = 4.0          # segundos con la misma imagen
TRAMO_PLANO = 3          # planos seguidos sin nada que se vea
CARTEL_MAX = 6           # palabras por cartel en pantalla
CARTEL_MIN = 1.5         # segundos que pedimos para cualquier cartel (estimación nuestra)
CARTEL_POR_PALABRA = 0.4  # segundos por palabra leída en pantalla (estimación nuestra)

GUIONES = "[-" + chr(0x2013) + chr(0x2014) + "]"
HORA = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d+)?"
RANGO = HORA + r"\s*(?:" + GUIONES + r"|a)\s*" + HORA
SEPARADOR = r"(?:" + GUIONES + r"|\||:)"
# Una marca de tiempo al principio de la línea: entre corchetes o paréntesis, un
# tramo («0:00-0:03»), un tiempo del minuto cero («0:03»), uno con décimas
# («1:03.5») o con horas («00:00:03»), o cualquiera seguido de un separador.
# «9:30 y la moto no arranca» se queda: eso es una hora y se dice.
MARCA_TIEMPO_RE = re.compile(
    r"^\s*(?:[\[(]\s*(?:" + RANGO + "|" + HORA + r")\s*[\])]"
    r"|" + RANGO +
    r"|\d{1,2}:\d{1,2}:\d{2}(?:[.,]\d+)?"
    r"|\d{1,2}:\d{2}[.,]\d+"
    r"|0?0:\d{2}"
    r"|" + HORA + r"(?=\s*" + SEPARADOR + r"))"
    r"\s*" + SEPARADOR + r"?\s*")
ETIQUETAS_DE_CARTEL = r"(?:texto en pantalla|en pantalla|cartel|texto|r[oó]tulo|s[uú]per)\s*\d*\s*:\s*"
CARTEL_ETIQUETA_RE = re.compile(r"^" + ETIQUETAS_DE_CARTEL, re.IGNORECASE)
CARTEL_EN_LINEA_RE = re.compile(r"\[\s*" + ETIQUETAS_DE_CARTEL + r"([^\]]*)\]", re.IGNORECASE)
# Etiquetas de guion que no se dicen. Es una lista cerrada: «IVA: lo pagas tú» se dice.
ETIQUETA_RE = re.compile(r"^(?:gancho|plano|escena|toma|voz en off|voz|off|intro|cuerpo|cierre|cta|final|hook|beat)"
                         r"\s*\d*\s*:\s*", re.IGNORECASE)
INDICACION_RE = re.compile(r"\[[^\]]*\]|\([^)]*\)")
IMAGEN_RE = re.compile(r"\[[^\]]*\]")       # lo que se ve va entre corchetes; (pausa) no es imagen
BOM = chr(0xFEFF)
PALABRA_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
NUMERO_RE = re.compile(r"\d+(?:[.,:]\d+)*")


def clasifica(linea):
    """Quita la marca de tiempo y la etiqueta. Devuelve ("cartel" o "dicho", texto)."""
    s = MARCA_TIEMPO_RE.sub("", linea.strip(), count=1).strip()
    if s.startswith(">"):
        return "cartel", s[1:].strip()
    m = CARTEL_ETIQUETA_RE.match(s)
    if m:
        return "cartel", s[m.end():].strip()
    return "dicho", ETIQUETA_RE.sub("", s, count=1).strip()


def lineas(guion):
    for linea in guion.lstrip(BOM).splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        tipo, texto = clasifica(linea)
        yield linea.strip(), tipo, texto


def hablado(linea):
    """Lo que se dice en voz alta: sin indicaciones de plano."""
    return re.sub(r"\s+", " ", INDICACION_RE.sub(" ", linea)).strip()


def palabras_de_entero(n):
    """Palabras que hacen falta para decir un número entero en castellano."""
    if n == 0:
        return 1
    total = 0
    if n >= 1_000_000:
        m = n // 1_000_000
        total += 2 if m == 1 else palabras_de_entero(m) + 1   # «un millón», «tres millones»
        n %= 1_000_000
    if n >= 1000:
        m = n // 1000
        total += 1 if m == 1 else palabras_de_entero(m) + 1   # «mil», «dieciocho mil»
        n %= 1000
    if n >= 100:
        total += 1                                            # «cien», «trescientos»
        n %= 100
    if n:
        total += 1 if (n <= 30 or n % 10 == 0) else 3         # «veintidós», «cuarenta y cinco»
    return total


def palabras_de_decimales(decimales):
    """«5» es «cinco»; «05», «cero cinco»: cada cero delante es una palabra más."""
    ceros = len(decimales) - len(decimales.lstrip("0"))
    resto = decimales.lstrip("0")[:3]
    return ceros + (palabras_de_entero(int(resto)) if resto else 0)


def palabras_de_cifra(cifra):
    """«18.000» son 2 palabras, «18,5» son 3, «9:30» son 3 («nueve y treinta»)."""
    if ":" in cifra:
        partes = [re.split(r"[.,]", x)[0] or "0" for x in cifra.split(":")]
        hora, minutos = int(partes[0]), int(partes[1])
        return palabras_de_entero(hora) + (1 + palabras_de_entero(minutos) if minutos else 0)
    entera, _, decimales = cifra.partition(",")
    trozos = entera.split(".")
    if len(trozos) > 1 and all(len(t) == 3 for t in trozos[1:]):
        entera = "".join(trozos)                  # punto de miles
    elif len(trozos) > 1:
        entera, decimales = trozos[0], trozos[1]  # punto decimal
    n = palabras_de_entero(int(entera or "0"))
    if decimales:
        n += 1 + palabras_de_decimales(decimales)         # «coma» y lo que sigue
    return n


def palabras_dichas(texto):
    texto = re.sub(r"(?<=\d)[ºª]", "", texto)            # «1º» se dice «primero»
    n = len(PALABRA_RE.findall(texto))
    n += sum(palabras_de_cifra(c) for c in NUMERO_RE.findall(texto))
    n += 2 * texto.count("%") + texto.count("€") + texto.count("$")   # «por ciento», «euros»
    return n


def palabras_de_cartel(cartel):
    # En pantalla una cifra se lee de un vistazo: cuenta como una palabra.
    return len(PALABRA_RE.findall(cartel)) + len(NUMERO_RE.findall(cartel))


def segundos_de_lectura(cartel):
    return round(max(CARTEL_MIN, palabras_de_cartel(cartel) * CARTEL_POR_PALABRA), 1)


def tiene_algo_que_se_ve(texto):
    if CIFRA_RE.search(texto) and NUMERO_RE.search(texto):
        return True
    if nombres_propios(texto):
        return True
    vistas = ESCENA | NUMEROS_HABLADOS | PALABRAS_DE_DINERO
    return any(normaliza(p) in vistas for p in PALABRA_RE.findall(texto))


def planos(guion):
    """Las líneas que se dicen. Una línea que solo indica el plano no es un plano,
    pero marca que en el plano de antes y en el de después se ve algo."""
    salida, imagen_pendiente = [], False
    for original, tipo, texto in lineas(guion):
        if tipo == "cartel":
            continue
        dicho = hablado(texto)
        texto = CARTEL_EN_LINEA_RE.sub(" ", texto)     # un [EN PANTALLA: ...] es un cartel, no una imagen
        if not dicho:
            if IMAGEN_RE.search(texto):
                if salida:
                    salida[-1]["imagen"] = True
                imagen_pendiente = True
            continue
        salida.append({"linea": original, "dicho": dicho,
                       "imagen": imagen_pendiente or bool(IMAGEN_RE.search(texto))})
        imagen_pendiente = False
    return salida


def carteles(guion):
    salida = []
    for _, tipo, texto in lineas(guion):
        if tipo == "cartel":
            salida.append(texto)
        else:
            salida += [m.strip() for m in CARTEL_EN_LINEA_RE.findall(texto)]
    return [c for c in salida if c]


def tramos_planos(lista):
    """Cada racha de TRAMO_PLANO o más planos seguidos sin nada que se vea, entera."""
    tramos, inicio = [], None
    for i, p in enumerate(lista + [{"se_ve": True}], 1):
        if not p["se_ve"]:
            inicio = inicio or i
        elif inicio:
            if i - inicio >= TRAMO_PLANO:
                tramos.append((inicio, i - 1))
            inicio = None
    return tramos


def cronometra(guion, ppm=PPM, objetivo=None):
    if not ppm or ppm <= 0:
        raise ValueError("el ritmo tiene que ser mayor que cero palabras por minuto")
    lista = planos(guion)
    lista_carteles = carteles(guion)
    modo = "voz" if lista else ("carteles" if lista_carteles else "vacío")
    avisos = []
    t = 0.0

    if modo == "carteles":
        # Reel sin voz: cada cartel dura lo que se tarda en leerlo.
        for c in lista_carteles:
            p = {"linea": "> " + c, "dicho": "", "imagen": True, "se_ve": True,
                 "palabras": palabras_de_cartel(c), "segundos": segundos_de_lectura(c),
                 "inicio": round(t, 1)}
            t += p["segundos"]
            p["fin"] = round(t, 1)
            lista.append(p)
    else:
        for p in lista:
            p["palabras"] = palabras_dichas(p["dicho"])
            p["segundos"] = round(p["palabras"] * 60 / ppm, 1)
            p["inicio"] = round(t, 1)
            t += p["segundos"]
            p["fin"] = round(t, 1)
            p["se_ve"] = p["imagen"] or tiene_algo_que_se_ve(p["dicho"])
        if lista and lista[0]["fin"] > GANCHO_MAX:
            avisos.append(f"GANCHO LARGO: el primer plano dura {lista[0]['segundos']} s. "
                          f"El gancho tiene que entrar en unos tres o cuatro segundos: lo fuerte delante, y corta.")
        for i, p in enumerate(lista, 1):
            if p["segundos"] > PLANO_MAX:
                avisos.append(f"PLANO LARGO: el plano {i} dura {p['segundos']} s. Pártelo en dos o cambia de imagen.")
        for desde, hasta in tramos_planos(lista):
            avisos.append(f"TRAMO PLANO (revísalo): del plano {desde} al {hasta} no encuentro "
                          f"ninguna cifra, nombre, escena ni indicación de plano. Si en pantalla se ve tu "
                          f"trabajo, puede valer; si no, mete algo concreto.")

    total = round(t, 1)
    if objetivo and modo != "vacío" and abs(total - objetivo) > objetivo * 0.2:
        avisos.append(f"DURACIÓN: sale en {total} s y querías {objetivo} s.")
    for c in lista_carteles:
        n = palabras_de_cartel(c)
        if n > CARTEL_MAX:
            avisos.append(f"CARTEL LARGO: «{c}» tiene {n} palabras. En pantalla, {CARTEL_MAX} como mucho.")
    return {"modo": modo, "ppm": ppm, "total": total, "objetivo": objetivo, "planos": lista,
            "carteles": lista_carteles, "avisos": avisos}


def minuto(seg):
    return f"{int(seg // 60)}:{seg % 60:04.1f}"


def pinta(r, out=sys.stdout):
    if r["modo"] == "carteles":
        n = len(r["planos"])
        print(f"\nTIEMPOS DEL REEL · {n} {'cartel' if n == 1 else 'carteles'}, sin voz "
              f"(tiempo de lectura estimado)", file=out)
    else:
        print(f"\nTIEMPOS DEL REEL · {len(r['planos'])} planos a {r['ppm']} palabras por minuto", file=out)
    print("=" * 70, file=out)
    for i, p in enumerate(r["planos"], 1):
        texto = p["linea"] if len(p["linea"]) <= 46 else p["linea"][:43] + "..."
        print(f"  {i:>2}  {minuto(p['inicio'])}-{minuto(p['fin'])}  {p['segundos']:>4} s  {texto}", file=out)
    print("-" * 70, file=out)
    linea = f"  TOTAL  {r['total']} s"
    if r["objetivo"]:
        linea += f"  (querías {r['objetivo']} s)"
    if r["modo"] == "voz" and r.get("carteles"):
        n = len(r["carteles"])
        linea += f"  ·  {n} {'cartel' if n == 1 else 'carteles'} en pantalla"
    print(linea, file=out)
    for a in r["avisos"]:
        print(f"\n  {a}", file=out)
    if r["modo"] == "carteles":
        print("\n  Deja cada cartel en pantalla por lo menos ese tiempo. Si al verlo no te da tiempo a leerlo, alárgalo.",
              file=out)
    elif not r["avisos"]:
        print("\n  Sin avisos. Ahora grábalo y cronométralo de verdad.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Cronometra el guion de un reel, plano a plano.")
    ap.add_argument("entrada", nargs="?", default="-", help="archivo con el guion (una línea por plano), o -")
    ap.add_argument("--ppm", type=int, default=PPM, help="tus palabras por minuto en voz alta")
    ap.add_argument("--objetivo", type=float, help="segundos que quieres que dure")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.ppm <= 0:
        ap.error("--ppm tiene que ser mayor que cero")
    if args.objetivo is not None and args.objetivo <= 0:
        ap.error("--objetivo tiene que ser mayor que cero")

    try:
        guion = sys.stdin.read() if args.entrada == "-" else open(args.entrada, encoding="utf-8-sig").read()
    except (OSError, UnicodeDecodeError):
        ap.error(f"no puedo leer «{args.entrada}»: no existe o no es un archivo de texto")
    r = cronometra(guion, args.ppm, args.objetivo)
    if not r["planos"]:
        print("no hay nada que cronometrar", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    pinta(r)


if __name__ == "__main__":
    main()

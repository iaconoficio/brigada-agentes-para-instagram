#!/usr/bin/env python3
"""
semana.py · La Brigada (IA con Oficio)

Convierte el plan de la semana en dos cosas que se pueden usar:

  1. Una tabla para leer de un vistazo, con el día, la hora, el formato y el tema.
  2. Con --ics, un archivo de calendario (.ics) para el móvil o el ordenador:
     un recordatorio para preparar cada pieza, otro para publicarla y, con
     --repaso, otro para el repaso de 48 horas después.

Y avisa de lo que no cuadra:

  MISMO DÍA   dos publicaciones el mismo día (las historias no cuentan)
  VENTA       más piezas que venden de las que pide la ficha
  SIN HORA    una pieza sin hora: el aviso saltará a las 9 de la mañana
  ANTES       preparar una pieza el mismo día que se publica
  PASADO      una fecha que ya ha pasado
  SEGUIDAS    dos piezas seguidas del mismo formato (es una nota, no un fallo)

El plan va en un archivo JSON. Este es uno de ejemplo, inventado:

  {
    "semana": "2026-11-02",
    "venta_cada": 3,
    "version": 1,
    "piezas": [
      {"dia": "martes", "hora": "19:00", "formato": "reel", "pata": "enseñar",
       "tema": "No siempre es la rueda", "preparar": "lunes", "vende": false},
      {"dia": "jueves", "hora": "19:00", "formato": "carrusel", "pata": "enseñar",
       "tema": "Cinco cosas que miro antes de una ITV", "preparar": "miércoles"},
      {"dia": "sábado", "hora": "11:00", "formato": "post", "pata": "ofrecer",
       "tema": "Por qué no cambio una pieza sin enseñártela", "vende": true}
    ]
  }

  semana      obligatorio: cualquier día de la semana; se toma su lunes
  venta_cada  de «Cada cuánto pedir algo que venda» en la ficha: 1 (en todos
              los posts), 3 (uno de cada tres) o 0 (solo cuando haya algo que
              ofrecer; no se avisa). También vale el texto tal cual.
  version     1 la primera vez, 2 si se corrige, y así
  hora        opcional; sin hora, el aviso salta a las 9 de la mañana
  preparar    opcional; el día para grabar o preparar. Si es un día de la
              semana que va después, se entiende la semana anterior
              (preparar el domingo una pieza del lunes).
  pata        opcional: enseñar, enseñar el trabajo, opinar, contarte u ofrecer
  vende       opcional: true o false (también «sí» o «no»)

Las horas del calendario van sin zona horaria (lo que el estándar llama hora
flotante): se leen en la hora local de quien abre el calendario.

Funciona sin internet y no envía nada a ningún sitio.

Uso
  python3 semana.py plan.json
  python3 semana.py plan.json --ics semana.ics
  python3 semana.py plan.json --ics semana.ics --repaso
  python3 semana.py plan.json --json
"""

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FORMATOS = {"reel", "carrusel", "post", "foto", "historia", "stories", "directo"}
HISTORIAS = {"historia", "stories"}
PATAS = {"ensenar": "enseñar", "ensenar el trabajo": "enseñar el trabajo", "opinar": "opinar",
         "contarte": "contarte", "ofrecer": "ofrecer"}
VENTA_TEXTOS = {"en todos los posts": 1, "uno de cada dos": 2, "uno de cada tres": 3,
                "uno de cada cuatro": 4, "solo cuando haya algo que ofrecer": 0}
SI, NO = {"si", "true", "1"}, {"no", "false", "0", ""}
AVISO_MINUTOS = 30          # antes de publicar, a media hora
AVISO_DIA_ENTERO = "PT9H"   # en los avisos de todo el día, a las 9 de la mañana
DURACION_MINUTOS = 30       # el hueco de publicar en el calendario
HORA_RE = re.compile(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$")


class PlanMal(ValueError):
    """El plan tiene algo que no se puede convertir en fechas."""


def normaliza(texto):
    base = unicodedata.normalize("NFD", str(texto).strip().lower())
    return " ".join("".join(c for c in base if unicodedata.category(c) != "Mn").split())


def lunes_de(fecha):
    try:
        d = dt.date.fromisoformat(str(fecha))
    except ValueError:
        raise PlanMal(f"«{fecha}» no es una fecha: escríbela como 2026-11-02")
    return d - dt.timedelta(days=d.weekday())


def indice_dia(nombre):
    clave = normaliza(nombre)
    if clave not in DIAS:
        raise PlanMal(f"«{nombre}» no es un día de la semana")
    return DIAS.index(clave)


def hora_de(texto):
    if texto in (None, ""):
        return None
    m = HORA_RE.match(str(texto).strip())
    if not m:
        raise PlanMal(f"«{texto}» no es una hora: escríbela como 19:00")
    return dt.time(int(m.group(1)), int(m.group(2)))


def venta_de(valor):
    if isinstance(valor, bool) or valor is None:
        if valor is None:
            return 0
        raise PlanMal("«venta_cada» tiene que ser un número (1, 3...) o el texto de la ficha")
    if isinstance(valor, int) and valor >= 0:
        return valor
    clave = normaliza(valor)
    if clave in VENTA_TEXTOS:
        return VENTA_TEXTOS[clave]
    raise PlanMal(f"«venta_cada»: «{valor}» no lo entiendo. Usa 1, 3, 0 o el texto de la ficha")


def vende_de(valor, n):
    if isinstance(valor, bool):
        return valor
    clave = normaliza("" if valor is None else valor)
    if clave in SI:
        return True
    if clave in NO:
        return False
    raise PlanMal(f"pieza {n}: «vende» tiene que ser sí o no")


def lee_plan(plan, hoy=None):
    """Comprueba el plan y le pone fechas. Devuelve (piezas, avisos)."""
    if not isinstance(plan, dict) or not plan.get("piezas"):
        raise PlanMal("el plan no tiene piezas")
    if not plan.get("semana"):
        raise PlanMal("falta «semana»: pon un día de la semana que se planifica, como 2026-11-02")
    lunes = lunes_de(plan["semana"])
    venta_cada = venta_de(plan.get("venta_cada"))
    version = plan.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PlanMal("«version» tiene que ser 1, 2, 3...")

    piezas = []
    for i, p in enumerate(plan["piezas"], 1):
        if not isinstance(p, dict) or not p.get("dia") or not str(p.get("tema", "")).strip():
            raise PlanMal(f"a la pieza {i} le falta el día o el tema")
        formato = normaliza(p.get("formato", "post"))
        if formato not in FORMATOS:
            raise PlanMal(f"pieza {i}: «{p.get('formato')}» no es un formato que conozca "
                          f"({', '.join(sorted(FORMATOS))})")
        pata = normaliza(p.get("pata", ""))
        if pata and pata not in PATAS:
            raise PlanMal(f"pieza {i}: «{p.get('pata')}» no es una pata ({', '.join(PATAS.values())})")
        fecha = lunes + dt.timedelta(days=indice_dia(p["dia"]))
        preparar = None
        if p.get("preparar"):
            # Siempre antes de publicar: el domingo de una pieza del lunes es el domingo anterior.
            preparar = fecha - dt.timedelta(days=(fecha.weekday() - indice_dia(p["preparar"])) % 7)
        piezas.append({"n": i, "fecha": fecha, "hora": hora_de(p.get("hora")), "formato": formato,
                       "pata": PATAS.get(pata, ""), "tema": " ".join(str(p["tema"]).split()),
                       "vende": vende_de(p.get("vende"), i), "preparar": preparar,
                       "nota": " ".join(str(p.get("nota", "")).split())})
    piezas.sort(key=lambda p: (p["fecha"], p["hora"] or dt.time(23, 59), p["n"]))
    orden_en_el_dia = {}
    for p in piezas:
        p["orden"] = orden_en_el_dia[p["fecha"]] = orden_en_el_dia.get(p["fecha"], 0) + 1

    avisos = []
    publicaciones = [p for p in piezas if p["formato"] not in HISTORIAS]
    por_dia = {}
    for p in publicaciones:
        por_dia.setdefault(p["fecha"], []).append(p)
    for fecha, del_dia in por_dia.items():
        if len(del_dia) > 1:
            avisos.append(("MISMO DÍA", f"{len(del_dia)} publicaciones el {NOMBRE_DIA[fecha.weekday()]}. "
                                        f"Mejor repartirlas."))
    venden = sum(p["vende"] for p in piezas)
    if venta_cada > 1 and venden:
        permitidas = len(piezas) // venta_cada
        if permitidas == 0:
            avisos.append(("VENTA", f"con {len(piezas)} pieza(s) y una de cada {venta_cada} en su ficha, "
                                    f"esta semana no tocaría vender. Si vende, que la siguiente no."))
        elif venden > permitidas:
            avisos.append(("VENTA", f"{venden} piezas piden algo que vende y su ficha pide una de cada "
                                    f"{venta_cada}: con {len(piezas)} piezas, {permitidas} como mucho."))
    hoy = hoy or dt.date.today()
    for p in piezas:
        if p["hora"] is None:
            avisos.append(("SIN HORA", f"pieza {p['n']} ({p['formato']}): sin hora, el aviso saltará a las 9 "
                                       f"de la mañana. Pregúntale a qué hora suele publicar."))
        if p["preparar"] == p["fecha"]:
            avisos.append(("ANTES", f"pieza {p['n']}: se prepara el mismo día que se publica. Mejor un día antes."))
        if p["fecha"] < hoy:
            avisos.append(("PASADO", f"pieza {p['n']}: el {p['fecha']:%d/%m/%Y} ya ha pasado. ¿Es la semana buena?"))
    for a, b in zip(publicaciones, publicaciones[1:]):
        if a["formato"] == b["formato"]:
            avisos.append(("SEGUIDAS", f"piezas {a['n']} y {b['n']} son las dos {a['formato']}. "
                                       f"Es una nota: si le funciona, adelante."))
    return piezas, avisos


def tabla(piezas, avisos):
    lunes = piezas[0]["fecha"] - dt.timedelta(days=piezas[0]["fecha"].weekday())
    lineas = [f"SEMANA DEL {lunes:%d/%m/%Y}", ""]
    lineas.append("| Día | Hora | Formato | Tema | Pata | Vende | Preparar |")
    lineas.append("| --- | --- | --- | --- | --- | --- | --- |")
    for p in piezas:
        dia = f"{NOMBRE_DIA[p['fecha'].weekday()]} {p['fecha']:%d/%m}"
        hora = p["hora"].strftime("%H:%M") if p["hora"] else "sin hora"
        preparar = (f"{NOMBRE_DIA[p['preparar'].weekday()]} {p['preparar']:%d/%m}" if p["preparar"] else "")
        tema = p["tema"].replace("|", "/")
        lineas.append(f"| {dia} | {hora} | {p['formato']} | {tema} | {p['pata']} | "
                      f"{'sí' if p['vende'] else 'no'} | {preparar} |")
    if avisos:
        lineas.append("")
        lineas += [f"- {tipo}: {texto}" for tipo, texto in avisos]
    return "\n".join(lineas)


# ---------- calendario (iCalendar, RFC 5545) ----------

def escapa(texto):
    texto = texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return texto.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def dobla(linea):
    """Las líneas de un .ics no pasan de 75 bytes: se parten y la siguiente empieza con un espacio."""
    trozos, actual = [], b""
    for c in linea:
        b = c.encode("utf-8")
        limite = 75 if not trozos else 74
        if len(actual) + len(b) > limite:
            trozos.append(actual)
            actual = b""
        actual += b
    trozos.append(actual)
    return "\r\n ".join(t.decode("utf-8") for t in trozos)


def evento(uid, resumen, descripcion, fecha, hora=None, sello=None, version=1):
    lineas = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{sello}", f"SEQUENCE:{version - 1}"]
    if hora:
        inicio = dt.datetime.combine(fecha, hora)
        lineas += [f"DTSTART:{inicio:%Y%m%dT%H%M%S}",
                   f"DTEND:{inicio + dt.timedelta(minutes=DURACION_MINUTOS):%Y%m%dT%H%M%S}"]
        disparo = f"-PT{AVISO_MINUTOS}M"
    else:
        lineas += [f"DTSTART;VALUE=DATE:{fecha:%Y%m%d}",
                   f"DTEND;VALUE=DATE:{fecha + dt.timedelta(days=1):%Y%m%d}"]
        disparo = AVISO_DIA_ENTERO
    lineas += [f"SUMMARY:{escapa(resumen)}", f"DESCRIPTION:{escapa(descripcion)}",
               "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escapa(resumen)}",
               f"TRIGGER:{disparo}", "END:VALARM", "END:VEVENT"]
    return lineas


def calendario(piezas, repaso=False, ahora=None, version=1):
    sello = (ahora or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IA con Oficio//La Brigada//ES",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:La Brigada · semana"]
    for p in piezas:
        # El identificador no depende del tema: al corregir la v1, el evento es el mismo.
        base = f"{p['fecha']:%Y%m%d}-{p['orden']}-{p['formato']}"
        uid = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
        detalle = f"{p['formato'].capitalize()}: {p['tema']}" + (f"\n{p['nota']}" if p["nota"] else "")
        if p["preparar"]:
            lineas += evento(f"{uid}-prep@la-brigada", f"Preparar {p['formato']}: {p['tema']}",
                             detalle + "\nGraba o prepara la pieza. Revísala antes de publicar.",
                             p["preparar"], sello=sello, version=version)
        lineas += evento(f"{uid}-pub@la-brigada", f"Publicar {p['formato']}: {p['tema']}",
                         detalle + "\nNada se publica solo: lo publicas tú.",
                         p["fecha"], p["hora"], sello=sello, version=version)
        if repaso:
            lineas += evento(f"{uid}-rep@la-brigada", f"Repaso 48 h: {p['tema']}",
                             "Mira en las estadísticas de la publicación cuánta gente la vio, cuántos la "
                             "guardaron, la compartieron y comentaron, y si llegó algún mensaje. Compárala "
                             "solo con tus publicaciones anteriores.",
                             p["fecha"] + dt.timedelta(days=2), sello=sello, version=version)
    lineas.append("END:VCALENDAR")
    return "\r\n".join(dobla(l) for l in lineas) + "\r\n"


def sal(mensaje):
    print(mensaje, file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="Convierte el plan de la semana en una tabla y un calendario.")
    ap.add_argument("plan", help="archivo JSON con el plan, o - para leerlo de la entrada")
    ap.add_argument("--ics", help="guarda aquí el calendario (.ics)")
    ap.add_argument("--repaso", action="store_true", help="añade un recordatorio de repaso 48 horas después")
    ap.add_argument("--json", action="store_true", help="devuelve las piezas con sus fechas y los avisos en JSON")
    args = ap.parse_args()

    try:
        bruto = sys.stdin.read() if args.plan == "-" else open(args.plan, encoding="utf-8-sig").read()
        plan = json.loads(bruto.lstrip(chr(0xFEFF)))
        piezas, avisos = lee_plan(plan)
    except OSError as e:
        sal(f"No puedo abrir el plan: {e.strerror or e}")
    except UnicodeDecodeError:
        sal("El plan no está guardado en UTF-8. Guárdalo en UTF-8 y vuelve a probar.")
    except json.JSONDecodeError as e:
        sal(f"El plan no es un JSON válido: {e}")
    except PlanMal as e:
        sal(f"El plan tiene un problema: {e}")

    if args.json:
        salida = [{**p, "fecha": p["fecha"].isoformat(),
                   "hora": p["hora"].strftime("%H:%M") if p["hora"] else None,
                   "preparar": p["preparar"].isoformat() if p["preparar"] else None} for p in piezas]
        print(json.dumps({"piezas": salida, "avisos": [{"tipo": t, "texto": x} for t, x in avisos]},
                         ensure_ascii=False, indent=2))
    else:
        print(tabla(piezas, avisos))
    if args.ics:
        try:
            with open(args.ics, "w", encoding="utf-8", newline="") as fh:
                fh.write(calendario(piezas, args.repaso, version=plan.get("version", 1)))
        except OSError as e:
            sal(f"No puedo guardar el calendario en {args.ics}: {e.strerror or e}")
        print(f"\nCalendario guardado en {args.ics}.", file=sys.stderr)


if __name__ == "__main__":
    main()

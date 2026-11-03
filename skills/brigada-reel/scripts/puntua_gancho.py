#!/usr/bin/env python3
"""
puntua_gancho.py · La Brigada (IA con Oficio)

Puntúa la primera frase de un reel, el gancho, en cinco cosas que suelen tener
los ganchos que retienen:

  DURACIÓN    se dice en unos tres segundos
  CONCRECIÓN  lleva algo comprobable: una cifra, un nombre, un precio
  TENSIÓN     hay algo en juego: un error, una pérdida, un "nadie"
  ARRANQUE    lo interesante va delante, no en la palabra nueve
  A QUIÉN     le habla a alguien, no al aire

Qué es: cinco comprobaciones locales sobre el texto, hechas para el español
(acentos, ñ, ¿ y ¡, cifras con punto de miles, euros, verbos sin pronombre).
Funciona sin internet y no envía nada a ningún sitio.

Qué NO es: un predictor de visualizaciones. Sirve para cazar lo que casi
siempre falla: saludos, preámbulos, frases gastadas, ganchos sin nada concreto
y ganchos que tardan demasiado en decirse. Entre dos ganchos que pasan el
corte no elige bien, porque ahí deciden otras cosas que un texto no ve. Los
umbrales son iniciales y están pendientes de calibrar con ganchos reales en
español.

Dos formatos, porque no se miden igual:
  reel   el gancho que dices en los tres primeros segundos (por defecto).
         Necesita algo concreto y hablarle a alguien.
  post   la primera línea de un post o la portada de un carrusel, que se lee.
         Aguanta una frase-golpe corta, así que pesan más la tensión, el
         arranque y que sea corta. Para salir FUERTE necesita además algo
         concreto o hablarle de tú a quien lo lee.

Cuenta como concreto una cifra, un nombre o una escena que se ve: el ruido
al frenar, la grieta del techo, el lunes a primera hora. Una palabra de escena
suelta no basta: hacen falta dos, o una y hablarle a quien lo ve. La emoción
(miedo, rabia, vergüenza) también pone algo en juego.

Tres cosas restan siempre, aunque el resto esté bien: las frases gastadas
(«nadie te cuenta», «esto lo cambia todo»), la estructura «no es solo X, es Y»
y diagnosticar a quien lo ve («tienes una hernia», «lo tuyo es artrosis»).
Lo que va todo en mayúsculas (un cartel) no se toma por nombres propios.

Es una adaptación al español de hookscore.py, de Jake Schincariol (licencia
MIT): github.com/Jakeschincariol/instagram-agent-skill

Uso
  python3 puntua_gancho.py ganchos.txt          # uno por línea, ordenados
  python3 puntua_gancho.py --gancho "Perdí 18.000 € por no firmar un papel."
  python3 puntua_gancho.py --formato post --gancho "Lunes otra vez."
  python3 puntua_gancho.py ganchos.txt --json
"""

import argparse
import json
import re
import statistics
import sys
import unicodedata

# Palabras: letras con tildes y ñ. Cifras: con punto de miles, coma decimal,
# euros, dólares o porcentaje pegados.
TOKEN_RE = re.compile(
    r"[€$]\s?\d[\d.,]*|\d[\d.,]*\s?(?:%|€|\$)?|[^\W\d_]+(?:['’-][^\W\d_]+)*",
    re.UNICODE,
)
CIFRA_RE = re.compile(
    r"[€$]\s?\d[\d.,]*"
    r"|\d[\d.,]*\s?(?:%|€|\$|k\b|x\b|euros?\b|pavos\b|d[oó]lares\b|pesos\b"
    r"|h\b|horas?\b|min\b|minutos?\b|segundos?\b|d[ií]as?\b|semanas?\b"
    r"|mes(?:es)?\b|años?\b|veces\b|clientes?\b|mesas?\b|personas?\b)?",
    re.IGNORECASE,
)
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27bf]")


def normaliza(palabra):
    """Minúsculas y sin tildes, para comparar con las listas."""
    base = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn").strip("'’")


def tokens(texto):
    # "18.000 €" se dice como una sola cosa, así que cuenta como una.
    return TOKEN_RE.findall(texto)


def palabras(texto):
    return [t for t in tokens(texto) if not t[0].isdigit() and t[0] not in "€$"]


# Las cifras dichas en voz alta cuentan igual que las escritas. "Uno", "una" y
# "primero" no están: casi siempre son relleno, no cantidad.
NUMEROS_HABLADOS = {
    "cero", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintiuna",
    "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis",
    "veintisiete", "veintiocho", "veintinueve", "treinta", "cuarenta",
    "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien", "ciento",
    "cientos", "doscientos", "trescientos", "cuatrocientos", "quinientos",
    "seiscientos", "setecientos", "ochocientos", "novecientos", "mil", "millon",
    "millones", "docena", "docenas", "mitad", "doble", "triple",
}
PALABRAS_DE_DINERO = {
    "euros", "euro", "pavos", "dolares", "pesos", "centimos", "sueldo",
    "alquiler", "factura", "facturas", "facturacion", "beneficio",
    "beneficios", "precio", "precios", "presupuesto", "ingresos", "gastos", "caja",
}

# Palabras que ponen algo en juego. Sin ninguna, el gancho es una afirmación;
# con una, es un motivo para seguir mirando. Se comparan sin tildes.
TENSION = {
    "nunca", "nadie", "nada", "jamas", "ninguno", "ninguna", "no", "sin", "ni",
    "error", "errores", "equivoco", "equivocas", "equivocado", "equivocada",
    "mal", "peor", "peores", "perdi", "perdiste", "perdio", "perdimos",
    "perder", "pierdes", "pierde", "pierdo", "perdiendo", "perdida", "perdidas",
    "cuesta", "cuestan", "costo", "costaron", "caro", "cara", "gratis", "pague",
    "pagas", "pagar", "pagando", "cobrar", "cobras", "cobre", "estafa",
    "estafas", "timo", "mentira", "mentiras", "mienten", "verdad", "secreto",
    "secretos", "oculto", "prohibido", "prohibida", "ilegal", "multa", "multas",
    "basta", "odio", "odias", "despedido", "despedida", "despidieron", "cerre",
    "cerrar", "cierre", "quiebra", "ruina", "arruino", "problema", "problemas",
    "riesgo", "peligro", "cuidado", "ojo", "aviso", "antes", "hasta", "solo",
    "todavia", "aun", "ya", "pero", "excepto", "salvo", "aunque", "deberias",
    "deberia", "tiras", "tirando", "regalas", "regalando", "sobra", "falta",
    "fallo", "fracaso", "fracase", "tarde", "ultimo", "ultima", "ahorre",
    "ahorras", "ahorrar", "gane", "ganas", "ganar", "deje", "deja", "dejar",
    "vs", "frente", "tampoco",
}

# La emoción también pone algo en juego: no hace falta perder dinero para que
# una frase pese. Solo palabras que casi siempre son emoción («pena» o «sola»
# no están: «vale la pena» y «una sola vez» no lo son). Se comparan sin tildes.
EMOCION = {
    "dolor", "duele", "duelen", "miedo", "culpa", "culpable", "verguenza",
    "cansado", "cansada", "agotado", "agotada", "harto", "harta",
    "rabia", "enfado", "enfadado", "enfadada", "soledad", "llorar",
    "lloras", "llore", "angustia", "triste", "tristeza",
    "asco", "roto", "rota", "rechazo", "nervios", "agobio", "agobiado", "agobiada",
}

# Lo que se ve: personas de tu vida, sitios, cosas, ruidos y momentos del día.
# No están las palabras que nombran un oficio entero («cliente», «taller»,
# «obra»): salen en casi cualquier frase del sector y no pintan nada. Una sola
# palabra de esta lista no basta para que el gancho sea concreto (mira
# mira_concrecion). Se comparan sin tildes.
ESCENA = {
    "papa", "mama", "padre", "madre", "abuela", "abuelo", "hijo", "hija",
    "hijos", "hijas", "pareja", "novio", "novia", "marido", "jefe", "jefa",
    "amiga", "amigo", "vecino", "vecina", "suegra",
    "manos", "espalda", "rodilla",
    "cocina", "mesa", "cama", "sofa", "movil", "calle", "playa", "bar",
    "plato", "cafe", "puerta", "ventana", "espejo", "ducha", "cena", "comida",
    "desayuno", "llaves", "techo", "pared", "suelo", "escalera", "persiana",
    "grifo", "enchufe", "caldera", "radiador", "tuberia", "gotera", "grieta",
    "humedad", "mancha", "rueda", "ruedas", "frenos", "motor", "bateria",
    "manillar", "aceite", "grasa", "tinte", "tijeras", "horno", "mostrador",
    "ruido", "olor", "semaforo", "rotonda", "aparcamiento",
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    "noche", "madrugada", "verano", "invierno", "navidad", "vacaciones",
}

# Aperturas que gastan el primer segundo sin decir nada.
APERTURAS_FLOJAS = [
    "hola", "buenas", "bueno", "pues", "vale", "ok", "oye", "mira", "a ver",
    "hoy", "bienvenidos", "bienvenidas", "bienvenido", "bienvenida", "que tal",
    "chicos", "chicas", "familia", "gente", "amigos", "basicamente",
    "sinceramente", "la verdad es que", "es que", "hay", "esto es", "este es",
    "en este", "en el video", "os voy", "te voy", "quiero contaros", "queria",
    "como sabeis", "como sabes", "un saludo", "hace tiempo", "sabias que",
    "alguna vez", "te has preguntado",
]

# Imperativos que se ganan el primer puesto.
IMPERATIVOS = {
    "deja", "prueba", "copia", "roba", "guarda", "usa", "borra", "apunta",
    "escribe", "cambia", "evita", "empieza", "olvida", "haz", "pon", "manda",
    "revisa", "sube", "no", "nunca", "deje", "pruebe", "haced", "dejad", "probad",
}

# Segunda persona: pronombres y los verbos más comunes, porque en español el
# pronombre casi nunca se dice ("¿Sabes cuánto pierdes?").
SEGUNDA_PERSONA = {
    "tu", "tus", "te", "ti", "contigo", "usted", "ustedes", "vosotros",
    "vosotras", "os", "vuestro", "vuestra", "vuestros", "vuestras",
    "sabes", "sabias", "tienes", "haces", "hiciste", "quieres", "puedes",
    "pierdes", "perdiste", "ganas", "pagas", "cobras", "usas", "eres", "vas",
    "crees", "piensas", "necesitas", "buscas", "dejas", "sigues", "publicas",
    "vendes", "trabajas", "imaginas", "llevas", "has", "cometes", "cometiste",
    "abres", "cierras", "das", "dices", "ves", "sientes", "miras",
    "oyes", "frenas", "arrancas", "llegas", "entras", "sales", "pones", "vienes",
    "compras", "firmas", "pides", "tocas", "enciendes", "cambias", "ahorras",
    "gastas", "tuyo", "tuya", "tuyos", "tuyas",
}
PRIMERA_PERSONA = {
    "yo", "me", "mi", "mis", "conmigo", "nosotros", "nosotras", "nos",
    "nuestro", "nuestra", "nuestros", "nuestras", "perdi", "gane", "cerre",
    "abri", "aprendi", "deje", "tengo", "llevo", "hice", "hago", "cobro",
    "pague", "use", "uso", "monte", "soy", "estoy", "fui", "vi", "veo", "descubri", "probe",
    "estuve", "tardaba", "cobraba", "pensaba", "creia", "trabajaba",
}

ELIMINATORIAS = [
    (re.compile(r"(?i)^\W*(?:deja de (?:hacer )?scroll|para de (?:hacer )?scroll"
                r"|no (?:hagas|sigas haciendo) scroll|no pases de largo)"),
     "Empieza con «deja de hacer scroll». Pedir atención demuestra que aún no te la has ganado."),
    (re.compile(r"(?i)\b(?:en (?:este|el) (?:v[ií]deo|reel|post)(?: de hoy)?"
                r"|hoy (?:os|te) (?:voy a|traigo)"
                r"|(?:os|te) voy a (?:ense[ñn]ar|contar|explicar|mostrar))\b"),
     "Preámbulo. Bórralo y empieza por lo que importa."),
    (re.compile(r"(?i)^\W*(?:hola|buenas(?=\s*[!,.]|\s*$)|buenos d[ií]as|buenas (?:tardes|noches)|qu[ée] tal|bienvenid[oa]s?)\b"),
     "Saludo. Nadie entra en Instagram para que le saluden."),
    (HASHTAG_RE,
     "Hashtag en el gancho. Los hashtags van al final del texto, si van."),
    (EMOJI_RE,
     "Emoji en el gancho. A tamaño de gancho hay sitio para palabras o para un emoji, no para los dos."),
    (re.compile(r"(?i)\b(?:(?<!si )nadie (?:te|me|nos|os) (?:lo )?(?:cuenta|cont[oó]|dice|dijo|ha contado|ha dicho)"
                r"|lo que nadie (?:te )?(?:cuenta|dice)|el secreto que"
                r"|esto lo cambia todo|te va a cambiar la vida|va a cambiar tu vida|te va a volar la cabeza"
                r"|no te lo puedes perder|lo que (?:nadie|pocos) sabe[n]?)\b"),
     "Frase gastada. Si la usa todo el mundo, ya no frena a nadie: di lo que ibas a contar."),
    (re.compile(r"(?i)\bno es (?:solo|s[oó]lo|solamente|[uú]nicamente) [^.!?\n]{2,60}[,.;:]\s*(?:es|sino)\b(?!\s+que)"),
     "Estructura «no es solo X, es Y». Suena a texto de IA: di la Y directamente."),
    # «Si tienes una hernia, no cargues así» no diagnostica: pone una condición.
    (re.compile(r"(?i)(?<!si )(?<!¿)\b(?:tienes|eres|sufres|padeces|lo tuyo es)\s+(?:un\s+|una\s+|el\s+|la\s+)?"
                r"(?:hernia|artrosis|tendinitis|ci[aá]tica|lumbalgia|contractura|fibromialgia"
                r"|ansiedad|depresi[oó]n|tdah|trastorno)\b"),
     "Diagnostica a quien lo ve. A distancia no se diagnostica: cuenta lo que pasa, no lo que la persona tiene o es."),
]


def limita(n):
    return max(0.0, min(100.0, n))


def nombres_propios(texto):
    """Palabras en mayúscula que no empiezan frase: nombres, marcas, lugares.
    Si todo va en mayúsculas (un cartel), no se puede saber: no cuenta ninguna."""
    encontrados = set()
    letras = [c for c in texto if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        return encontrados
    for frase in re.split(r"[.!?¡¿\n]+", texto):
        ps = palabras(frase)
        for p in ps[1:]:
            if len(p) >= 3 and p[0].isupper():
                encontrados.add(p)
    return encontrados


def mira_duracion(texto, formato="reel"):
    """Un gancho tiene que llegar antes de que se mueva el pulgar."""
    n = len(tokens(texto))
    segundos = n / 2.75                 # unas 165 palabras por minuto, en voz alta
    caracteres = len(texto.strip())
    if formato == "post":
        # Se lee, no se dice: una frase-golpe de dos palabras vale.
        if n == 0:
            return 0.0, "no hay palabras"
        nota = 100.0 if n <= 12 else limita(100 - (n - 12) * 11)
        if caracteres > 90:             # más de tres líneas en el móvil
            nota -= 12
        return limita(nota), f"{n} palabras, {caracteres} caracteres (mejor 12 palabras o menos)"
    if 5 <= n <= 12:
        nota = 100.0
    elif n < 5:
        nota = limita(100 - (5 - n) * 20)
    else:
        nota = limita(100 - (n - 12) * 11)
    if caracteres > 65:                 # dos líneas de texto grande en pantalla
        nota -= 12
    return limita(nota), f"{n} palabras, {caracteres} caracteres, unos {segundos:.1f} s en voz alta (mejor entre 5 y 12 palabras)"


def de_escena(palabra):
    """La palabra de ESCENA que hay detrás, también en plural («enchufes»), o ""."""
    b = normaliza(palabra)
    for forma in (b, b[:-2] if b.endswith("es") else "", b[:-1] if b.endswith("s") else ""):
        if forma and forma in ESCENA:
            return forma
    return ""


def le_habla(texto):
    return any(normaliza(p) in SEGUNDA_PERSONA for p in palabras(texto))


def mira_concrecion(texto):
    """Una cosa concreta vale más que tres abstractas. Una escena también lo es,
    si se ve: dos detalles, o uno y alguien dentro («tu cocina»)."""
    cifras = [c.strip() for c in CIFRA_RE.findall(texto) if c.strip()]
    propios = nombres_propios(texto)
    habladas = [p for p in palabras(texto)
                if normaliza(p) in NUMEROS_HABLADOS or normaliza(p) in PALABRAS_DE_DINERO]
    escena = sorted({de_escena(p) for p in palabras(texto) if de_escena(p)})
    escena_cuenta = len(escena) >= 2 or (len(escena) == 1 and le_habla(texto))
    datos = len(cifras) + len(propios) + len(habladas)
    if datos == 0 and not escena_cuenta:
        nota = 15.0
    else:
        nota = limita(45 + datos * 30 + (len(escena) * 15 if escena_cuenta else 0))
    vistos = ", ".join(cifras[:2] + sorted(propios)[:2] + habladas[:2] + escena[:2])
    if escena and not escena_cuenta:
        detalle = (f"{datos} dato(s) y un detalle suelto ({escena[0]}): una palabra sola no pinta "
                   "una escena; añade otra o háblale a quien lo ve")
    else:
        detalle = f"{datos} dato(s) y {len(escena)} detalle(s) de escena" + (
            f": {vistos}" if vistos else ": ni cifra, ni nombre, ni escena, nada que se vea")
    return nota, detalle


def mira_tension(texto):
    """Algo que se puede perder, un error, una negación, una emoción."""
    marcas = sorted({normaliza(p) for p in palabras(texto)
                     if normaliza(p) in TENSION or normaliza(p) in EMOCION})
    if re.search(r"[€$]\s?\d|\d\s?(?:€|euros?\b)", texto):
        marcas.append("un precio")
    n = len(marcas)
    nota = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detalle = f"{n} marca(s) de tensión" + (f": {', '.join(marcas[:4])}" if marcas else
                                            ": en esta frase no hay nada en juego")
    return limita(nota), detalle


def mira_arranque(texto):
    """La palabra interesante no puede ir en la posición nueve."""
    ts = tokens(texto)
    if not ts:
        return 0.0, "vacío"
    bajas = [normaliza(t) for t in ts]
    inicio = " ".join(bajas[:3])
    castigo, floja = 0, None
    for f in APERTURAS_FLOJAS:
        if inicio == f or inicio.startswith(f + " "):
            castigo, floja = 30, f
            break
    propios = nombres_propios(texto)
    carga = None
    for i, (t, b) in enumerate(zip(ts, bajas)):
        if (b in TENSION or b in EMOCION or de_escena(b) or b in NUMEROS_HABLADOS
                or b in PALABRAS_DE_DINERO or CIFRA_RE.fullmatch(t.strip()) or t in propios):
            carga = i
            break
    if carga is None:
        base, donde = 30.0, "no hay ninguna palabra con carga"
    elif carga <= 3:
        base, donde = 100.0, f"la carga llega en la palabra {carga + 1}"
    elif carga <= 6:
        base, donde = 70.0, f"la carga llega en la palabra {carga + 1}, se puede adelantar"
    else:
        base, donde = 40.0, f"la carga llega en la palabra {carga + 1}, demasiado tarde"
    detalle = donde + (f"; arranque flojo «{floja}»" if floja else "")
    return limita(base - castigo), detalle


def mira_a_quien(texto):
    """Apuntado a una persona, o flotando en el aire."""
    bajas = [normaliza(p) for p in palabras(texto)]
    if le_habla(texto):
        return 100.0, "le habla a quien lo ve"
    if bajas and bajas[0] in IMPERATIVOS:
        return 90.0, f"empieza con una orden («{bajas[0]}»)"
    if any(b in PRIMERA_PERSONA for b in bajas):
        return 70.0, "en primera persona, sin nombrar a quien lo ve"
    return 35.0, "en tercera persona, no le habla a nadie"


COMPROBACIONES = ["DURACIÓN", "CONCRECIÓN", "TENSIÓN", "ARRANQUE", "A QUIÉN"]
# En la primera línea de un post mandan estas tres; las otras dos suman.
NUCLEO_POST = ["DURACIÓN", "TENSIÓN", "ARRANQUE"]
FORMATOS = ("reel", "post")


def notas_que_mandan(resultados, formato):
    nombres = NUCLEO_POST if formato == "post" else COMPROBACIONES
    return [resultados[c][0] for c in nombres]


def puntua(texto, formato="reel"):
    if formato not in FORMATOS:
        raise ValueError(f"formato desconocido: {formato}")
    resultados = {
        "DURACIÓN": mira_duracion(texto, formato),
        "CONCRECIÓN": mira_concrecion(texto),
        "TENSIÓN": mira_tension(texto),
        "ARRANQUE": mira_arranque(texto),
        "A QUIÉN": mira_a_quien(texto),
    }
    avisos = [msg for patron, msg in ELIMINATORIAS if patron.search(texto)]
    notas = [resultados[c][0] for c in COMPROBACIONES]
    if formato == "post":
        nucleo = notas_que_mandan(resultados, formato)
        extra = statistics.mean([resultados["CONCRECIÓN"][0], resultados["A QUIÉN"][0]])
        total = statistics.mean(nucleo) * 0.5 + min(nucleo) * 0.3 + extra * 0.2 - len(avisos) * 15
        minimo = min(nucleo)
    else:
        # La más floja manda: con un solo fallo, el pulgar sigue bajando.
        total = statistics.mean(notas) * 0.6 + min(notas) * 0.4 - len(avisos) * 15
        minimo = min(notas)
    total = limita(total)
    fuerte = total >= 70 and minimo >= 55 and not avisos
    if formato == "post":
        # Corta y con tensión no basta: si no hay nada que se vea ni nadie a quien
        # hablarle, es una frase bonita que sirve para cualquier cuenta.
        fuerte = fuerte and (resultados["CONCRECIÓN"][0] >= 55 or le_habla(texto))
    veredicto = "FUERTE" if fuerte else ("VALE" if total >= 50 else "FLOJO")
    return resultados, total, veredicto, avisos


def nota_de_formato(texto, formato):
    """Avisos que no restan, pero que conviene saber."""
    if formato == "post" and len(tokens(texto)) <= 4:
        return ("Frase-golpe: buena parte de su fuerza depende de la segunda línea. "
                "Pásale también la segunda para ver cómo funcionan juntas.")
    return ""


def barra(nota, ancho=24):
    llenas = round(nota / 100 * ancho)
    return "#" * llenas + "." * (ancho - llenas)


def mas_flojo(resultados, formato):
    nombres = NUCLEO_POST if formato == "post" else COMPROBACIONES
    return min(nombres, key=lambda c: resultados[c][0])


def pinta_uno(texto, resultados, total, veredicto, avisos, formato="reel", out=sys.stdout):
    titulo = "PRIMERA LÍNEA DE POST" if formato == "post" else "GANCHO DE REEL"
    print(f"\nPUNTUACIÓN · {titulo}", file=out)
    print("=" * 62, file=out)
    print(f"  «{texto.strip()}»\n", file=out)
    for nombre in COMPROBACIONES:
        nota, detalle = resultados[nombre]
        print(f"  {nombre:<11} {barra(nota)} {nota:5.1f}", file=out)
        print(f"  {'':<11} {detalle}", file=out)
    print("-" * 62, file=out)
    print(f"  {'TOTAL':<11} {barra(total)} {total:5.1f}   {veredicto}", file=out)
    for a in avisos:
        print(f"\n  ELIMINATORIO  {a}", file=out)
    if veredicto != "FUERTE":
        print(f"\n  Lo más flojo: {mas_flojo(resultados, formato)}. Arregla eso y vuelve a pasarlo.", file=out)
    nota = nota_de_formato(texto, formato)
    if nota:
        print(f"\n  Ojo: {nota}", file=out)
    print("", file=out)


def pinta_tabla(filas, out=sys.stdout):
    print("\nRANKING DE GANCHOS\n" + "=" * 78, file=out)
    for i, f in enumerate(filas, 1):
        marca = "->" if i == 1 else "  "
        gancho = f["gancho"] if len(f["gancho"]) <= 62 else f["gancho"][:59] + "..."
        print(f"{marca} {f['total']:5.1f} {f['veredicto']:<7} {gancho}", file=out)
        print(f"        lo más flojo: {f['mas_flojo']} ({f['comprobaciones'][f['mas_flojo']]['nota']:.0f})", file=out)
        for a in f["avisos"]:
            print(f"        eliminatorio: {a}", file=out)
    print("\nGraba el primero. Si el primero está por debajo de 50, ninguno de estos es el gancho.\n",
          file=out)


def main():
    ap = argparse.ArgumentParser(description="Puntúa el gancho de un reel en cinco propiedades.")
    ap.add_argument("entrada", nargs="?", default="-", help="archivo con un gancho por línea, o -")
    ap.add_argument("--gancho", help="puntúa un solo gancho escrito en la línea de órdenes")
    ap.add_argument("--formato", choices=FORMATOS, default="reel",
                    help="reel: lo que dices en los 3 primeros segundos; post: la primera línea que se lee")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.gancho:
        lineas = [args.gancho]
    else:
        try:
            bruto = sys.stdin.read() if args.entrada == "-" else open(args.entrada, encoding="utf-8-sig").read()
        except (OSError, UnicodeDecodeError):
            pista = ". Para puntuar una frase suelta, usa --gancho \"tu frase\"" if " " in args.entrada else ""
            ap.error(f"no puedo leer «{args.entrada}»: no existe o no es un archivo de texto{pista}")
        bruto = bruto.lstrip(chr(0xFEFF))
        lineas = [l.strip() for l in bruto.splitlines() if l.strip()]
    if not lineas:
        print("no hay nada que puntuar", file=sys.stderr)
        sys.exit(2)

    salida = []
    for linea in lineas:
        resultados, total, veredicto, avisos = puntua(linea, args.formato)
        salida.append({
            "gancho": linea,
            "formato": args.formato,
            "comprobaciones": {k: {"nota": round(v[0], 1), "detalle": v[1]} for k, v in resultados.items()},
            "mas_flojo": mas_flojo(resultados, args.formato),
            "avisos": avisos,
            "nota": nota_de_formato(linea, args.formato),
            "total": round(total, 1),
            "veredicto": veredicto,
        })

    if args.json:
        print(json.dumps(salida if len(salida) > 1 else salida[0], indent=2, ensure_ascii=False))
        return
    if len(salida) == 1:
        pinta_uno(lineas[0], *puntua(lineas[0], args.formato), formato=args.formato)
    else:
        pinta_tabla(sorted(salida, key=lambda f: -f["total"]))
    sys.exit(0 if max(f["total"] for f in salida) >= 70 else 1)


if __name__ == "__main__":
    main()

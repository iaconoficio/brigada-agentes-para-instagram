# La comanda

La comanda es un archivo JSON con lo que va en el documento, página a página. El script `scripts/emplata.py` la lee, la revisa y la emplata. Hay un ejemplo completo en `assets/comanda-ejemplo.json`.

## Lo de arriba

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `titulo` | Sí | El nombre del documento. Por ejemplo, «Tu semana del 16 de noviembre». Una línea, 90 caracteres como mucho |
| `para` | Sí | El negocio o la persona que lo recibe, como en «Nombre» de su ficha. Una línea, 60 caracteres como mucho |
| `cuenta` | No | Su cuenta de Instagram, con @. 40 caracteres como mucho |
| `preparado_por` | No | Quien lo prepara, si no es la misma persona. Sale en la portada y en la contraportada. Una línea, 60 caracteres como mucho |
| `fecha` | No | Una línea corta para la portada, 60 caracteres como mucho |
| `marca` | No | Sus colores y su logotipo (abajo). Sin marca, van los colores de La Brigada |
| `paginas` | Sí | La lista de páginas, en el orden en que se leen. Como mucho, 40 |

## La marca

| Campo | Qué es |
| --- | --- |
| `fondo` | El color de fondo de las páginas. Mejor claro |
| `texto` | El color del texto. Tiene que leerse sobre el fondo y sobre `suave` (contraste 4,5 o más) |
| `acento` | El color de los antetítulos, los números y los botones. Mejor que se lea sobre el fondo (contraste 3 o más) |
| `suave` | El color de las tarjetas. Suele ir bien el blanco |
| `logo` | La ruta a su logotipo, dentro de la carpeta de la comanda: PNG, JPG, WEBP o SVG, de 2 MB como mucho |
| `manuscrita` | `true` (o «sí») para el título de la portada en letra manuscrita |

Los colores van en código: `#1C2541` o `#123`. Si la persona solo sabe decirlos con palabras («azul marino, naranja»), propón códigos, enséñaselos y que los confirme.

## Las páginas

Cada página lleva su `tipo`. Todas admiten `antetitulo` (la línea pequeña de arriba) y todas menos la portada admiten `nota` (una línea al pie; en la de texto va con las demás notas). Los campos que el script no conoce se quedan fuera, sin aviso.

| Tipo | Obligatorio | Lo demás | Por página |
| --- | --- | --- | --- |
| `portada` | `titulo` | `antetitulo`, `subtitulo`, `piezas`: lista de `{"dia", "formato"}`, hasta 4 | 1 |
| `idea` | `titulo` | `texto`, `oscura`: `true` para fondo oscuro | 1 |
| `semana` | `filas`: lista de `{"dia", "hora", "formato", "tema"}` | `titulo`, `nota` | 7 filas |
| `puntos` | `puntos`: lista de textos o de `{"texto", "fuente"}` | `titulo`, `nota` | 3 puntos |
| `guion` | `planos`: lista de `{"dices", "cartel", "se_ve"}` | `titulo`, `nota`, `oscura` | 3 planos |
| `texto` | `texto`: el texto del post entero | `titulo`, `imagen` (lo que va en la imagen, en dos o tres palabras), `notas`: lista corta (o una sola nota) | 1 |
| `laminas` | `laminas`: lista de textos, un texto con las láminas separadas por `---`, o `{"archivo": "carrusel.txt"}` (un .txt o .md dentro de la carpeta de la comanda) | `titulo`, `nota` | 6 láminas |
| `lista` | `items`: lista de textos | `titulo`, `nota`, `casillas`: `false` para puntos en vez de casillas | 7 |
| `tabla` | `columnas` (de 2 a 5) y `filas` (cada una con tantas celdas como columnas; una celda vacía queda para rellenar) | `titulo`, `nota` | 8 filas |
| `cifras` | `cifras`: lista de 2 a 4 `{"numero", "texto"}` | `titulo`, `nota` | 1 |

Si una lista no cabe en una página, el script la parte en varias, repartidas a partes iguales, y añade «1 de 2» al antetítulo (o lo pone de antetítulo si no hay). Una página con su lista vacía es un error, no se quita sin avisar. La contraportada no va en la comanda: la pone siempre el script al final.

Los campos de sí o no (`oscura`, `casillas`, `manuscrita`) van con `true` o `false`; también valen «sí» y «no». Un `null` cuenta como vacío.

En los textos, `**así**` sale en negrita y un salto de línea (`\n`) se respeta.

## Cuánto texto cabe

Son orientaciones, no datos. Si las pasas, el script avisa (OJO). Si tiene un navegador, además mide de verdad y marca en rojo lo que se sale.

| Dónde | Palabras, como mucho |
| --- | --- |
| Título de la portada | 12 |
| Subtítulo de la portada | 30 |
| Título de una idea | 16 |
| Texto de una idea | 60 |
| Tema de una fila de la semana | 14 |
| Cada punto | 40 |
| Lo que se dice en un plano | 35 |
| El cartel de un plano | 8 |
| Lo que se ve en un plano | 16 |
| Cada lámina | 40 |
| Cada línea de una lista | 18 |
| Cada celda de una tabla | 12 |
| Lo que dice cada cifra | 6 |
| Cada nota del texto de un post | 25 |

El texto de un post se ve entero hasta 700 caracteres. Si es más largo, en la maqueta se corta con «más», como en Instagram, y entero va en el archivo para copiar.

## Un trozo de ejemplo

```json
{
  "titulo": "Tu semana del 16 de noviembre",
  "para": "Calefacción Olmo",
  "cuenta": "@calefaccion.olmo",
  "marca": {"fondo": "#EEF3F6", "texto": "#15314B", "acento": "#C2531F", "suave": "#FFFFFF"},
  "paginas": [
    {"tipo": "portada", "antetitulo": "Plan de la semana", "titulo": "Tu semana del 16 de noviembre",
     "piezas": [{"dia": "martes", "formato": "Reel"}, {"dia": "jueves", "formato": "Carrusel"}]},
    {"tipo": "idea", "oscura": true, "antetitulo": "La duda de la semana",
     "titulo": "«¿Se me ha roto la caldera?»", "texto": "Casi siempre es aire."}
  ]
}
```

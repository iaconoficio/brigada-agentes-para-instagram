# El pedido

El pedido es un archivo JSON con la semana ya aprobada, pieza a pieza. El script `scripts/para_llevar.py` lo lee, lo revisa, dibuja las imágenes y lo deja todo listo para subir. Hay un ejemplo completo en `assets/pedido-ejemplo.json`.

## Lo de arriba

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `titulo` | Sí | El nombre de la semana, como «Tu semana del 16 de noviembre». Una línea, 90 caracteres como mucho. Con él se nombra el paquete si no le das otro nombre |
| `para` | Sí | El negocio o la persona, como en «Nombre» de su ficha. Sale en la cabecera de cada imagen. 60 caracteres como mucho |
| `cuenta` | Sí | Su cuenta de Instagram, con o sin @, sin espacios. Sale debajo del nombre |
| `aprobado` | Sí | Quién ha dado el sí a los textos y qué día: `{"por": "Marta Olmo", "fecha": "2026-11-14"}` |
| `marca` | No | El fondo, el color del texto, la letra y la foto (abajo). Sin marca, fondo blanco, como en la Lámina |
| `calendario` | No | El `.ics` de brigada-plan (`semana.py --ics`), dentro de la carpeta del pedido. Va en el paquete como `semana.ics` |
| `preparado_por` | No | Quien lo prepara, si no es la misma persona. Sale en el LEEME y en la página. 60 caracteres como mucho |
| `piezas` | Sí | Las publicaciones de la semana, en orden. De 1 a 7 |

**Sobre `aprobado`:** solo se escribe cuando la persona ha visto los textos y ha dicho que sí. Sin `aprobado`, el script no hace nada.

## La marca

| Campo | Qué es |
| --- | --- |
| `fondo` | `blanco`, `negro` o un color en código, como `#EEF3F6`. Con blanco o negro, los colores son los de la Lámina |
| `texto` | El color del texto, en código. Hace falta si el fondo es de color, y tiene que leerse sobre el fondo (contraste 4,5 o más) |
| `letra` | `sans` (como la del móvil), `serif` (con remate) o `mono` (de máquina de escribir). Por defecto, `sans` |
| `foto` | La ruta a su foto de perfil, dentro de la carpeta del pedido: PNG, JPG o WEBP, de 2 MB como mucho. Sin foto, van sus iniciales |
| `verificado` | `true` para la insignia azul. Solo si su cuenta está verificada de verdad |

Los colores van en código: `#1C2541` o `#123`. Si la persona solo sabe decirlos con palabras, propón códigos, enséñaselos y que los confirme.

## Las piezas

Todas llevan:

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `dia` | Sí | El día de publicarla, corto: «martes 17». Con él se nombra su carpeta |
| `hora` | No | La hora, como `19:00`. La de brigada-plan; si no hay, no se inventa |
| `formato` | Sí | `reel`, `carrusel` o `post` |
| `texto` | Sí | El texto de la publicación, tal cual se aprobó. 2.200 caracteres como mucho, lo que admite Instagram |

Y según el formato:

| Formato | Obligatorio | Lo demás |
| --- | --- | --- |
| `reel` | `portada`: el texto de la portada. `guion`: el guion, para que lo tenga a mano al grabar | `carteles`: lista con los textos en pantalla, en el orden del guion. Como mucho 15 |
| `carrusel` | `laminas`: lista de textos, un texto con las láminas separadas por una línea con `---`, o `{"archivo": "carrusel.txt"}`. De 2 a 20 láminas | `numerar`: `false` para quitar el «1/10» de abajo. Por defecto va |
| `post` | `lamina`: el texto de la imagen | |

Los textos largos (`texto`, `portada`, `guion`, `lamina`) también pueden venir de un archivo: `{"archivo": "guion-martes.txt"}`, un .txt o .md dentro de la carpeta del pedido.

Los campos que el script no conoce se quedan fuera, sin aviso.

## Lo que sale

Al lado del pedido (o donde digas con `--salida`), tres cosas con el mismo nombre:

| Qué | Para qué |
| --- | --- |
| La carpeta | Una subcarpeta por pieza, con sus imágenes y su texto, y el LEEME |
| El .zip | La misma carpeta, para mandarla de una vez |
| La página .html | Para verlo todo en el móvil, copiar los textos y descargar el .zip. Funciona sin internet |

Las medidas de cada imagen:

| Imagen | Medida | Archivo |
| --- | --- | --- |
| Lámina del carrusel | 1080x1350 | `01.jpg`, `02.jpg`... |
| Imagen del post | 1080x1350 | `post.jpg` |
| Portada del reel | 1080x1920 | `portada-del-reel.jpg` |
| Texto en pantalla del reel | 1080x1920, fondo transparente | `textos-en-pantalla-opcional/01.png`... |

## Cuánto texto cabe

No hay un número fijo: el script lo mide dibujando cada imagen. La letra se hace más pequeña hasta un mínimo; si con la más pequeña no cabe, o si una palabra es más ancha que la línea, avisa con ARREGLA y no entrega nada.

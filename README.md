# La Brigada · Agentes de IA para Instagram, en español

La Brigada te prepara la semana de Instagram con tu voz: el guion del reel, el texto de cada publicación y el carrusel. Y te la entrega lista para subir, con las imágenes hechas. Gratis, en español de España y pensada para gente con oficio.

**Tú apruebas y publicas.** Nada sale sin tu sí.

> **Versión 0.1.** Funciona en Claude. La versión para ChatGPT está en preparación.

## Qué la hace distinta

- **Gratis y abierta.** Código abierto con licencia MIT. La Brigada no cuesta nada; Claude tiene plan gratuito y planes de pago.
- **Sin abrir otra cuenta.** No hay otra plataforma, ni otra contraseña, ni otra cuota.
- **En español de España, para oficios.** Escrita en castellano de España: entiende tildes, ñ, «¿» y «¡», euros y cifras con punto de miles, y caza las muletillas de IA en español.
- **Lista para subir.** No te deja solo los textos: te da las imágenes del carrusel, del post y de la portada del reel, una carpeta por publicación y el texto para copiar.
- **Tú decides.** No entra en tu cuenta, no publica y no manda mensajes por ti.

## Qué hace y qué no

| Hace | No hace |
| --- | --- |
| Escribe el guion de tus reels, el texto de tus posts y tus carruseles, con tu voz | Publicar por ti |
| Puntúa tus ganchos antes de grabar | Grabar el vídeo |
| Quita lo que suena a IA de tus textos | Entrar en tu cuenta ni pedirte la contraseña |
| Te deja la semana lista para subir: las imágenes hechas y los textos para copiar | Generar fotos ni ilustraciones |
| Sus scripts trabajan sin conectarse a nada | Prometerte seguidores ni viralidad |

## La brigada

Cada agente tiene su partida, como en una cocina. Están en el orden en que suelen trabajar en una semana.

| Agente | Qué prepara |
| --- | --- |
| `brigada-ficha` | Te entrevista una vez sobre tu negocio, a quién te diriges y tu voz. Los demás la leen |
| `brigada-plan` | Un diagnóstico de arranque y, cada semana, una duda de tus clientes contada en tres piezas (reel, carrusel y post), con días, horas, un archivo para tu calendario y el repaso de las 48 horas |
| `brigada-reel` | Tres ganchos puntuados, el guion plano a plano con sus carteles, cuánto dura y la versión sin salir en cámara |
| `brigada-caption` | El texto del post: la primera línea que se ve antes del «más», un cierre que no siempre vende y como mucho cinco hashtags, revisado con un script |
| `brigada-carrusel` | Elige una de siete estructuras, puntúa la portada y escribe una idea por lámina, revisado con un script |
| `brigada-humano` | Quita las huellas de IA, respeta tus palabras y puntúa cuánto suena a persona |
| `brigada-emplatado` | Te enseña el trabajo con diseño, para leerlo en el móvil: una idea por página, con tus colores y los textos aparte para copiar |
| `brigada-para-llevar` | Con tus textos ya aprobados, hace las imágenes (carrusel, post y portada del reel) con tus colores y te deja la semana lista para subir: una carpeta por publicación y un .zip |

**Próximamente:** las stories, contar tu semana en un audio y preparar respuestas a comentarios y mensajes directos.

## Instalación

### En la app de Claude

Según la [ayuda de Claude](https://support.claude.com/en/articles/12512180), las skills están en los planes Free, Pro, Max, Team y Enterprise. Desde el ordenador:

1. **Activa la ejecución de código.** En **Settings > Capabilities**, enciende **Code execution and file creation**. Sin esto, los agentes no funcionan. En Team y Enterprise, si no ves la opción, pídesela a quien lleva la cuenta.
2. Descarga los ocho agentes. Cada enlace baja un .zip ya preparado: no lo abras, se sube tal cual.

| Agente | Descarga |
| --- | --- |
| `brigada-ficha` | [brigada-ficha.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-ficha.zip) |
| `brigada-plan` | [brigada-plan.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-plan.zip) |
| `brigada-reel` | [brigada-reel.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-reel.zip) |
| `brigada-caption` | [brigada-caption.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-caption.zip) |
| `brigada-carrusel` | [brigada-carrusel.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-carrusel.zip) |
| `brigada-humano` | [brigada-humano.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-humano.zip) |
| `brigada-emplatado` | [brigada-emplatado.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-emplatado.zip) |
| `brigada-para-llevar` | [brigada-para-llevar.zip](https://github.com/iaconoficio/brigada-agentes-para-instagram/raw/main/para-la-app-de-claude/brigada-para-llevar.zip) |

Si al descargar te aparece una carpeta y no un archivo .zip (Safari a veces lo abre solo), bájalo con otro navegador, como Chrome.

3. En Claude, ve a **Customize > Skills**, pulsa **+**, luego **+ Create skill** y **Upload a skill**, y sube los ocho .zip, uno a uno. `brigada-para-llevar` necesita `brigada-emplatado`: sube los dos.
4. Crea un Proyecto para La Brigada y trabaja siempre dentro de él.
5. Sigue con [tu primera semana](#tu-primera-semana-mensaje-a-mensaje).

Los nombres de los menús son los de la ayuda de Claude. Si en tu app se ven distintos, sigue [la ayuda](https://support.claude.com/en/articles/12512180).

### En Claude Code (terminal, escritorio o VS Code)

En la terminal, dentro de Claude Code, añade La Brigada como catálogo de plugins e instálala:

```text
/plugin marketplace add iaconoficio/brigada-agentes-para-instagram
/plugin install brigada@brigada
```

Al instalar te pregunta dónde: elige **Install for you** para tenerla en todos tus proyectos. Los agentes aparecen al escribir `/brigada:`. En la app de escritorio y en VS Code los pasos son otros: están en [la documentación de Claude Code](https://code.claude.com/docs/en/plugins/install). Después, sigue con [tu primera semana](#tu-primera-semana-mensaje-a-mensaje): en Claude Code se escribe lo mismo, desde tu carpeta de trabajo.

### En ChatGPT

En preparación.

## Tu primera semana, mensaje a mensaje

Dentro del Proyecto, abre un chat y escribe. Cada mensaje despierta a un agente.

1. **«Hazme la ficha».** `brigada-ficha` te pregunta por tu negocio, a quién te diriges y cómo hablas. Solo se hace una vez. Al acabar te da tu ficha. En la app, súbela a los archivos del Proyecto: así los demás agentes la leen en cada chat.
2. **«Qué publico esta semana».** `brigada-plan` elige una duda que te hacen tus clientes y la reparte en un reel, un carrusel y un post, con días, horas y un archivo para tu calendario. La primera vez te hace antes un diagnóstico: si tienes web, publicaciones o estadísticas, dáselas; si no, sigue sin ellas. Sube también el plan de cada semana (`PLAN-SEMANA.md`) a los archivos del Proyecto, para que no te repita dudas.
3. **«Hazme el reel», «Hazme el carrusel» y «Escríbeme el texto del post».** `brigada-reel`, `brigada-carrusel` y `brigada-caption` escriben cada pieza, y `brigada-humano` les quita el tono de IA.
4. **Léelo y di qué cambias.** Si lo quieres ver con diseño, pide «emplátalo».
5. **«Dámelo listo para subir».** `brigada-para-llevar` te enseña todos los textos juntos y te pide tu sí. Contesta «sí»: sin él no hace imágenes. Después te pasa los textos a imágenes, con tus colores, y te deja la semana en un .zip, una carpeta por publicación. Si no puede hacer las imágenes allí mismo, te da una página: la abres, pulsas «Descargar todo» y te llevas el mismo .zip.
6. **Tú lo subes a Instagram.**

Las semanas siguientes, empieza en el paso 2.

## Sin instalar nada: la Lámina de texto

[`herramientas/lamina-de-texto.html`](herramientas/lamina-de-texto.html) es una página que se abre con el navegador, funciona sin internet y no envía nada. Pegas tus textos y te da las imágenes para Instagram, con aspecto de tuit: una por post, o todas las láminas de un carrusel numeradas y juntas en un .zip. Antes de descargar, te avisa de las rayas y de las muletillas de IA con la misma lista que usa `brigada-humano`.

## Los scripts, uno a uno

Los agentes los usan solos, pero también puedes probarlos tú, desde una terminal abierta en la carpeta de La Brigada (en Windows, a veces el comando es `python` o `py` en vez de `python3`). Los archivos como `texto.txt` o `guion.txt` son tuyos: pon ahí tu texto. Con un gancho:

```bash
python3 skills/brigada-reel/scripts/puntua_gancho.py --gancho "Llevo 26 años en hostelería y este error lo veo cada semana"
```

Con el texto de un post, para ver lo que se lee antes del «más» y revisarlo:

```bash
python3 skills/brigada-caption/scripts/revisa_caption.py texto.txt --buscar "taller de motos"
```

Con el plan de la semana, para verlo en una tabla y llevártelo al calendario:

```bash
python3 skills/brigada-plan/scripts/semana.py skills/brigada-plan/assets/semana-ejemplo.json --ics semana.ics
```

Con un carrusel (láminas separadas por una línea con `---`), para verlo lámina a lámina, revisarlo y sacar el texto alternativo de cada una:

```bash
python3 skills/brigada-carrusel/scripts/revisa_carrusel.py skills/brigada-carrusel/assets/carrusel-ejemplo.txt --alt
```

Con el trabajo de la semana en una comanda, para entregarlo con diseño (en HTML y, si tienes Chrome, en PDF):

```bash
python3 skills/brigada-emplatado/scripts/emplata.py skills/brigada-emplatado/assets/comanda-ejemplo.json --salida semana.html --pdf semana.pdf
```

Con la semana ya aprobada, para tenerla lista para subir: las imágenes hechas, una carpeta por publicación y un .zip (dibuja y mide con tu Chrome; sin Chrome, te deja una página que lo hace en tu navegador):

```bash
python3 skills/brigada-para-llevar/scripts/para_llevar.py skills/brigada-para-llevar/assets/pedido-ejemplo.json --salida semana-lista
```

Con un guion de reel, para saber cuánto dura antes de grabarlo:

```bash
python3 skills/brigada-reel/scripts/tiempos.py guion.txt --objetivo 30
```

Y con un texto:

```bash
python3 skills/brigada-humano/scripts/humaniza.py borrador.txt -o limpio.txt --informe
python3 skills/brigada-humano/scripts/detecta.py borrador.txt limpio.txt
```

Son comprobaciones locales y orientativas. No predicen visualizaciones ni garantizan pasar ningún detector.

## Seguridad

- **Versión oficial:** solo la de [github.com/iaconoficio/brigada-agentes-para-instagram](https://github.com/iaconoficio/brigada-agentes-para-instagram). Desconfía de copias con otro nombre.
- Los scripts solo usan Python estándar, no se conectan a internet y no envían nada.
- `brigada-emplatado` y `brigada-para-llevar` usan tu Chrome, Chromium o Edge si lo encuentran, sin ventana, con el archivo en local y la red cortada, solo para comprobar que todo cabe, hacer el PDF y dibujar las imágenes.
- Revisamos cada cambio antes de aceptarlo.
- Para avisar de un problema de seguridad, lee [SECURITY.md](SECURITY.md).

## Créditos

La Brigada parte de [instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill), de Jake Schincariol (licencia MIT): de ahí vienen la idea de un equipo de agentes para Instagram que trabajan juntos y el punto de partida de `brigada-reel`, `brigada-caption`, `brigada-carrusel` y `brigada-plan`. Su licencia y sus créditos se mantienen en [LICENSE](LICENSE) y en cada uno de esos cuatro agentes. También toma ideas de [suede-creator-skills](https://github.com/JasonColapietro/suede-creator-skills), de Suede AI (licencia MIT). Gracias a los dos por abrir su trabajo.

## Licencia y marca

El código y los textos se publican con licencia MIT: puedes usarlos, cambiarlos y compartirlos. La licencia no da derecho a usar los nombres «La Brigada» ni «IA con Oficio» ni sus logotipos.

La Brigada no está afiliada a Instagram ni a Meta, ni cuenta con su respaldo. Instagram es una marca de Meta Platforms, Inc.

## Quién lo hace

**Toni Mont · IA con Oficio.** La IA explicada por un hostelero que la usa cada día.

- Comunidad de WhatsApp: [entra aquí](https://chat.whatsapp.com/F4LVhDev0ahGSJixjCsLc9)
- Instagram: [@soytonimont](https://www.instagram.com/soytonimont/)
- Web: [tonimont.com](https://tonimont.com)

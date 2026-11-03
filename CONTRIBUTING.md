# Cómo colaborar

Gracias por querer mejorar La Brigada. Cualquier cambio entra por una propuesta (pull request) que se revisa antes de aceptarla.

## Reglas de la casa

1. **En español.** Textos, comentarios del código y mensajes de los scripts.
2. **Sin red.** Los scripts solo pueden usar la biblioteca estándar de Python. Nada que se conecte a internet, instale paquetes o envíe datos.
3. **Nada publica solo.** Ninguna skill puede publicar, comentar, seguir, dar «me gusta» ni mandar mensajes en nombre de nadie.
4. **Sin contraseñas.** Ninguna skill pide credenciales ni entra en cuentas.
5. **Nada copiado.** Ni textos, ni guiones, ni plantillas de otros sin permiso y sin citar la fuente.
6. **Sin enlaces de afiliado** ni publicidad dentro de las skills.
7. **Los .zip, al día.** Si cambias algo en `skills/`, añádelo a git y rehaz los .zip de la app de Claude:

```bash
python3 herramientas/empaqueta_agentes.py
```

8. **Las pruebas pasan.** Antes de proponer un cambio:

```bash
python3 -m unittest discover -s pruebas -v
```

## Qué es lo más útil ahora

- Ganchos y textos reales en español para calibrar los puntuadores.
- Muletillas de IA que veas a menudo y no estén en `skills/brigada-humano/scripts/muletillas.json`.
- Expresiones de tu país (España, México, Argentina, Colombia...) para que la Brigada escriba bien en cada uno.

## Cómo proponer un cambio

1. Haz un fork del repositorio.
2. Crea una rama con un nombre claro, por ejemplo `muletillas-mexico`.
3. Haz tus cambios y pasa las pruebas.
4. Abre la propuesta explicando qué cambia y por qué.

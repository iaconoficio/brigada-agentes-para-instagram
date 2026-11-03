# Seguridad

## Cómo avisar de un problema

No abras una incidencia pública para un fallo de seguridad. Escríbenos a **hola@tonimont.com**, o usa el botón «Report a vulnerability» de la pestaña Security de este repositorio.

Cuéntanos:

- qué versión o qué cambio está afectado;
- qué puede pasar, en pocas palabras;
- cómo reproducirlo;
- si tienes una idea para arreglarlo.

No incluyas contraseñas, datos personales ni secretos de nadie.

## Qué cubre

Las skills (los archivos SKILL.md), los scripts de Python, los manifiestos de plugin (`.claude-plugin/`) y la forma de instalarlo.

## Cómo está hecho para ser seguro

- **Versión oficial:** solo la de `github.com/iaconoficio/brigada-agentes-para-instagram`.
- **Sin red:** los scripts solo usan la biblioteca estándar de Python. No se conectan a internet, no instalan nada y no envían datos.
- **Sin cuentas:** ninguna skill pide contraseñas ni entra en Instagram por ti.
- **Nada entra sin revisión:** cualquier cambio de otra persona se revisa y se aprueba antes de llegar a la rama principal.
- **Nada se publica solo:** las skills preparan borradores. Publicar es siempre decisión tuya.

Esto no es una garantía, es cómo trabajamos. Si encuentras algo que no cuadra, avísanos.

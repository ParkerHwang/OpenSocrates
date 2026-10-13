<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Ayuda para razonar y obtener resultados que puedas comprender, evaluar y utilizar.**

OpenSocrates ofrece 48 métodos de razonamiento para sintetizar fuentes, comprender
perspectivas, comparar opciones y redactar mensajes útiles. v1.5.2 añade español
(`es`), francés, alemán, italiano, portugués y tailandés al contenido en inglés,
coreano, chino simplificado y japonés. Las diez lenguas incluyen 480 procedimientos
completos, 3.840 casos canónicos y 1.440 preguntas dirigidas al agente, tres por
método e idioma. La revisión de contenido es 5: se conservan los textos y valores
de los cuatro idiomas anteriores, pero la identidad de revisión de cada método
pasa de 4 a 5. No se añaden métodos específicos de programación.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | **Español** | [Português](README.pt.md) | [ไทย](README.th.md)

## Aplicaciones y plataformas

| Aplicación | Distribución | Plataforma y activación |
| --- | --- | --- |
| Codex | Hooks existentes y entorno nativo de decisión | Mac Apple Silicon y Windows x64; revisar la confianza de los 7 hooks en una sesión interactiva |
| Claude Code CLI / Code local de Desktop | Entrada nativa sin estado y referencias completas | Mac Apple Silicon; CLI Claude, inicio de sesión y permisos de plugin/hooks |
| Claude Web / Desktop Chat / Cowork | Skill de cuenta en ZIP sin código ejecutable | Exportación en Mac o Windows; carga y activación separadas en la cuenta |
| Antigravity | Regla y skill modulares | Mac Apple Silicon y Windows x64; ámbito de proyecto o global |

Se mantiene el alcance de plataformas de v1.5.0. Claude Code nativo en Windows
queda fuera. Windows ARM64 y la migración a Go pertenecen al trabajo separado
de v1.6.0. La skill de cuenta no instala una integración nativa de Claude.

## Instalar o actualizar

Prepara Node.js 20 o posterior e inicia sesión en la aplicación elegida.
Los entornos nativos están incluidos; la instalación no requiere Python.
Obtén archivos y sumas SHA-256 en la
[versión v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
npx --yes opensocrates@1.5.2 update --host codex
```

Para una instalación existente utiliza `update` en lugar de `install`.
Abre `/hooks` en Codex interactivo, revisa los 7 hooks OpenSocrates y concede
las aprobaciones necesarias mediante el mecanismo de confianza de la aplicación.
Después inicia una conversación nueva. `status` informa de instalación e
integridad; no demuestra aprobación de hooks ni aplicación real.

En Mac Apple Silicon usa `install --host claude` para Claude Code.
Para Antigravity elige una carpeta de trabajo existente con ruta absoluta;
sin `--workspace` el ámbito es global. Evita copias activas duplicadas para una
misma tarea. En Windows usa una ruta de unidad local entre comillas, por ejemplo
`"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Exporta la skill de cuenta a una ruta absoluta de archivo ZIP en una carpeta
existente y después súbela y actívala en Claude, **Customize → Skills**.
Antes de reemplazar una skill OpenSocrates, guarda una copia y su estado de
activación. Exportar no equivale a cargar, activar ni seleccionar automáticamente.
Añade esta instrucción en **Settings → General → Instructions for Claude**,
conservando las instrucciones actuales:

```text
Para solicitudes que requieran interpretación o juicio, como sintetizar
fuentes, comparar opciones, tomar decisiones o redactar mensajes, carga la
skill OpenSocrates activada y sigue sus instrucciones aunque no la mencione.
Antes de aplicar un método, lee su procedimiento completo y comprueba las
condiciones de uso. No añadas procedimientos innecesarios a tareas mecánicas
como dar formato.
```

En interfaces antiguas de Cowork utiliza **Settings → Cowork → Global instructions**.
Si Web y Desktop usan cuentas distintas, configura cada una y comienza una
conversación nueva. La selección depende del modelo y puede omitirse: no añade
hooks nativos ni uso garantizado en cada mensaje. El valor predeterminado y
`--host all` siguen seleccionando solo Codex.

## Elegir el idioma de las instrucciones

La escritura latina no distingue de forma fiable el español de otros idiomas
compatibles. Usa una preferencia explícita o guardada. Desde la raíz del paquete
Codex instalado en Mac:

```sh
bin/launch.sh locale codex set es
bin/launch.sh locale codex get
bin/launch.sh locale codex reset
```

En Windows utiliza `node bin/launch.mjs locale codex set es`.
`set follow` o `reset` borra solo la preferencia de idioma. Esta opción se aplica
al selector conservado; las solicitudes de decisión sin estado exigen el campo
JSON explícito `locale` y no leen ajustes. Los paquetes de cuenta o contenido
utilizan la guía y las referencias del idioma correspondiente.

El orden es: idioma explícito de confianza, preferencia guardada y caracteres
de la entrada actual. Los kana seleccionan japonés primero; en otro caso, el
predominio de caracteres tailandeses, hangul o han selecciona tailandés, coreano
o chino. Los empates, entradas vacías y escrituras desconocidas usan inglés.
El japonés sin kana es ambiguo y necesita `ja`. El portugués usa ortografía
brasileña bajo el código genérico `pt`, sin afirmar soporte individual de todas
las variantes. El idioma de instrucciones, respuesta, interfaz y mensajes npm
son distintos. El instalador npm no tiene una opción `--locale`.

## Atribución, privacidad y límites

La línea final exacta `Powered by OpenSocrates` solo aparece tras leer por
completo un método canónico admisible y aplicarlo realmente a la respuesta.
La orientación de lectura por sí sola y las tareas mecánicas no cumplen esa
condición. La atribución no prueba aplicación nativa ni resultados mejores.

La ruta de decisión predeterminada no llama a un modelo selector adicional
ni guarda prompts sin procesar, conversaciones, capturas o razonamientos ocultos.
La entrada nativa de Claude no lee conversaciones ni crea una base de datos.
Las solicitudes normales siguen la autenticación, permisos, conservación y
condiciones de la aplicación. Instalación, carga, lectura completa, aplicación
y utilidad son pruebas diferentes. No se afirman mejoras universales de
calidad, coste o velocidad.

Consulta la [guía de idiomas](docs/v1.5.2.md), los [ajustes](docs/settings.md),
la [configuración visual](docs/setup-guide.md) y la [política de seguridad](SECURITY.md).
Las guías de [Mac](docs/macos-v1.5.md) y [Windows](docs/windows-v1.5.md) conservan
sus observaciones históricas; usa aquí los comandos actuales de 1.5.2.

OpenSocrates es independiente y usa la [licencia MIT](LICENSE). No está afiliado
a OpenAI, Anthropic o Google ni cuenta con su respaldo. [Cambios](CHANGELOG.md).

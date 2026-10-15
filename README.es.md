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

## Migración nativa v1.6.0

Esta rama es un candidato v1.6.0 sin publicar. Conserva los diez idiomas de v1.5.2; los programas Go nativos sustituyen Python, Node.js y npm. Los usuarios tampoco necesitan Go. Windows ARM64 usa archivos nativos propios. Claude Code nativo sigue limitado a macOS ARM64. Firma, notarización y publicación requieren pruebas separadas. Los cambios de contenido de los métodos quedan para v1.6.1 o posterior.

## Aplicaciones y plataformas

[v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2) · [v1.6.0](docs/native-v1.6.md) · [Setup](docs/setup-guide.md) · [Security](SECURITY.md)

| Aplicación | Distribución | Plataforma y activación |
| --- | --- | --- |
| Codex | Hooks existentes y entorno nativo de decisión | Mac Apple Silicon y Windows x64/ARM64; revisar la confianza de los 7 hooks en una sesión interactiva |
| Claude Code CLI / Code local de Desktop | Entrada nativa sin estado y referencias completas | Mac Apple Silicon; CLI Claude, inicio de sesión y permisos de plugin/hooks |
| Claude Web / Desktop Chat / Cowork | Skill de cuenta en ZIP sin código ejecutable | Exportación en Mac o Windows; carga y activación separadas en la cuenta |
| Antigravity | Regla y skill modulares | Mac Apple Silicon y Windows x64/ARM64; ámbito de proyecto o global |

## Instalar o actualizar

Descarga el ejecutable nativo y su paquete de una versión aprobada. Antes de publicar, los paquetes del candidato son compilaciones locales. Para transferir una instalación v1.5 gestionada por npm usa explícitamente `adopt`, conservando ajustes, permisos e integraciones desactivadas. Después usa `update` con un paquete verificado.

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/bundle.zip
```

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

Abre `/hooks` en Codex interactivo, revisa los 7 hooks OpenSocrates y concede
las aprobaciones necesarias mediante el mecanismo de confianza de la aplicación.
Después inicia una conversación nueva. `status` informa de instalación e
integridad; no demuestra aprobación de hooks ni aplicación real.

En Mac Apple Silicon usa `install --host claude` para Claude Code.
Para Antigravity elige una carpeta de trabajo existente con ruta absoluta;
sin `--workspace` el ámbito es global. Evita copias activas duplicadas para una
misma tarea. En Windows usa una ruta de unidad local entre comillas, por ejemplo
`"C:\Work\Reading Workshop"`.

```text
./opensocrates install --host claude --package /absolute/path/to/claude-bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/antigravity-bundle.zip --workspace /absolute/path/to/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
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

Con el ejecutable nativo en Mac:

```text
./opensocrates locale set es
./opensocrates locale get
./opensocrates locale reset
```

En Windows x64/ARM64 usa `.\opensocrates.exe`. Los comandos `locale` no tienen argumento de aplicación.
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
las variantes. El idioma de instrucciones, respuesta, interfaz y mensajes de gestión
son distintos. El instalador no tiene una opción `--locale`.

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

La [guía nativa](docs/native-v1.6.md) describe actualizaciones automáticas, recuperación y pruebas pendientes. Las instrucciones v1.5.2 y npm pertenecen al canal de mantenimiento publicado.

OpenSocrates es independiente y usa la [licencia MIT](LICENSE). No está afiliado
a OpenAI, Anthropic o Google ni cuenta con su respaldo. [Cambios](CHANGELOG.md).

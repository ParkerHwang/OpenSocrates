<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Pon en práctica 48 métodos de razonamiento en tus conversaciones con la IA.**

OpenSocrates ofrece procedimientos de razonamiento reutilizables en **Claude,
Codex y Antigravity**. Compara opciones, interpreta información contradictoria y
explora un plan desde otra perspectiva. Describe tu tarea con tus propias palabras:
los métodos aportan preguntas, comprobaciones y pasos a los que recurrir.

[Empieza con tu aplicación](#start-with-your-app) · [Mira un ejemplo](#see-it-in-a-task) · [Explora los métodos](#a-method-for-the-question)

**48 métodos · 10 idiomas de instrucciones · Licencia MIT**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · **Español** · [Português](README.pt.md) · [ไทย](README.th.md)

## Herramientas para la tarea que tienes delante

- **Empieza por tu tarea.** Cada método ya incluye preguntas y comprobaciones listas para reutilizar en distintas conversaciones.
- **Encuentra una perspectiva útil.** Recurre a métodos para comparar opciones, evaluar evidencias, explorar supuestos y planificar.
- **Adáptalos a tu trabajo.** Lee cada procedimiento, estudia sus ejemplos y adapta el material de código abierto a tus necesidades.

<a id="see-it-in-a-task"></a>

## Un ejemplo concreto

Después de la configuración, prueba una solicitud como esta:

> Estábamos a punto de comprar una herramienta alojada en la nube, pero ahora el flujo de trabajo debe funcionar sin conexión.
> ¿Deberíamos comprarla, crear una propia o resolverlo manualmente por ahora?

Para una decisión como esta, el [análisis de compensaciones](content/methods/trade-off-analysis/procedure.es.md)
ofrece una secuencia reutilizable: identificar requisitos, comparar opciones
viables, separar hechos conocidos de supuestos y explicar qué cambiaría la
recomendación. El método aporta esa estructura junto con tu solicitud habitual.

<a id="start-with-your-app"></a>

## Empieza con tu aplicación

Elige dónde quieres usar OpenSocrates.
[Descarga v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

<details>
<summary><strong>Claude Chat & Cowork</strong> — sube una skill y empieza una conversación</summary>

Para Claude web, Desktop Chat y Cowork:

1. En **Settings → Capabilities**, activa **Code execution and file creation**. Si tu organización gestiona la cuenta, confirma que su política permite Skills y ejecución de código.
2. Descarga el [ZIP de la skill de cuenta](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip) y su [archivo SHA-256](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256).
3. Abre **Customize → Skills → + → Create skill → Upload a skill**, sube el ZIP y actívalo. Haz una copia de seguridad de una skill OpenSocrates existente antes de reemplazarla.
4. Añade la [instrucción de cuenta que se configura una sola vez](docs/setup-guide.md#claude-standing-instructions) a cada cuenta Claude que uses, conservando tus instrucciones actuales. Empieza una conversación nueva y describe tu tarea.

El ZIP de la skill portátil contiene todos los métodos y ejemplos.
[Guía visual de configuración](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Guía de Skills de Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Mac Apple Silicon</summary>

Necesitas [Node.js 20 o posterior](https://nodejs.org/en/download), la CLI de Claude
y una cuenta Claude con sesión iniciada. Funciona con Claude Code en la terminal
y Code local de Claude Desktop. Ejecuta en **Terminal**:

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

Confirma `enabled: true`, `integrity: verified` y `registration: confirmed`.
Revisa cualquier solicitud de confianza del proyecto y empieza una sesión local nueva.
[Guía visual de configuración](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Mac Apple Silicon o Windows x64</summary>

Necesitas [Node.js 20 o posterior](https://nodejs.org/en/download) y Codex. El entorno
nativo viene incluido en el paquete. Ejecuta en **Terminal en Mac** o **PowerShell en Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

Abre Codex interactivo y escribe `/hooks` en el campo de entrada. Revisa las siete
definiciones de hooks OpenSocrates y aprueba las que consideres de confianza;
después empieza una conversación nueva.
[Guía visual de configuración](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

Para actualizar una instalación Codex existente:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Mac Apple Silicon o Windows x64</summary>

Necesitas [Node.js 20 o posterior](https://nodejs.org/en/download). Elige una carpeta
de trabajo y sustituye el ejemplo por la ruta completa de una carpeta que ya
exista. Ejecuta en **Terminal en Mac** o **PowerShell en Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
```

En Windows, usa una ruta de unidad local entre comillas, como `"C:\Work\Reading Workshop"`.
Para una configuración global, omite `--workspace`. Elige instalación global o en
la carpeta de trabajo para un mismo proyecto y empieza una conversación nueva.
[Confirma la skill y la regla](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**¿Configuras con ayuda de un agente?** Usa la [solicitud de configuración](docs/setup-guide.md#ask-an-agent-to-finish-setup)
o la [guía de instalación actual](docs/agent-discovery.md). Selecciona cada aplicación
con su opción `--host`; el valor predeterminado y `--host all` seleccionan Codex.

<a id="a-method-for-the-question"></a>

## Un método para tu pregunta

| Tu tarea | Un método que explorar |
| --- | --- |
| Elegir entre opciones con prioridades contrapuestas | [Análisis de compensaciones](content/methods/trade-off-analysis/procedure.es.md) |
| Entender qué supuestos da por hechos un plan | [Mapeo de supuestos](content/methods/assumption-mapping/procedure.es.md) |
| Valorar el respaldo de una afirmación | [Pensamiento crítico](content/methods/critical-thinking/procedure.es.md) |
| Prepararse para lo que podría salir mal en un plan | [Análisis premortem](content/methods/premortem-analysis/procedure.es.md) |

Cada método incluye propósito, condiciones de uso, procedimiento completo,
ejemplos y preguntas para el asistente. Explora el texto, sigue los pasos de
razonamiento y reutiliza los métodos en tu trabajo.

[Explora los 48 métodos](content/methods/)

## El texto completo de los métodos en diez idiomas

Inglés, coreano, chino simplificado, japonés, francés, alemán, italiano, español,
portugués y tailandés. Cada idioma incluye los procedimientos y ejemplos
completos de los 48 métodos.

Son los idiomas del texto de los métodos que lee tu asistente.
[Guía de idiomas](docs/v1.5.2.md) · [Ajustes del idioma de instrucciones de Codex](docs/settings.md)

## Código abierto, listo para explorar

Lee los métodos completos y el código fuente, adáptalos a tu trabajo o aporta
un nuevo ejemplo. OpenSocrates es un proyecto independiente disponible bajo la
[licencia MIT](LICENSE).

[Versiones](https://github.com/ParkerHwang/OpenSocrates/releases) · [Guía de configuración](docs/setup-guide.md) · [Privacidad y seguridad](SECURITY.md) · [Contribuir](CONTRIBUTING.md) · [Incidencias](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Cambios](CHANGELOG.md)

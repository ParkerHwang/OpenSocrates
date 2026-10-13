## Purpose

Utiliza este procedimiento para identificar cómo podría fallar un proceso, producto o control previsto antes de confiar en él. Conecta modo de fallo con efecto, causa plausible, detección existente y control preventivo o detector. Produce prioridades ordinales y acciones con responsables, no puntuaciones falsas de riesgo. Hace visible la incertidumbre y enfoca primero consecuencias o controles débiles que merecen atención.

## Use when

Úsalo para lanzamientos, cambios de flujo, diseño de servicios, traspasos, barreras de seguridad, flujos de datos o funciones con secuencia y ámbito de fallo definidos. Sirve antes de comprometerse, tras cambios significativos o cuando incidentes recurrentes revelan fallos no examinados. Usa incidentes, pruebas, registros y conocimiento experto disponibles. Limita el análisis al proceso o componente describible y accionable.

## Do not use when

No sustituye respuesta de emergencia, revisión jurídica, análisis de peligros obligatorio de especialistas ni diagnóstico causal de incidentes ya recurrentes. No asignes números de gravedad, frecuencia o detectabilidad sin escala, calibración y fuente. Una lista larga no equivale a exhaustividad; no priorices fallos solo por ser fáciles de imaginar. Si se desconocen límite o función prevista, establécelos primero o suspende.

## Inputs to establish

Nombra proceso, producto o componente, límite, función, usuarios, condiciones operativas y controles actuales. Mapea pasos o interfaces principales e identifica peligros, restricciones, incidentes, pruebas y responsables conocidos. Define antes de clasificar el lenguaje ordinal, como urgente, relevante, vigilancia o baja atención, explicando qué significa cada etiqueta aquí. Haz como máximo dos preguntas capaces de cambiar prioridad, como qué fallo causa daño irreversible o qué control lo detectaría antes de publicar.

## Procedure

1. **Fija el límite.** Describe función, contexto operativo, interfaces y exclusiones; divide procesos grandes en secuencias manejables. **Resultado visible/cambio de estado:** límite y pasos con funciones o condiciones desconocidas no verificadas.
2. **Nombra fallos y efectos.** Por paso, indica qué puede salir mal y efecto inmediato, posterior, sobre usuarios o seguridad. Distingue modos para permitir controles diferentes. **Resultado visible/cambio de estado:** registro de fallos y efectos ligado a pasos.
3. **Traza causas y controles.** Registra causas plausibles, controles preventivos y detectores y evidencia de funcionamiento real. Separa fallos observados y posibilidades hipotéticas. **Resultado visible/cambio de estado:** causas y controles verificados, inferidos, supuestos o no verificados.
4. **Fija prioridad ordinal.** Aplica la regla cualitativa previa según consecuencia, exposición plausible y debilidad de control. Sin datos cuantitativos defendibles, no calcules productos ni números de prioridad de riesgo; compara en palabras. **Resultado visible/cambio de estado:** lista breve ordenada con motivos de urgencia, relevancia, vigilancia o baja atención.
5. **Asigna acciones de control.** Prefiere prevención que elimine causas, después detección antes del daño y finalmente contención del impacto. Nombra responsable, activador, evidencia de finalización e incertidumbre residual. **Resultado visible/cambio de estado:** plan de control por modo priorizado.
6. **Reevalúa tras cambiar.** Declara observación o prueba que mostraría menor exposición o mejor detección y qué reabriría el modo. **Resultado visible/cambio de estado:** evaluación respaldada, provisional o en suspenso y condición de cambio; no cierres un modo por planificar una acción.

## Public output contract

Devuelve límite, modos, efectos, causas, controles actuales, prioridad ordinal, responsable y señal de verificación. Indica si cada elemento relevante es observado, inferido, supuesto, no verificado o en conflicto. Nunca presentes puntuaciones inventadas de gravedad/frecuencia/detectabilidad ni clasificación precisa sin procedencia. La Conclusion Card puede resumir el fallo de máxima atención y condición de cambio; la traza contiene el registro completo.

## Evidence and uncertainty rules

Un fallo hipotético no es frecuencia observada. Documentar un control no demuestra eficacia; la evidencia debe mostrar funcionamiento, cobertura o prueba acotada. Separa consecuencia, probabilidad y detectabilidad. Usa lenguaje ordinal solo con definición local y fundamento declarado. Para umbrales vinculantes de seguridad o regulación, sigue el requisito autorizado y marca interpretaciones no verificadas. Si evaluaciones creíbles discrepan, marca prioridad conflicted y suspende el orden donde importe el conflicto.

## Stop conditions

Detente si no puede establecerse función, límite o condición operativa, un modo de alta consecuencia carece de contención segura o la clasificación depende de números inventados. Ante peligros inmediatos, sigue primero el proceso de incidentes o seguridad. Suspende recomendar publicar si un control decisivo no ha sido probado o asignado a un responsable.

## Complement handoff

Deriva a premortem-analysis si un plan elegido necesita una narración humana de fallo y alertas tempranas antes del compromiso. Transfiere plan acotado, modos priorizados, efectos y controles; el complemento añade escenarios plausibles sin convertir prioridades ordinales en falsa precisión.

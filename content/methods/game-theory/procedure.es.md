## Purpose

Utiliza este procedimiento si el resultado de una decisión depende de la respuesta de otro actor y el resultado de ese actor depende a su vez de la decisión. Hace visibles jugadores, acciones disponibles, incentivos, información, temporalidad y compromisos creíbles antes de recomendar un movimiento. No permite inventar matrices de beneficios, asignar probabilidades ni llamar equilibrio a resultados sin respaldo.

## Use when

Úsalo para movimientos competitivos, negociación, pujas, precios, entrada o disuasión, contratos, estándares compartidos y elecciones donde otra parte adapte estratégicamente su conducta. Sirve cuando falta preguntar qué harán si actuamos así o promesas, amenazas, reputación o ventajas informativas pueden cambiar el resultado. Declara interacción repetida y posibilidades de cooperación en lugar de asumirlas.

## Do not use when

No lo uses para optimización de un solo actor sin respuesta estratégica significativa, reglas vinculantes sin discreción, elecciones mecánicas ni supuestos rivales incapaces de afectar resultados. No reduzcas negociación a competición de suma cero sin evidencia. No infieras racionalidad, motivos ocultos ni beneficios numéricos por mera conveniencia aparente.

## Inputs to establish

Establece decisión focal, jugadores y derechos decisorios, acciones factibles, resultados valorados, información de cada jugador, orden de movimientos e interacción única o repetida. Registra compromisos creíbles, restricciones y conducta pasada solo con fuentes o aportaciones. Los beneficios pueden ser ordinales o cualitativos sin escala defendible. Haz como máximo dos preguntas breves, únicamente si un jugador, acción, incentivo, información o momento ausentes cambiarían el movimiento recomendado.

## Procedure

1. Publica decisión y registro de jugadores con quién actúa, quién resulta afectado y quién veta o retrasa. Marca funciones observadas, aportadas por el usuario, inferidas o supuestas; crea el límite visible del juego. Resultado visible/cambio de estado: límite publicado.
2. Publica acciones e información de cada jugador: opciones factibles, qué observa cada uno, movimientos simultáneos o secuenciales y repetición. Convierte competencia vaga en estructura especificada. Resultado visible/cambio de estado: estructura publicada.
3. Publica incentivos de resultados relevantes. Usa consecuencias con fuentes o del usuario, etiquetadas verified, computed, inferred, assumed, unverified o conflicted; conserva comparaciones ordinales sin beneficios exactos defendibles. Resultado visible/cambio de estado: incentivos publicados.
4. Publica comprobación de respuestas: compara mejores respuestas creíbles en simultáneo o razona hacia atrás desde la última decisión en secuencia. Si hay acción dominante respaldada, explica por qué; en otro caso muestra pares pertinentes sin fingir conocer todos los motivos. Resultado visible/cambio de estado: respuestas publicadas.
5. Publica resultados estables candidatos y si hay uno, varios o ninguno respaldado. Usa equilibrio solo con supuestos de acción, incentivos, información y momento suficientemente sustentados; en otro caso di condicional y qué falta. Resultado visible/cambio de estado: resultados publicados.
6. Publica palancas y movimiento recomendado. Explica si cambia incentivos, información, momento, acciones disponibles o credibilidad del compromiso y adjunta una señal observable de respuesta, haciendo accionable la estrategia. Resultado visible/cambio de estado: movimiento y señal publicados.
7. Publica conclusión, mayor incertidumbre y condición observable que invertiría el movimiento. Si falta beneficio, jugador o momento decisivos, publica suspensión y comprobación mínima que la levante sin elegir ganador ficticio. Resultado visible/cambio de estado: suspensión publicada.

## Public output contract

Devuelve un resultado compacto con `players`, `actions`, `incentives`, `information`, `timing`, `response_analysis`, `candidate_outcome`, `equilibrium_caveat`, `move` y `flip_condition`. Un resultado candidato no es automáticamente deseable, justo, eficiente ni inevitable. Decláralo respaldado, condicional, en conflicto o en suspenso. Usa etiquetas probatorias de tarjeta y resume movimientos o compromisos materialmente distintos como alternativas. No reveles transcripciones privadas de razonamiento.

## Evidence and uncertainty rules

Separa conducta observada de teorías sobre motivos. Afirmar beneficios requiere fuente, registro del usuario, cálculo reproducible o supuesto explícito, con fuente y alcance etiquetados. No inventes probabilidades, descuento, información oculta ni racionalidad. Un patrón estable significa que ningún cambio unilateral respaldado mejora el resultado bajo supuestos declarados; no demuestra deseabilidad social. Amenazas o promesas solo cuentan si el actor conservaría motivos para cumplirlas al llegar la decisión. Marca incentivos ausentes, contradictorios u obsoletos no verificados o en conflicto y reduce el respaldo.

## Stop conditions

Detente y haz una pregunta bloqueante si conjuntos plausibles de jugadores, acciones o momentos producen movimientos distintos y el propósito no permite elegir. Suspende sin incentivo, información o secuencia decisivos. Detente sin selección si no hay interdependencia estratégica significativa. Termina con estructura, respuesta condicional, movimiento, estado probatorio y señal de cambio públicos; no sigas calculando para crear falsa precisión.

## Complement handoff

Deriva a `stakeholder-analysis` solo si aparecen cuestiones relevantes de poder, consentimiento, legitimidad, apoyo de implementación o grupos afectados no representados. Transfiere jugadores, incentivos, conflictos, compromisos e incertidumbre pendiente. El complemento mapea actores y necesidades de participación sin repetir respuestas ni fabricar beneficios ausentes.

## Purpose

Utiliza este procedimiento si una brecha recurrente de resultados puede proceder de objetivos, reglas, valores, supuestos o estructura de autoridad que orientan la acción, no solo de ejecución. Separa la corrección de bucle simple dentro de la regla actual de un movimiento de doble bucle que cuestiona la regla misma. Produce una declaración rectora revisada y prueba segura de aprendizaje, no un veredicto sobre actitud o intención personales.

## Use when

Úsalo si el mismo problema retorna tras una corrección procedimental razonable, una política u objetivo crea repetidamente la conducta que después critica o rutinas defensivas impiden examinar premisas propias. Sirve para aprendizaje operativo, de producto o equipo acotado, con brecha observable entre expectativa y realidad y contexto suficiente para identificar la regla que orientó la acción.

## Do not use when

No lo uses si un defecto aislado de ejecución explica plenamente el fallo, la tarea es mecánica o debe seguirse una respuesta vinculante de seguridad, jurídica o normativa sin cuestionarla. No infieras intención de recurrencia ni uses «mentalidad» en lugar de evidencia. Si hay daño activo, aplica primero respuesta cualificada de incidentes o seguridad; el análisis de aprendizaje no debe retrasar la contención.

## Inputs to establish

Establece resultado esperado y observado, alcance y ventana de brecha, regla u objetivo vigente, correcciones previas de bucle simple y evidencia de recurrencia. Recoge objetivo, valor, supuesto, incentivo y autoridad que pudieron hacer razonable la regla. Nombra funciones afectadas sin culpar. Define prueba limitada y límite seguro para cambiar prácticas. Haz como máximo dos preguntas, solo si distinguen defectos de ejecución de problemas de variables rectoras; en otro caso etiqueta no verificado o supuesto.

## Procedure

1. **Publica la brecha.** Declara resultados esperado y observado, ventana, alcance, impacto y evidencia de recurrencia en un registro. Separa observaciones directas, relatos del usuario, registros comprobados e interpretaciones. **Resultado visible/cambio de estado:** estado de brecha.
2. **Publica la separación de bucle simple.** Registra la corrección que mejoraría ejecución conservando la regla y por qué recurrencia o efectos secundarios requieren revisión profunda. **Resultado visible/cambio de estado:** registro de brecha con acción de bucle simple y activador del doble.
3. **Publica variables rectoras.** Vincula acción a objetivo, valor, regla, supuesto, incentivo y autoridad decisoria. Etiqueta cada vínculo `verified`, `computed`, `inferred`, `assumed`, `unverified` o `conflicted`. **Resultado visible/cambio de estado:** mapa de variables rectoras.
4. **Publica reglas revisadas candidatas.** Compara cambios de regla u objetivo con beneficio, coste, función afectada y objeción pendiente. No clasifiques con probabilidades inventadas; conserva el conflicto si el propósito no elige una. **Resultado visible/cambio de estado:** registro de reglas revisadas.
5. **Publica prueba de aprendizaje.** Elige cambio práctico limitado y reversible con resultado observable, ventana, responsable, límite de detención y regla decisoria. No retires controles de seguridad ni expongas a daños evitables; la falta de autorización suspende la prueba. **Resultado visible/cambio de estado:** prueba o suspensión.
6. **Publica registro de aprendizaje.** Cuando haya evidencia, declara la regla respaldada, revisada, rechazada o en suspenso; registra siguiente comprobación segura y ubicación de memoria organizativa. Sin observación decisiva, publica una candidata provisional. **Resultado visible/cambio de estado:** estado de aprendizaje y comprobación siguiente.

## Public output contract

Devuelve `result_gap`, `governing_assumption_rule`, `evidence`, `revised_rule` y `learning_test` como campos para tarjeta. Muestra la acción de bucle simple aparte, sin presentar una corrección rutinaria como doble bucle. La regla revisada debe nombrar variable rectora cambiada, alcance, responsable e incertidumbre pendiente. La prueba debe indicar señal observable, límite seguro y regla decisoria. Es válido suspender si falta evidencia o autoridad para cambiar la regla.

## Evidence and uncertainty rules

La recurrencia respalda un patrón solo con eventos, alcance y comparación identificados; no demuestra que una regla cause todos los eventos. Distingue registros fechados, observaciones reproducibles y políticas explícitas de recuerdos o historias plausibles. No atribuyas la brecha a personas sin examinar regla, incentivo, autoridad, carga o controles. Usa relevancia ordinal solo con consecuencia decisoria declarada. No inventes probabilidades ni afirmes que una prueba breve demuestra teorías organizativas. Ante ramas creíbles contradictorias, muestra conflicto y suspende la conclusión de regla revisada.

## Stop conditions

Suspende sin brecha concreta de expectativa frente a realidad, patrón creíble de recurrencia o registros que distingan ejecución de efectos de regla. Suspende si regla o autoridad se desconocen y no pueden inferirse con seguridad. Detén el análisis si daño activo exige contención o la prueba debilita controles obligatorios, crea exposición evitable o cambios irreversibles. Si un defecto de ejecución explica el evento y no queda cuestión rectora, detente y deriva a un método enfocado de fallo o causa.

## Complement handoff

Deriva a `root-cause-analysis` cuando haga falta cadena causal completa, revisión de controles y responsable de prevención antes de cambiar la regla. Transfiere solo brecha, cronología relevante, vínculos de regla y control, estados probatorios conocidos y rama pendiente publicados. No transfieras culpa, deliberación oculta ni certeza causal inventada; no actives el complemento completo si la prueba ya responde la pregunta acotada de regla.

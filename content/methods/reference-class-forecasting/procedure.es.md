## Purpose

Usa este procedimiento para sustituir un pronóstico interno por una comparación externa fundada en casos terminados y comparables. Estima el objetivo desde resultados observados y explicita hechos actuales que justifican ajustes. Ayuda a calibrar; no es promesa ni permiso para inventar población, distribución o probabilidades.

## Use when

Úsalo para pronósticos de plazos, costes, demanda, adopción, fiabilidad o entregas si hay casos similares y el plan interno puede ser optimista. Es especialmente útil si se afirma «este caso es diferente» sin mostrar cómo cambia el intervalo esperado. Sirve para decisiones que necesitan un intervalo fundamentado, no una estimación puntual.

## Do not use when

No lo uses sin clase defendible de casos terminados, si objetivo o unidad no están claros o en casos únicos sin resultados comparables. Unas anécdotas no son distribución base. No selecciones solo éxitos ni conviertas pronósticos internos en evidencia. Detente y deriva tareas mecánicas o necesidades de diagnóstico causal.

## Inputs to establish

Establece resultado objetivo, unidad, horizonte, fecha de corte y límites aceptables. Define inclusión y exclusión antes de mirar resultados. Reúne casos, definiciones, cobertura, datos ausentes y fuentes. Registra diferencias actuales conocidas y pronóstico interno. Haz como máximo dos preguntas si cambiarían clase u objetivo. Etiqueta entradas verificadas, calculadas, inferidas, supuestas, no verificadas o contradictorias.

## Procedure

1. Publica objetivo, unidad, horizonte y límite decisorio en una frase. **Resultado visible/cambio de estado:** base del pronóstico; suspende objetivos ambiguos sin estrecharlos silenciosamente.
2. Publica regla de clase: inclusión, exclusión, similitud y vacíos de cobertura conocidos. **Resultado visible/cambio de estado:** intuición convertida en definición auditable.
3. Publica distribución solo de casos disponibles: cantidad, centro, dispersión, intervalo y colas cuando sean calculables. **Resultado visible/cambio de estado:** estadísticas con entradas, fuentes y evidencia; lo indisponible sigue no verificado.
4. Publica referencia externa junto al plan interno y explica dirección de diferencia. **Resultado visible/cambio de estado:** posición dentro, encima o debajo de la distribución, sin confundirla con probabilidad.
5. Publica ajustes por diferencias materiales, uno a uno. **Resultado visible/cambio de estado:** dirección, justificación y evidencia por ajuste; cifras solo con escala defendible.
6. Publica intervalo acotado y condiciones que hacen plausibles sus extremos. **Resultado visible/cambio de estado:** amplía o suspende si son débiles cobertura, selección o colas; no inventes tasas base.
7. Publica estado respaldado, provisional o suspendido, condición de cambio y una comprobación siguiente. **Resultado visible/cambio de estado:** falta de clase o dato decisivo explícitamente suspendida, no recomendación arbitraria.

## Public output contract

Devuelve `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition` y estado respaldado, provisional o suspendido. Di qué respalda la clase observada, sin asegurar que el caso actual coincida. Etiqueta fundamentos **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**. Expón falta de cobertura o sesgo de selección; la condición de cambio debe ser observable, no «si aparece información».

## Evidence and uncertainty rules

Solo respaldan la clase casos terminados con objetivo, unidad e inclusión definidos. Una fuente puede verificar resultados sin verificar comparabilidad actual: marca la comparación inferida salvo respaldo directo. Muestra casos o referencias y redondeo de cálculos. No inventes mediana, colas, muestra, tasa base ni probabilidad. Conserva sesgos de selección, casos ausentes, definiciones contradictorias y límites de muestras pequeñas. Diferencias declaradas siguen siendo hipótesis de ajuste hasta respaldarse dirección y efecto.

## Stop conditions

Haz una pregunta bloqueante y detente si objetivo, unidad o límite admiten interpretaciones materialmente distintas. Suspende sin clase, definición o entrada comparativa decisiva defendibles. Si solo quedan explicación causal, elección entre opciones o cálculo mecánico, deriva en vez de forzar un pronóstico externo.

## Complement handoff

Deriva a `sensitivity-analysis` si la decisión depende de cambios en distribución o ajuste actual. Transfiere objetivo, referencia observada, intervalos de ajustes probados, límites de cobertura y condición de cambio. El complemento debe variar entradas sin reconstruir la clase ni declarar una nueva tasa base.

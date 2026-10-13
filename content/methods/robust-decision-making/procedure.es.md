## Purpose

Usa este procedimiento para elegir una acción aceptable en varios futuros plausibles cuando ningún pronóstico merece controlar la decisión. Explicita incertidumbre, fracaso y compensaciones; separa un primer paso robusto de acciones que deben esperar señales. Robusto no significa óptimo en cada futuro, sino superar el mínimo declarado sin distribuciones de probabilidad inventadas.

## Use when

Úsalo para políticas, infraestructura, inversiones, productos u operaciones duraderos expuestos a incertidumbres que interactúan. Encaja si fracasar cuesta mucho, revertir es lento o los actores no acuerdan un pronóstico. Responde qué sobrevive a condiciones plausibles, más que qué resultado es más probable.

## Do not use when

No lo uses si un caso esperado es fiable y la elección barata y completamente reversible, ni si una regla vinculante deja una única acción. Evita catálogos arbitrarios de peores casos, supuesta superioridad universal u ocultar costes de robustez. Si no pueden definirse éxito y fracaso, aclara la decisión o establece criterios con un método de evidencia.

## Inputs to establish

Establece decisión, acciones viables, horizonte, actores y rendimiento mínimo aceptable. Define fracaso, arrepentimiento inaceptable y compensaciones materiales antes de probar. Enumera incertidumbres profundas, dependencias, restricciones y pocos mundos plausibles; no asignes probabilidades salvo fuente defendible del usuario. Registra reversibilidad, coste, momento y compromisos. Haz como máximo dos preguntas si cambiarían acciones o mínimo aceptable.

## Procedure

1. Publica marco, candidatos y criterios de aceptación. **Resultado visible/cambio de estado:** opciones acotadas y mínimo explícito de aceptación/fracaso.
2. Publica registro de incertidumbres y mundos distintos, internamente coherentes. **Resultado visible/cambio de estado:** conjunto visible de pruebas en vez de un pronóstico; mundos con supuestos y dependencias, no probabilidades.
3. Prueba cada acción en cada mundo según los criterios. **Resultado visible/cambio de estado:** matriz estrategia–mundo con estados aceptable, frágil o fallido y evidencia.
4. Publica condiciones de fracaso, exposición al arrepentimiento y grupos de mundos que tensionan una acción. **Resultado visible/cambio de estado:** vulnerabilidades y compensaciones identificadas, no escondidas en una puntuación global.
5. Publica acción robusta o menor conjunto que supere el mínimo en los mundos probados. **Resultado visible/cambio de estado:** recomendación separada de coste, oportunidad perdida y vulnerabilidad residual.
6. Publica salvaguardas, primeros pasos reversibles, acciones contingentes y señales con respuestas desencadenadas. **Resultado visible/cambio de estado:** decisión adaptativa, no apuesta única por un mundo preferido.
7. Publica estado respaldado, provisional o suspendido y condición observable de cambio. **Resultado visible/cambio de estado:** criterios o mundos decisivos ausentes implican suspensión, no robustez declarada.

## Public output contract

Devuelve `uncertainties`, `plausible_worlds`, `regret_or_failure_criteria`, `robust_action`, `tradeoffs`, `monitoring_signals`, `flip_condition` y estado respaldado, provisional o suspendido. Explica por qué supera el mínimo y dónde sigue frágil. La tarjeta muestra una conclusión, fundamentos etiquetados, incertidumbre pendiente y condición observable de cambio; las matrices detalladas pertenecen al registro o artefacto de apoyo.

## Evidence and uncertainty rules

Los mundos son pruebas estructuradas, no pronósticos ni muestras ponderadas por probabilidad. Fundamenta cada mundo material en observaciones, mecanismos defendibles, restricciones del usuario o supuestos explícitos. No inventes frecuencias, pérdidas esperadas, utilidades ni robustez universal. Aceptable remite al criterio publicado. Expón entradas y unidades de comparaciones calculadas; conserva conflictos sin promediarlos. Una acción robusta puede costar más o ofrecer menos beneficio: muestra esa compensación.

## Stop conditions

Haz una pregunta bloqueante y detente si acciones o rendimiento mínimo admiten interpretaciones materialmente distintas. Suspende si falta incertidumbre, umbral de fracaso o acción decisivos. Detente si basta un pronóstico fiable, una regla elimina discreción o quedan construcción de escenarios, verificación de evidencia o comparación ordinaria.

## Complement handoff

Deriva a `scenario-planning` cuando los mundos requieran estructura externa o narrativa de señales más deliberadas. Transfiere marco, incertidumbres, mínimo, grupos vulnerables y mundos actuales. El complemento debe enriquecer sin ocultar criterios de fracaso ni convertir mundos en probabilidades.

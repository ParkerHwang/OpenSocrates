## Purpose

Utiliza este procedimiento para actualizar la confianza en hipótesis rivales cuando llega nueva evidencia y pueden declararse responsablemente el fundamento previo y la dirección de la verosimilitud. Hace visibles tasas base, dirección probatoria, cambio posterior y sensibilidad. Las probabilidades exactas son opcionales; una actualización ordinal es honesta cuando los datos numéricos carecen de procedencia, pero una distribución posterior precisa debe mostrar datos y normalización.

## Use when

Úsalo para señales diagnósticas, interpretación de pruebas, evidencia secuencial, estimaciones de riesgo y decisiones donde una observación nueva deba cambiar la confianza en hipótesis rivales. Sirve para preguntar cuán probable es una hipótesis después de la evidencia, especialmente si hay riesgo de ignorar las tasas base.

## Do not use when

No lo uses sin fundamento previo defendible ni siquiera una dirección ordinal de cómo difiere la evidencia entre hipótesis, ni para aplicar una regla estricta. No confundas `P(E|H)` con `P(H|E)`, reutilices la misma evidencia como actualizaciones independientes ni inventes porcentajes exactos que creen falsa certeza.

## Inputs to establish

Establece hipótesis mutuamente excluyentes y suficientemente exhaustivas, la decisión actual, el fundamento previo o tasa base, evidencia nueva, dirección o valores de verosimilitud bajo cada hipótesis, dependencias entre evidencias y umbral de acción. Haz como máximo dos preguntas decisivas si una distribución previa o definición probatoria ausentes alteran la actualización; en otro caso usa una previa ordinal etiquetada.

## Procedure

1. Publica las hipótesis rivales y el umbral de decisión. Declara qué se actualiza y marca las hipótesis como aportadas por el usuario, respaldadas por fuentes o provisionales; así queda visible el estado de actualización.
2. Publica el fundamento previo de cada hipótesis, incluida fuente de tasa base, población de referencia o previa ordinal acotada. Si se desconocen las previas, muestra la incertidumbre sin elegir un número conveniente.
3. Publica cada evidencia y su dirección bajo todas las hipótesis: apoya, debilita o resulta básicamente neutral. Comprueba si las evidencias son independientes o reutilizan parcialmente la misma señal.
4. Publica el cambio posterior con aritmética exacta solo si los datos son defendibles; en otro caso declara una actualización cualitativa o intervalo. Muestra la normalización entre hipótesis rivales y conserva la dirección de previa a posterior.
5. Publica la sensibilidad a los supuestos de previa y verosimilitud. Identifica el cambio de valor o dirección que invertiría la clasificación o el cruce del umbral de acción.
6. Publica la hipótesis actualmente principal, el estado posterior y la siguiente evidencia que más mejoraría la decisión. Mantén visible una hipótesis plausible peor clasificada cuando siga siendo relevante.
7. Publica la conclusión actualizada y una condición observable de cambio. Si falta la previa o la dirección de verosimilitud, suspende el resultado o mantenlo provisional sin comunicar una posterior inventada.

## Public output contract

Devuelve `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold` y `flip_condition`. La tarjeta debe distinguir una posterior calculada de una actualización ordinal o inferida. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; una tasa base no queda verificada automáticamente por ser numérica.

## Evidence and uncertainty rules

La previa debe proceder de una tasa base defendible, estimación experta con procedencia o posterior anterior. La verosimilitud es `P(E|H)`, no la probabilidad de la hipótesis tras la evidencia. No actualices dos veces con evidencia dependiente. Si datos creíbles discrepan, muestra el conflicto y reduce el respaldo o suspende el resultado. Si la sensibilidad cruza el umbral de acción, declara que la decisión es frágil.

## Stop conditions

Detente y haz una pregunta bloqueante si falta el conjunto de hipótesis o la definición probatoria y diferentes elecciones invertirían la acción. Suspende cuando no exista una previa o dirección de verosimilitud defendible, o la dependencia impida una actualización fiable. Detente cuando la tarea real sea una regla estricta, buscar explicaciones o clasificar calidad de fuentes.

## Complement handoff

Deriva a `abduction` cuando lo pendiente sea generar y comparar explicaciones, no actualizar hipótesis definidas. Transfiere la evidencia observada, las hipótesis candidatas y la prueba discriminante. El complemento no debe repetir el cálculo posterior.

## Purpose

Utiliza este procedimiento para generalizar desde observaciones manteniendo una conclusión probabilística y limitada por la muestra. Identifica el tipo de inducción, comprueba tamaño, diversidad y representatividad, busca activamente contraejemplos y declara alcance y solidez de la generalización. Observaciones repetidas aumentan el respaldo solo si el fundamento de muestreo y medición justifica extenderlas.

## Use when

Úsalo para patrones de datos, encuestas, comentarios de usuarios, incidentes repetidos y afirmaciones que pasan de casos observados a poblaciones más amplias o conductas futuras. Sirve para generalizaciones estadísticas, enumerativas, causales o analógicas cuando se necesita saber hasta dónde las observaciones apoyan la afirmación.

## Do not use when

No lo uses para muestras de conveniencia no representativas, aplicación de reglas estrictas ni afirmaciones causales que requieren diseño causal y no extensión de patrones. No confundas muchas observaciones duplicadas con diversidad, infieras «todos» desde muestras pequeñas ni conviertas tendencias plausibles en conclusiones necesarias.

## Inputs to establish

Establece observaciones, población objetivo o alcance futuro, proceso de muestreo, definición de medición, grupos comparativos, ventana temporal y decisión afectada. Identifica tipo de inducción y sesgos conocidos de selección, supervivencia, no respuesta o medición. Haz como máximo una pregunta decisiva si población o fundamento de muestra son desconocidos y modifican el alcance.

## Procedure

1. Publica premisas observadas y generalización propuesta como afirmaciones separadas. Marca procedencia y estado probatorio de cada observación; crea la referencia visible de inducción.
2. Publica tipo —enumerativo, estadístico, causal o analógico— y puente entre muestra y alcance objetivo. Declara los supuestos que hacen plausible el puente.
3. Publica fundamento muestral: tamaño, diversidad, selección, casos ausentes, calidad de medición y cobertura temporal. Distingue descripción respaldada por fuentes de representatividad inferida.
4. Publica la búsqueda más sólida de contraejemplos y su resultado. Incluye casos no seleccionados, resultados negativos, diferencias entre subgrupos y excepciones futuras plausibles disponibles.
5. Publica generalización acotada con límite de alcance y solidez cualitativa como fuerte, moderada o débil. Sustituye redacción universal por población o intervalo proporcional solo si el intervalo tiene procedencia defendible.
6. Publica consecuencia decisoria y próxima observación que más mejoraría o cuestionaría la generalización. Declara si respalda actuar, vigilar o ampliar muestreo.
7. Publica conclusión actual y condición observable de cambio. Si la muestra es demasiado sesgada, escasa o inadecuada al objetivo, suspende o mantén provisional en lugar de extrapolar.

## Public output contract

Devuelve `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence` y `flip_condition`. Distingue casos observados de afirmación amplia. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; normalmente la generalización es inferida, no verificada directamente.

## Evidence and uncertainty rules

El tamaño muestral por sí solo no establece representatividad. Comprueba selección, cobertura, abandono, medición, equilibrio entre subgrupos y pertinencia temporal. Un contraejemplo limita afirmaciones universales sin demostrar la tendencia contraria. No reutilices una observación como apoyo independiente y prueba de contraejemplo a la vez. Sin fundamento muestral o alcance objetivo, reduce el respaldo o suspende la conclusión.

## Stop conditions

Detente y haz una pregunta bloqueante si no puede conocerse población objetivo o proceso de muestra y distintos alcances cambian la acción. Suspende ante muestra materialmente no representativa, afirmación causal que excede el diseño o riesgo decisivo de contraejemplo pendiente. Detente si la tarea es regla estricta, diagnóstico entre hipótesis rivales o comparación de calidad de fuentes.

## Complement handoff

Deriva a `evidence-hierarchy` si queda decidir si muestra o diseño merecen peso suficiente para la afirmación. Transfiere fundamento muestral, generalización, límite de alcance y riesgo principal de contraejemplo. El complemento no debe repetir la generalización.

## Purpose

Utiliza este procedimiento para ajustar una afirmación a calidad, carácter directo, aplicabilidad y riesgo de sesgo de sus fuentes. Clasifica el tipo de afirmación, compara diseños de estudio o evidencia sin tratar una jerarquía rígida como universal y declara estado probatorio y solidez resultantes. Una fuente de nivel inferior puede ser útil si encaja directamente con la pregunta y diseños más fuertes no lo hacen.

## Use when

Úsalo al mezclar investigación, políticas, experimentos de producto, opiniones expertas, relatos de usuarios u otra evidencia y necesitar una etiqueta de solidez defendible. Sirve para determinar si las fuentes apoyan una afirmación, un estudio se aplica al contexto objetivo o debe cambiar la redacción según la calidad probatoria.

## Do not use when

No lo uses si domina una preferencia de valores y no respaldo factual, o si reglas formales, modelos causales o métodos de conflicto de fuentes son más específicos. No clasifiques por prestigio solamente, descartes automáticamente evidencia pertinente de nivel inferior ni llames fuerte a una fuente sin comprobar carácter directo y límites.

## Inputs to establish

Establece afirmación, población o contexto objetivo, tipo —efecto, pronóstico, mecanismo o experiencia—, umbral decisorio, fuentes, diseños, muestras, medidas y conflictos conocidos. Identifica fuentes directas, indirectas o solo contextuales. Haz como máximo una pregunta decisiva si el contexto objetivo cambia la aplicabilidad.

## Procedure

1. Publica afirmación, contexto objetivo y umbral decisorio. Declara si trata efecto, predicción, mecanismo o experiencia; así queda visible la revisión probatoria.
2. Publica una tabla de afirmaciones y fuentes con tipo, diseño, muestra o fundamento, carácter directo y alcance. Marca cada fuente comprobada, aportada por el usuario, inferida o no disponible.
3. Publica dimensiones de calidad —rigor de diseño, riesgo de sesgo, validez de medición, integridad y aplicabilidad— con etiquetas cualitativas u ordinales con procedencia. No inventes una puntuación compuesta precisa.
4. Publica posición jerárquica y límites de cada fuente. Explica por qué es fuerte o débil para esta afirmación particular, sin convertir su posición en autoridad universal.
5. Publica acuerdos, inconsistencias y evidencia ausente entre fuentes. Mantén visible el conflicto creíble; no promedies resultados incompatibles sin una regla de síntesis justificada.
6. Publica estado probatorio y conclusión calibrada: fuertemente respaldada, respaldada, provisional, no verificada, en conflicto o en suspenso. Declara la menor limitación de fuente o aplicabilidad que restringe la redacción.
7. Publica siguiente acción verificadora y condición observable de cambio. Si falta apoyo decisivo, suspende o reduce el respaldo sin presentar una conclusión de alto riesgo como establecida.

## Public output contract

Devuelve `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion` y `flip_condition`. La tarjeta debe mostrar estado probatorio y enlace seguro de fuente o etiqueta de aportación del usuario cuando corresponda. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

La jerarquía de diseños orienta, pero no sustituye la adecuación a la pregunta. Comprueba carácter directo, población, resultado, tiempo, medición, selección, abandono y sesgo de comunicación. Una opinión experta puede identificar mecanismos sin estimar magnitudes; un relato puede mostrar experiencia sin establecer prevalencia. Si las fuentes discrepan materialmente o la mejor es indirecta, reduce el respaldo o suspende e indica la limitación.

## Stop conditions

Detente y haz una pregunta bloqueante si contexto o afirmación no están definidos y la aplicabilidad cambiaría la decisión. Suspende si ninguna fuente apoya directamente una afirmación relevante, no se resuelve el conflicto o los límites impiden una etiqueta de solidez segura. Detente cuando la cuestión sea elegir valores, implicación formal o generar explicaciones, no calibrar evidencia.

## Complement handoff

Deriva a `triangulation` cuando vías independientes de evidencia puedan corroborar o revelar un conflicto relevante. Transfiere tabla de afirmaciones y fuentes, límites de calidad y desacuerdo pendiente. El complemento debe comprobar independencia y convergencia sin reconstruir clasificaciones.

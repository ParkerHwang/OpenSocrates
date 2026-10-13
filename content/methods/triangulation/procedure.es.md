## Purpose

Usa este procedimiento para comparar líneas independientes de evidencia y evitar que una fuente, método, teoría o investigador reciba más confianza de la merecida. Define afirmación y evidencia necesaria, comprueba independencia en vez de contar citas y comunica convergencia, conflicto y vacíos. El acuerdo solo informa si las líneas difieren significativamente y responden a la misma afirmación.

## Use when

Úsalo si una fuente o método podría tener sesgo, se combinan pruebas cualitativas y cuantitativas o partes interesadas aportan relatos rivales. Encaja en verificación importante, evaluación de programas, síntesis investigadora y decisiones donde corroboración o conflicto cambiarían la acción.

## Do not use when

No lo uses si todas las fuentes repiten datos únicos, se trata de preferencias de valor o decide una regla formal directa. No cuentes copias de un informe como independientes, promedies conflictos para borrarlos ni recojas líneas sobre afirmaciones distintas sin declarar la discrepancia.

## Inputs to establish

Establece afirmación focal, decisión, tipos de evidencia necesarios, líneas candidatas, fuentes comunes previas, métodos, investigadores, periodos y sesgos. Elige diversidad de datos, método, teoría o investigador y justifica su utilidad. Haz como máximo una pregunta decisiva si afirmación o límites de independencia no están claros.

## Procedure

1. Publica afirmación y decisión que cambiaría. Indica evidencia necesaria y alcance; fija estado visible de corroboración.
2. Publica cada línea con origen de datos, método, investigador, población, tiempo y sesgo esperado. Marca entradas proporcionadas por usuario, comprobadas, inferidas o indisponibles.
3. Publica comprobación de independencia: datos, medición, institución o modelo compartidos, o fuentes realmente separadas. Diversidad metodológica no implica independencia si hereda los mismos datos brutos.
4. Publica resultado frente a la misma afirmación: converge, choca o no responde. Indica dirección y importancia, sin contar votos.
5. Publica vacíos y explicaciones plausibles del conflicto por alcance, tiempo, medición, selección o análisis. Mantén explicaciones rivales hasta resolverlas con comprobación.
6. Publica estado combinado y conclusión calibrada. Acuerdo puede fortalecer respaldo; conflicto material rebaja o suspende salvo regla justificada de prioridad o alcance.
7. Publica siguiente comprobación independiente y condición observable de cambio. Sin independencia o afirmación común, declara insuficiente triangulación, no corroboración falsa.

## Public output contract

Devuelve `focal_claim`, `evidence_needed`, `evidence_streams`, `independence_check`, `stream_results`, `agreement_conflict`, `agreement_conflict_gap`, `combined_evidence_state`, `calibrated_conclusion` y `flip_condition`. La tarjeta resume convergencia o conflicto e identifica enlaces de fuentes o etiquetas seguras de información del usuario. Usa **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted** para fundamentos.

## Evidence and uncertainty rules

Independencia trata de datos, medición, incentivos y origen analítico compartidos, no cantidad de citas. Una línea que no responde es un vacío, no evidencia negativa. Acuerdo dependiente no justifica corroboración fuerte. Conserva conflictos materiales y suspende o rebaja hasta justificar alcance, calidad o precedencia.

## Stop conditions

Detente y haz una pregunta bloqueante si no se define afirmación o independencia. Suspende si todas las líneas comparten fuente no verificada, hay conflicto material irresuelto o responden preguntas diferentes. Detente si solo queda ordenar fuentes, elegir valores o deducir formalmente.

## Complement handoff

Deriva a `evidence-hierarchy` si la disputa restante es calidad, diseño o aplicabilidad de líneas individuales. Transfiere inventario, veredicto de independencia, convergencia/conflicto y comprobación ausente. El complemento no debe inferir independencia del número de fuentes.

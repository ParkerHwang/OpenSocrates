## Purpose

Utiliza este procedimiento para convertir un término ambiguo o disputado en una definición decisoria utilizable, sin fingir que una entrada de diccionario resuelve la cuestión. Separa significados rivales, contrasta condiciones candidatas con ejemplos y casos límite, y registra qué se sigue del significado operativo elegido. El resultado apoya una acción, medición o política manteniendo visible la ambigüedad residual.

## Use when

Úsalo cuando términos como seguro, justo, calidad, listo, fiable, sostenible o exitoso sostienen la decisión y distintas personas pueden entenderlos de modo diferente. Sirve para políticas, requisitos de producto, criterios de evaluación, contratos, investigación y desacuerdos parcialmente semánticos. También es útil antes de mapear argumentos cuando una palabra compartida oculta afirmaciones diferentes.

## Do not use when

No lo uses si el término ya tiene una definición operativa estable en una especificación autorizada y solo falta aplicarla o verificarla. No resuelvas disputas fácticas reescribiendo definiciones ni trates un juicio moral preferido como esencia descubierta. Una definición no sustituye la evidencia de que un caso la cumpla.

## Inputs to establish

Establece término objetivo, decisión o medición que controla, hablante o documento que lo usa y contexto relevante. Recoge pocos casos positivos claros, negativos claros y hasta tres casos límite. Registra definiciones autorizadas, preferencias del usuario y consecuencias prácticas. Haz como máximo dos preguntas, únicamente si no puede acotarse de otro modo el contexto previsto o uso decisorio.

## Procedure

1. Publica en una frase el concepto, contexto y decisión controlada. Marca si el contexto procede del usuario, documento rector o supuesto; así queda visible el análisis.
2. Publica entre dos y cuatro significados rivales, cada uno con fuente o hablante y resultado permitido. No fusiones usos distintos solo por compartir palabra.
3. Publica casos positivos y negativos claros y muestra cómo clasifica cada significado cada caso. Esto revela si el desacuerdo es semántico, factual o ambos.
4. Publica por separado condiciones necesarias y suficientes candidatas. Declara cada condición respaldada, propuesta o no verificada; nunca trates una condición plausible como establecida.
5. Publica pruebas de límite y contraejemplos. Muestra el caso que más amenaza el significado elegido y si debe estrecharse la regla, ampliarse o dejarse sin resolver.
6. Publica un significado operativo, su alcance, exclusiones y ambigüedad residual. Declara su consecuencia para la decisión, medición o requisito y explicita el cambio de estado resultante.
7. Publica el vínculo entre concepto y decisión y una condición observable de cambio. Si ninguna definición clasifica fiablemente el caso decisivo, suspende el juicio sin elegir una etiqueta por conveniencia.

## Public output contract

Devuelve `concept`, `competing_meanings`, `chosen_operational_meaning`, `necessary_conditions`, `sufficient_conditions`, `boundary_cases`, `residual_ambiguity`, `consequence`, `decision_consequence` y `flip_condition`. La conclusión debe indicar qué permite o excluye el significado elegido, sin atribuir al concepto una esencia eterna. Conserva como máximo tres supuestos relevantes y dos incertidumbres pendientes. Los fundamentos de tarjeta usan **verified**, **inferred**, **assumed**, **unverified** o **conflicted**; los ejemplos son evidencia solo cuando se declara su procedencia y relevancia.

## Evidence and uncertainty rules

Una definición autorizada apoya el uso de un término, no que el mundo la satisfaga. Distingue definición respaldada por fuente, convención elegida por el usuario y operacionalización propuesta. Un caso límite no clasificable no demuestra que tenga razón ninguna parte; evidencia ambigüedad residual. Si significados rivales conducen a acciones distintas de alto riesgo, revela el conflicto y reduce el respaldo o suspende hasta seleccionar un contexto autorizado.

## Stop conditions

Detente y haz una pregunta bloqueante si el contexto objetivo es incompatible entre lecturas plausibles y la decisión no puede acotarse con seguridad. Suspende si el caso decisivo sigue sin clasificarse o falta evidencia necesaria para aplicar el significado operativo. Detente si el término es estable, la disputa factual y otro método puede tratar la evidencia restante.

## Complement handoff

Deriva a `argument-mapping` cuando el significado elegido revele afirmaciones rivales, premisas compartidas u objeciones que necesitan separación estructural. Transfiere únicamente significado operativo elegido, caso límite relevante y consecuencia pendiente. El complemento no debe repetir el inventario completo de definiciones.

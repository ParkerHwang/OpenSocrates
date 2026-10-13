## Purpose

Utiliza este procedimiento para comparar explicaciones rivales de un hecho observado o sorprendente y elegir la mejor explicación actual sin presentarla como demostrada. Requiere al menos dos candidatas vigentes, evalúa su adecuación explicativa y sus riesgos, e identifica evidencia capaz de distinguirlas. El resultado es un diagnóstico provisional con una comprobación siguiente concreta, no un permiso para adaptar los hechos a una historia preferida.

## Use when

Úsalo para depuración, diagnóstico, investigación, interpretación de anomalías y otras situaciones donde varias causas podrían explicar una misma observación. Sirve con información incompleta y preguntas sobre qué es más probable que esté ocurriendo o por qué surgió un resultado inesperado. Úsalo cuando una regla deductiva no resuelva ya el resultado.

## Do not use when

No lo uses cuando reglas explícitas y premisas establecidas impliquen la conclusión, ni cuando ninguna observación permita distinguir las explicaciones. Una sola candidata no constituye un conjunto de explicaciones. No puntúes una historia con precisión inventada ni trates la ausencia de observaciones contrarias como confirmación. Evita afirmar certeza causal cuando las candidatas sean únicamente interpretaciones descriptivas.

## Inputs to establish

Establece la observación sorprendente, la referencia esperada, la decisión o diagnóstico afectado, los hechos conocidos, las explicaciones plausibles y las pruebas o fuentes disponibles. Identifica si cada candidata propone una causa, un mecanismo, un error de datos o una explicación del alcance. Haz como máximo una pregunta decisiva si la observación o el objetivo de la decisión no están claros; en otro caso, procede declarando los supuestos.

## Procedure

1. Publica la observación que necesita explicación y la referencia que contradice. Identifica las partes que son hechos comprobados, relatos del usuario o supuestos; así queda visible el estado de la anomalía.
2. Publica al menos dos explicaciones candidatas con sus observaciones previstas y su alcance. Añade una explicación de error de medición, selección o comunicación cuando sea plausible, sin adoptar por defecto la primera historia sustantiva.
3. Publica una comparación cualitativa de adecuación explicativa, cobertura, simplicidad, coherencia con el conocimiento establecido y posibilidad de prueba. Usa categorías ordinales como fuerte, moderada, débil o desconocida; no inventes probabilidades.
4. Publica evidencia discriminante: la observación, experimento o fuente que separaría las principales candidatas. Indica qué resultado reforzaría, debilitaría o dejaría sin cambios cada una.
5. Publica la mejor explicación actual y por qué encabeza la comparación, con estado provisional. Mantén visibles las alternativas e indica si el resultado es un diagnóstico, una hipótesis de trabajo o un conjunto sin resolver.
6. Publica la siguiente acción de verificación y el modo de fallo relevante, incluido qué demostraría que la explicación es errónea o que el vínculo con la evidencia no es fiable.
7. Publica la conclusión actual, las candidatas y una condición observable de cambio. Si ninguna candidata dispone de apoyo discriminante o falta una observación decisiva, deja el resultado en suspenso en lugar de elegir la narración más llamativa.

## Public output contract

Devuelve `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test` y `flip_condition`. La primera línea debe decir «mejor explicación actual» o equivalente cuando el resultado sea provisional. Etiqueta los fundamentos como **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; la adecuación de una candidata es una inferencia, no una prueba directa.

## Evidence and uncertainty rules

Un hecho sorprendente puede motivar una hipótesis, pero no establece su causa. Exige apoyo independiente o discriminante antes de elevar el estado de una candidata. Evita contar la misma observación varias veces mediante distintos criterios. Si varias candidatas encajan por igual, comunica la competencia sin resolver. Si una prueba relevante no está disponible, conserva la explicación como provisional o en suspenso e indica la evidencia ausente.

## Stop conditions

Detente y haz una pregunta bloqueante cuando la observación o el objetivo sean demasiado vagos para identificar explicaciones candidatas. Deja el resultado en suspenso cuando solo haya una candidata, no exista una implicación comprobable o falte evidencia decisiva. Detente cuando premisas explícitas impliquen el resultado o lo restante sea calidad de fuentes, validez formal o comparación de opciones.

## Complement handoff

Deriva a `value-of-information` cuando la decisión principal sea comprar, recopilar o esperar información discriminante. Transfiere las candidatas, la evidencia que cambiaría la decisión y el coste o retraso de la siguiente prueba. El complemento no debe repetir la comparación de explicaciones.

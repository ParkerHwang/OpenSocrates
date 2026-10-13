## Purpose

Utiliza este procedimiento para probar si una regla, coste, flujo o arquitectura familiares son realmente necesarios o meramente heredados. Descompón el problema en afirmaciones y restricciones, verifica cada una y reconstruye una opción desde las que sobrevivan. Protege tanto de copiar sin fundamento como de reducir temerariamente: una restricción no se descarta por resultar incómoda y una posibilidad física no es automáticamente un plan viable.

## Use when

Úsalo cuando «así se hace», convenciones sectoriales, dependencias históricas o costes supuestos bloqueen rediseños de gran impacto. Sirve para precios, arquitectura de producto, procesos operativos, asignación de recursos y requisitos cuya base se quiere cuestionar. Es útil si opciones obsoletas parecen heredar supuestos ya inválidos.

## Do not use when

No lo uses para ejecutar procedimientos estándar validados ni descartar reglas vinculantes, restricciones de seguridad, obligaciones jurídicas o interfaces externas fijas. No trates preferencias, presupuestos, plazos o coordinación social como hechos puramente físicos. No prometas rediseños desde supuestos no verificados ni omitas restricciones de implementación tras descomponer.

## Inputs to establish

Establece resultado objetivo, enfoque actual, requisitos declarados, restricciones, recursos, dependencias y motivo por el que se cree necesario el enfoque. Separa restricciones duras, negociables, convenciones y desconocidos. Haz como máximo dos preguntas decisivas, solo si cambian la reconstrucción. Identifica reglas de alto riesgo que deban mantenerse vigentes.

## Procedure

1. Publica en una frase resultado y enfoque actual, luego límite y medida de éxito. Crea una referencia visible para comparar con la reconstrucción.
2. Publica una descomposición en requisitos atómicos, dependencias y restricciones afirmadas. Marca cada elemento aportado por usuario, respaldado por fuente, inferido o supuesto; cambia el estado de «dado» a «por verificar».
3. Publica el veredicto de necesidad de cada restricción: necesaria física o lógicamente, vinculante externamente, contingente, basada en preferencia o no verificada. Adjunta prueba o fuente que lo respalda.
4. Publica las restricciones supervivientes y retira solo supuestos que no superaron verificación. Si un elemento disputado afecta materialmente seguridad, legalidad o factibilidad, mantenlo como restricción pendiente explícita sin eliminarlo silenciosamente.
5. Publica una reconstrucción desde las restricciones supervivientes. Declara implicaciones de recursos, tiempo, dependencias y coordinación para que no sea solo imaginable físicamente.
6. Publica diferencias frente al enfoque convencional: qué cambia, supuesto habilitante y nuevo riesgo o intercambio. Añade una pequeña validación por cada requisito no verificado.
7. Publica requisitos derivados, opción reconstruida y condición observable de cambio. Si falta una restricción irreductible o dato decisivo, concluye provisionalmente o en suspenso sin proclamar un avance extraordinario.

## Public output contract

Devuelve `irreducible_constraints`, `derived_requirements`, `reconstructed_option`, `assumptions_reintroduced`, `reintroduced_assumptions`, `conventional_delta`, `new_risks` y `flip_condition`. La primera línea declara rediseño respaldado, provisional o en suspenso. Distingue opciones físicamente posibles de las que cumplen coste, tiempo, seguridad y gobernanza del usuario. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; no presentes convenciones sin etiqueta como evidencia.

## Evidence and uncertainty rules

«Necesario» requiere fundamento lógico, físico, contractual, de seguridad u otro nombrado; la incomodidad no demuestra necesidad. Una fuente sobre práctica común apoya prevalencia, no inevitabilidad. Los cálculos deben declarar datos y unidades. Si la reconstrucción depende de vínculos no verificados, puede ser hipótesis acotada, no recomendación fuertemente respaldada. Conserva conflictos sin promediar restricciones incompatibles.

## Stop conditions

Detente y haz una pregunta bloqueante si resultado o límites no negociables de seguridad o legalidad están poco claros y las respuestas producirían reconstrucciones distintas. Suspende si no puede establecerse una restricción irreductible o dato requerido. Detén el método cuando todas las restricciones relevantes sean externas fijas o solo reste comparar opciones, verificar evidencia o implementar.

## Complement handoff

Deriva a `morphological-analysis` si los requisitos supervivientes varían en varias dimensiones coherentes y sigue explorar combinaciones. Transfiere requisitos derivados, restricciones conservadas y exclusiones de factibilidad. El complemento no debe repetir descomposición ni rediscutir los supuestos retirados.

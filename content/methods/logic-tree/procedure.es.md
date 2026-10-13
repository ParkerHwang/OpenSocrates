## Purpose

Usa este procedimiento para descomponer una pregunta amplia de diagnóstico, planificación o cobertura en una jerarquía con ramas mutuamente claras, cobertura colectivamente adecuada y hojas accionables. Selecciona un eje por nivel, separa árboles de porqués y de cómos y asigna una comprobación o acción a cada rama terminal. El árbol estructura la búsqueda; no demuestra que todas sus ramas sean verdaderas.

## Use when

Úsalo cuando el problema sea amplio, las causas no estén claras, un plan necesite cobertura o una pregunta de por qué, cómo o qué necesite estructura exhaustiva. Sirve para diagnóstico, cobertura de riesgos, requisitos y exploración de soluciones cuando los solapamientos duplicarían responsables o dejarían trabajo sin atender.

## Do not use when

No lo uses para bucles de retroalimentación estrechamente acoplados que una jerarquía no represente responsablemente, ni si basta una lista o un cálculo directo. No mezcles causas y soluciones al mismo nivel, no ocultes vacíos materiales bajo «otros» ni sigas subdividiendo una rama cuya acción siguiente ya está clara.

## Inputs to establish

Establece pregunta raíz, tipo de árbol (`why`, `how` o `what`), medida de éxito, alcance, hechos conocidos y comprobaciones disponibles. Elige y justifica el eje del primer nivel. Haz como máximo una pregunta decisiva si la raíz o el tipo cambiarían el análisis; en otro caso formula una raíz acotada.

## Procedure

1. Publica una pregunta raíz medible y el tipo elegido. Expón alcance y medida de éxito para establecer el estado inicial visible.
2. Publica ramas del primer nivel con un único eje y etiquétalo. Indica si cada rama es observada, inferida o candidata que requiere verificación.
3. Publica otro nivel solo cuando una división más fina cambie una acción o prueba. Muestra en cada nivel las comprobaciones de exclusión mutua y cobertura como actualización de estado.
4. Publica las hojas con una comprobación, solicitud de datos, responsable o acción siguiente para cada una. Una hoja abstracta no es terminal: mantén abierto el árbol o reduce la raíz.
5. Publica ramas podadas y motivos, como evidencia contradictoria, exclusión del alcance o cobertura duplicada. No elimines una rama solo porque resulte incómoda.
6. Publica prioridades basadas en importancia material, evidencia y capacidad de actuar, sin precisión numérica inventada. Marca ramas que necesiten otro método causal o de evidencia.
7. Publica árbol completo, vacíos de cobertura y condición observable de cambio. Si una rama crítica no admite prueba ni delimitación, suspende el juicio o haz una pregunta bloqueante.

## Public output contract

Devuelve `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order` y `flip_condition`. El resultado debe mostrar ramas claras entre sí, cobertura colectivamente pertinente y hojas ejecutables. Usa etiquetas **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted** para los fundamentos de la tarjeta. El árbol no constituye por sí mismo prueba causal.

## Evidence and uncertainty rules

Exclusión mutua (ME) y exhaustividad colectiva (CE) son comprobaciones separadas: ausencia de solapamiento no implica cobertura y cobertura no implica ausencia de solapamiento. Una fórmula conocida es una estructura candidata hasta que sus supuestos encajen en el dominio. La evidencia o prueba de cada hoja debe identificarse; las ramas sin respaldo siguen siendo hipótesis. Declara vacíos si hay conflicto o si una rama ausente podría cambiar la decisión, y suspende o rebaja la conclusión.

## Stop conditions

Detente y haz una pregunta bloqueante si no puedes delimitar raíz o tipo y las alternativas conducirían a trabajos diferentes. Suspende si un vacío material no tiene prueba o la interdependencia haría engañosa la jerarquía. Detente cuando las hojas tengan acciones claras y el resto corresponda a métodos causales, de evidencia o de decisión.

## Complement handoff

Deriva a `root-cause-analysis` si la rama seleccionada aborda un fallo recurrente y requiere una cadena causal en vez de más descomposición. Transfiere raíz, rama, vacíos de evidencia y pruebas de hojas. El complemento no debe reconstruir ramas ajenas.

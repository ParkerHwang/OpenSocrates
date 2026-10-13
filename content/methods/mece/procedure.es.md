## Purpose

Usa este procedimiento para comprobar si una clasificación o descomposición es mutuamente excluyente y colectivamente exhaustiva en el mismo nivel. Fija un eje, comprueba por separado solapamientos y vacíos y mantén una granularidad uniforme. El resultado es una regla defendible con casos fronterizos conocidos, no una promesa de que todas las categorías reales sean naturalmente nítidas.

## Use when

Úsalo si categorías, grupos de responsabilidad, opciones, requisitos, causas o ramas duplican u omiten casos materiales. Sirve para revisar una clasificación existente y como comprobación específica dentro de un árbol lógico o una estructura ejecutiva. Aplícalo cuando la regla clasificatoria, y no una fuente factual, sea el obstáculo de la decisión.

## Do not use when

No lo uses si se estudia precisamente el solapamiento natural, si las categorías representan intencionadamente distintos ejes o si solo hay que aplicar una taxonomía vinculante. No mezcles edad, geografía, intención y fase del proceso en un nivel. No ocultes una clase ausente importante bajo «otros» ni fuerces exclusividad falsa donde la pertenencia sea realmente multietiqueta.

## Inputs to establish

Establece universo, propósito de la decisión, categorías candidatas, único eje propuesto, reglas de inclusión y exclusión y casos fronterizos conocidos. Indica si se admite una etiqueta o varias. Haz como máximo una pregunta si universo o propósito son materialmente ambiguos; en otro caso define un universo acotado.

## Procedure

1. Publica universo, propósito y único eje en una frase. Esto fija el estado visible e impide mezclar criterios.
2. Publica cada categoría candidata con una regla de inclusión y otra de exclusión. Marca límites explícitos, inferidos o no verificados.
3. Publica la prueba de exclusión mutua con casos plausibles que encajen en dos categorías. Ante cada solapamiento fusiona, redelimita o permite explícitamente multietiquetas; registra el cambio.
4. Publica la prueba de cobertura colectiva con casos extremos y observaciones conocidas. Añade una categoría solo si el caso ausente pertenece al universo declarado; si no, reduce el universo y declara la exclusión.
5. Publica la comprobación de granularidad: compara abstracción, tamaño y utilidad decisoria. Revisa categorías que sean subcategorías ocultas de otras o demasiado amplias para actuar.
6. Publica casos fronterizos, regla final y solapamientos pendientes intencionados. No uses un grupo «otros» vago para una parte material del universo.
7. Publica clasificación, veredicto de solapamientos y vacíos, y condición observable de cambio. Suspende la clasificación si el eje no permite decidir o un caso importante queda sin clasificar; no fuerces etiquetas.

## Public output contract

Devuelve `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases` y `flip_condition`. Distingue ME de CE e indica clasificación de etiqueta única o múltiple. Etiqueta fundamentos como **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; las categorías no prueban prevalencia.

## Evidence and uncertainty rules

ME y CE son pruebas lógicas de cobertura, no demostración empírica de utilidad. Un ejemplo puede revelar solapamientos o vacíos sin mostrar su frecuencia. Separa observaciones respaldadas por fuentes de elecciones de diseño. Si falta una categoría material, queda un caso disputado o el eje cambia la decisión, marca el resultado provisional o suspendido.

## Stop conditions

Detente y haz una pregunta bloqueante si no puedes delimitar universo o propósito. Suspende si el eje no representa casos materiales sin solapamientos engañosos o si una categoría ausente cambia la decisión. Detente cuando la regla supere ME/CE en el alcance necesario y el trabajo restante corresponda a descomposición estructural o comparación.

## Complement handoff

Deriva a `logic-tree` si las categorías validadas son el primer nivel de un diagnóstico o plan más amplio y necesitan ramas recursivas y pruebas en las hojas. Transfiere universo, eje, categorías finales, casos fronterizos y veredicto de cobertura. El complemento no debe repetir MECE en ese nivel.

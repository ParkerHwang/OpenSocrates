## Purpose

Utiliza este procedimiento para representar una decisión temporal, donde una acción cambia las posibilidades siguientes y eventos inciertos conducen a elecciones posteriores. Separa nodos de decisión, azar y resultado para hacer trazable la recomendación a la información. Puede usar evaluación aritmética hacia atrás si valores y probabilidades están acotados, pero debe suspender el resultado antes que fabricar precisión en ramas sin apoyo.

## Use when

Úsalo para lanzamientos por etapas, piloto frente a expansión, plazos de mantenimiento o sustitución, esperar una prueba y decisiones con ramas condicionales. Sirve cuando importa el orden de acciones, las decisiones posteriores dependen de observaciones y los resultados tienen valores respaldados por fuentes o consecuencias cualitativas claramente etiquetadas. Resulta útil para elegir una estrategia disponible tras nueva información, no meramente la opción mejor puntuada ahora.

## Do not use when

No lo uses para comparaciones estáticas sin secuencia o azar significativos, diagramas mecánicos ni reglas vinculantes sin discreción. No dibujes ramas independientes para eventos con causa compartida o dependencia de resultados anteriores. No calcules valor esperado sin acotar probabilidades, valores finales o acciones condicionales. Si la incertidumbre es profunda y los futuros externos coherentes importan más que la aritmética de ramas, deriva a scenario-planning.

## Inputs to establish

Declara punto decisorio, acciones, momentos de observación, eventos de azar, resultados finales, puntos de reversión y persona o sistema que puede actuar en cada nodo. Registra procedencia probabilística, unidades, temporalidad, costes, beneficios y dependencias. Marca probabilidades como verificadas, calculadas de datos declarados, inferidas, supuestas, no verificadas o en conflicto. Haz como máximo dos preguntas decisivas: qué observación cambia la próxima acción disponible y qué fuente acota esta rama, por ejemplo.

## Procedure

1. **Fija la secuencia.** Declara decisión, orden de acciones y observaciones, horizonte y puntos de reversión o detención. **Resultado visible/cambio de estado:** marco del árbol con nodos conocidos de decisión, azar, observación o resultado.
2. **Enumera ramas condicionales.** En cada nodo decisorio enumera acciones aún factibles; en cada nodo aleatorio, resultados mutuamente excluyentes y posibilidades siguientes. Conserva dependencias sin aplanarlas en ramas ajenas. **Resultado visible/cambio de estado:** registro de ramas con campos de padre, hijo, condición y próxima acción.
3. **Describe resultados finales.** Asigna a cada rama final consecuencia, unidad, momento, grupo afectado y estado probatorio. Mantén restricciones no comparables de seguridad o derechos fuera del valor agregado. **Resultado visible/cambio de estado:** registro final con valores ausentes o contradictorios en suspenso o pendientes.
4. **Acota incertidumbre.** Adjunta fuente o cálculo reproducible a cada probabilidad; comprueba que las ramas condicionales sean completas y compatibles con el evento previo. Sin probabilidad acotable, usa intervalo defendible o rama cualitativa solo declarando su fundamento, sin fingir respuesta numérica. **Resultado visible/cambio de estado:** mapa de procedencia probabilística o suspensión de rama no acotada.
5. **Evalúa hacia atrás y somete a variaciones.** Desde resultados finales, calcula o compara ramas superiores con valores y unidades declarados. Varía probabilidades o resultados relevantes dentro de intervalos defendibles y muestra peor exposición, arrepentimiento o umbral de reversión en vez de depender de un solo valor esperado. **Resultado visible/cambio de estado:** tabla de evaluación con acción recomendada, condición de cambio y riesgo residual.
6. **Fija estrategia.** Explica acción respaldada ahora, observación que activaría otra acción y punto donde pausar. Si una rama pendiente puede cambiar la estrategia, suspende la recomendación y nombra la mínima observación segura. **Resultado visible/cambio de estado:** nodos de decisión, azar y resultado, resumen final, procedencia probabilística, reversión, incertidumbre y condición de cambio de la Conclusion Card.

## Public output contract

Devuelve nodos decisorios, aleatorios y finales, ramas condicionales, consecuencias terminales y punto de reversión. Muestra procedencia de cada rama numérica y unidades y expresiones de valores calculados. Incluye exposición al riesgo, condición de cambio o detención y próxima observación si la estrategia es provisional. La conclusión no debe implicar que un árbol demuestra un resultado; aritmética detallada y dependencias van en la traza.

## Evidence and uncertainty rules

Usa verified solo para fuentes identificables que respalden rama o resultado; computed para aritmética transparente con datos declarados, inferred para consecuencias desde fundamentos etiquetados, assumed para premisas de planificación explícitas, unverified para datos no comprobados y conflicted para fuentes creíbles discordantes. No inventes tasas base, probabilidades, utilidad, independencia ni valores finales. Si las ramas no son mutuamente excluyentes, revisa antes de calcular. Un intervalo numérico estrecho sin procedencia es falsa precisión.

## Stop conditions

Suspende si falta secuencia, próxima acción, resultado o fundamento probabilístico capaz de cambiar la estrategia. Suspende si no pueden representarse dependencias sin doble conteo o una norma vinculante elimina discreción. Si el espacio de ramas es demasiado abierto, declara la observación ausente y deriva a scenario-planning sin producir valor esperado sin apoyo.

## Complement handoff

Deriva a scenario-planning cuando varios futuros externos coherentes determinen la preparación en lugar de ramas aleatorias acotadas. Transfiere solo marco decisorio, incertidumbres relevantes, señales de ramas y acciones contingentes o sin arrepentimiento; excluye probabilidades sin apoyo y deliberación privada.

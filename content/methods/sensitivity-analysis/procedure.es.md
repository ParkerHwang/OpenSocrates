## Purpose

Usa este procedimiento para probar cómo cambia un modelo, comparación o decisión al variar entradas o pesos importantes en intervalos defendibles. Identifica variables influyentes, umbrales de cambio, interacciones y supuestos frágiles. Produce una comprobación transparente de robustez, no permiso para elegir intervalos dramáticos ni afirmar que el modelo demuestre el futuro.

## Use when

Úsalo si ya existe cálculo, pronóstico, caso de negocio, regla de puntuación o comparación y entradas inciertas pueden cambiar la decisión. Ayuda a priorizar datos, revelar umbrales y distinguir conclusiones estables de dependencias estrechas. Admite cambios numéricos u ordinales con escala explícita.

## Do not use when

No lo uses sin modelo, comparación, regla decisoria o relación que variar. No fabriques sensibilidad para preguntas factuales, referencias indefinidas o intervalos sin procedencia. No varíes independientemente variables correlacionadas, supongas linealidad sin comprobar ni reportes umbrales más precisos que las entradas.

## Inputs to establish

Establece modelo o regla base, resultado, umbral, entradas o pesos, unidades y resultado actual. Define intervalos plausibles con procedencia, dependencias y restricciones. Indica diseño, redondeo y prueba individual, combinaciones estructuradas o comparación ordinal. Registra opción o política informada. Haz como máximo dos preguntas si cambiarían referencia o intervalo.

## Procedure

1. Publica fórmula o regla, entradas, unidades y resultado base. **Resultado visible/cambio de estado:** inicio reproducible y umbral identificado.
2. Publica intervalos, pesos, dependencias y evidencia de cada intervalo. **Resultado visible/cambio de estado:** límites verificados, calculados, inferidos, supuestos, no verificados o contradictorios, no elegidos para impresionar.
3. Prueba una entrada cada vez y después solo combinaciones estructuradas defendibles. **Resultado visible/cambio de estado:** registro de entrada modificada, salida, método, unidades y redondeo; mueve juntas entradas correlacionadas cuando proceda.
4. Publica dirección, magnitud o cambio ordinal, interacciones y valores que cruzan umbrales. **Resultado visible/cambio de estado:** variables influyentes, no influyentes, robustas o frágiles, sin confundir ranking con causalidad.
5. Publica implicación decisoria y prioridad de investigar variables que puedan cambiarla. **Resultado visible/cambio de estado:** esfuerzo ligado a condición de cambio identificada, no a mayor variación bruta.
6. Publica conclusión robusta, frágil, provisional o suspendida y siguiente validación. **Resultado visible/cambio de estado:** referencia, intervalo o umbral ausentes implican suspensión explícita, no sensibilidad fabricada.

## Public output contract

Devuelve `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority` y `flip_condition`, con estado respaldado, provisional o suspendido. Indica umbral y entradas que lo cruzan. La tarjeta identifica cálculos y entradas, límites de intervalo o modelo y cambio observable de entrada o umbral. Conserva fórmulas y registro completo en traza o artefacto.

## Evidence and uncertainty rules

Los intervalos necesitan fuente, restricción del usuario, observación histórica o supuesto explícito; conveniencia no es evidencia. Expón fórmula, operandos, unidades y redondeo. Conserva no linealidad, correlación, discontinuidad e incertidumbre de forma cuando importen. Con pesos solo ordinales reporta dirección u orden de umbrales, no porcentajes falsamente precisos. La frecuencia de casos muestreados no implica probabilidad real. Un modelo robusto puede producir una decisión frágil con umbral u objetivo incorrectos.

## Stop conditions

Haz una pregunta bloqueante y detente si referencia, umbral o resultado admiten interpretaciones materialmente diferentes. Suspende sin intervalo, dependencia o regla necesarios. Detente si ninguna variación defendible cambia decisiones o solo quedan verificar evidencia, explicar causas o comparar compensaciones más amplias.

## Complement handoff

Deriva a `trade-off-analysis` cuando deban integrarse resultados con criterios, pesos y preferencias de actores entre opciones. Transfiere referencia, umbrales, robustez o fragilidad, procedencia y prioridades. El complemento compara usando esos límites sin tratar ranking de sensibilidad como preferencia o probabilidad.

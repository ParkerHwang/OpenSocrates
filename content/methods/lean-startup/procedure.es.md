## Purpose

Usa este procedimiento para reducir una hipótesis de mercado, producto o modelo de negocio mediante un experimento mínimo de aprendizaje. Convierte el supuesto más arriesgado en una prueba segura con una métrica útil para actuar y una decisión declarada de antemano. Aquí un MVP es un instrumento de aprendizaje, no un producto incompleto, un plan de lanzamiento integral ni una prueba de demanda por el mero hecho de haberse entregado algo.

## Use when

Úsalo cuando una hipótesis importante de valor, crecimiento, adopción o ingresos no está verificada y una pequeña observación podría cambiar la decisión de pivotar, perseverar o detenerse. Encaja con objetivos identificables, exposición acotada y métricas observables. Aplícalo antes de inversiones grandes cuando una prueba reversible responda la pregunta.

## Do not use when

No hagas pruebas reales mínimas si seguridad, legalidad, privacidad, ciberseguridad o exposición irreversible de clientes u operaciones las hacen inadecuadas. Un lanzamiento sin medición no es un experimento; una métrica de vanidad no demuestra aprendizaje. No lo uses para tareas mecánicas, decisiones vinculantes sin discreción experimental ni causas operativas desconocidas que deben diagnosticarse primero.

## Inputs to establish

Establece decisión, usuario o contexto objetivo, una hipótesis refutable, supuesto más arriesgado y evidencia disponible. Define prueba mínima o MVP, exposición, métrica y unidad, ventana de observación, umbral o regla cualitativa, responsable y límites de reversión o detención. Registra efectos de selección, límites de acceso y fuente de referencia inicial. Haz como máximo dos preguntas concisas si cambiarían seguridad, métrica o decisión; en otro caso marca el vacío no verificado y suspende si es decisivo.

## Procedure

1. **Publica la hipótesis.** Formula una condición que vincule acción u oferta, contexto y resultado observable. Clasifica cada fundamento como verificado, calculado, inferido, supuesto o no verificado. **Resultado visible/cambio de estado:** hipótesis refutable.
2. **Publica el supuesto más arriesgado.** Elige aquel cuya falsedad más alteraría la decisión y cuya evidencia sea más débil o contradictoria. Explica importancia y evidencia que lo debilitaría, sin inventar probabilidades. **Resultado visible/cambio de estado:** supuesto más arriesgado.
3. **Publica la ficha de prueba mínima.** Diseña la menor prueba reversible: audiencia o alcance limitados, artefacto, duración, responsable, consentimiento o acceso y condición de detención o reversión. Suspende exposiciones materiales y señala una comprobación más segura sin exposición real. **Resultado visible/cambio de estado:** ficha o suspensión.
4. **Publica la especificación de medición.** Identifica métrica, unidad, fuente, ventana, referencia inicial disponible y umbral o regla. Explica su relación con la pregunta de aprendizaje; etiqueta umbrales provisionales como supuestos. **Resultado visible/cambio de estado:** medición comprobable.
5. **Publica el registro de resultados.** Tras una prueba autorizada registra conducta esperada y observada, observaciones ausentes, selección, desviaciones y estado de evidencia. No sustituyas un resultado ausente con relatos de éxito. **Resultado visible/cambio de estado:** registro; sin resultado, hipótesis no verificada.
6. **Publica la siguiente decisión.** Aplica la regla previa: pivotar, perseverar, detener o suspender. Expón hipótesis modificada o siguiente prueba, responsable, límites y una o dos condiciones observables de cambio. **Resultado visible/cambio de estado:** decisión acotada.

## Public output contract

Devuelve campos `hypothesis`, `riskiest_assumption`, `minimum_test`, `metric_threshold` y `next_decision`, listos para la tarjeta. La prueba debe indicar alcance seguro, señal observable y detención o reversión; la métrica, fuente y unidad; la decisión, las cuatro opciones anteriores. Incluye como máximo dos incertidumbres materiales en el resultado contraído. Si faltan métrica, umbral o resultado decisivos, declara el resultado no verificado o suspendido, sin recomendar incondicionalmente.

## Evidence and uncertainty rules

Entregar un artefacto no demuestra demanda; una métrica no demuestra automáticamente causalidad. Verifica observaciones y fuentes solo para el fundamento concreto. Muestra entradas y expresiones de cálculos; etiqueta modelos como inferencias, umbrales elegidos y premisas no probadas como supuestos, comprobaciones ausentes como no verificadas y desacuerdos como contradictorios. Indica contexto, selección o acceso y ventana. No inventes probabilidades, conversiones, tamaños de muestra ni reacciones. Una prueba actualiza la hipótesis en ese contexto, no para todo usuario o periodo futuro.

## Stop conditions

Suspende si faltan decisión, contexto, supuesto más arriesgado, métrica o regla que pudieran cambiar el resultado. Detén pruebas inseguras, ilegales, invasivas, sensibles para la seguridad, irreversibles o no autorizadas. Detente si ninguna señal distingue alternativas, falta reversión obligatoria o se infiere éxito de métricas de vanidad. Deriva las causas operativas desconocidas en vez de ocultarlas con experimentos de producto.

## Complement handoff

Deriva a `jobs-to-be-done` si es necesario descubrir primero tarea, contexto o progreso deseado del usuario. Transfiere únicamente contexto, hipótesis, supuesto arriesgado, estado observado de evidencia y necesidad pendiente. No repitas el experimento ni sugieras que la derivación aporta resultados ausentes. Usa primero `assumption-mapping` si deben priorizarse varios supuestos.

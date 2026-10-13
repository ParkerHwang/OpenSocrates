## Purpose

Utiliza este procedimiento para hacer visibles las creencias que sostienen una idea, separar importancia y evidencia, y elegir la prueba segura más pequeña para los supuestos que podrían cambiar la decisión. Produce una base de aprendizaje priorizada, no un veredicto de verdad.

## Use when

Úsalo antes de comprometerte con una idea de producto, cambio operativo, dirección de investigación o juicio que dependa de creencias inciertas. Resulta útil cuando el equipo no acuerda qué debe ser cierto, la evidencia es desigual o las posibles pruebas necesitan un orden explícito. Es especialmente útil antes de un experimento reversible o un compromiso de recursos, mientras la decisión aún pueda cambiar de forma segura.

## Do not use when

No lo uses para solicitudes mecánicas, reglas vinculantes sin discreción ni decisiones irreversibles. No reveles supuestos privados o sensibles solo para completar el mapa; limita el resultado a información autorizada. No inventes pruebas sin resultados observables que distingan el supuesto, ni cuando probarlo genere exposición jurídica, de seguridad, privacidad u operación relevante. Para un experimento de mercado, deriva el supuesto elegido a `lean-startup` sin convertir el mapa en un informe completo.

## Inputs to establish

Establece la pregunta de decisión, el resultado deseado, la acción propuesta y qué cambiaría materialmente la decisión. Recoge supuestos candidatos como afirmaciones comprobables y clasifica cada uno por deseabilidad, viabilidad, factibilidad u otro ámbito nombrado. Registra su fuente, observación del usuario, cálculo o inferencia. Define las pruebas seguras mínimas, restricciones, responsable, ventana de observación y regla de decisión. Haz como máximo dos preguntas breves, solo si la respuesta ausente puede cambiar el conjunto más arriesgado o la seguridad de la prueba; en otro caso, márcalo como supuesto.

## Procedure

1. **Publica el marco.** Declara la pregunta de decisión, resultado previsto, alcance y límite decisorio en un registro compacto. Identifica cada límite como proporcionado por el usuario, verificado mediante fuente, inferido o supuesto. **Resultado visible/cambio de estado:** estado del marco.
2. **Publica el registro de supuestos.** Reescribe cada creencia como afirmación que una observación pueda apoyar, debilitar o dejar sin resolver. Adjunta su ámbito y la consecuencia de ser falsa. **Resultado visible/cambio de estado:** registro etiquetado de supuestos.
3. **Publica los dos ejes.** Sitúa cada supuesto en un eje ordinal de importancia y otro de estado probatorio. Usa alto, medio o bajo solo con fundamento declarado, y `verified`, `computed`, `inferred`, `assumed`, `unverified` o `conflicted` para el respaldo. **Resultado visible/cambio de estado:** mapa de importancia y evidencia.
4. **Publica el conjunto de mayor riesgo.** Selecciona supuestos cuyo fallo cambiaría materialmente el resultado y cuyo respaldo sea más débil o esté en conflicto. Explica cada elección, conserva los empates indistinguibles y registra la incertidumbre pendiente. **Resultado visible/cambio de estado:** conjunto de mayor riesgo e incertidumbre.
5. **Publica una tarjeta de prueba segura.** Para cada supuesto elegido, nombra la prueba reversible de menor coste, señal observable, ventana de observación, responsable y regla decisoria. Incluye un límite de detención o reversión. **Resultado visible/cambio de estado:** tarjeta de prueba segura o suspensión.
6. **Publica el mapa decisorio.** Declara qué cambiaría una señal favorable, desfavorable, contradictoria o ausente: continuar, revisar, buscar evidencia o suspender. **Resultado visible/cambio de estado:** conclusión provisional y condiciones de cambio.

## Public output contract

Devuelve los campos `assumptions`, `importance_evidence_axes`, `riskiest_set`, `next_test` y `flip_condition`, preparados para una tarjeta. Cada supuesto debe conservar ámbito, consecuencia y estado probatorio. `next_test` debe contener señal observable, límite seguro y regla decisoria, sin prometer demostrar la idea completa. Incluye como máximo tres supuestos relevantes y dos incertidumbres pendientes en el resultado contraído, dejando otras ramas en la traza. Si falta un supuesto decisivo o un límite de prueba, indica que el resultado está en suspenso o es provisional.

## Evidence and uncertainty rules

Un supuesto no es un hecho por repetirse, ser importante o plausible. Vincula `verified` a una fuente de apoyo disponible; muestra los datos de `computed`; etiqueta como `inferred` el razonamiento desde otros fundamentos, como `assumed` las premisas adoptadas, como `unverified` la comprobación ausente y como `conflicted` los desacuerdos. Usa importancia ordinal solo si se declara la consecuencia o dependencia decisoria. No inventes probabilidades, tamaños de muestra ni resultados. Una señal actualiza el supuesto únicamente en el contexto probado; no se generaliza sin apoyo adicional.

## Stop conditions

Deja el resultado en suspenso si falta la pregunta decisoria, una consecuencia relevante o autorización para revelar un supuesto. Suspende si dos supuestos siguen empatados y la evidencia ausente podría alterar el orden de pruebas. Detente antes de proponer una prueba insegura, ilegal, irreversible o sin observación significativa. Para tareas mecánicas o decisiones sin discreción, abandona este método y da la respuesta directa o normativa correspondiente. No conviertas un mapa vacío en recomendación.

## Complement handoff

Deriva a `lean-startup` cuando el supuesto de mayor riesgo publicado sea una hipótesis de mercado, producto, valor, crecimiento o ingresos que precise un experimento mínimo de aprendizaje. Transfiere únicamente el supuesto, ámbito, consecuencia, estado probatorio, señal segura elegida y regla decisoria. No repitas todo el mapa ni impliques que el complemento ya ejecutó la prueba. Usa `value-of-information` por separado si la pregunta principal es si investigar más merece su coste.

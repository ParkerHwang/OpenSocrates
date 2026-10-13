## Purpose

Usa este procedimiento para ejecutar un ciclo acotado Plan–Do–Check–Act sobre una hipótesis de mejora operativa. Hace visibles objetivo, medida, ejecución pequeña, comparación y decisión de estandarización para acumular mejora como evidencia y memoria organizativa. Es un bucle de aprendizaje controlado, no sustituto del diagnóstico de causas desconocidas ni de la respuesta a un incidente activo de seguridad.

## Use when

Úsalo si el proceso o servicio admite cambios pequeños y reversibles, la mejora esperada es medible y varios ciclos pueden elevar un estándar. Encaja con ventanas de observación cortas y una decisión clara entre estandarizar, revisar o abandonar. Permite aprender ejecutando sin comprometer toda la operación con cambios no probados.

## Do not use when

No lo uses si la causa raíz es desconocida y experimentar ocultaría o agravaría daño, si una regla vinculante impide discreción o si urge responder a seguridad, ciberseguridad, legalidad o incidentes. No ejecutes ciclos para aparentar actividad sin regla de comprobación. No conviertas tareas mecánicas en programas de mejora ni estandarices algo solo por anunciarlo o completarlo una vez.

## Inputs to establish

Establece objetivo, referencia observada o estado del proceso, hipótesis, alcance, responsable y dirección esperada. Antes de Do define métrica, unidad, fuente, ventana, salvaguardas, detención y comparación. Especifica evidencia para estandarizar, revisar o abandonar y dónde registrar próximo ciclo o estándar versionado. Haz como máximo dos preguntas si cambiarían seguridad, medida o decisión Act; marca otros vacíos no verificados y suspende los decisivos.

## Procedure

1. **Publica la ficha Plan.** Expón objetivo, referencia, hipótesis, dirección, alcance, responsable y plazo. Etiqueta la referencia verificada, calculada, proporcionada por usuario, inferida, supuesta o no verificada. **Resultado visible/cambio de estado:** planificación.
2. **Publica la especificación Check.** Identifica métrica, unidad, fuente, recogida, ventana, comparación, salvaguardas y detención. Declara previamente evidencia para estandarizar, revisar o abandonar. **Resultado visible/cambio de estado:** regla de comprobación.
3. **Publica el registro Do.** Ejecuta solo el alcance pequeño aprobado; registra cambio real, desviaciones, exclusiones, incidentes y observaciones. Conserva reversión y no amplíes exposición por señales iniciales favorables. **Resultado visible/cambio de estado:** ejecución auditable.
4. **Publica el resultado Check.** Compara valores o descripciones esperados y observados según la regla previa. Identifica datos ausentes, factores de confusión, límites de fuentes y contradicciones. **Resultado visible/cambio de estado:** diferencia y estado de evidencia.
5. **Publica la decisión Act.** Elige estandarizar, revisar, abandonar o suspender según evidencia y salvaguardas. Si hay resultados mixtos o falta medida decisiva, mantén el cambio provisional y registra el pendiente. **Resultado visible/cambio de estado:** decisión o suspensión.
6. **Publica el siguiente ciclo.** Registra estándar versionado o hipótesis revisada, responsable, siguiente observación y una o dos condiciones observables de cambio. Conserva aprendizaje y datos no verificados. **Resultado visible/cambio de estado:** plan siguiente o resultado suspendido.

## Public output contract

Devuelve `plan_objective_measure`, `do_scope`, `check_rule` y `act_standardize_decision`, listos para tarjeta y con evidencia de cada fundamento material. Incluye referencia inicial o su ausencia, exposición acotada, comparación y detención, y las cuatro decisiones posibles. Añade hipótesis siguiente o motivo claro para no continuar. La ausencia de una medida decisiva suspende el resultado.

## Evidence and uncertainty rules

Distingue observación directa, fuente enlazada, cálculo reproducible, registro del usuario, inferencia y premisa adoptada. Para `computed`, muestra entradas, expresión, unidades y redondeo pertinente. Sin referencia defendible o si cambia la recogida, marca comparación no verificada. No inventes probabilidades, efectos, muestras ni certeza causal. Un ciclo puede respaldar aprendizaje local, rara vez un estándar permanente; conflictos creíbles mantienen Act contradictorio o suspendido. Conserva desviaciones y señales negativas.

## Stop conditions

Suspende si faltan objetivo, referencia, medida, comparación, responsable o alcance seguro que puedan cambiar Act. Detén inmediatamente daño continuo, debilitamiento de controles obligatorios, exceso de autorización o pérdida de reversión segura. Deriva a `root-cause-analysis` si el ciclo ocultaría una causa desconocida. Tras una comprobación fallida o inconcluyente, detente si no hay hipótesis revisada ni siguiente observación segura; no repitas Do sin aprender.

## Complement handoff

Deriva a `root-cause-analysis` cuando Check revele fallo repetido, vías causales rivales o controles débiles que requieren diagnóstico previo. Transfiere plan, Do acotado, resultado, desviaciones, evidencia y pregunta de control pendiente. No transfieras acusaciones sin respaldo ni empieces otro método completo solo porque el primer ciclo fue inconcluyente.

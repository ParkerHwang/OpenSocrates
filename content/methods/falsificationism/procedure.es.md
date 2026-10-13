## Purpose

Utiliza este procedimiento para convertir afirmaciones, explicaciones o planes preferidos en predicciones arriesgadas comprobables y especificar qué contaría en su contra. Separa afirmación objetivo, supuestos auxiliares y fallos de medición, y declara qué puede o no establecer la prueba observada. Una predicción fallida es evidencia contra la configuración probada, pero no refuta automáticamente toda idea relacionada.

## Use when

Úsalo si una afirmación debería producir una predicción arriesgada, se pregunta qué demostraría errónea una explicación o se confunden historias retrospectivas con pronósticos. Sirve para hipótesis de investigación, planes de producto, diagnósticos y afirmaciones fuertes que necesitan un intento decisivo de refutación.

## Do not use when

No lo uses sin implicación comprobable, para elecciones de valores o ejecución mecánica, ni si solo se define un concepto. No trates comprobabilidad como prueba, rescates toda predicción fallida mediante supuestos auxiliares ad hoc ni descartes teorías complejas tras un fallo sin revisar medición y configuración auxiliar.

## Inputs to establish

Establece afirmación, alcance, predicción arriesgada, ventana, medición, supuestos auxiliares, umbral refutador y decisión afectada. Declara si la prueba está planificada, observada o no disponible. Haz como máximo una pregunta decisiva si predicción o umbral no pueden acotarse de otro modo.

## Procedure

1. Publica afirmación y alcance y reescríbela como predicción arriesgada que pueda fallar. Así queda visible el objetivo de prueba, no una explicación retrospectiva.
2. Publica el refutador: resultado, umbral o patrón observable contrario a la afirmación. Excluye condiciones vagas como «evidencia inesperada».
3. Publica supuestos auxiliares y condiciones de medición por separado. Marca qué fallo afectaría a afirmación, configuración o medición.
4. Publica prueba planificada u observada, procedencia y resultado. Si no está disponible, declara observación necesaria y conserva estado no verificado.
5. Publica interpretación: respaldada para esta prueba, debilitada, aún no probada o inconcluyente. No conviertas un resultado no refutador en confirmación fuerte.
6. Publica reparaciones propuestas y comprueba si se especificaron antes del resultado o se añadieron ad hoc. Una reparación que inmuniza sin apoyo independiente sigue siendo debilidad.
7. Publica estado actual, siguiente prueba y condición observable de cambio. Sin refutador formulable, suspende o rechaza aplicar el método sin fabricar lenguaje de apariencia científica.

## Public output contract

Devuelve `claim`, `scope`, `risky_prediction`, `falsifier`, `auxiliary_assumptions`, `measurement_conditions`, `observed_needed_test`, `test_and_provenance`, `observed_or_needed_result`, `status` y `flip_condition`. Distingue no probado, inconcluyente, debilitado y respaldado para esta prueba. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; una afirmación no refutada no queda verificada automáticamente.

## Evidence and uncertainty rules

El refutador debe ser observable y vincularse a un alcance especificado previamente. Una prueba fallida puede atacar un supuesto auxiliar o medición y no la teoría entera. No cuentes ajustes retrospectivos como apoyo independiente. Si no se ejecutó la prueba o el umbral se eligió después de observar resultados, etiqueta la conclusión no verificada o en conflicto y declara la limitación.

## Stop conditions

Detente y haz una pregunta bloqueante si no puede acotarse afirmación o predicción. Rechaza o suspende si no existe implicación comprobable, falta la observación necesaria o una afirmación de alto riesgo no tiene prueba segura. Detente si la tarea es calidad de fuentes, implicación formal o generar explicaciones, no un intento de refutación.

## Complement handoff

Deriva a `lean-startup` solo si la afirmación refutable es una hipótesis de producto o mercado y la siguiente decisión es una prueba mínima segura. Transfiere predicción, refutador, condiciones de medición y exclusiones de seguridad. El complemento no debe sustituir un refutador ausente con un experimento genérico.

## Purpose

Utiliza este procedimiento para elegir un modo de respuesta según la forma observada de una situación. Distingue patrones repetibles de causa y efecto de situaciones que necesitan análisis experto, experimentos seguros, contención urgente o mejor marco. El propósito no es adornar una recomendación con una etiqueta de dominio, sino mostrar evidencia de clasificación, acción resultante y señal capaz de modificarla.

## Use when

Úsalo si la respuesta propuesta puede no encajar con la situación: procesos fijos para problemas adaptativos, esperar análisis durante disrupciones rápidas o tratar varios problemas distintos como uno. Es útil cuando decidir entre estandarizar, analizar, probar y actuar constituye la propia decisión. También puede separar situaciones mixtas en partes que exigen respuestas diferentes.

## Do not use when

No lo uses para tareas mecánicas, reglas establecidas sin discreción significativa ni solicitudes de cálculo conocido o transcripción. No fuerces una clasificación si se quiere una etiqueta decorativa sin cambio de acción. No consideres lo complejo automáticamente más importante ni lo claro automáticamente seguro; la clasificación describe la relación decisoria, no la gravedad de las consecuencias.

## Inputs to establish

Establece pregunta decisoria, límite de situación, horizonte, patrón observado y restricciones inmediatas de seguridad o continuidad. Recoge observaciones, ejemplos previos, conocimiento experto y hechos del usuario, señalando qué está comprobado, inferido, supuesto o no verificado. Haz como máximo dos preguntas breves, solo si la respuesta podría cambiar el modo de acción. Si falta la observación decisiva, declara un límite provisional y continúa únicamente hasta una suspensión claramente marcada.

## Procedure

1. Publica en una frase pregunta decisoria, alcance, horizonte y restricción inmediata. Marca cada elemento aportado por el usuario o supuesto; así queda visible el marco. Resultado visible/cambio de estado: marco publicado.
2. Publica un registro causal de observaciones que separe relaciones repetibles, dependientes de expertos, retroalimentación emergente, disrupción aguda y observaciones aún no interpretables. Adjunta estado probatorio a cada observación relevante. Resultado visible/cambio de estado: registro publicado.
3. Publica una clasificación provisional —claro, complicado, complejo, caótico o confuso— con las dos o tres observaciones que la sostienen. Si distintas partes respaldan clasificaciones diferentes, divide la situación y publica sus límites separados sin promediarlos. Resultado visible/cambio de estado: clasificación publicada.
4. Publica el modo correspondiente: percibir–categorizar–responder para patrón repetible, percibir–analizar–responder para patrón dependiente de expertos, probar–percibir–responder para patrón adaptativo o actuar–percibir–responder para disrupción urgente. Para una clasificación confusa, publica la mínima tarea de marco u observación que elimine la confusión. Resultado visible/cambio de estado: modo de acción publicado.
5. Publica una siguiente acción segura y sus señales de aprendizaje o transición. Declara qué se observará, por quién y cuándo; una señal debe ser observable, no una esperanza genérica de mejora. Resultado visible/cambio de estado: registro de señales publicado.
6. Publica estado de conclusión, evidencia, una incertidumbre relevante y condición que invertiría clasificación o modo de acción. No afirmes certeza solo por haber elegido etiqueta. Resultado visible/cambio de estado: conclusión publicada.
7. Si un límite, observación o restricción ausentes pueden cambiar el modo, publica un resultado en suspenso o provisional y la pregunta o comprobación bloqueante. Esto cambia el estado a suspensión, sin rellenar carencias con hechos inventados. Resultado visible/cambio de estado: suspensión publicada.

## Public output contract

Devuelve un resultado compacto para tarjeta con `decision_question`, `domain`, `classification_evidence`, `action_mode`, `transition_signals`, `next_action` y `flip_condition`. El dominio es una conclusión apoyada por observaciones visibles, no una insignia. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted** cuando corresponda. Incluye como máximo tres supuestos relevantes y dos incertidumbres pendientes. Si se suspende, indica qué falta y qué comprobación permite levantar la suspensión.

## Evidence and uncertainty rules

Trata observaciones directas, fuentes identificadas, registros del usuario y cálculos reproducibles como evidencia solo de lo que realmente respaldan. Una etiqueta normalmente se infiere del patrón; no queda verificada porque una fuente use la misma palabra. No inventes probabilidades de transición, impacto o éxito. Separa el hecho de que exista retroalimentación de su interpretación inferida. Marca cambios de límite, clasificaciones rivales u observaciones obsoletas como en conflicto o no verificadas, y reduce el respaldo si esa incertidumbre podría modificar la siguiente acción.

## Stop conditions

Detente y haz una pregunta bloqueante cuando dos límites u observaciones plausibles exijan acciones materialmente distintas y no pueda elegirse según el propósito del usuario o restricción autorizada. Suspende si no se establece la relación decisiva, restricción inmediata o señal de transición. Termina al publicar un modo accionable, una señal observable y una condición de cambio. No esperes análisis exhaustivo en urgencias; registra la contención y reconsidera la clasificación tras nuevas observaciones.

## Complement handoff

Deriva a `scenario-planning` solo si la clasificación revela varios futuros externos coherentes que necesitan preparaciones diferentes. Transfiere límite, evidencia de clasificación, modo, señales e incertidumbre pendiente publicados. No repitas toda la clasificación ni pidas al complemento inventar un hecho ausente que primero debería levantar la suspensión de este procedimiento.

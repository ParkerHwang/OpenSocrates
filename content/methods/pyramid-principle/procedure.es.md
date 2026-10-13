## Purpose

Usa este procedimiento para convertir un juicio sólido en una respuesta ejecutiva cuya idea rectora aparezca primero. Agrupa razones del mismo nivel, verifica que cada afirmación superior resuma detalles y elige un orden uniforme para puntos equivalentes. Mejora la comunicación; no debe aparentar que un juicio pendiente ya esté resuelto.

## Use when

Úsalo en informes, memorandos, resúmenes ejecutivos, propuestas, presentaciones o solicitudes de comenzar por la respuesta. Encaja con análisis largos cuya conclusión ya tiene apoyo suficiente pero cuesta examinar rápidamente. Aplícalo después de comprobar juicio y evidencia subyacentes.

## Do not use when

No lo uses para omitir evidencia ausente, ocultar conflictos materiales o elegir una conclusión aún no formulada. No fuerces tres grupos si solapan u omiten puntos decisivos. Si hay conclusión directa, no antepongas antecedentes; conserva alcance e incertidumbre necesarios en la tarjeta.

## Inputs to establish

Establece pregunta rectora, conclusión, fundamentos materiales, alternativas, decisión del público, alcance y estado de evidencia. Elige orden deductivo, temporal, estructural o por importancia. Haz como máximo una pregunta si falta decisión del público o conclusión; en otro caso identifica audiencia y continúa.

## Procedure

1. Publica arriba pregunta rectora e idea central de una frase. Marca conclusión respaldada, provisional, contradictoria o suspendida; fija el estado visible de comunicación.
2. Publica entre tres y cuatro grupos que conjuntamente apoyen la idea. Cada uno tiene mensaje clave de una línea; registra solapamientos y cobertura ausente como vacíos estructurales.
3. Publica detalles bajo cada grupo y verifica relación vertical: el mensaje resume detalles, sin introducir afirmaciones nuevas.
4. Publica y aplica uniformemente orden horizontal deductivo, temporal, estructural o por importancia. Registra órdenes alternativos que cambiarían materialmente la interpretación.
5. Publica respuesta principal, razones agrupadas y detalles de arriba abajo. Mantén visibles supuestos, conflictos y fundamentos no verificados; no los elimines al pulir.
6. Publica alternativa o contraargumento más fuerte y motivo de no seleccionarlo. Si el juicio no está resuelto, cambia a provisional o suspendido en vez de aparentar respuesta definitiva.
7. Publica estructura final lista para tarjeta y condición observable de cambio. Confirma entregable, restricciones explícitas, comprobaciones de evidencia y declaraciones de incertidumbre.

## Public output contract

Devuelve `top_line_answer`, `governing_thought`, `grouped_reasons`, `reason_groups`, `supporting_detail_order`, `scope_and_assumptions`, `alternatives_considered`, `completion_check` y `flip_condition`. La primera frase es la conclusión; los antecedentes solo la apoyan. Limita fundamentos a afirmaciones materiales y etiqueta **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**. Puede integrarse en un memorando, conservando conclusión primero.

## Evidence and uncertainty rules

Una buena estructura no eleva la calidad de evidencia. Cada grupo necesita base visible; los vínculos inferidos no son hechos directos. Si hay conflicto entre grupos, muéstralo en vez de promediarlo en una narración fluida. Si un fundamento, alternativa o requisito de finalización ausentes cambiarían la respuesta, usa conclusión provisional o suspendida e identifica lo que falta.

## Stop conditions

Detente y haz una pregunta bloqueante si faltan pregunta estable o decisión del público y distintas respuestas iniciales cambiarían materialmente el resultado. Suspende juicios sin respaldo, contradictorios o incompletos. Detente si la respuesta ya está clara y solo queda formato mecánico; no añadas comentarios del método a ese trabajo.

## Complement handoff

Deriva a `argument-mapping` si aparecen estructuras pendientes de apoyo, objeción o premisas compartidas. Transfiere idea rectora, grupos materiales y el único vínculo pendiente. El complemento no debe reordenar la respuesta terminada ni crear una segunda pirámide completa.

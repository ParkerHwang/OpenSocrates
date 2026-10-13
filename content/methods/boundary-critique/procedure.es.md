## Purpose

Utiliza este procedimiento para hacer visible el límite de un juicio. Identifica quién y qué incluye el marco actual, quién resulta afectado pero excluido y cómo cambiar el límite modifica la conclusión. No busca una lista más larga de actores interesados; revela supuestos sobre titularidad, beneficio, coste, autoridad, horizonte, jurisdicción y borde del sistema que hacen parecer inevitable la respuesta actual. Separa afirmaciones descriptivas, sobre lo que ocurre, de las normativas, sobre lo que debe contar o hacerse.

## Use when

Úsalo cuando una respuesta pueda cambiar según qué actores cuenten, de quién se midan resultados, qué geografía o periodo se incluya, quién tenga la decisión o qué externalidades se excluyan. Es especialmente útil en política, producto, organización, interés público y cambio sistémico, donde una respuesta técnicamente correcta para un grupo puede imponer costes a otro. Una comparación acotada puede usarlo si oculta una población u horizonte omitidos.

## Do not use when

No lo uses si alcance, responsable decisorio, población afectada, jurisdicción y horizonte ya están explícitos y solo falta comparar opciones o verificar fuentes. No conviertas una solicitud mecánica en ejercicio de límites. No infieras un grupo afectado solo porque sea imaginable; márcalo como hipótesis hasta que la tarea o evidencia haga relevante la conexión.

## Inputs to establish

Establece pregunta decisoria, responsable, beneficiarios previstos, regla de inclusión actual, horizonte, geografía o jurisdicción, recursos contados y medida de resultados. Nombra hasta tres hechos ausentes que podrían alterar materialmente el límite. Si el usuario no proporciona límite, declara uno provisional razonable y haz como máximo una pregunta breve solo si distintas respuestas cambiarían la recomendación. Distingue hechos del usuario, fuentes comprobadas, efectos inferidos y elecciones de valores.

## Procedure

1. Publica en una frase la pregunta decisoria y el límite provisional: quién, qué, dónde, cuándo y para qué resultado. Declara si proviene del usuario o es supuesto; así queda visible el marco.
2. Publica el conjunto incluido con actores, propósitos, conocimiento, recursos y derechos decisorios. Adjunta un motivo breve para cada inclusión, haciendo el límite auditable y no meramente afirmado.
3. Publica los omitidos pero afectados. Separa efectos directos, indirectos y personas que podrían cuestionar el marco; marca las entradas inciertas como hipótesis, no hechos.
4. Publica la separación entre hechos y valores: observaciones descriptivas aparte de juicios sobre qué beneficio, coste, voz o derecho debe contar. Evita así disfrazar una elección de valores como borde neutral del sistema.
5. Publica una comparación de beneficios y costes entre grupos incluidos y omitidos, usando solo efectos relevantes. Etiqueta la evidencia de cada efecto y marca los no verificados como pendientes.
6. Publica una o más variantes de límite, como mayor horizonte, otra jurisdicción o un grupo afectado adicional. Indica para cada variante si cambia conclusión, orden de opciones, riesgo o criterio de finalización.
7. Publica el límite actual, la consecuencia del cambio más relevante para decidir y una condición observable de cambio. Si falta un hecho decisivo del límite, declara la conclusión provisional o en suspenso sin llenarla de especulación.

## Public output contract

Devuelve un resultado compacto preparado para tarjeta con `current_boundary`, `omitted_boundary`, `benefit_and_cost_effects`, `boundary_variant`, `consequence_of_changing_it` y `flip_condition`. La primera línea declara el límite actual y si apoya, debilita o suspende el juicio. Incluye como máximo tres supuestos relevantes y dos incertidumbres pendientes. En la tarjeta usa **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted** para fundamentos; las alternativas resumen variantes relevantes del límite sin listar todos los actores.

## Evidence and uncertainty rules

Un grupo afectado no constituye por sí mismo evidencia de un efecto. Para cada beneficio o coste relevante usa fuente, documento del usuario, cálculo reproducible o inferencia claramente etiquetada. No trates la mayoría o preferencia del responsable como prueba de que un grupo omitido sea irrelevante. Si las variantes producen conclusiones incompatibles, etiqueta el juicio **conflicted** o **held** hasta que el responsable autorizado elija el alcance rector. Un hecho decisivo ausente solo permite una conclusión provisional.

## Stop conditions

Detente y haz una pregunta bloqueante cuando dos límites plausibles lleven a acciones materialmente distintas y no puedan elegirse con seguridad desde el propósito del usuario o una regla autorizada. Suspende si un grupo, jurisdicción u horizonte decisivos no pueden identificarse. Detén el método cuando el límite esté explícito y no queden actores ni bordes omitidos relevantes; deriva al método de comparación o evidencia que corresponda.

## Complement handoff

Deriva a `stakeholder-analysis` únicamente como complemento enfocado si la revisión revela preguntas relevantes de poder, consentimiento, ejecución o conflicto. Transfiere conjuntos publicados incluidos y omitidos, variante elegida y efecto pendiente que requiere análisis de actores. No actives un segundo procedimiento completo ni repitas el inventario de límites.

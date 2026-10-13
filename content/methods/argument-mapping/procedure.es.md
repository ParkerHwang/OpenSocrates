## Purpose

Utiliza este procedimiento para mostrar cómo las afirmaciones, fundamentos, objeciones y refutaciones apoyan o debilitan una conclusión. Crea un mapa argumental auditable, en lugar de un mapa mental libre, para mantener visibles las premisas compartidas, los vínculos sin apoyo y las objeciones pendientes. Puede aclarar una disputa antes de decidir, pero colocar una premisa en una estructura ordenada no la convierte en verdadera.

## Use when

Úsalo cuando un argumento político, jurídico, estratégico, de investigación o de producto contiene varias afirmaciones anidadas y no está claro qué evidencia apoya cada conclusión. Sirve para disputas con múltiples objeciones, refutaciones o supuestos compartidos. Úsalo cuando la tarea principal sea distinguir relaciones de apoyo y ataque, y después declarar la solidez resultante o la condición para dejarla en suspenso.

## Do not use when

No lo uses para una lista sencilla, un cálculo directo o una tarea cuyo único problema sea la calidad de las fuentes. No dibujes asociaciones, cronología o semejanzas temáticas como si fueran apoyo lógico. No deduzcas que una conclusión es sólida porque el mapa esté completo ni ocultes elecciones de valores en premisas aparentemente neutrales.

## Inputs to establish

Establece la conclusión objetivo, la decisión o pregunta, el alcance relevante, los fundamentos directos, las premisas compartidas, las objeciones, las refutaciones y las fuentes disponibles. Identifica si cada elemento es un hecho, regla, inferencia, preferencia o supuesto. Haz como máximo dos preguntas decisivas cuando una afirmación o alcance ausentes cambiarían el mapa; en otro caso, señala la carencia y procede.

## Procedure

1. Publica la conclusión principal y la decisión que debe apoyar. Marca su estado actual como respaldado, provisional, en conflicto o en suspenso; así queda visible el estado del argumento.
2. Publica las premisas de apoyo directas y distínguelas de las premisas conjuntamente necesarias. Dibuja solo vínculos explícitos de apoyo y etiqueta cada uno como declarado, inferido o no verificado.
3. Publica los fundamentos subordinados de cada premisa, conservando la jerarquía entre afirmación y fundamento. Adjunta referencias de fuentes o cálculos disponibles y registra como carencias los vínculos sin apoyo.
4. Publica las objeciones como ramas de ataque separadas y las refutaciones solo cuando respondan a la afirmación real de la objeción. Marca una objeción como pendiente si la refutación no modifica ni su evidencia ni su alcance.
5. Publica las premisas ocultas o compartidas y comprueba si retirar cada una cambia la conclusión. Este cambio identifica la menor debilidad relevante, sin dar el mismo peso a todas las frases.
6. Publica un veredicto del mapa: vínculo mejor respaldado, vínculo más débil, objeción pendiente y ramas redundantes o irrelevantes. Distingue integridad del mapa, verdad de las premisas y validez de las inferencias.
7. Publica el estado probatorio actual de la conclusión y una condición observable de cambio. Si falta una premisa relevante o sigue pendiente una objeción decisiva, reduce el respaldo o deja la conclusión en suspenso, sin reparar silenciosamente el argumento.

## Public output contract

Devuelve `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict` y `flip_condition`. El resultado público debe mostrar un mapa compacto de afirmaciones, fundamentos y objeciones, no una transcripción del razonamiento privado. Etiqueta los fundamentos como **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**. Incluye en la tarjeta solo ramas relevantes y envía el detalle a la traza cuando haga falta.

## Evidence and uncertainty rules

Una fuente puede apoyar una afirmación sin apoyar el paso de esa afirmación a la conclusión. Evalúa por separado carácter directo, relevancia y alcance. No cuentes dos veces premisas compartidas como apoyo independiente. Una refutación contra un testigo o medición puede debilitar el vínculo de apoyo sin demostrar la conclusión contraria. Fundamentos creíbles contradictorios exigen mostrar el conflicto y suspender o reducir el respaldo, salvo que una regla explícita de precedencia lo resuelva.

## Stop conditions

Detente y haz una pregunta bloqueante si falta la conclusión objetivo o el alcance de la decisión y distintas interpretaciones crearían mapas diferentes. Deja el resultado en suspenso si no se puede apoyar una premisa relevante o una objeción decisiva carece de resolución. Detente cuando la tarea sea solo clasificar fuentes, un cálculo sencillo o una definición estable; deriva al método más específico.

## Complement handoff

Deriva a `evidence-hierarchy` cuando el mapa muestre que el obstáculo pendiente es la calidad de fuentes, el diseño del estudio o el carácter directo, y no la estructura argumental. Transfiere únicamente los vínculos entre afirmaciones y fuentes, los vínculos sin apoyo y el conflicto relevante. El complemento no debe reconstruir todo el mapa.

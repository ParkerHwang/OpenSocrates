## Purpose

Usa este procedimiento para estructurar varios futuros externos coherentes y preparar decisiones. No predice un futuro: revela cómo se comporta una decisión cuando divergen fuerzas importantes e inciertas. Separa acciones útiles en varios futuros de acciones contingentes y mantiene señales visibles para revisar después.

## Use when

Úsalo en estrategia, inversión, políticas, infraestructura o productos de horizonte largo, especialmente cinco años o más o tras fallos repetidos de pronóstico. Encaja con «¿para qué prepararnos?» cuando condiciones externas plausibles moldean resultados. Sirve antes de compromisos irreversibles, no solo tras elegir un pronóstico.

## Do not use when

No lo uses para pronósticos puntuales breves, variaciones numéricas optimista/base/pesimista ni decisiones sin incertidumbre externa significativa. No elijas ejes correlacionados, cuatro variantes del mismo futuro bueno/malo, probabilidades ni relatos sin acciones. Para variar entradas numéricas de un modelo usa sensitivity-analysis.

## Inputs to establish

Establece pregunta focal, horizonte, límite sistémico, decisión y premisas suficientemente previsibles comunes. Enumera impulsores con evidencia de impacto e incertidumbre; identifica dos incertidumbres críticas independientes. Registra restricciones, actores, compromisos y observaciones que servirían de señales. Haz como máximo dos preguntas si cambiarían pregunta o ejes. Etiqueta premisas e impulsores verificados, calculados, inferidos, supuestos, no verificados o contradictorios.

## Procedure

1. Publica pregunta, horizonte, límite, decisión y premisas comunes. **Resultado visible/cambio de estado:** pregunta acotada de preparación en vez de especulación abierta.
2. Publica dos ejes críticos y justifica impacto alto y dificultad predictiva. **Resultado visible/cambio de estado:** descarta candidatos correlacionados, poco relevantes o previsibles, o conviértelos en premisas comunes.
3. Publica matriz 2×2 con cuatro escenarios nombrados, coherentes y una vía breve de aparición. **Resultado visible/cambio de estado:** futuros distintos como entornos plausibles de prueba; sin probabilidades ni preferencias.
4. Publica validez y vulnerabilidad de la decisión en cada escenario. **Resultado visible/cambio de estado:** registro de prueba que distinga acciones comunes útiles, contingentes y fallos en toda la matriz.
5. Publica señales, respuestas desencadenadas y frecuencia de revisión para distinguir escenarios conforme evolucionen condiciones. **Resultado visible/cambio de estado:** seguimiento vivo, no narrativa estática.
6. Publica conclusión de robustez y condición observable de cambio. **Resultado visible/cambio de estado:** ejes, premisas o implicaciones no defendibles generan conclusión provisional o suspendida, no pronóstico disfrazado.

## Public output contract

Devuelve `driving_uncertainties`, `scenarios`, `signposts`, `no_regret_actions`, `contingent_actions`, `decision_check` y `flip_condition`, con estado respaldado, provisional o suspendido. `scenarios` contiene cuatro resúmenes nombrados con vías e implicaciones. La tarjeta muestra preparación, incertidumbre material, condición observable de cambio y alternativas breves. Conserva matriz y frecuencia en registro o artefacto.

## Evidence and uncertainty rules

Respalda premisas comunes con fuentes o márcalas supuestas. Un eje es hipótesis de marco sobre impacto e incertidumbre, no hecho medido salvo evidencia. Los escenarios son coherentes y plausibles, pero no pronósticos: no adjuntes porcentajes, rankings ni probabilidades ocultas. Separa señales observadas e interpretación inferida. No inventes tendencias, fechas ni impulsores. Si los ejes dependen entre sí, revisa o suspende.

## Stop conditions

Haz una pregunta bloqueante y detente si pregunta, horizonte o límite tienen significados materialmente distintos. Suspende sin incertidumbres independientes de impacto alto, premisas defendibles o decisión accionable. Detente ante pronóstico breve, variación de modelo o elección operativa resuelta; deriva sin forzar cuatro escenarios.

## Complement handoff

Deriva a `pestel-analysis` si los impulsores necesitan revisión política, económica, social, tecnológica, ambiental o legal. Transfiere pregunta, horizonte, premisas, candidatos, ejes y evidencia. El complemento debe comprobar impulsores externos sin reducir escenarios a un único futuro predicho.

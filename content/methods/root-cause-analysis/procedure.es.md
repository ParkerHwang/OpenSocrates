## Purpose

Usa este procedimiento para explicar fallos recurrentes o consecuencias que una solución rápida no pueda abordar con seguridad. Separa síntoma visible, causas próximas, condiciones contribuyentes y condiciones sistémicas controlables. No busca culpar ni descubrir una única raíz. Produce cadena causal, prevención con responsable y señal verificable de cambio en el riesgo de recurrencia.

## Use when

Úsalo para incidentes repetidos, fallos de calidad, degradación, defectos, traspasos incumplidos o soluciones provisionales recurrentes. Requiere evento, población, periodo e impacto observables. Es útil si se culpa a individuos por interacciones previsibles entre herramientas, carga, incentivos, formación y controles. Usa registros, cronologías, entrevistas, muestras o diagramas de espina de pescado, vinculando cada afirmación a observación o supuesto marcado.

## Do not use when

No lo uses para resolver deberes vinculantes, inferir intención de un error ni rediseñar sistemas sin fallo concreto. Un suceso aislado puede necesitar causal-reasoning o revisión de incidente. No llames raíz al desencadenante más fácil de nombrar. No prometas eliminar recurrencia con una intervención si existen vías independientes o falta evidencia.

## Inputs to establish

Define fallo observable, alcance, ventana, impacto y recurrencia. Reúne cronología, proceso esperado y real, registros y controles. Personas y componentes son participantes, no causas presumidas. Haz como máximo dos preguntas que cambiarían diagnóstico, por ejemplo si ocurrió con otro operador o qué control debía detectarlo. Marca registros ausentes, recuerdos retrospectivos y supuestos no probados.

## Procedure

1. **Delimita el fallo.** Expón qué ocurrió, dónde, cuándo, frecuencia e impacto; separa evento e interpretación. **Resultado visible/cambio de estado:** problema de una frase y límites esperados/observados, con alcance desconocido no verificado.
2. **Separa niveles.** Clasifica síntoma, causa próxima, condición contribuyente, debilidad de control y condición sistémica. Conserva múltiples vías si hay evidencia. **Resultado visible/cambio de estado:** inventario causal etiquetado, no acusación.
3. **Construye la cadena.** Usa cronología, porqués, mapa de proceso o agrupación causa–efecto para conectar candidatos con condiciones observables. Detén especulaciones y registra comprobaciones ausentes. **Resultado visible/cambio de estado:** cadena con evidencia por vínculo material.
4. **Prueba controlabilidad contrafactual.** Pregunta si eliminar o modificar cada condición raíz impediría plausiblemente el fallo manteniendo contexto similar. Considera vías independientes y controles aún vulnerables. **Resultado visible/cambio de estado:** candidatos controlables, contribuyentes, pendientes o contradichos, sin rankings fabricados.
5. **Elige acciones y responsables.** Separa contención de daño, prevención que cambia condiciones y detección de recurrencia. Asigna responsable, plazo y señal a cada acción material. **Resultado visible/cambio de estado:** registro vinculado a cadena y riesgo residual si no se completa.
6. **Verifica y revisa.** Define observación posterior que mostraría menor recurrencia o diagnóstico incorrecto. Reabre vínculos contradichos; anunciar acciones no cierra el análisis. **Resultado visible/cambio de estado:** diagnóstico suspendido, provisional o respaldado, verificación fechada y siguiente comprobación.

## Public output contract

Devuelve problema acotado, cadena, condición raíz controlable y distinción entre contención, prevención y detección. Muestra evidencia por vínculo, responsables, señales y riesgo residual. La Conclusion Card puede resumir diagnóstico y condición de cambio; conserva ramas detalladas en el registro. Sin raíz establecida, di «la explicación principal es» y mantén provisional, sin presentar un culpable como hecho.

## Evidence and uncertainty rules

Síntomas repetidos no demuestran causas repetidas. Distingue registros fechados, pruebas reproducibles y observaciones directas de relatos retrospectivos. «Error humano» no es diagnóstico completo si intervienen carga, interfaz, incentivos, formación, traspasos o controles. No calcules prioridades o probabilidades sin escala y procedencia defendibles. Justifica términos material, plausible, pendiente o de baja consecuencia. Muestra conflictos entre ramas y suspende la conclusión raíz.

## Stop conditions

Detente y suspende si se desconoce el límite del fallo, faltan registros discriminantes o todos los candidatos dependen de relatos no probados. No nombres individuos como causa sin evidencia directa y examen sistémico. Si el daño continúa, prioriza contención segura y procedimientos cualificados de incidente o seguridad.

## Complement handoff

Deriva a failure-mode-effects-analysis si el diagnóstico debe convertirse en inventario prospectivo de fallos y controles. Transfiere solo límites públicos del fallo, ramas y controles conocidos; el complemento no debe repetir culpa infundada ni inventar gravedad.

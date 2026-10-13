## Purpose

Utilisez cette procédure pour généraliser des observations en gardant une conclusion probabiliste et bornée par l'échantillon. Elle identifie le type d'induction, vérifie taille, diversité et représentativité, cherche activement des contre-exemples et précise périmètre et force de la généralisation. Des observations répétées ne renforcent le soutien que si échantillonnage et mesure justifient l'extension.

## Use when

Utilisez-la pour tendances de données, enquêtes, retours utilisateur, incidents répétés et affirmations passant de cas observés à une population plus large ou un comportement futur. Elle convient aux généralisations statistiques, énumératives, causales ou analogiques si l'utilisateur souhaite connaître l'étendue du soutien fourni par les observations.

## Do not use when

Ne l'utilisez pas pour un échantillon de convenance non représentatif, une règle stricte ou une affirmation causale exigeant un plan causal plutôt qu'une extension de phénomène. Des observations dupliquées ne constituent pas une diversité ; n'inférez pas « tous » d'un petit échantillon et ne faites pas d'une tendance plausible une conclusion nécessaire.

## Inputs to establish

Établissez observations, population ou périmètre futur cible, processus d'échantillonnage, définition de mesure, groupes de comparaison, période et décision touchée. Identifiez type d'induction et biais connus de sélection, survivance, non-réponse ou mesure. Posez au maximum une question décisive si population ou fondement d'échantillon est inconnu et modifie le périmètre.

## Procedure

1. Publiez prémisses observées et généralisation proposée séparément. Marquez provenance et état probant de chaque observation ; cela établit la référence visible de l'induction.
2. Publiez type d'induction — énumérative, statistique, causale ou analogique — et passage de l'échantillon au périmètre cible. Énoncez les hypothèses qui rendent ce passage plausible.
3. Publiez le fondement de l'échantillon : taille, diversité, sélection, cas manquants, qualité de mesure et couverture temporelle. Distinguez une description sourcée d'une représentativité inférée.
4. Publiez la recherche du contre-exemple le plus solide et son résultat. Incluez si disponibles cas non sélectionnés, résultats négatifs, différences de sous-groupes et exceptions futures plausibles.
5. Publiez une généralisation bornée, une limite de périmètre et un niveau qualitatif fort, moyen ou faible. Remplacez les termes universels par une population ou un intervalle de proportion seulement si l'intervalle a une provenance défendable.
6. Publiez la conséquence décisionnelle et la prochaine observation améliorant ou contestant le plus la généralisation. Précisez si le résultat soutient action, surveillance ou échantillonnage supplémentaire.
7. Publiez conclusion actuelle et condition observable de révision. Si l'échantillon est trop biaisé, limité ou inadéquat à la cible, suspendez le résultat ou gardez-le provisoire au lieu d'extrapoler.

## Public output contract

Renvoyez `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence` et `flip_condition`. Distinguez cas observés et affirmation plus large. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; la généralisation est normalement inférée, pas directement vérifiée.

## Evidence and uncertainty rules

La taille seule ne prouve pas la représentativité. Vérifiez sélection, couverture, attrition, mesure, équilibre des sous-groupes et pertinence temporelle. Un contre-exemple limite une affirmation universelle sans prouver la tendance contraire. Ne réutilisez pas la même observation comme soutien indépendant et test de contre-exemple. Si fondement d'échantillon ou périmètre cible manque, affaiblissez ou suspendez la conclusion.

## Stop conditions

Arrêtez-vous et posez une question bloquante si population cible ou processus d'échantillonnage est impossible à connaître et que différents périmètres changeraient l'action. Suspendez si l'échantillon est sensiblement non représentatif, si l'affirmation causale dépasse le plan d'étude ou si un risque décisif de contre-exemple reste irrésolu. Arrêtez si la tâche est règle stricte, diagnostic d'hypothèses concurrentes ou comparaison de qualité des sources.

## Complement handoff

Passez à `evidence-hierarchy` si la question restante est le poids suffisant de l'échantillon ou du plan d'étude pour soutenir l'affirmation. Transmettez fondement d'échantillon, généralisation, limite de périmètre et risque principal de contre-exemple. La méthode complémentaire ne doit pas refaire la généralisation.

## Purpose

Utilisez cette procédure pour comparer des flux de preuves indépendants afin qu’une source, méthode, théorie ou enquêteur ne porte pas plus de confiance qu’il n’en mérite. Elle définit affirmation et preuves requises, vérifie l’indépendance plutôt que de compter les citations et rapporte convergence, conflit et lacunes. L’accord n’est informatif que si les flux diffèrent significativement et répondent à la même affirmation.

## Use when

Utilisez-la si une source ou méthode unique peut être biaisée, si preuves qualitatives et quantitatives se mêlent ou si des parties intéressées fournissent des récits concurrents. Elle convient à la vérification d’affirmations importantes, l’évaluation de programmes, la synthèse de recherche et aux décisions qu’une corroboration ou un conflit modifierait.

## Do not use when

Ne l’utilisez pas si toutes les sources répètent un jeu de données, si le sujet est une préférence de valeur ou si une règle formelle directe tranche. Ne comptez pas plusieurs copies d’un rapport comme indépendantes, ne moyennez pas un conflit pour l’effacer et ne recueillez pas des flux répondant à des affirmations différentes sans signaler l’écart.

## Inputs to establish

Établissez affirmation centrale, décision, types de preuves requis, flux candidats, sources amont communes, méthodes, enquêteurs, fenêtres temporelles et risques de biais pertinents. Choisissez l’axe de diversité — données, méthode, théorie ou enquêteur — et pourquoi il peut tester l’affirmation. Posez au plus une question décisive si affirmation ou limite d’indépendance est floue.

## Procedure

1. Publiez affirmation centrale et décision qu’elle pourrait changer. Précisez preuves requises et portée ; cela crée l’état visible de corroboration.
2. Publiez chaque flux avec origine des données, méthode, enquêteur, population, période et biais attendu. Marquez entrées fournies par l’utilisateur, vérifiées, inférées et indisponibles.
3. Publiez la vérification d’indépendance : données, mesure, institution ou modèle partagés, ou source réellement distincte. La diversité méthodologique ne constitue pas une indépendance si tous héritent des mêmes données brutes.
4. Publiez le résultat de chaque flux pour la même affirmation : convergence, conflit ou absence de réponse. Précisez direction et importance du résultat plutôt que de compter les votes.
5. Publiez lacunes et explications plausibles du conflit : périmètre, calendrier, mesure, sélection ou analyse. Gardez les explications concurrentes visibles jusqu’à une vérification résolutive.
6. Publiez état probant combiné et conclusion calibrée. L’accord peut renforcer un résultat étayé ; un conflit substantiel l’affaiblit ou le suspend sauf règle de priorité ou périmètre justifiée.
7. Publiez prochaine vérification indépendante et condition observable de basculement. Si les flux ne sont pas indépendants ou ne répondent pas à la même affirmation, dites que la triangulation est insuffisante plutôt que de rapporter une fausse corroboration.

## Public output contract

Renvoyez `focal_claim`, `evidence_needed`, `evidence_streams`, `independence_check`, `stream_results`, `agreement_conflict`, `agreement_conflict_gap`, `combined_evidence_state`, `calibrated_conclusion` et `flip_condition`. La fiche résume convergence ou conflit et nomme liens de sources pertinents ou étiquettes sûres fournies par l’utilisateur. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

L’indépendance concerne données, mesure, incitations et filiation analytique, pas le nombre de citations. Un flux ne répondant pas à l’affirmation est une lacune, pas une preuve négative. L’accord de flux dépendants ne justifie pas une corroboration forte. Si des flux substantiels se contredisent, préservez le conflit et suspendez ou affaiblissez jusqu’à justification de périmètre, qualité ou priorité.

## Stop conditions

Arrêtez et posez une question bloquante si affirmation centrale ou limite d’indépendance est indéfinissable. Suspendez si tous les flux partagent une source non vérifiée, si un conflit substantiel est irrésolu ou si les flux répondent à des questions différentes. Arrêtez pour un simple classement de sources, choix de valeur ou implication formelle.

## Complement handoff

Passez le relais à `evidence-hierarchy` si le désaccord restant porte sur qualité, conception ou applicabilité de flux individuels. Transmettez inventaire, verdict d’indépendance, résumé de convergence/conflit et vérification manquante. La méthode complémentaire ne doit pas inférer l’indépendance du nombre de sources.

## Purpose

Utilisez cette procédure pour calibrer une affirmation selon qualité, caractère direct, applicabilité et risque de biais des sources qui la soutiennent. Elle classe le type d'affirmation, compare les plans d'étude ou formes d'éléments sans universaliser une hiérarchie rigide, puis indique état probant et force de conclusion. Une source de niveau inférieur peut rester utile si elle correspond directement à la question et que les plans plus forts n'y correspondent pas.

## Use when

Utilisez-la lorsque recherche, politiques, expériences produit, avis experts, déclarations utilisateur ou autres éléments sont mélangés et qu'une étiquette de force défendable est nécessaire. Elle convient aux questions sur le soutien des sources, l'applicabilité d'une étude au contexte cible et la formulation appropriée aux différences de qualité.

## Do not use when

Ne l'utilisez pas si le différend principal concerne une préférence de valeurs plutôt qu'un soutien factuel, ou si une règle formelle, un modèle causal ou une méthode de conflit de sources est plus spécifique. Ne classez pas par prestige seul, n'écartez pas automatiquement des éléments pertinents de niveau inférieur et ne dites pas qu'une source est forte sans vérifier caractère direct et limites.

## Inputs to establish

Établissez affirmation, population ou contexte cible, type d'affirmation — effet, prévision, mécanisme ou expérience —, seuil de décision, sources, plans d'étude, échantillons, mesures et conflits connus. Identifiez pour chaque source si elle est directe, indirecte ou seulement contextuelle. Posez au maximum une question décisive si le contexte cible modifie l'applicabilité.

## Procedure

1. Publiez affirmation, contexte cible et seuil de décision. Précisez s'il s'agit d'effet, prévision, mécanisme ou expérience ; cela établit l'état visible de l'examen probant.
2. Publiez un tableau affirmation-source indiquant type, plan, échantillon ou fondement, caractère direct et périmètre. Marquez chaque source vérifiée, fournie par l'utilisateur, inférée ou indisponible.
3. Publiez les dimensions de qualité : rigueur du plan, risque de biais, validité des mesures, exhaustivité et applicabilité, avec des étiquettes qualitatives ou ordinales sourcées. N'inventez pas de score composite précis.
4. Publiez la position hiérarchique et les limites de chaque source. Expliquez pourquoi elle est forte ou faible pour cette affirmation particulière, plutôt que de traiter sa position comme autorité universelle.
5. Publiez convergences, incohérences et éléments manquants entre sources. Gardez visible tout conflit crédible ; ne moyennez pas des résultats incompatibles en un nombre unique sans règle de synthèse justifiée.
6. Publiez état probant et formulation calibrée : fortement étayé, étayé, provisoire, non vérifié, conflictuel ou suspendu. Indiquez la plus petite limite de source ou d'applicabilité qui contraint la formulation.
7. Publiez prochaine action de vérification et condition observable de révision. Sans soutien décisif, suspendez ou affaiblissez l'affirmation plutôt que de présenter une conclusion à forts enjeux comme établie.

## Public output contract

Renvoyez `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion` et `flip_condition`. La fiche doit montrer état probant et lien de source sûr ou mention « fourni par l'utilisateur » si applicable. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

La hiérarchie des plans est un guide, pas un substitut à leur adéquation à la question. Vérifiez caractère direct, population, résultat, temps, mesure, sélection, attrition et biais de publication. Un avis expert peut identifier un mécanisme sans estimer une taille d'effet ; une déclaration utilisateur peut révéler une expérience sans établir sa prévalence. Si les sources divergent sensiblement ou si la meilleure est indirecte, affaiblissez ou suspendez le résultat et nommez la limite.

## Stop conditions

Arrêtez-vous et posez une question bloquante si contexte cible ou affirmation est indéfini et que l'applicabilité changerait la décision. Suspendez si aucune source ne soutient directement une affirmation importante, si un conflit reste irrésolu ou si les limites empêchent une étiquette de force sûre. Arrêtez si le problème est un choix de valeurs, une implication formelle ou la génération d'explications plutôt qu'un calibrage probant.

## Complement handoff

Passez à `triangulation` si des flux indépendants peuvent corroborer ou révéler un conflit important. Transmettez tableau affirmation-source, limites de qualité et désaccord non résolu. La méthode complémentaire vérifie indépendance et convergence sans reconstruire les classements.

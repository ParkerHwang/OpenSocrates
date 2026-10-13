## Purpose

Utilisez cette procédure pour transformer un jugement ou une analyse solide en réponse destinée à la direction, dont l’idée directrice apparaît d’abord. Regroupez les raisons au même niveau, vérifiez que chaque énoncé supérieur résume ses détails et choisissez un ordre cohérent pour les points de même niveau. Elle améliore la structure de communication ; elle ne doit pas donner l’apparence d’un jugement établi à un jugement non tranché.

## Use when

Utilisez-la pour rapports, notes de décision, synthèses exécutives, propositions, présentations ou toute demande commençant par la réponse. Elle convient à une analyse longue dont la conclusion est suffisamment étayée, mais difficile à parcourir. Utilisez-la après avoir vérifié jugement sous-jacent et preuves.

## Do not use when

Ne l’utilisez pas pour contourner des preuves manquantes, cacher un conflit substantiel ou choisir une conclusion que l’analyse n’a pas établie. Ne forcez pas trois groupes de raisons s’ils se recoupent ou omettent un point décisif. Ne placez pas le contexte avant la réponse lorsqu’une conclusion directe est disponible, mais préservez périmètre et incertitude nécessaires dans la fiche.

## Inputs to establish

Établissez question directrice, conclusion actuelle, fondements substantiels, alternatives, décision du public, périmètre et état des preuves. Choisissez pour les raisons de même niveau un ordre déductif, chronologique, structurel ou d’importance. Posez au plus une question si la décision du public ou la conclusion manque ; sinon, précisez le public visé et poursuivez.

## Procedure

1. Publiez en tête la question directrice et une idée directrice en une phrase. Marquez la conclusion étayée, provisoire, contradictoire ou suspendue ; cela crée l’état visible de communication.
2. Publiez trois à quatre groupes de raisons soutenant ensemble l’idée directrice. Donnez à chacun un message clé en une ligne et relevez recoupements ou couverture manquante comme lacunes structurelles.
3. Publiez les détails sous chaque groupe et vérifiez la relation verticale : le message clé doit résumer ses détails, pas introduire une affirmation nouvelle.
4. Publiez l’ordre horizontal des groupes de même niveau — déductif, chronologique, structurel ou d’importance — et appliquez-le de façon cohérente. Relevez tout ordre alternatif modifiant substantiellement l’interprétation.
5. Publiez réponse principale, raisons regroupées et détails du haut vers le bas. Gardez visibles hypothèses nécessaires, conflits et fondements non vérifiés plutôt que de les effacer par polissage.
6. Publiez l’alternative ou le contre-argument le plus fort et la raison de son rejet. Si le jugement sous-jacent n’est pas tranché, marquez le résultat provisoire ou suspendu au lieu de présenter une réponse exécutive définitive.
7. Publiez la structure finale prête pour une fiche et une condition observable de basculement. Confirmez la présence du livrable demandé, des contraintes explicites, des vérifications probantes et des incertitudes divulguées.

## Public output contract

Renvoyez `top_line_answer`, `governing_thought`, `grouped_reasons`, `reason_groups`, `supporting_detail_order`, `scope_and_assumptions`, `alternatives_considered`, `completion_check` et `flip_condition`. La première phrase est la conclusion ; le contexte vient ensuite seulement en appui. Limitez les fondements de la fiche aux affirmations substantielles et marquez-les **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. La structure peut s’intégrer à une note, mais doit garder la conclusion en premier.

## Evidence and uncertainty rules

Une bonne structure ne renforce pas les preuves. Chaque groupe de raisons exige un fondement visible et les liens inférés ne doivent pas être présentés comme des faits directs. Si les groupes se contredisent, montrez le conflit plutôt que de le lisser dans un récit. Si un fondement, une alternative ou un élément d’achèvement manquant peut changer la réponse, utilisez une conclusion provisoire ou suspendue et nommez cet élément.

## Stop conditions

Arrêtez et posez une question bloquante sans question directrice stable ou décision du public si plusieurs réponses principales seraient substantiellement différentes. Suspendez si le jugement sous-jacent est non étayé, contradictoire ou incomplet. Arrêtez lorsque la réponse est déjà claire et que la suite n’est que mise en forme mécanique ; n’ajoutez pas de commentaire méthodologique à ce travail.

## Complement handoff

Passez le relais à `argument-mapping` si les groupes de raisons révèlent une structure irrésolue de soutien, objection ou prémisse partagée. Transmettez idée directrice, groupes substantiels et unique lien non résolu. La méthode complémentaire ne doit pas réordonner la réponse exécutive achevée ni produire une seconde pyramide complète.

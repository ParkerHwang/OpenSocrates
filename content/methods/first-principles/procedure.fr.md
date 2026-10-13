## Purpose

Utilisez cette procédure pour vérifier si une règle, un coût, un processus ou une architecture familière est réellement nécessaire ou simplement hérité. Décomposez le problème en affirmations et contraintes, vérifiez chacune, puis reconstruisez une option à partir des contraintes qui subsistent. La procédure protège contre l'imitation aveugle comme contre la réduction imprudente : une contrainte ne disparaît pas parce qu'elle gêne, et une possibilité physique n'est pas automatiquement un plan viable.

## Use when

Utilisez-la lorsque « c'est ainsi qu'on fait », une convention sectorielle, une dépendance historique ou une structure de coûts supposée bloque une refonte à fort effet de levier. Elle convient aux prix, architectures produit, processus opérationnels, allocations de ressources et exigences lorsque l'utilisateur veut questionner le fondement d'un choix existant. Elle aide si des options usées semblent hériter d'hypothèses devenues fausses.

## Do not use when

Ne l'utilisez pas pour une procédure standard validée que la tâche demande seulement d'exécuter, ou si une règle obligatoire, contrainte de sécurité, obligation légale ou interface fixée extérieurement ne peut être écartée. Ne traitez pas préférence, budget, calendrier ou coordination sociale comme faits purement physiques. Ne promettez pas une refonte à partir d'hypothèses non vérifiées et n'omettez pas les contraintes de mise en œuvre après décomposition.

## Inputs to establish

Établissez résultat cible, approche actuelle, exigences déclarées, contraintes, ressources, dépendances et raison de la nécessité supposée de l'approche. Séparez contraintes strictes, négociables, conventions et inconnues. Posez au maximum deux questions décisives, seulement si la réponse change la reconstruction. Identifiez toute règle à forts enjeux devant rester en vigueur.

## Procedure

1. Publiez résultat cible et approche actuelle en une phrase, puis périmètre et mesure de réussite. Cela établit une référence visible à comparer avec l'option reconstruite.
2. Publiez une décomposition en exigences atomiques, dépendances et contraintes affirmées. Marquez chaque élément fourni par l'utilisateur, sourcé, inféré ou supposé ; cela fait passer l'état de « donné » à « à vérifier ».
3. Publiez le verdict de nécessité de chaque contrainte : nécessaire physiquement ou logiquement, obligatoire extérieurement, contingente, préférentielle ou non vérifiée. Joignez le test ou la source soutenant ce verdict.
4. Publiez les contraintes survivantes et retirez seulement les hypothèses ayant échoué à la vérification. Si un élément contesté peut affecter sensiblement sécurité, légalité ou faisabilité, gardez-le comme contrainte non résolue explicite au lieu de le retirer silencieusement.
5. Publiez une reconstruction fondée sur ces contraintes. Précisez implications de ressources, temps, dépendances et coordination pour qu'elle ne soit pas seulement physiquement imaginable.
6. Publiez l'écart avec l'approche conventionnelle : changement, hypothèse qui l'a permis et nouveau risque ou compromis. Ajoutez une petite action de validation à chaque exigence non vérifiée.
7. Publiez exigences dérivées, option reconstruite et condition observable de révision. Si une contrainte irréductible ou entrée décisive manque, rendez la conclusion provisoire ou suspendue plutôt que revendiquer une percée.

## Public output contract

Renvoyez `irreducible_constraints`, `derived_requirements`, `reconstructed_option`, `assumptions_reintroduced`, `reintroduced_assumptions`, `conventional_delta`, `new_risks` et `flip_condition`. La première ligne précise si la refonte est étayée, provisoire ou suspendue. Distinguez option physiquement possible et option satisfaisant coûts, temps, sécurité et gouvernance de l'utilisateur. Les fondements de la fiche portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; une convention non étiquetée n'est pas un élément probant.

## Evidence and uncertainty rules

« Nécessaire » exige un fondement logique, physique, contractuel, de sécurité ou autre explicitement nommé ; la gêne ne prouve pas la nécessité. Une source décrivant une pratique courante soutient sa prévalence, pas son caractère inévitable. Les calculs précisent entrées et unités. Si une reconstruction dépend d'un lien non vérifié, la conclusion peut être une hypothèse bornée mais pas une recommandation fortement étayée. Gardez les conflits plutôt que moyenner des contraintes incompatibles.

## Stop conditions

Arrêtez-vous et posez une question bloquante si résultat cible ou limite non négociable de sécurité/légalité est peu clair et que plusieurs réponses produisent des reconstructions différentes. Suspendez si une contrainte irréductible ou entrée requise ne peut être établie. Arrêtez cette méthode si toutes les contraintes pertinentes sont fixées extérieurement ou si le travail restant est comparaison ordinaire d'options, vérification d'éléments ou mise en œuvre.

## Complement handoff

Passez à `morphological-analysis` si les exigences survivantes varient selon plusieurs dimensions cohérentes et qu'il faut explorer les combinaisons. Transmettez exigences dérivées, contraintes conservées et exclusions de faisabilité. La méthode complémentaire ne doit pas répéter la décomposition ni rediscuter les hypothèses retirées.

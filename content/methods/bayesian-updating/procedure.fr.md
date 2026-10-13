## Purpose

Utilisez cette procédure pour actualiser la confiance dans des hypothèses concurrentes lorsque de nouveaux éléments arrivent et que le fondement préalable ainsi que le sens des vraisemblances peuvent être exprimés de manière responsable. Elle rend visibles les taux de base, le sens des éléments, la variation a posteriori et la sensibilité. Les probabilités exactes sont facultatives ; une actualisation ordinale est honnête si les entrées numériques n'ont pas de provenance, mais un résultat a posteriori précis doit montrer ses entrées et sa normalisation.

## Use when

Utilisez-la pour les signaux diagnostiques, l'interprétation de tests, les éléments séquentiels, les estimations de risque et les décisions où une observation nouvelle doit modifier la confiance dans des hypothèses concurrentes. Elle convient aux questions de probabilité après observation, notamment lorsque les taux de base risquent d'être négligés.

## Do not use when

Ne l'utilisez pas sans fondement préalable défendable, sans même un sens ordinal de la différence des éléments entre hypothèses, ou pour une application stricte de règles. Ne confondez pas `P(E|H)` et `P(H|E)`, ne réutilisez pas les mêmes éléments comme actualisations indépendantes et n'inventez pas de pourcentages exacts donnant une fausse certitude.

## Inputs to establish

Établissez des hypothèses mutuellement exclusives et suffisamment exhaustives, la décision actuelle, le fondement préalable ou taux de base, les nouveaux éléments, le sens ou les valeurs de vraisemblance sous chaque hypothèse, les dépendances entre éléments et le seuil d'action. Posez au maximum deux questions décisives si un fondement préalable ou une définition manquante change l'actualisation ; sinon, utilisez un niveau préalable ordinal étiqueté.

## Procedure

1. Publiez les hypothèses concurrentes et le seuil de décision. Précisez ce qui est actualisé et marquez les hypothèses comme fournies par l'utilisateur, étayées par une source ou provisoires ; cela établit l'état visible de l'actualisation.
2. Publiez le fondement préalable de chaque hypothèse, notamment la source du taux de base, la population de référence ou un niveau ordinal borné. Si les probabilités préalables sont inconnues, montrez l'incertitude au lieu de choisir un nombre commode.
3. Publiez chaque élément et son sens sous chaque hypothèse : favorable, défavorable ou largement neutre. Vérifiez si les éléments sont indépendants ou réutilisent partiellement le même signal.
4. Publiez la variation a posteriori avec un calcul exact seulement si les entrées sont défendables ; sinon, indiquez une actualisation qualitative ou un intervalle. Montrez la normalisation des hypothèses concurrentes et préservez le sens de l'a priori vers l'a posteriori.
5. Publiez la sensibilité aux hypothèses de probabilités préalables et de vraisemblance. Identifiez le changement de valeur ou de sens qui inverserait le classement ou ferait franchir le seuil d'action.
6. Publiez l'hypothèse actuellement dominante, le statut a posteriori et les prochains éléments qui amélioreraient le plus la décision. Gardez visible une hypothèse moins bien classée mais plausible si elle reste importante.
7. Publiez la conclusion actualisée et une condition observable de révision. Si le fondement préalable ou le sens de vraisemblance manque, suspendez le résultat ou gardez-le provisoire au lieu d'afficher une probabilité a posteriori inventée.

## Public output contract

Renvoyez `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold` et `flip_condition`. La fiche doit distinguer une probabilité a posteriori calculée d'une actualisation ordinale ou inférée. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; un taux de base numérique n'est pas automatiquement vérifié.

## Evidence and uncertainty rules

La probabilité préalable doit provenir d'un taux de base défendable, d'une estimation experte avec provenance ou d'une probabilité a posteriori antérieure. La vraisemblance est `P(E|H)`, pas la probabilité de l'hypothèse après observation. N'actualisez pas deux fois à partir d'éléments dépendants. Si des entrées crédibles divergent, montrez le conflit et affaiblissez ou suspendez le résultat. Si la sensibilité traverse le seuil d'action, indiquez que la décision est fragile.

## Stop conditions

Arrêtez-vous et posez une question bloquante si les hypothèses ou la définition des éléments manquent et que différents choix inverseraient l'action. Suspendez le résultat en l'absence de fondement préalable ou de sens de vraisemblance défendable, ou si une dépendance empêche une actualisation fiable. Arrêtez si la véritable tâche est une règle stricte, la recherche d'explications ou le classement de qualité des sources.

## Complement handoff

Passez à `abduction` si le problème principal est de générer et comparer des explications plutôt que d'actualiser un ensemble d'hypothèses défini. Transmettez les éléments observés, les hypothèses candidates et le test discriminant. La méthode complémentaire ne doit pas refaire le calcul a posteriori.

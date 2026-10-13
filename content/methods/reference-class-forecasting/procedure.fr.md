## Purpose

Utilisez cette procédure pour remplacer une prévision interne par une comparaison externe fondée sur une classe défendable de cas achevés comparables. Elle estime une cible à partir des résultats observés et explicite les faits actuels justifiant un ajustement. C’est une aide à la calibration, pas une promesse ni une autorisation d’inventer population, distribution ou probabilité.

## Use when

Utilisez-la pour prévoir délais, coûts, demande, adoption, fiabilité ou livraison si des cas passés similaires sont disponibles et que le plan interne peut être optimiste. Elle est particulièrement utile quand une proposition affirme « ce cas est différent » sans montrer comment cela modifie l’intervalle attendu. Elle convient à une décision exigeant un intervalle étayé plutôt qu’une estimation ponctuelle.

## Do not use when

Ne l’utilisez pas sans classe défendable de cas achevés, si cible et unité sont floues ou pour un cas unique sans résultat comparable. Quelques anecdotes ne constituent pas une distribution de base ; ne sélectionnez pas seulement les réussites et ne transformez pas une prévision interne en preuve. Pour une décision purement mécanique ou un besoin de diagnostic causal plutôt que de calibration, arrêtez et réorientez.

## Inputs to establish

Établissez résultat cible, unité, horizon, date limite des données et limite acceptable. Définissez les règles d’inclusion et d’exclusion avant d’examiner les résultats. Recueillez cas observés, définitions des résultats, couverture, données manquantes et statut des sources. Relevez différences connues du projet actuel et prévision interne. Posez au plus deux questions décisives, seulement si elles changent la classe ou la cible. Marquez chaque entrée vérifiée, calculée, inférée, supposée, non vérifiée ou contradictoire.

## Procedure

1. Publiez cible, unité, horizon et limite décisionnelle en une phrase. **Résultat visible/changement d’état :** une référence prévisionnelle existe ; toute cible ambiguë est suspendue plutôt que restreinte silencieusement.
2. Publiez la règle de classe de référence : inclusion, exclusion, dimensions de similarité et lacunes de couverture connues. **Résultat visible/changement d’état :** l’intuition devient une définition de classe auditable.
3. Publiez la distribution observée avec les seuls cas disponibles : effectif, centre, dispersion, intervalle et queues lorsqu’ils sont calculables. **Résultat visible/changement d’état :** chaque statistique a ses entrées et une étiquette de source/preuve ; les statistiques indisponibles restent non vérifiées.
4. Publiez la référence externe à côté du plan interne et expliquez le sens de leur différence. **Résultat visible/changement d’état :** le jugement indique si le plan interne est dans, au-dessus ou au-dessous de la distribution observée sans traiter cette position comme une probabilité.
5. Publiez les ajustements des différences substantielles du cas actuel, une par une. **Résultat visible/changement d’état :** chaque ajustement a direction, justification et état des preuves ; un ajustement numérique exige une ampleur défendable.
6. Publiez un intervalle délimité et les conditions rendant ses bornes plausibles. **Résultat visible/changement d’état :** l’intervalle est élargi ou suspendu si couverture, sélection ou preuves des queues sont faibles ; aucun taux de base fabriqué ne comble la lacune.
7. Publiez le statut étayé, provisoire ou suspendu, une condition de basculement et une prochaine vérification. **Résultat visible/changement d’état :** une classe ou entrée de résultat décisive manquante devient une suspension explicite, pas une recommandation arbitraire.

## Public output contract

Renvoyez `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition` et un statut étayé, provisoire ou suspendu. La conclusion dit ce que soutient la classe observée, sans promettre que le cas actuel la reproduira. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; l’incertitude nomme couverture manquante ou risque de sélection, et la condition de basculement est observable, pas « si de nouvelles informations apparaissent ».

## Evidence and uncertainty rules

La classe n’est soutenue que par des cas achevés dont cible, unité et inclusion sont définies. Une source peut vérifier un résultat observé sans vérifier la comparabilité du projet actuel ; marquez cette comparaison inférée sauf soutien direct. Les calculs montrent cas ou références utilisés et règle d’arrondi. N’inventez médiane, queue, effectif, taux de base ou probabilité. Préservez biais de sélection, cas manquants, définitions divergentes et limites des petits échantillons. « Ce cas est différent » reste une hypothèse d’ajustement tant que direction et effet ne sont pas étayés.

## Stop conditions

Posez une question bloquante et arrêtez si cible, unité ou limite décisionnelle présente des interprétations substantiellement différentes. Suspendez la conclusion si aucune classe défendable, définition de résultat ou entrée comparative décisive ne peut être établie. Arrêtez si la suite relève d’une explication causale, d’un choix d’options ou d’un calcul mécanique ; passez le relais plutôt que de forcer une prévision externe.

## Complement handoff

Passez le relais à `sensitivity-analysis` si la décision dépend des changements de distribution de référence ou d’ajustement du cas actuel. Transmettez cible, référence observée, plages d’ajustement testées, limites de couverture et condition de basculement. La méthode complémentaire doit faire varier ces entrées sans reconstruire la classe ni traiter le résultat comme un nouveau taux de base.

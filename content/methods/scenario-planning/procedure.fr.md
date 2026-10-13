## Purpose

Utilisez cette procédure pour structurer plusieurs futurs externes cohérents et y préparer des choix. Le but n’est pas de prévoir un futur unique, mais d’exposer le comportement d’une décision lorsque des forces importantes et incertaines divergent. Le résultat sépare actions sans regret et conditionnelles et garde visibles des signaux précurseurs pour un réexamen ultérieur.

## Use when

Utilisez-la pour stratégie, investissement, politique, infrastructure ou produit à long horizon, particulièrement cinq ans ou plus ou après des échecs répétés de prévision. Elle répond à « À quoi devons-nous nous préparer ? » si plusieurs conditions externes peuvent plausiblement façonner l’issue. Elle aide avant un engagement irréversible, pas seulement après avoir choisi une prévision.

## Do not use when

Ne l’utilisez pas pour une prévision ponctuelle à court terme, une simple variation numérique optimiste/centrale/pessimiste ou une décision sans incertitude externe significative. Ne choisissez pas deux axes corrélés, ne rédigez pas quatre versions du même futur bon/mauvais, n’attribuez pas de probabilités et ne concluez pas par des récits sans action. Pour comparer les entrées numériques d’un modèle unique, utilisez l’analyse de sensibilité.

## Inputs to establish

Établissez question centrale, horizon, limite du système, décision actuelle et prémisses communes suffisamment prévisibles pour tenir dans tous les futurs. Listez forces motrices candidates avec preuves d’impact et d’incertitude et identifiez deux incertitudes critiques indépendantes. Relevez contraintes, parties prenantes, engagements et observations pouvant devenir des signaux. Posez au plus deux questions décisives, seulement si la réponse change question centrale ou paire d’axes. Marquez prémisses et forces vérifiées, calculées, inférées, supposées, non vérifiées ou contradictoires.

## Procedure

1. Publiez question centrale, horizon, limites, décision actuelle et prémisses communes. **Résultat visible/changement d’état :** une demande ouverte sur le futur devient une question de préparation délimitée.
2. Publiez les deux axes critiques et pourquoi chacun a un impact élevé et est difficile à prévoir. **Résultat visible/changement d’état :** les candidats corrélés, peu importants ou prévisibles sont rejetés ou placés dans les prémisses communes.
3. Publiez une matrice 2×2 de quatre scénarios nommés, cohérents en interne, avec un bref chemin d’émergence. **Résultat visible/changement d’état :** quatre futurs distincts existent comme environnements plausibles de test ; aucun ne reçoit probabilité ou préférence.
4. Publiez validité et vulnérabilité de la décision actuelle dans chaque scénario. **Résultat visible/changement d’état :** un relevé de test en soufflerie distingue actions sans regret, conditionnelles et choix échouant dans toute la matrice.
5. Publiez signaux précurseurs, réponses aux déclencheurs et fréquence de réexamen pour distinguer les scénarios à mesure que le contexte évolue. **Résultat visible/changement d’état :** les scénarios deviennent un plan vivant de surveillance plutôt qu’un récit statique.
6. Publiez la conclusion de robustesse et une condition observable de basculement. **Résultat visible/changement d’état :** si axes, prémisses ou implications d’action ne sont pas défendables, la conclusion devient provisoire ou suspendue plutôt qu’une prévision déguisée.

## Public output contract

Renvoyez `driving_uncertainties`, `scenarios`, `signposts`, `no_regret_actions`, `contingent_actions`, `decision_check` et `flip_condition`, avec statut étayé, provisoire ou suspendu. `scenarios` contient quatre résumés nommés avec chemins et implications décisionnelles. La fiche énonce conclusion de préparation, incertitude substantielle, condition observable changeant le plan et résumé compact des alternatives. Gardez matrice complète et cadence de réexamen dans la trace ou un artefact d’appui.

## Evidence and uncertainty rules

Les prémisses communes doivent être sourcées ou explicitement supposées. Un axe est une hypothèse de cadrage sur impact et incertitude, pas un fait mesuré sauf preuve contraire. Les scénarios doivent être cohérents et plausibles, mais ne sont pas des prévisions ; n’ajoutez jamais pourcentages, classements ou probabilités cachées. Séparez signaux observés et interprétations inférées. N’inventez tendance, date de déclenchement ou force externe. Si les axes sont dépendants, révisez la paire ou suspendez.

## Stop conditions

Posez une question bloquante et arrêtez si question centrale, horizon ou limite décisionnelle a des sens substantiellement différents. Suspendez sans incertitudes indépendantes à impact élevé, prémisses défendables ou décision exploitable. Arrêtez pour une prévision courte, une variation de modèle ou un choix opérationnel tranché ; réorientez plutôt que de forcer quatre scénarios.

## Complement handoff

Passez le relais à `pestel-analysis` si les forces des scénarios exigent un examen structuré politique, économique, social, technologique, environnemental ou juridique. Transmettez question centrale, horizon, prémisses communes, forces candidates, axes retenus et états des preuves. La méthode complémentaire teste les forces externes sans réduire les scénarios à un futur unique prédit.

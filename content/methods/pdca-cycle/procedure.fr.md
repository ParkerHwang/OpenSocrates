## Purpose

Utilisez cette procédure pour conduire un cycle Plan–Do–Check–Act délimité sur une hypothèse d’amélioration opérationnelle. Elle rend visibles objectif, mesure, petit périmètre d’exécution, règle de comparaison et décision de standardisation, pour accumuler preuves et mémoire organisationnelle. C’est une boucle d’apprentissage contrôlée, pas un substitut au diagnostic d’une cause profonde inconnue ni à la réponse à un incident de sécurité en cours.

## Use when

Utilisez-la lorsqu’un processus ou service peut changer dans un périmètre réduit et réversible, que l’amélioration attendue est mesurable et que des cycles répétés peuvent relever un standard. Elle convient à une hypothèse d’amélioration exigeant une courte fenêtre d’observation et une décision claire de standardiser, réviser ou abandonner. Utilisez-la pour apprendre de l’exécution sans engager toute l’exploitation dans un changement non testé.

## Do not use when

Ne l’utilisez pas si la cause profonde est inconnue et que l’expérimentation peut masquer ou aggraver un préjudice, si une règle contraignante ne laisse aucune latitude ou si une réponse urgente de sécurité, juridique ou à un incident est requise. Ne lancez pas un cycle pour créer de l’activité sans règle de vérification. Ne transformez pas une demande mécanique en programme d’amélioration et ne standardisez pas un changement parce qu’il a été annoncé ou réalisé une fois.

## Inputs to establish

Établissez objectif d’amélioration, référence observée ou état du processus, hypothèse, périmètre, responsable et direction attendue du changement. Définissez avant Do l’indicateur, l’unité, la source, la fenêtre d’observation, les garde-fous, la condition d’arrêt et la règle de comparaison. Précisez les preuves nécessaires pour standardiser, réviser ou abandonner, ainsi que l’endroit où consigner le prochain cycle ou le standard versionné. Posez au plus deux questions concises, seulement si une réponse manquante peut changer la limite de sécurité, la mesure ou la décision Act ; sinon, étiquetez le manque comme non vérifié et suspendez s’il est décisif.

## Procedure

1. **Publiez la fiche Plan.** Énoncez objectif, référence, hypothèse d’amélioration, direction attendue, périmètre, responsable et limite temporelle. Marquez la référence comme vérifiée, calculée, fournie par l’utilisateur, inférée, supposée ou non vérifiée. **Résultat visible/changement d’état :** état du plan.
2. **Publiez la spécification Check.** Nommez indicateur, unité, source, méthode de collecte, fenêtre d’observation, règle de comparaison, garde-fous et condition d’arrêt. Annoncez les preuves permettant de standardiser, réviser ou abandonner. **Résultat visible/changement d’état :** règle de vérification.
3. **Publiez le journal Do.** Exécutez seulement dans le petit périmètre approuvé et consignez changement réel, écarts, exclusions, incidents et observations. Gardez un retour arrière possible et n’élargissez pas l’exposition parce que le premier signal semble favorable. **Résultat visible/changement d’état :** relevé d’exécution auditable.
4. **Publiez le résultat Check.** Comparez valeurs ou descriptions attendues et observées selon la règle annoncée. Identifiez données manquantes, facteurs de confusion, limites des sources et contradictions. **Résultat visible/changement d’état :** écart de résultat avec état des preuves.
5. **Publiez la décision Act.** Choisissez standardisation, révision, abandon ou suspension selon les preuves et garde-fous. Si le résultat est mitigé ou la mesure décisive manque, maintenez le changement provisoire et consignez la condition non résolue. **Résultat visible/changement d’état :** décision Act ou suspension.
6. **Publiez le prochain cycle.** Consignez standard versionné ou hypothèse révisée, responsable, prochaine observation et une ou deux conditions observables de basculement. Transmettez les apprentissages et ce qui reste non vérifié. **Résultat visible/changement d’état :** plan du prochain cycle ou résultat suspendu.

## Public output contract

Renvoyez les champs prêts pour une fiche `plan_objective_measure`, `do_scope`, `check_rule` et `act_standardize_decision`, avec l’état des preuves pour chaque fondement substantiel. `plan_objective_measure` doit inclure la référence ou son absence ; `do_scope` montre l’exposition délimitée ; `check_rule` montre la comparaison et la règle d’arrêt ; `act_standardize_decision` distingue standardisation, révision, abandon et suspension. Incluez une hypothèse pour le prochain cycle ou une raison claire de ne pas poursuivre. Une mesure décisive manquante produit un résultat suspendu.

## Evidence and uncertainty rules

Traitez observation directe, source liée, calcul reproductible, relevé fourni par l’utilisateur, inférence et prémisse de travail adoptée comme des états probants différents. Pour `computed`, montrez entrées, expression, unités et arrondi pertinent. Sans référence défendable ou si la collecte a changé, marquez la comparaison non vérifiée. N’inventez ni probabilités, ni tailles d’effet, ni effectifs d’échantillon, ni certitude causale. Un cycle peut soutenir un apprentissage local, mais prouve rarement un standard permanent ; des observations crédibles contradictoires maintiennent la décision Act en conflit ou suspendue. Préservez écarts et signaux négatifs plutôt que de rapporter seulement l’amélioration.

## Stop conditions

Suspendez si objectif, référence, mesure, règle de comparaison, responsable ou périmètre sûr manque et peut modifier la décision Act. Arrêtez immédiatement si le cycle cause un préjudice continu, affaiblit un contrôle requis, dépasse l’autorisation ou perd un retour arrière sûr. Si la cause profonde est inconnue et que le cycle peut la masquer, passez le relais à `root-cause-analysis`. Après une vérification échouée ou non concluante, arrêtez si aucune hypothèse révisée ou prochaine observation sûre n’existe ; ne répétez pas Do sans apprentissage.

## Complement handoff

Passez le relais à `root-cause-analysis` si Check révèle une défaillance répétée, des chemins causaux concurrents ou une faiblesse de contrôle à diagnostiquer avant un autre cycle. Transmettez plan publié, périmètre Do délimité, résultat Check, écarts, états des preuves et question de contrôle restante. Ne transmettez pas d’accusation non étayée et ne lancez pas une seconde méthode complète simplement parce que le premier cycle est non concluant.

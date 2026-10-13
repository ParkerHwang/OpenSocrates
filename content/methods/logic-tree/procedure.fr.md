## Purpose

Utilisez cette procédure pour décomposer une vaste question de diagnostic, de planification ou de couverture en une hiérarchie dont les branches sont mutuellement claires, collectivement adéquates et exploitables aux feuilles. Choisissez un seul axe de décomposition par niveau, séparez les arbres des causes et des moyens et associez une vérification ou une prochaine action à chaque branche terminale. L’arbre structure la recherche ; il ne prouve pas que chaque branche est vraie.

## Use when

Utilisez-la si le problème est vaste, les causes incertaines, un plan nécessite une couverture ou une question « pourquoi », « comment » ou « quoi » exige une structure exhaustive. Elle convient au diagnostic, à la couverture des risques, aux exigences et à l’exploration de solutions lorsque des branches qui se recoupent entraîneraient des responsabilités dupliquées ou des tâches oubliées.

## Do not use when

Ne l’utilisez pas pour une boucle de rétroaction étroitement couplée qu’une hiérarchie ne peut représenter de façon responsable, ni lorsqu’une simple liste ou un calcul direct suffit. Ne mélangez pas causes et solutions au même niveau, n’utilisez pas « autre » pour masquer une lacune substantielle et cessez de subdiviser une branche dès que sa prochaine action est claire.

## Inputs to establish

Établissez la question racine, le type d’arbre (`why`, `how` ou `what`), la mesure de réussite, le périmètre, les faits connus et les vérifications disponibles. Choisissez un axe de décomposition pour le premier niveau et expliquez son adéquation. Posez au plus une question décisive si la racine ou le type d’arbre modifie l’analyse ; sinon, énoncez une racine délimitée.

## Procedure

1. Publiez une question racine mesurable et le type d’arbre retenu. Précisez périmètre et mesure de réussite ; cela crée l’état initial visible de l’arbre.
2. Publiez les branches du premier niveau selon un axe unique et nommez cet axe. Indiquez pour chaque branche si elle est observée, inférée ou candidate à vérifier.
3. Publiez le niveau suivant seulement si une subdivision plus fine change une action ou un test. À chaque niveau, montrez les vérifications d’exclusion mutuelle et de couverture comme une mise à jour d’état.
4. Publiez les feuilles, chacune avec une méthode de vérification, une demande de données, un responsable ou une prochaine action. Une feuille encore abstraite n’est pas terminale ; laissez l’arbre ouvert ou restreignez la racine.
5. Publiez les branches élaguées et la raison de chaque élagage : preuves contradictoires, hors périmètre ou couverture dupliquée. Ne supprimez pas une branche uniquement parce qu’elle gêne.
6. Publiez un ordre de priorité selon l’importance, les preuves et la possibilité d’agir, sans précision numérique inventée. Signalez les branches nécessitant une méthode causale ou probante distincte.
7. Publiez l’arbre achevé, les lacunes de couverture et une condition observable de basculement. Si une branche critique n’est ni testable ni délimitée, suspendez le jugement ou posez une question bloquante.

## Public output contract

Renvoyez `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order` et `flip_condition`. Le résultat public doit montrer des branches mutuellement claires, une couverture collectivement pertinente et des feuilles exécutables. Les fondements de la fiche portent les étiquettes **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. Ne présentez pas l’arbre lui-même comme preuve d’une affirmation causale.

## Evidence and uncertainty rules

ME et CE sont des vérifications distinctes : l’absence de recoupement ne garantit pas la couverture, et la couverture ne garantit pas l’absence de recoupement. Une formule familière reste une structure candidate tant que ses hypothèses ne conviennent pas au domaine. La preuve ou le test de chaque feuille doit être identifiable ; les branches non étayées restent des hypothèses. Si les branches se contredisent ou qu’une branche manquante peut changer la décision, divulguez la lacune et suspendez ou affaiblissez la conclusion.

## Stop conditions

Arrêtez et posez une question bloquante si la question racine ou le type d’arbre ne peut être délimité et que les alternatives mèneraient à des travaux différents. Suspendez si une lacune substantielle de couverture n’a pas de test, ou si l’interdépendance des branches rend une hiérarchie trompeuse. Arrêtez lorsque les feuilles ont des actions claires et que la suite relève d’une méthode causale, probante ou décisionnelle.

## Complement handoff

Passez le relais à `root-cause-analysis` si la branche retenue concerne une défaillance récurrente et exige une chaîne causale plutôt qu’une décomposition supplémentaire. Transmettez la racine, la branche retenue, les lacunes probantes et les tests des feuilles. La méthode complémentaire ne doit pas reconstruire les branches sans rapport.

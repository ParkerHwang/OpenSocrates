## Purpose

Utilisez cette procédure pour transformer une affirmation, explication ou un plan favori en prédiction risquée et testable, et préciser ce qui compterait contre lui. Elle sépare l'affirmation cible des hypothèses auxiliaires et des erreurs de mesure, puis indique ce que le test observé peut et ne peut pas établir. Une prédiction échouée constitue un élément contre le dispositif testé ; elle ne réfute pas automatiquement toutes les idées associées.

## Use when

Utilisez-la lorsqu'une affirmation doit produire une prédiction risquée, si l'utilisateur demande ce qui pourrait montrer qu'une explication est fausse ou si des récits après coup sont pris pour des prévisions. Elle convient aux hypothèses de recherche, plans produit, explications diagnostiques et affirmations fortes exigeant une tentative décisive de réfutation.

## Do not use when

Ne l'utilisez pas si aucune implication testable ne peut être énoncée, si la tâche est un choix de valeurs ou une exécution mécanique, ou si l'affirmation n'est qu'une définition. Ne prenez pas la testabilité pour une preuve, ne sauvez pas chaque prédiction échouée par une hypothèse auxiliaire ad hoc et n'abandonnez pas une théorie complexe après un seul échec sans vérifier mesure et dispositif auxiliaire.

## Inputs to establish

Établissez affirmation cible, périmètre, prédiction risquée, fenêtre d'observation, mesure, hypothèses auxiliaires, seuil de réfutation et décision touchée. Précisez si le test est prévu, observé ou indisponible. Posez au maximum une question décisive si prédiction ou seuil ne peut être borné autrement.

## Procedure

1. Publiez l'affirmation et son périmètre, puis reformulez-la en prédiction risquée pouvant échouer. Cela établit une cible visible de test plutôt qu'une explication après coup.
2. Publiez le réfutateur : résultat, seuil ou phénomène observable comptant contre l'affirmation. Excluez les conditions vagues comme « éléments inattendus ».
3. Publiez hypothèses auxiliaires et conditions de mesure séparément de l'affirmation cible. Précisez quel échec mettrait en cause l'affirmation, le dispositif ou la mesure.
4. Publiez test prévu ou observé, provenance et résultat. Si le test est indisponible, indiquez l'observation nécessaire et gardez le statut non vérifié.
5. Publiez l'interprétation : étayée pour ce test, affaiblie, pas encore testée ou non concluante. Ne faites pas d'un résultat non réfutant une confirmation forte.
6. Publiez toute réparation proposée et vérifiez si elle était prévue avant le résultat ou ajoutée ad hoc. Une réparation immunisant l'affirmation sans soutien indépendant reste une faiblesse.
7. Publiez statut actuel, prochain test et condition observable de révision. Si aucun réfutateur ne peut être énoncé, suspendez le résultat ou refusez la méthode plutôt que fabriquer un langage d'apparence scientifique.

## Public output contract

Renvoyez `claim`, `scope`, `risky_prediction`, `falsifier`, `auxiliary_assumptions`, `measurement_conditions`, `observed_needed_test`, `test_and_provenance`, `observed_or_needed_result`, `status` et `flip_condition`. Distinguez non testé, non concluant, affaibli et étayé pour ce test. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; une affirmation non réfutée n'est pas automatiquement vérifiée.

## Evidence and uncertainty rules

Un réfutateur doit être observable et lié au périmètre préspécifié de l'affirmation. Un test échoué peut viser une hypothèse auxiliaire ou une mesure plutôt que toute la théorie. Ne comptez pas un ajustement après coup comme soutien indépendant. Si le test n'a pas été réalisé ou le seuil a été choisi après les résultats, marquez la conclusion non vérifiée ou conflictuelle et indiquez la limite.

## Stop conditions

Arrêtez-vous et posez une question bloquante si affirmation ou prédiction ne peut être bornée. Refusez ou suspendez sans implication testable, si l'observation nécessaire est indisponible ou si une affirmation à forts enjeux n'a pas de test sûr. Arrêtez si la tâche est qualité des sources, implication formelle ou génération d'explications plutôt que tentative de réfutation.

## Complement handoff

Passez à `lean-startup` seulement si l'affirmation réfutable concerne un produit ou marché et qu'un test minimal sûr est la prochaine décision. Transmettez prédiction risquée, réfutateur, conditions de mesure et exclusions de sécurité. Le complément ne doit pas remplacer un réfutateur manquant par une expérience générique.

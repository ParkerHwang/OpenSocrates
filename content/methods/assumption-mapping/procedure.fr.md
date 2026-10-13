## Purpose

Utilisez cette procédure pour rendre visibles les croyances soutenant une idée, séparer l'importance des éléments probants et choisir le plus petit test sûr des hypothèses susceptibles de changer la décision. Elle produit un support d'apprentissage hiérarchisé, pas un verdict de vérité.

## Use when

Utilisez-la avant de vous engager dans une idée de produit, un changement opérationnel, une orientation de recherche ou un jugement fondé sur des croyances incertaines. Elle est utile si une équipe ne s'accorde pas sur ce qui doit être vrai, si les éléments probants sont inégaux ou si les tests possibles demandent un ordre explicite. Elle aide particulièrement avant une expérience réversible ou un engagement de ressources, tant que la décision peut encore changer sans risque.

## Do not use when

Ne l'utilisez pas pour une demande mécanique, une règle obligatoire sans latitude ou une décision irréversible. N'exposez pas d'hypothèses privées ou sensibles simplement pour compléter la carte ; limitez le résultat aux informations autorisées. N'inventez pas de test si aucun résultat observable ne peut départager l'hypothèse ou si le test crée une exposition juridique, de sécurité, de confidentialité ou opérationnelle importante. Pour une expérience de marché, transmettez l'hypothèse choisie à `lean-startup` plutôt que de transformer la carte en rapport complet.

## Inputs to establish

Établissez la question de décision, le résultat souhaité, l'action proposée et ce qui changerait sensiblement la décision. Recueillez des hypothèses candidates sous forme d'énoncés testables, classés par désirabilité, viabilité, faisabilité ou autre domaine nommé. Consignez pour chacune la source, l'observation utilisateur, le calcul ou l'inférence. Définissez les plus petits tests sûrs possibles, les contraintes, le responsable, la fenêtre d'observation et la règle de décision. Posez au maximum deux questions concises, seulement si la réponse manquante pourrait changer les hypothèses les plus risquées ou la sécurité du test ; sinon, marquez-la comme supposée.

## Procedure

1. **Publiez le cadre.** Regroupez la question de décision, le résultat visé, le périmètre et les limites de décision dans une fiche compacte. Marquez chaque limite comme fournie par l'utilisateur, vérifiée à partir d'une source, inférée ou supposée. **Résultat visible/changement d'état :** cadre établi.
2. **Publiez le registre des hypothèses.** Reformulez chaque croyance en énoncé qu'une observation pourrait soutenir, affaiblir ou laisser indéterminé. Joignez son domaine et la conséquence de sa fausseté. **Résultat visible/changement d'état :** registre d'hypothèses étiqueté.
3. **Publiez les deux axes.** Placez chaque hypothèse sur un axe ordinal d'importance et un axe d'état probant. N'utilisez élevé, moyen ou faible qu'avec un fondement explicite ; employez `verified`, `computed`, `inferred`, `assumed`, `unverified` ou `conflicted` pour le soutien. **Résultat visible/changement d'état :** carte importance/éléments probants.
4. **Publiez l'ensemble le plus risqué.** Sélectionnez les hypothèses dont la fausseté changerait sensiblement le résultat et dont le soutien est le plus faible ou contradictoire. Justifiez chaque choix, conservez les ex æquo impossibles à départager et consignez l'incertitude non résolue. **Résultat visible/changement d'état :** ensemble le plus risqué et incertitude.
5. **Publiez une fiche de test sûr.** Pour chaque hypothèse retenue, nommez le test réversible le moins coûteux, le signal observable, la fenêtre d'observation, le responsable et la règle de décision. Ajoutez une limite d'arrêt ou de retour arrière. **Résultat visible/changement d'état :** fiche de test sûr ou suspension.
6. **Publiez la carte de décision.** Précisez ce que changerait un signal favorable, défavorable, contradictoire ou absent : poursuivre, réviser, chercher des éléments ou suspendre. **Résultat visible/changement d'état :** conclusion provisoire et conditions de révision.

## Public output contract

Renvoyez les champs prêts pour la fiche `assumptions`, `importance_evidence_axes`, `riskiest_set`, `next_test` et `flip_condition`. Chaque hypothèse conserve son domaine, sa conséquence et son état probant. `next_test` doit inclure un signal observable, une limite sûre et une règle de décision ; il ne doit pas promettre de prouver l'idée entière. Le résultat replié contient au maximum trois hypothèses importantes et deux incertitudes non résolues ; les autres branches restent dans la trace. Si une hypothèse décisive ou une limite de test manque, indiquez que le résultat est suspendu ou provisoire.

## Evidence and uncertainty rules

Une hypothèse n'est pas un fait parce qu'elle est répétée, importante ou plausible. Reliez les affirmations `verified` à une source disponible ; montrez les entrées des `computed` ; marquez `inferred` le raisonnement fondé sur d'autres éléments, `assumed` les prémisses adoptées, `unverified` les vérifications manquantes et `conflicted` les désaccords. N'utilisez une importance ordinale qu'avec une conséquence ou une dépendance décisionnelle explicite. N'inventez ni probabilités, ni tailles d'échantillon, ni résultats de tests. Un signal ne met à jour l'hypothèse que dans le contexte testé ; il ne permet pas une généralisation sans autre soutien.

## Stop conditions

Suspendez le résultat si la question de décision, une conséquence importante ou l'autorisation d'exposer une hypothèse manque. Suspendez-le si deux hypothèses restent à égalité et que les éléments manquants pourraient changer l'ordre des tests. Arrêtez avant de proposer un test dangereux, illégal, irréversible ou sans observation significative. Si la tâche est mécanique ou la décision sans latitude, arrêtez cette méthode et utilisez la réponse directe ou réglementaire applicable. Ne transformez pas une carte vide en recommandation.

## Complement handoff

Passez à `lean-startup` si l'hypothèse la plus risquée publiée concerne le marché, le produit, la valeur, la croissance ou les revenus et requiert une expérience minimale d'apprentissage. Transmettez uniquement son énoncé, son domaine, sa conséquence, son état probant, le signal sûr retenu et la règle de décision. Ne répétez pas toute la carte et ne laissez pas entendre que la méthode complémentaire a déjà réalisé le test. Utilisez séparément `value-of-information` si la question ouverte est surtout de savoir si une recherche supplémentaire vaut son coût.

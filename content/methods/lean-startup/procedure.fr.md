## Purpose

Utilisez cette procédure pour réduire l’incertitude portant sur une hypothèse de marché, de produit ou de modèle économique au moyen d’une expérience d’apprentissage minimale. Elle transforme l’hypothèse la plus risquée en un test sûr avec un indicateur exploitable et une décision déclarée à l’avance. Le MVP est ici un instrument d’apprentissage, pas un produit inachevé, un plan de lancement complet ni une preuve de demande au seul motif qu’un produit a été livré.

## Use when

Utilisez-la lorsqu’une hypothèse importante sur la valeur, la croissance, l’adoption ou les revenus n’est pas vérifiée et qu’une petite observation pourrait modifier la décision de pivoter, persévérer ou arrêter. Elle convient à une décision de produit ou d’entreprise avec une cible identifiable, une exposition délimitée et un indicateur observable. Utilisez-la avant une construction coûteuse lorsqu’un test réversible peut répondre à la question.

## Do not use when

N’utilisez pas un test réel minimal lorsque la sécurité physique, le droit, la confidentialité, la sécurité informatique ou une exposition client ou opérationnelle irréversible le rendent inapproprié. Ne qualifiez pas d’expérience une livraison sans mesure et ne faites pas d’un indicateur flatteur une preuve d’apprentissage. N’utilisez pas cette méthode pour une tâche purement mécanique, une décision contraignante sans latitude expérimentale ou un problème dont la véritable cause opérationnelle inconnue doit d’abord être diagnostiquée.

## Inputs to establish

Établissez la décision, l’utilisateur ou le contexte cible, une hypothèse réfutable, son présupposé le plus risqué et les preuves disponibles. Définissez le test minimal ou MVP, la limite d’exposition, l’indicateur exploitable et son unité, la fenêtre d’observation, le seuil ou la règle qualitative, le responsable et la limite de retour arrière ou d’arrêt. Relevez les effets de sélection, les limites d’accès et la source de référence éventuelle. Posez au plus deux questions concises, seulement si la réponse peut modifier la sécurité du test, l’indicateur ou la prochaine décision ; sinon, marquez le manque comme non vérifié et suspendez la décision s’il est décisif.

## Procedure

1. **Publiez l’hypothèse.** Formulez une proposition conditionnelle reliant une action ou une offre à un contexte cible et à un résultat observable. Marquez chaque fondement comme vérifié, calculé, inféré, supposé ou non vérifié. **Résultat visible/changement d’état :** hypothèse réfutable.
2. **Publiez l’hypothèse la plus risquée.** Choisissez le présupposé dont l’invalidation modifierait le plus la décision et dont les preuves sont les plus faibles ou contradictoires. Dites pourquoi il compte et quelles preuves l’affaibliraient ; préservez l’incertitude sans inventer de probabilité. **Résultat visible/changement d’état :** hypothèse la plus risquée.
3. **Publiez la fiche du test minimal.** Concevez le plus petit test réversible avec une audience ou un périmètre limité, un artefact, une durée, un responsable, une limite de consentement ou d’accès et une condition d’arrêt ou de retour arrière. Si un test réel crée une exposition substantielle, suspendez-le et nommez une vérification plus sûre sans exposition réelle. **Résultat visible/changement d’état :** fiche du test minimal ou suspension.
4. **Publiez la spécification de mesure.** Nommez l’indicateur exploitable, l’unité, la source, la fenêtre d’observation, la référence si disponible et le seuil ou la règle de décision. Expliquez pourquoi l’indicateur représente la question d’apprentissage et étiquetez tout seuil de travail comme hypothèse. **Résultat visible/changement d’état :** état de mesure vérifiable.
5. **Publiez le relevé des résultats.** Après un test autorisé, relevez le comportement attendu et observé, les observations manquantes, les effets de sélection, les écarts et l’état des preuves. Ne remplacez pas un résultat absent par un récit de réussite ; en l’absence de résultat, l’hypothèse reste non vérifiée. **Résultat visible/changement d’état :** relevé des résultats.
6. **Publiez la prochaine décision.** Appliquez la règle annoncée pour pivoter, persévérer, arrêter ou suspendre. Indiquez l’hypothèse modifiée ou le prochain test, le responsable, la limite et une ou deux conditions observables de basculement. **Résultat visible/changement d’état :** décision délimitée.

## Public output contract

Renvoyez des champs prêts pour une fiche, nommés `hypothesis`, `riskiest_assumption`, `minimum_test`, `metric_threshold` et `next_decision`. Le test doit indiquer son périmètre sûr, le signal observable et la condition d’arrêt ou de retour arrière. L’indicateur doit préciser source et unité ; la décision doit distinguer pivot, persévérance, arrêt et suspension. Incluez au plus deux incertitudes substantielles dans le résultat replié. Un indicateur décisif, un seuil ou un résultat manquant produit une issue non vérifiée ou suspendue plutôt qu’une recommandation sans réserve.

## Evidence and uncertainty rules

Un artefact livré ne prouve pas la demande et un indicateur ne prouve pas automatiquement la causalité. Ne marquez observations directes et sources liées comme vérifiées que si elles soutiennent le fondement précis ; montrez les entrées et expressions des résultats calculés ; marquez les raisonnements fondés sur un modèle comme inférés, les seuils choisis ou prémisses non testées comme supposés, les vérifications manquantes comme non vérifiées et les désaccords comme contradictoires. Précisez le contexte testé, les limites d’accès ou de sélection et la fenêtre d’observation. N’inventez pas de probabilités, taux de conversion, tailles d’échantillon ou réactions de clients. Un test minimal actualise l’hypothèse dans le contexte testé ; il ne se généralise pas à tous les utilisateurs ni à toutes les périodes futures.

## Stop conditions

Suspendez la décision si la décision à prendre, le contexte cible, l’hypothèse la plus risquée, l’indicateur exploitable ou la règle de décision manque et pourrait changer l’issue. Arrêtez un test dont l’exposition est dangereuse, illégale, intrusive pour la vie privée, sensible pour la sécurité, irréversible ou non autorisée. Arrêtez si aucun signal observable ne distingue les alternatives, si un retour arrière nécessaire est indisponible ou si le résultat est inféré d’un indicateur flatteur. Si le problème est une défaillance opérationnelle à cause profonde inconnue, passez le relais plutôt que de la masquer par une expérience produit.

## Complement handoff

Passez le relais à `jobs-to-be-done` si le test ne peut préciser le besoin fonctionnel sous-jacent de l’utilisateur, son contexte ou le progrès souhaité et que la découverte doit précéder une hypothèse produit. Transmettez uniquement le contexte cible publié, l’hypothèse, son présupposé le plus risqué, l’état des preuves observées et le besoin utilisateur non résolu. Ne répétez pas l’expérience et ne suggérez pas que le relais fournit les résultats manquants. Utilisez d’abord `assumption-mapping` si plusieurs hypothèses doivent être hiérarchisées avant d’en tester une.

## Purpose

Utilisez cette procédure pour comparer plusieurs explications d'un fait observé ou surprenant et choisir la meilleure explication actuelle sans la présenter comme démontrée. Elle exige au moins deux candidats encore plausibles, évalue leur adéquation explicative et leurs risques, puis identifie les éléments permettant de les départager. Le résultat est un diagnostic provisoire accompagné d'une vérification concrète, pas une permission d'ajuster les faits à un récit favori.

## Use when

Utilisez-la pour le débogage, le diagnostic, l'enquête, l'interprétation d'anomalies et les situations où plusieurs causes pourraient expliquer la même observation. Elle convient aux informations incomplètes et aux questions sur ce qui se passe probablement ou sur la raison d'un résultat inattendu. Utilisez-la lorsqu'une règle déductive ne suffit pas déjà à trancher.

## Do not use when

Ne l'utilisez pas si des règles explicites et des prémisses établies impliquent la conclusion, ou si aucune observation ne peut départager les explications. Un candidat unique ne constitue pas un ensemble d'explications ; ne notez pas un récit avec une précision inventée et ne prenez pas l'absence d'observation contraire pour une confirmation. Évitez toute certitude causale lorsque les candidats ne sont que des interprétations descriptives.

## Inputs to establish

Établissez l'observation surprenante, la référence attendue, la décision ou le diagnostic concerné, les faits connus, les explications plausibles et les tests ou sources disponibles. Précisez si chaque candidat décrit une cause, un mécanisme, une erreur de données ou une différence de périmètre. Posez au maximum une question décisive si l'observation ou la décision visée manque de clarté ; sinon, avancez avec des hypothèses explicites.

## Procedure

1. Publiez l'observation à expliquer et la référence qu'elle contredit. Distinguez les faits vérifiés, les déclarations de l'utilisateur et les hypothèses ; cela établit l'état visible de l'anomalie.
2. Publiez au moins deux explications candidates avec les observations qu'elles prédisent et leur périmètre. Ajoutez une erreur de mesure, de sélection ou de signalement lorsqu'elle est plausible, au lieu d'adopter par défaut le premier récit substantiel.
3. Publiez une comparaison qualitative de l'adéquation explicative, de la couverture, de la simplicité, de la cohérence avec les connaissances établies et de la testabilité. Employez des niveaux ordinaux comme fort, moyen, faible ou inconnu ; n'inventez pas de probabilités.
4. Publiez les éléments discriminants : observation, expérience ou source qui départagerait les principaux candidats. Indiquez quel résultat renforcerait, affaiblirait ou laisserait inchangé chaque candidat.
5. Publiez la meilleure explication actuelle et la raison de sa première place, avec un statut provisoire. Gardez les alternatives visibles et précisez s'il s'agit d'un diagnostic, d'une hypothèse de travail ou d'un ensemble non départagé.
6. Publiez la prochaine action de vérification et le mode d'échec important, notamment ce qui montrerait que l'explication est erronée ou que son lien avec les éléments probants n'est pas fiable.
7. Publiez la conclusion actuelle, les candidats et une condition observable de révision. Si aucun candidat ne bénéficie d'éléments discriminants ou si une observation décisive manque, suspendez la conclusion au lieu de retenir le récit le plus frappant.

## Public output contract

Renvoyez `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test` et `flip_condition`. La première ligne doit indiquer « meilleure explication actuelle » ou un équivalent si le résultat est provisoire. Les fondements portent les étiquettes **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; l'adéquation d'un candidat est une inférence, pas une preuve directe.

## Evidence and uncertainty rules

Un fait surprenant peut motiver une hypothèse sans en établir la cause. Exigez un soutien indépendant ou discriminant avant de renforcer un candidat. Ne comptez pas plusieurs fois la même observation sous différents critères. Si les candidats expliquent aussi bien les faits, signalez qu'ils restent en concurrence. Si un test important est indisponible, gardez la meilleure explication provisoire ou suspendez-la et indiquez les éléments manquants.

## Stop conditions

Arrêtez-vous et posez une question bloquante lorsque l'observation ou la décision visée est trop vague pour identifier des explications candidates. Suspendez le résultat si un seul candidat existe, s'il n'a aucune implication testable ou si des éléments décisifs manquent. Arrêtez cette méthode lorsque des prémisses explicites impliquent le résultat ou que le travail restant porte sur la qualité des sources, la validité formelle ou la comparaison d'options.

## Complement handoff

Passez à `value-of-information` lorsque la décision principale consiste à acheter, recueillir ou attendre une information discriminante. Transmettez les candidats, les éléments susceptibles de modifier la décision et le coût ou le délai du prochain test. La méthode complémentaire ne doit pas refaire la comparaison des explications.

## Purpose

Utilisez cette procédure pour des conclusions qui suivent normalement mais peuvent être retirées devant une exception ou de nouveaux éléments. Elle énonce une règle par défaut, l'applique provisoirement, distingue les réfutations de conclusion des objections au lien justificatif et consigne des conditions explicites de retrait. Le résultat est un jugement provisoire contrôlé, pas une manière affaiblie d'énoncer une règle inconditionnelle.

## Use when

Utilisez-la en droit, politique, médecine, opérations, règles de sens commun et autres domaines où une généralisation admet des exceptions ou où les éléments arrivent progressivement. Elle convient aux raisonnements « normalement », « sauf si », « prima facie » et aux jugements devant rester révisables sans devenir arbitraires.

## Do not use when

Ne l'utilisez pas si une règle stricte et des prémisses établies impliquent le résultat, ou si le seul problème est le classement des sources ou l'actualisation statistique. Ne listez pas toute exception imaginable, ne prenez pas un problème de crédibilité pour une contradiction directe et ne privilégiez pas le dernier énoncé simplement pour sa nouveauté. L'absence de réfutateur connu ne prouve pas la conclusion.

## Inputs to establish

Établissez règle par défaut, faits déclencheurs, périmètre de la règle, exceptions connues, réfutateurs possibles de la conclusion et du lien justificatif, et décision touchée. Identifiez toute règle plus spécifique pouvant primer. Posez au maximum deux questions décisives si la règle ou le fait déclencheur est peu clair ; sinon, marquez la prémisse provisoire.

## Procedure

1. Publiez la règle par défaut sous une forme bornée comme « normalement P implique Q », avec source, périmètre et état probant. Cela établit l'état visible de la règle.
2. Publiez les faits applicables et la conclusion prima facie. Marquez-la provisoire et précisez les conditions d'application de la règle par défaut.
3. Publiez séparément les réfutateurs soutenant non-Q et les objections affaiblissant le lien P-vers-Q. Consignez pour chacun s'il est vérifié, allégué ou inconnu.
4. Publiez les règles concurrentes et appliquez la spécificité lorsqu'une règle est réellement un sous-ensemble d'une autre. Si cela ne résout pas le conflit, marquez l'état conflictuel ou suspendu au lieu d'utiliser nouveauté ou ton assuré.
5. Publiez les conditions explicites de retrait : fait observable qui retirerait Q, affaiblirait la justification ou exigerait un nouveau jugement. La condition doit être plus précise que « de nouvelles informations apparaissent ».
6. Publiez le statut actualisé après les réfutateurs connus : provisoire, étayé, retiré, conflictuel ou suspendu. Précisez si la conclusion change à cause d'une réfutation, d'une objection au lien ou d'un conflit non résolu.
7. Publiez conclusion actuelle, réfutateurs applicables et condition de révision. Si un fait déclencheur ou une exception décisive manque, suspendez le résultat ou gardez-le provisoire au lieu d'en faire une certitude.

## Public output contract

Renvoyez `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status` et `flip_condition`. La fiche doit rendre visibles le caractère provisoire et les réfutateurs importants. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; ne dites jamais que la conclusion par défaut est inconditionnelle.

## Evidence and uncertainty rules

Un réfutateur de conclusion contredit celle-ci ; une objection au lien affaiblit la raison pour laquelle les faits la soutiennent sans prouver son contraire. La spécificité est une priorité structurelle, pas une règle de nouveauté. Vérifiez périmètre et indépendance des nouveaux éléments avant de modifier le statut. Si un réfutateur important reste non résolu, affaiblissez ou suspendez le résultat et indiquez la vérification nécessaire.

## Stop conditions

Arrêtez-vous et posez une question bloquante si règle par défaut ou faits déclencheurs ne peuvent être identifiés et que les règles concurrentes conduisent à des actions différentes. Suspendez si une exception, source ou condition d'applicabilité décisive manque. Arrêtez lorsque la règle est stricte et sans exception ou que le travail restant porte sur une actualisation probabiliste.

## Complement handoff

Passez à `premortem-analysis` si la règle provisoire soutient un plan choisi et que l'inquiétude restante concerne ses échecs possibles. Transmettez conclusion par défaut, réfutateurs connus et conditions de retrait. La méthode complémentaire ne doit ni reclasser les réfutateurs ni répéter l'inventaire des règles.

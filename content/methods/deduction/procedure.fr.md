## Purpose

Utilisez cette procédure pour déterminer si une conclusion découle nécessairement de prémisses explicites et d'une règle, en séparant validité et vérité des prémisses. Elle normalise l'argument, expose les prémisses cachées, vérifie la forme et identifie la prémisse dont l'échec invaliderait la conclusion. Une forme valide ne suffit pas à rendre un argument du monde réel fondé.

## Use when

Utilisez-la pour appliquer des règles, vérifier des arguments formels, interpréter contrats ou politiques et examiner les affirmations selon lesquelles un résultat doit découler de conditions déclarées. Elle convient si les prémisses pertinentes peuvent être explicitées et si la question est l'implication nécessaire plutôt qu'une généralisation empirique.

## Do not use when

Ne l'utilisez pas si les prémisses sont incertaines et que la véritable tâche est d'estimer, diagnostiquer, généraliser ou actualiser la confiance. Ne traitez pas une prémisse probable comme démontrée, ne confondez pas `P(E|H)` avec l'implication logique et ne dites pas qu'une forme invalide est valide parce que sa conclusion se trouve être vraie. N'inventez pas de règle absente de la demande utilisateur ou de la source applicable.

## Inputs to establish

Établissez conclusion proposée, prémisses, règle applicable ou implication, périmètre, définitions et source de chaque prémisse. Marquez explicitement les prémisses cachées et précisez si la tâche exige validité, caractère fondé ou simple résultat conditionnel. Posez au maximum une question décisive si une règle ou prémisse manquante change la forme ; sinon, énoncez l'hypothèse conditionnelle.

## Procedure

1. Publiez la conclusion et normalisez l'argument en prémisses numérotées, règle et conclusion. Marquez les prémisses cachées `[implicit]` ; cela établit la formalisation visible.
2. Publiez la forme argumentative : modus ponens, modus tollens, syllogisme valide, affirmation du conséquent ou négation de l'antécédent, par exemple. Sans forme reconnue adaptée, montrez la relation structurelle pertinente sans forcer d'étiquette.
3. Publiez le verdict de validité : en supposant les prémisses vraies, la conclusion doit-elle être vraie ? Indiquez la structure du contre-exemple si la forme est invalide.
4. Publiez un tableau du statut des prémisses avec source, périmètre et état probant de chaque prémisse et règle. Séparez forme valide et argument fondé ; cela actualise visiblement le jugement.
5. Publiez la prémisse invalidante ou la condition de règle. Précisez exactement ce qui briserait l'implication et distinguez une exception à la règle d'une prémisse fausse.
6. Publiez la conclusion comme fondée, valide mais non fondée, invalide ou conditionnelle, avec la plus petite vérification manquante. Ne renforcez pas le statut parce que la conclusion semble plausible.
7. Publiez conclusion actuelle et condition observable de révision. Si une prémisse ou règle décisive est absente, suspendez l'affirmation réelle tout en conservant l'implication conditionnelle.

## Public output contract

Renvoyez `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict` et `flip_condition`. Le résultat doit préciser si la forme est valide et si les prémisses sont étayées, sans fusionner ces deux points en une seule étiquette de confiance. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

La validité est une relation structurelle ; elle ne vérifie pas les prémisses. Une source peut soutenir une prémisse sans prouver que la règle s'applique au périmètre. Les prémisses cachées restent des hypothèses jusqu'à être étayées. Si une prémisse est contestée, conservez le résultat conditionnel et affaiblissez ou suspendez la conclusion appliquée. Une conclusion vraie isolée ne valide pas une inférence invalide.

## Stop conditions

Arrêtez-vous et posez une question bloquante si règle applicable ou conclusion manque et que les formes possibles produisent des résultats différents. Suspendez si une prémisse importante ne peut être vérifiée, tout en présentant le conditionnel valide s'il existe. Arrêtez si la tâche est probabiliste, causale ou comparative plutôt que logique.

## Complement handoff

Passez à `conceptual-analysis` si le différend formel dépend d'un terme ambigu ou d'une définition de périmètre. Transmettez prémisses normalisées, terme contesté et règle touchée. La méthode complémentaire doit clarifier le concept sans refaire le verdict de validité.

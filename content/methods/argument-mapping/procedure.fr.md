## Purpose

Utilisez cette procédure pour montrer comment les affirmations, les fondements, les objections et leurs réfutations soutiennent ou affaiblissent une conclusion. Elle produit une carte argumentative vérifiable plutôt qu'une carte mentale libre, afin que les prémisses partagées, les liens sans soutien et les objections non résolues restent visibles. Elle peut clarifier un différend avant une décision, mais une structure nette ne rend pas une prémisse vraie.

## Use when

Utilisez-la lorsqu'un argument politique, juridique, stratégique, scientifique ou relatif à un produit comporte plusieurs affirmations imbriquées et que leurs liens avec les éléments probants sont peu clairs. Elle convient aux différends comportant plusieurs objections, réfutations ou hypothèses communes. Employez-la principalement pour démêler les relations de soutien et d'attaque, puis indiquer la solidité résultante ou la condition de suspension.

## Do not use when

Ne l'utilisez pas pour une simple liste, un calcul direct ou une tâche portant uniquement sur la qualité des sources. Ne représentez pas une association, une chronologie ou une similarité thématique comme un soutien logique. Une carte complète ne prouve pas que la conclusion est fondée ; ne dissimulez pas des choix de valeurs dans des prémisses apparemment neutres.

## Inputs to establish

Établissez la conclusion cible, la décision ou la question, le périmètre pertinent, les fondements directs, les prémisses partagées, les objections, les réfutations et les sources disponibles. Précisez pour chaque élément s'il s'agit d'un fait, d'une règle, d'une inférence, d'une préférence ou d'une hypothèse. Posez au maximum deux questions décisives lorsqu'une affirmation ou un périmètre manquant changerait la carte ; sinon, marquez la lacune et poursuivez.

## Procedure

1. Publiez la conclusion principale et la décision qu'elle doit soutenir. Indiquez son statut actuel : étayée, provisoire, conflictuelle ou suspendue ; cela établit l'état visible de l'argument.
2. Publiez les prémisses directement favorables et distinguez-les des prémisses conjointement nécessaires. Ne tracez que des liens de soutien explicites et marquez chaque lien comme déclaré, inféré ou non vérifié.
3. Publiez les sous-fondements de chaque prémisse en conservant la hiérarchie entre affirmation et fondement. Joignez les références des sources ou calculs disponibles et consignez comme lacunes les liens sans soutien.
4. Publiez les objections dans des branches d'attaque distinctes, puis les réfutations seulement lorsqu'elles répondent à l'affirmation réelle de l'objection. Marquez une objection comme non résolue si la réfutation ne modifie ni ses éléments probants ni son périmètre.
5. Publiez les prémisses cachées ou partagées et vérifiez si le retrait de chacune change la conclusion. Ce changement d'état identifie la plus petite faiblesse importante, sans donner le même poids à chaque phrase.
6. Publiez le verdict de la carte : lien le mieux étayé, lien le plus faible, objection non résolue et éventuelle branche redondante ou non pertinente. Distinguez l'exhaustivité de la carte de la vérité des prémisses et de la validité des inférences.
7. Publiez l'état probant actuel de la conclusion et une condition observable de révision. Si une prémisse importante manque ou qu'une objection décisive reste sans réponse, affaiblissez ou suspendez la conclusion au lieu de réparer silencieusement l'argument.

## Public output contract

Renvoyez `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict` et `flip_condition`. Le résultat public doit montrer une carte compacte des affirmations, fondements et objections, pas une transcription du raisonnement privé. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. Limitez la fiche aux branches importantes et placez au besoin les détails dans la trace.

## Evidence and uncertainty rules

Une source peut soutenir une affirmation sans soutenir le lien entre celle-ci et la conclusion. Évaluez séparément le caractère direct, la pertinence et le périmètre. Ne comptez pas deux fois une prémisse partagée comme soutien indépendant. Une réfutation visant un témoin ou une mesure peut affaiblir un lien sans prouver la conclusion opposée. Des fondements crédibles contradictoires exigent un conflit visible et un résultat suspendu ou affaibli, sauf si une règle explicite de priorité le résout.

## Stop conditions

Arrêtez-vous et posez une question bloquante si la conclusion cible ou le périmètre de décision manque et que plusieurs interprétations produiraient des cartes différentes. Suspendez le résultat lorsqu'une prémisse importante ne peut être étayée ou qu'une objection décisive reste sans résolution. Arrêtez si la tâche consiste uniquement à classer des sources, effectuer un calcul simple ou établir une définition stable ; passez à la méthode plus spécifique.

## Complement handoff

Passez à `evidence-hierarchy` si la carte montre que la qualité des sources, le plan d'étude ou le caractère direct des éléments, plutôt que la structure argumentative, est le problème restant. Transmettez seulement les liens affirmation-source, les liens non étayés et le conflit important. La méthode complémentaire ne doit pas reconstruire toute la carte argumentative.

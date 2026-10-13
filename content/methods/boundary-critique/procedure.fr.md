## Purpose

Utilisez cette procédure pour rendre visible le périmètre d'un jugement. Elle identifie les personnes et les éléments inclus dans le cadrage actuel, ceux qui sont touchés mais exclus, et la manière dont un changement de périmètre modifie la conclusion. L'objectif n'est pas d'allonger la liste des parties prenantes, mais d'exposer les hypothèses de responsabilité, bénéfice, coût, autorité, horizon temporel, juridiction et frontière du système qui font paraître la réponse inévitable. Séparez les affirmations descriptives sur ce qui se passe des affirmations normatives sur ce qui devrait compter ou être fait.

## Use when

Utilisez-la lorsque la réponse dépend des acteurs pris en compte, des résultats mesurés, de la zone géographique ou période retenue, du détenteur de la décision ou des externalités exclues. Elle est particulièrement utile pour les politiques, produits, organisations, questions d'intérêt public et changements de système, où une réponse techniquement juste pour un groupe impose des coûts à un autre. Une comparaison bornée peut y recourir si elle dissimule une population ou un horizon temporel omis.

## Do not use when

Ne l'utilisez pas si le périmètre, le responsable de décision, la population touchée, la juridiction et l'horizon temporel sont explicites et qu'il reste seulement à comparer des options ou vérifier une source. Ne transformez pas une demande purement mécanique en exercice de périmètre. N'inférez pas un groupe touché simplement parce qu'il est imaginable ; marquez-le comme hypothétique jusqu'à ce que la tâche ou les éléments établissent sa pertinence.

## Inputs to establish

Établissez la question de décision, le responsable, les bénéficiaires visés, la règle actuelle d'inclusion, l'horizon temporel, la géographie ou juridiction, les ressources comptées et la mesure du résultat. Nommez jusqu'à trois faits manquants susceptibles de changer sensiblement le périmètre. Si l'utilisateur ne fournit pas de périmètre, proposez-en un raisonnable et provisoire ; posez au maximum une question concise, seulement si différentes réponses modifieraient la recommandation. Distinguez faits fournis par l'utilisateur, sources vérifiées, effets inférés et choix de valeurs.

## Procedure

1. Publiez la question de décision en une phrase et le périmètre provisoire : qui, quoi, où, quand et pour quel résultat. Précisez si le périmètre vient de l'utilisateur ou est supposé ; cela établit le cadrage visible.
2. Publiez les éléments inclus : acteurs, objectifs, connaissances, ressources et droits de décision. Justifiez brièvement chaque inclusion pour rendre le périmètre vérifiable plutôt que simplement affirmé.
3. Publiez les éléments omis mais touchés. Séparez effets directs, effets indirects et personnes pouvant contester le cadrage ; marquez les entrées incertaines comme hypothèses plutôt que faits.
4. Publiez une séparation faits/valeurs : distinguez les observations descriptives des jugements sur les bénéfices, coûts, voix ou droits qui devraient compter. Ce changement d'état empêche un choix de valeurs de passer pour une frontière neutre du système.
5. Publiez une comparaison des bénéfices et coûts entre groupes inclus et omis, limitée aux effets importants. Étiquetez l'état probant de chaque effet et laissez les effets non vérifiés comme non résolus.
6. Publiez une ou plusieurs variantes de périmètre, par exemple un horizon plus long, une autre juridiction ou un groupe touché ajouté. Pour chacune, indiquez si la conclusion, l'ordre des options, le risque ou le critère d'achèvement change.
7. Publiez le périmètre actuel, la conséquence du changement le plus pertinent pour la décision et une condition observable de révision. Si un fait décisif du périmètre manque, rendez la conclusion provisoire ou suspendue au lieu de la remplir de spéculations.

## Public output contract

Renvoyez un résultat compact prêt pour la fiche avec `current_boundary`, `omitted_boundary`, `benefit_and_cost_effects`, `boundary_variant`, `consequence_of_changing_it` et `flip_condition`. La première ligne énonce le périmètre actuel et s'il soutient, affaiblit ou suspend le jugement. Incluez au maximum trois hypothèses importantes et deux incertitudes non résolues. Les fondements de la fiche portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; les alternatives résument les variantes pertinentes plutôt que toutes les parties prenantes.

## Evidence and uncertainty rules

Un groupe touché ne prouve pas à lui seul l'existence d'un effet. Appuyez chaque bénéfice ou coût important sur une source, un document utilisateur, un calcul reproductible ou une inférence clairement étiquetée. L'avis majoritaire ou la préférence du responsable ne prouve pas qu'un groupe omis est sans importance. Si des variantes conduisent à des conclusions incompatibles, marquez le jugement **conflicted** ou **held** jusqu'au choix du périmètre par le responsable autorisé. Un fait décisif manquant ne permet qu'une conclusion provisoire.

## Stop conditions

Arrêtez-vous et posez une question bloquante si deux périmètres plausibles conduisent à des actions sensiblement différentes et qu'aucun ne peut être choisi sans risque à partir de l'objectif utilisateur ou d'une règle faisant autorité. Suspendez le résultat si un groupe, une juridiction ou un horizon décisif ne peut être identifié. Arrêtez cette méthode lorsque le périmètre est explicite et qu'aucun acteur ou bord omis important ne subsiste ; passez à la méthode traitant la comparaison ou les éléments probants réels.

## Complement handoff

Passez à `stakeholder-analysis` uniquement comme complément ciblé si l'examen révèle des questions importantes de pouvoir, consentement, mise en œuvre ou conflit. Transmettez les ensembles inclus et omis publiés, la variante choisie et l'effet non résolu exigeant l'analyse des parties prenantes. N'activez pas une seconde procédure complète et ne répétez pas l'inventaire du périmètre.

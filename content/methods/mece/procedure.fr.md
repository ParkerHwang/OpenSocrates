## Purpose

Utilisez cette procédure pour tester si une classification ou une décomposition présente, au même niveau, une exclusion mutuelle et une exhaustivité collective. Fixez un seul axe, testez séparément recoupements et lacunes et maintenez une granularité cohérente des catégories. Le résultat est une règle de classification défendable avec des cas limites connus, pas la promesse que toute catégorie réelle est naturellement nette.

## Use when

Utilisez-la lorsque des catégories, groupes de responsabilités, options, exigences, causes ou branches d’un arbre des problèmes dupliquent ou omettent des cas substantiels. Elle sert à examiner une classification existante et comme vérification ciblée dans un arbre logique ou une structure de présentation à la direction. Utilisez-la lorsque la règle de classification elle-même, plutôt qu’une source factuelle, constitue le goulet d’étranglement décisionnel.

## Do not use when

Ne l’utilisez pas si le recoupement naturel est le phénomène étudié, si les catégories représentent intentionnellement des axes différents ou s’il suffit d’appliquer une taxonomie contraignante. Ne mélangez pas âge, géographie, intention et étape du processus à un même niveau. Ne cachez pas une grande classe manquante dans « autre » et ne forcez pas une fausse exclusivité lorsque l’appartenance est réellement multi-étiquette.

## Inputs to establish

Établissez l’univers à classer, l’objectif décisionnel, les catégories candidates, l’axe unique proposé, les règles d’inclusion et d’exclusion et les cas limites connus. Précisez si les catégories sont à étiquette unique ou multiple. Posez au plus une question si l’univers ou l’objectif de classification présente une ambiguïté substantielle ; sinon, énoncez un univers délimité.

## Procedure

1. Publiez l’univers, l’objectif décisionnel et un axe de classification en une seule phrase. Cela fixe l’état visible et évite de mélanger les critères.
2. Publiez les catégories candidates avec une règle d’inclusion et une d’exclusion chacune. Marquez les limites comme explicites, inférées ou non vérifiées.
3. Publiez le test d’exclusion mutuelle avec des cas plausibles pouvant relever de deux catégories. Pour chaque recoupement, fusionnez, redécoupez ou autorisez explicitement une appartenance multi-étiquette et consignez le changement d’état.
4. Publiez le test de couverture collective avec des cas limites et des observations connues. N’ajoutez une catégorie que si le cas manquant est pertinent pour l’univers annoncé ; sinon, restreignez l’univers et divulguez l’exclusion.
5. Publiez une vérification de granularité à ce niveau : comparez abstraction, taille et usage décisionnel des catégories. Retravaillez une catégorie qui est une sous-catégorie cachée de ses voisines ou trop large pour permettre une action.
6. Publiez les cas limites, la règle finale et les recoupements laissés intentionnellement non résolus. N’utilisez pas un vague groupe « autre » pour une part substantielle de l’univers.
7. Publiez le résultat classé, le verdict sur recoupements et lacunes et une condition observable de basculement. Si l’axe ne permet pas la décision ou qu’un cas important ne peut être classé, suspendez la classification plutôt que de forcer une étiquette.

## Public output contract

Renvoyez `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases` et `flip_condition`. Le résultat public doit distinguer ME de CE et préciser si la classification est à étiquette unique ou multiple. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** ; les catégories elles-mêmes ne prouvent pas la prévalence.

## Evidence and uncertainty rules

ME et CE sont des tests logiques de couverture, pas une preuve empirique d’utilité des catégories. Un exemple peut révéler un recoupement ou une lacune sans en établir la fréquence. Séparez observations sourcées et choix de conception des catégories. Si une catégorie substantielle manque, qu’un cas contesté reste irrésolu ou que l’axe change la décision, étiquetez le résultat comme provisoire ou suspendu.

## Stop conditions

Arrêtez et posez une question bloquante si l’univers ou l’objectif de classification ne peut être délimité. Suspendez si l’axe ne représente pas les cas substantiels sans recoupement trompeur ou si une catégorie manquante modifie la décision. Arrêtez lorsque la règle satisfait ME/CE au périmètre requis et que la suite relève d’une décomposition structurelle ou d’une comparaison d’options.

## Complement handoff

Passez le relais à `logic-tree` si les catégories validées constituent le premier niveau d’un diagnostic ou plan plus vaste et nécessitent des branches récursives et des tests de feuilles. Transmettez l’univers, l’axe, les catégories finales, les cas limites et le verdict de couverture. La méthode complémentaire ne doit pas répéter les vérifications MECE au même niveau.

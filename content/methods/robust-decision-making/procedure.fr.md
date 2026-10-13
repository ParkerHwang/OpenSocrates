## Purpose

Utilisez cette procédure pour choisir une action restant acceptable dans plusieurs futurs plausibles lorsqu’aucune prévision unique ne mérite de gouverner la décision. Elle rend visibles incertitudes, critères d’échec et compromis, puis sépare une première action robuste des actions devant attendre un signal précurseur. Robuste ne signifie pas optimal dans chaque futur ; l’action franchit le plancher annoncé sans dépendre d’une distribution de probabilités inventée.

## Use when

Utilisez-la pour des choix durables de politique, d’infrastructure, d’investissement, de produit ou d’exploitation exposés à des incertitudes interactives. Elle convient si l’échec coûte cher, le retour arrière est lent ou les parties prenantes ne s’accordent pas sur une prévision unique. Elle aide à répondre « Qu’est-ce qui peut résister à plusieurs conditions plausibles ? » plutôt que « Quel résultat est le plus probable ? ».

## Do not use when

Ne l’utilisez pas si un cas attendu est fiable et le choix peu coûteux et entièrement réversible, ou si une règle contraignante ne laisse qu’une action faisable. N’utilisez pas un catalogue de pires cas arbitraires, n’affirmez pas qu’une action est meilleure dans tous les futurs et ne cachez pas le coût de la robustesse. Si réussite et échec ne peuvent être définis, précisez d’abord la décision ou établissez les critères par une méthode probante.

## Inputs to establish

Établissez décision, actions faisables, horizon, parties prenantes et performance minimale acceptable. Définissez avant les tests échec, regret inacceptable et compromis substantiels. Listez incertitudes profondes, dépendances, contraintes connues et quelques descriptions de mondes plausibles ; n’attribuez pas de probabilités sans source défendable fournie par l’utilisateur. Relevez réversibilité, coûts, calendrier et engagements actuels. Posez au plus deux questions décisives, seulement si elles modifient les actions ou le plancher d’acceptabilité.

## Procedure

1. Publiez cadre décisionnel, actions candidates et critères d’acceptation. **Résultat visible/changement d’état :** un ensemble de choix délimité et un plancher explicite d’acceptabilité ou d’échec existent.
2. Publiez un registre d’incertitudes et des mondes plausibles distincts, cohérents en interne. **Résultat visible/changement d’état :** une prévision unique devient un ensemble visible de tests ; les mondes portent hypothèses et dépendances, pas des probabilités.
3. Testez chaque action dans chaque monde selon les critères déclarés. **Résultat visible/changement d’état :** une matrice stratégie-monde consigne états acceptables, fragiles ou échoués avec leurs étiquettes probantes.
4. Publiez conditions d’échec, exposition au regret et groupes de mondes mettant la même action sous tension. **Résultat visible/changement d’état :** vulnérabilités et compromis sont nommés au lieu d’être cachés dans un score global.
5. Publiez l’action robuste ou le plus petit ensemble d’actions franchissant le plancher dans les mondes testés. **Résultat visible/changement d’état :** la recommandation est distinguée de son coût, des possibilités perdues et de la vulnérabilité résiduelle.
6. Publiez garanties, premières actions réversibles, actions conditionnelles et signaux de surveillance avec leurs réponses déclenchées. **Résultat visible/changement d’état :** la décision devient adaptative plutôt qu’un pari unique sur un monde préféré.
7. Publiez un statut étayé, provisoire ou suspendu et une condition observable de basculement. **Résultat visible/changement d’état :** des critères ou mondes décisifs manquants entraînent une suspension, pas une revendication de robustesse.

## Public output contract

Renvoyez `uncertainties`, `plausible_worlds`, `regret_or_failure_criteria`, `robust_action`, `tradeoffs`, `monitoring_signals`, `flip_condition` et un statut étayé, provisoire ou suspendu. Décrivez pourquoi l’action franchit le plancher et où elle reste fragile. La fiche énonce une conclusion, étiquette les fondements substantiels, nomme l’incertitude irrésolue et la condition observable changeant l’action ; les matrices détaillées vont dans la trace ou un artefact d’appui.

## Evidence and uncertainty rules

Les mondes plausibles sont des cas de test structurés, pas des prévisions ni un échantillon pondéré par probabilité. Fondez chaque monde substantiel sur observation, mécanisme défendable, contrainte utilisateur ou hypothèse explicite. N’inventez fréquences des mondes, pertes attendues, scores d’utilité ou robustesse universelle. « Acceptable » renvoie au critère publié. Marquez les comparaisons calculées avec entrées et unités ; préservez les preuves contradictoires plutôt que de les moyenner. Une action robuste peut être inférieure en coût ou potentiel ; gardez le compromis visible.

## Stop conditions

Posez une question bloquante et arrêtez si les actions ou la performance minimale acceptable ont des interprétations substantiellement différentes. Suspendez si une incertitude décisive, un seuil d’échec ou une action faisable manque. Arrêtez si une prévision unique est fiable, une règle contraignante exclut toute latitude ou la suite relève de construction de scénarios, vérification probante ou comparaison ordinaire d’options.

## Complement handoff

Passez le relais à `scenario-planning` si l’ensemble des mondes nécessite une structure plus délibérée des futurs externes ou un récit des signaux précurseurs. Transmettez cadre décisionnel, registre d’incertitudes, plancher d’acceptation, groupes vulnérables et descriptions actuelles. La méthode complémentaire enrichit les mondes sans masquer les critères d’échec ni les transformer en probabilités.

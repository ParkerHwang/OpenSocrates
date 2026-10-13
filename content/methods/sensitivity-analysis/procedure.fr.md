## Purpose

Utilisez cette procédure pour tester comment un résultat de modèle, une comparaison ou une décision change lorsque des entrées ou poids importants varient dans des plages défendables. Elle identifie variables influentes, valeurs de basculement, interactions et hypothèses fragiles. Le résultat est une vérification transparente de robustesse, pas une permission de choisir des plages spectaculaires ni de suggérer qu’un modèle prouve le futur.

## Use when

Utilisez-la si un calcul, modèle prévisionnel, dossier économique, règle de notation ou comparaison d’options existe et que des entrées incertaines peuvent modifier la décision. Elle aide à prioriser les données, exposer un seuil caché et distinguer une conclusion résistant à des variations raisonnables d’une dépendant d’une hypothèse étroite. Des changements numériques ou ordinaux conviennent si l’échelle est explicite.

## Do not use when

Ne l’utilisez pas sans modèle, comparaison, règle décisionnelle ou relation entre variables à faire varier. Ne créez pas une analyse de sensibilité à partir d’une question purement factuelle, référence indéfinie ou plages sans provenance. Ne faites pas varier indépendamment des variables corrélées, ne traitez pas un modèle non linéaire comme linéaire sans vérifier et ne donnez pas une valeur de basculement précise au-delà de la précision des entrées.

## Inputs to establish

Établissez modèle ou règle de référence, indicateur de sortie, seuil décisionnel, entrées ou poids, unités et résultat actuel. Définissez pour chaque entrée incertaine une plage plausible et sa provenance, avec dépendances et contraintes. Énoncez dispositif de variation, règle d’arrondi et type de test : une entrée à la fois, combinaison structurée ou comparaison ordinale. Relevez l’option ou politique à éclairer. Posez au plus deux questions décisives, seulement si elles changent référence ou plage.

## Procedure

1. Publiez formule ou règle de référence, entrées, unités et résultat. **Résultat visible/changement d’état :** un état initial reproductible et un seuil nommé existent.
2. Publiez plages testées, poids, dépendances et preuves de chaque plage. **Résultat visible/changement d’état :** chaque limite de variation est vérifiée, calculée, inférée, supposée, non vérifiée ou contradictoire plutôt que choisie pour son effet.
3. Testez une entrée à la fois, puis seulement des combinaisons structurées défendables. **Résultat visible/changement d’état :** un journal consigne entrée modifiée, sortie obtenue, méthode, unités et arrondi ; les entrées corrélées varient ensemble si nécessaire.
4. Publiez sens de réponse, ampleur ou changement ordinal, interactions et valeurs franchissant le seuil. **Résultat visible/changement d’état :** les variables sont influentes, non influentes, robustes ou fragiles, sans prétendre que le rang prouve la causalité.
5. Publiez implication décisionnelle et priorité de recherche des variables pouvant changer le choix. **Résultat visible/changement d’état :** l’effort d’enquête est lié à une condition de basculement nommée plutôt qu’à la plus grande variation brute.
6. Publiez une conclusion robuste, fragile, provisoire ou suspendue et la prochaine vérification de validation. **Résultat visible/changement d’état :** une référence, plage ou seuil manquant entraîne une suspension explicite, pas une affirmation de sensibilité fabriquée.

## Public output contract

Renvoyez `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority` et `flip_condition`, avec un statut étayé, provisoire ou suspendu. Précisez seuil et entrées pouvant le franchir. Les fondements de la fiche identifient valeurs calculées et entrées ; l’incertitude nomme les limites de plage ou modèle ; le basculement est un changement observable d’entrée ou seuil. Gardez journal complet et formules dans la trace ou un artefact d’appui.

## Evidence and uncertainty rules

Les plages nécessitent source, contrainte utilisateur, observation historique ou hypothèse explicite ; une plage commode n’est pas une preuve. Les calculs exposent formule, opérandes, unités et arrondi. Préservez non-linéarité, corrélation, discontinuité et incertitude de forme du modèle si pertinentes. Si seuls des poids ordinaux sont défendables, indiquez direction ou ordre des seuils, pas des pourcentages pseudo-précis. Ne déduisez pas une probabilité réelle de la fréquence d’échantillonnage d’un cas de test. Un résultat robuste peut rester une décision fragile si le seuil ou l’objectif est erroné.

## Stop conditions

Posez une question bloquante et arrêtez si référence, seuil ou sortie cible a des interprétations substantiellement différentes. Suspendez si une plage, dépendance ou règle requise ne peut être établie. Arrêtez si aucune variation défendable ne changerait la décision ou si la suite relève de vérification probante, explication causale ou compromis plus vaste entre options.

## Complement handoff

Passez le relais à `trade-off-analysis` si les résultats de sensibilité doivent être combinés à critères, poids et préférences des parties prenantes entre options. Transmettez référence, valeurs de basculement, constats robustes/fragiles, provenance des plages et priorités de recherche. La méthode complémentaire compare les choix selon ces limites sans traiter un rang de sensibilité comme préférence ou probabilité.

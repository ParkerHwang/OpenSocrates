## Purpose

Utilisez cette procédure pour représenter une décision dans le temps, où une action change les possibilités suivantes et des événements incertains conduisent à des choix ultérieurs. Elle sépare nœuds de décision, d'aléa et de résultat pour relier une recommandation aux informations. Elle peut calculer par remontée de l'arbre si valeurs et probabilités sont bornées, mais doit suspendre le résultat plutôt que fabriquer de la précision lorsque des branches ne sont pas étayées.

## Use when

Utilisez-la pour lancements par étapes, choix entre pilote et extension, calendrier de maintenance ou remplacement, attente d'un test et autres décisions conditionnelles. Elle convient si l'ordre des actions compte, si les choix ultérieurs dépendent d'un résultat observé et si les résultats disposent d'une valeur sourcée ou d'une conséquence qualitative clairement étiquetée. L'arbre aide lorsque la question porte sur la stratégie disponible après de nouvelles informations, pas seulement l'option actuellement la mieux notée.

## Do not use when

Ne l'utilisez pas pour une comparaison statique sans séquence ni branche aléatoire significative, un organigramme mécanique ou une règle obligatoire sans latitude. Ne dessinez pas de branches indépendantes pour des événements partageant une cause ou dépendant d'un résultat antérieur. Ne calculez pas d'espérance si probabilités, valeurs finales ou actions conditionnelles ne peuvent être bornées. Si l'incertitude profonde et des futurs externes cohérents comptent plus que le calcul des branches, passez à scenario-planning.

## Inputs to establish

Énoncez point de décision, actions possibles, moments d'observation, événements aléatoires, résultats terminaux, points de retour arrière et acteur capable d'agir à chaque nœud. Consignez provenance des probabilités, unités finales, calendrier, coûts, bénéfices et dépendances. Marquez chaque probabilité verified, computed à partir de données explicites, inferred, assumed, unverified ou conflicted. Posez au maximum deux questions décisives, comme « Quelle observation change l'action suivante disponible ? » et « Quelle source borne cette branche ? ».

## Procedure

1. **Fixez la séquence.** Énoncez décision, ordre des actions et observations, horizon et points possibles de retour arrière ou d'arrêt. **Résultat visible/changement d'état :** publiez le cadre de l'arbre en marquant chaque nœud connu décision, aléa, observation ou résultat.
2. **Énumérez les branches conditionnelles.** À chaque décision, listez les actions faisables ; à chaque aléa, les résultats mutuellement exclusifs et leurs possibilités suivantes. Conservez les dépendances au lieu d'aplatir en branches sans rapport. **Résultat visible/changement d'état :** créez un registre parent, enfant, condition et action suivante.
3. **Décrivez les résultats terminaux.** Attribuez à chaque branche une conséquence, unité, temporalité, groupe touché et état probant. Gardez les contraintes incomparables de sécurité ou de droits hors valeur agrégée. **Résultat visible/changement d'état :** publiez un registre final et marquez toute valeur manquante ou contradictoire suspendue ou non résolue.
4. **Bornez l'incertitude.** Joignez source ou calcul reproductible à chaque probabilité ; vérifiez exhaustivité et compatibilité des branches conditionnelles avec l'événement antérieur. Sans probabilité bornable, utilisez un intervalle défendable ou une branche qualitative seulement avec fondement explicite ; ne prétendez pas à une réponse numérique. **Résultat visible/changement d'état :** publiez la provenance des probabilités ou une note de suspension de la branche non bornée.
5. **Remontez et éprouvez l'arbre.** Depuis les résultats terminaux, calculez ou comparez les branches parentes avec valeurs et unités explicites. Faites varier probabilités ou résultats importants dans des intervalles défendables ; montrez exposition du pire cas, regret ou seuil de retour arrière plutôt qu'une seule espérance. **Résultat visible/changement d'état :** publiez un tableau de remontée avec action recommandée, condition de bascule et risque résiduel.
6. **Fixez la stratégie.** Expliquez l'action actuellement étayée, l'observation déclenchant une autre action et le point de pause. Si une branche non résolue peut changer la stratégie, suspendez la recommandation et nommez la plus petite observation sûre. **Résultat visible/changement d'état :** publiez nœuds décision/aléa/résultat, résumé final, provenance des probabilités, point de retour arrière, incertitude et condition de révision de la Conclusion Card.

## Public output contract

Renvoyez nœuds de décision, d'aléa et de résultat, branches conditionnelles, conséquences terminales et point de retour arrière. Montrez la provenance de chaque probabilité numérique et les unités et expressions des valeurs calculées. Incluez exposition au risque, condition de bascule ou arrêt et prochaine observation si la stratégie est provisoire. La conclusion publique ne doit pas laisser croire qu'un arbre prouve un résultat ; calculs détaillés et dépendances appartiennent à la trace.

## Evidence and uncertainty rules

Utilisez verified seulement pour une source identifiable soutenant la branche ou le résultat ; computed pour un calcul transparent à entrées déclarées, inferred pour une conséquence de fondements étiquetés, assumed pour une prémisse de planification explicite, unverified pour une entrée non vérifiée et conflicted pour un désaccord crédible. N'inventez taux de base, probabilité, utilité, indépendance ou valeur terminale. Révisez les branches non mutuellement exclusives avant le calcul. Un intervalle étroit sans provenance est une fausse précision.

## Stop conditions

Suspendez si séquence, action suivante, résultat de branche ou fondement probabiliste manque d'une manière susceptible de changer la stratégie. Suspendez si les dépendances ne peuvent être représentées sans double comptage ou qu'une règle obligatoire supprime la latitude. Si l'espace des branches est trop ouvert pour être borné, indiquez l'observation manquante et passez à scenario-planning plutôt que produire une espérance non étayée.

## Complement handoff

Passez à scenario-planning si plusieurs futurs externes cohérents, plutôt que des branches aléatoires bornées, déterminent la préparation. Transmettez seulement cadre décisionnel, incertitudes importantes, repères des branches et actions sans regret ou conditionnelles ; excluez probabilités non étayées et délibération privée.

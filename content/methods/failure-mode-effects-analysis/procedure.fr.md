## Purpose

Utilisez cette procédure pour identifier comment un processus, produit ou contrôle prévu pourrait échouer avant de s'y fier. Elle relie mode de défaillance, effet, cause plausible, détection existante et contrôle préventif ou de détection. Le résultat est une priorité ordinale et une liste d'actions attribuées, pas un faux score de risque. Elle rend l'incertitude visible et concentre l'effort sur les défaillances dont conséquences ou contrôles faibles méritent d'abord attention.

## Use when

Utilisez-la pour lancement, changement de processus, conception de service, transmission, barrière de sécurité, chaîne de données ou fonctionnalité avec séquence et surface de défaillance définies. Elle aide avant engagement, après changement significatif de conception ou lorsqu'un incident récurrent révèle une catégorie non examinée. Utilisez données d'incident, tests, registres de service et expertise disponibles. Limitez l'analyse au processus ou composant descriptible et sur lequel on peut agir.

## Do not use when

Ne la substituez pas à une réponse urgente, un examen de conformité juridique, une analyse de dangers spécialisée obligatoire ou un diagnostic causal d'incident récurrent. N'attribuez pas de chiffres de gravité, occurrence ou détectabilité sans échelle, calibration et source. Une longue liste n'est pas une preuve d'exhaustivité ; ne classez pas plus haut une défaillance simplement parce qu'elle est plus imaginable. Si périmètre ou fonction prévue est inconnu, établissez-le d'abord ou suspendez l'évaluation.

## Inputs to establish

Nommez processus, produit ou composant, périmètre, fonction prévue, utilisateurs, conditions d'exploitation et contrôles actuels. Cartographiez étapes ou interfaces principales et identifiez dangers connus, contraintes, incidents, résultats de tests et responsables. Définissez avant le classement les niveaux ordinaux — urgent, important, à surveiller ou faible attention, par exemple — avec leur sens local. Posez au maximum deux questions changeant le classement, comme « Quelle défaillance pourrait causer un dommage irréversible ? » ou « Quel contrôle la détecterait avant publication ? ».

## Procedure

1. **Fixez le périmètre.** Décrivez fonction prévue, contexte d'exploitation, interfaces et exclusions ; scindez un grand processus en séquence exploitable. **Résultat visible/changement d'état :** publiez périmètre et étapes, en marquant fonctions ou conditions inconnues non vérifiées.
2. **Nommez modes et effets.** Pour chaque étape, indiquez ce qui peut échouer et l'effet immédiat, en aval, utilisateur ou de sécurité. Distinguez assez les modes pour permettre des contrôles différents. **Résultat visible/changement d'état :** publiez un registre défaillance-effet relié à chaque étape.
3. **Retracez causes et contrôles.** Consignez causes plausibles, contrôles préventifs, contrôles de détection et éléments montrant leur fonctionnement réel. Séparez défaillances observées et possibilités hypothétiques. **Résultat visible/changement d'état :** ajoutez causes et contrôles avec états verified, inferred, assumed ou unverified.
4. **Fixez la priorité ordinale.** Appliquez la règle qualitative annoncée à partir de conséquence, exposition plausible et faiblesse des contrôles. Sans entrées quantitatives défendables, ne calculez pas de produit ni de nombre de priorité de risque ; expliquez en mots. **Résultat visible/changement d'état :** publiez une liste courte ordonnée avec la raison de chaque niveau urgent, important, à surveiller ou faible attention.
5. **Attribuez les actions de contrôle.** Préférez supprimer la cause, puis détecter avant dommage, puis confiner l'impact. Nommez responsable, déclencheur, preuve d'achèvement et incertitude résiduelle. **Résultat visible/changement d'état :** publiez un plan de contrôle lié à chaque mode priorisé.
6. **Réévaluez après changement.** Précisez l'observation ou test montrant une exposition réduite ou une meilleure détection, et ce qui rouvrirait le mode. **Résultat visible/changement d'état :** publiez priorité étayée, provisoire ou suspendue et condition de révision ; une action planifiée ne clôt pas une défaillance.

## Public output contract

Renvoyez périmètre, modes, effets, causes, contrôles actuels, priorité ordinale, responsable et signal de vérification. Précisez si chaque élément important est observé, inféré, supposé, non vérifié ou conflictuel. Ne présentez jamais scores inventés de gravité/occurrence/détectabilité ou classement précis sans provenance. La Conclusion Card peut résumer la défaillance demandant le plus d'attention et la condition modifiant sa priorité ; la trace peut contenir le registre complet.

## Evidence and uncertainty rules

Une défaillance hypothétique n'est pas un taux observé. Un contrôle documenté n'est pas automatiquement efficace ; les éléments doivent montrer fonctionnement, couverture ou test borné. Séparez conséquence, probabilité et détectabilité. Utilisez des niveaux ordinaux seulement avec définition locale et fondement explicite. Si un seuil de sécurité ou réglementaire est obligatoire, suivez l'exigence faisant autorité et marquez l'interprétation non vérifiée. Si deux évaluations crédibles divergent, marquez la priorité conflictuelle et suspendez l'ordre des actions lorsque le conflit est important.

## Stop conditions

Arrêtez si fonction, périmètre ou conditions ne peuvent être établis, si un mode à graves conséquences n'a aucun confinement sûr ou si le classement exigerait des chiffres inventés. En cas de danger immédiat, suivez d'abord le processus d'incident ou sécurité applicable. Suspendez une recommandation de publication si un contrôle décisif n'a pas été testé ou n'a pas de responsable attribué.

## Complement handoff

Passez à premortem-analysis si un plan choisi exige un récit humain de défaillance et des signaux précoces avant engagement. Transmettez plan borné, modes priorisés, effets et contrôles ; le complément ajoute des scénarios plausibles sans transformer une priorité ordinale en fausse précision.

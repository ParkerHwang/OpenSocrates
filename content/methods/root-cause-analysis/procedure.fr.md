## Purpose

Utilisez cette procédure pour expliquer une défaillance récurrente ou aux conséquences qu’une correction rapide ne peut traiter sans risque. Elle sépare symptôme visible, causes immédiates, conditions contributives et conditions systémiques contrôlables. Le but n’est pas de blâmer ni de découvrir une racine unique. Elle produit une chaîne causale, une prévention avec responsable et un signal vérifiant si le risque de récurrence a changé.

## Use when

Utilisez-la pour incidents répétés, défauts échappant aux contrôles, dégradation de service, anomalies récurrentes, relais manqués ou contournements qui reviennent. Elle convient aux défaillances opérationnelles ou produit délimitées par événement observable, population, période et impact. Elle aide si une équipe blâme quelqu’un pour une interaction prévisible entre outils, charge, incitations, formation et contrôles. Utilisez journaux, chronologies, entretiens, échantillons ou regroupement en arêtes de poisson, mais reliez les affirmations à une observation ou hypothèse marquée.

## Do not use when

Ne l’utilisez pas pour trancher un devoir juridique ou politique contraignant, inférer une intention d’une erreur unique ou reconcevoir un système sans cible de défaillance concrète. Un événement isolé sans récurrence peut relever de causal-reasoning ou d’un examen d’incident. Ne nommez pas le déclencheur le plus proche « racine » parce qu’il est facile à désigner. Ne promettez pas qu’une intervention éliminera la récurrence si plusieurs chemins indépendants existent ou que les preuves manquent.

## Inputs to establish

Formulez le problème avec défaillance observable, périmètre affecté, fenêtre temporelle, impact et sens de « récurrence ». Recueillez chronologie, processus attendu et réel, dossiers pertinents et contrôles connus. Nommez personnes ou composants comme participants, pas comme causes présumées. Posez au plus deux questions pouvant changer le diagnostic, comme « La même défaillance s’est-elle produite avec un autre opérateur ? » ou « Quel contrôle aurait dû la détecter ? ». Marquez explicitement journaux indisponibles, souvenirs rétrospectifs et hypothèses non testées.

## Procedure

1. **Délimitez la défaillance.** Décrivez quoi, où, quand, fréquence et impact ; distinguez événement et interprétation. **Résultat visible/changement d’état :** publiez énoncé du problème en une phrase et limite attendu-observé, avec périmètre inconnu non vérifié.
2. **Séparez les niveaux.** Classez les observations en symptôme, cause immédiate, condition contributive, faiblesse de contrôle ou condition systémique. Gardez plusieurs branches si les preuves soutiennent plusieurs chemins. **Résultat visible/changement d’état :** créez un inventaire causal étiqueté plutôt qu’une accusation.
3. **Construisez la chaîne.** Utilisez chronologie, questions « pourquoi », carte de processus ou regroupement cause-effet pour relier chaque candidat à la prochaine condition observable. Arrêtez la branche lorsqu’elle devient spéculative et consignez la vérification manquante. **Résultat visible/changement d’état :** publiez chaîne causale et état du soutien de chaque lien substantiel.
4. **Testez la contrôlabilité contrefactuelle.** Pour chaque condition profonde proposée, demandez si sa suppression ou modification empêcherait plausiblement la défaillance, le reste du contexte restant similaire. Considérez chemins indépendants et contrôles pouvant encore échouer. **Résultat visible/changement d’état :** marquez chaque candidat contrôlable, contributif, irrésolu ou contredit, sans classement numérique fabriqué.
5. **Choisissez actions et responsables.** Séparez confinement limitant le préjudice actuel, prévention modifiant la condition et détection interceptant une récurrence. Attribuez responsable, limite d’échéance et signal de test à chaque action substantielle. **Résultat visible/changement d’état :** publiez registre d’actions lié à la chaîne, avec risque résiduel si une action n’est pas achevée.
6. **Vérifiez et révisez.** Définissez l’observation ultérieure montrant une baisse de récurrence ou un diagnostic erroné. Rouvrez la chaîne si une preuve nouvelle contredit un lien ; ne clôturez pas parce qu’une action a été annoncée. **Résultat visible/changement d’état :** publiez diagnostic suspendu, provisoire ou étayé, condition de vérification datée et prochaine vérification.

## Public output contract

Renvoyez problème délimité, chaîne causale, condition profonde contrôlable et distinction entre confinement, prévention et détection. Montrez état probant de chaque lien substantiel, responsable, signal de vérification et risque résiduel. Une Conclusion Card peut résumer diagnostic et condition de basculement ; les branches détaillées vont dans la trace. Si la condition profonde n’est pas établie, dites « l’explication principale est » et gardez le travail provisoire plutôt que de présenter un coupable unique comme fait.

## Evidence and uncertainty rules

Un symptôme répété ne prouve pas une cause répétée. Distinguez relevé horodaté, test reproductible ou observation directe d’un récit rétrospectif ou plausible. « Erreur humaine » n’est jamais un diagnostic complet si charge, interface, incitations, formation, relais ou contrôles absents peuvent contribuer. Ne calculez priorité de risque ou probabilité de récurrence sans échelle défendable et provenance ; utilisez substantiel, plausible, irrésolu ou à faible conséquence seulement avec fondement déclaré. Si les branches se contredisent, montrez le conflit et suspendez la conclusion profonde.

## Stop conditions

Arrêtez et suspendez si la limite de défaillance est inconnue, les dossiers distinguant les causes indisponibles ou chaque candidat fondé sur un récit non testé. Nommez un individu comme cause uniquement si des preuves directes soutiennent l’affirmation et que les conditions systémiques ont été examinées. Si le préjudice continue, privilégiez confinement sûr et procédures qualifiées d’incident ou de sécurité plutôt qu’une explication soignée.

## Complement handoff

Passez le relais à failure-mode-effects-analysis si le diagnostic doit devenir un inventaire prospectif des défaillances possibles du processus ou de la conception et des contrôles à attribuer. Transmettez uniquement limite publique de défaillance, branches causales et contrôles connus ; la méthode complémentaire ne doit pas répéter des accusations non étayées ni inventer des scores de gravité.

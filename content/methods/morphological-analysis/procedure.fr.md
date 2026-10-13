## Purpose

Utilisez cette procédure lorsqu’une solution complexe peut varier selon plusieurs dimensions indépendantes et que l’espace des options doit être exploré systématiquement. Elle décompose le problème en paramètres cohérents, énumère des valeurs plausibles pour chacun, crée des combinaisons, élimine les incompatibilités selon des règles explicites et choisit des concepts représentatifs à tester. Le résultat est un espace de conception transparent et des candidats filtrés, pas la promesse que chaque combinaison est faisable ou de valeur égale.

## Use when

Utilisez-la pour concevoir des politiques, services, produits, modèles opérationnels ou stratégies lorsque les alternatives qualitatives comptent et qu’aucun modèle numérique unique ne saisit le problème. Elle aide lorsqu’une équipe optimise toujours une seule dimension, manque des combinaisons ou doit comparer configurations conventionnelles et non évidentes. Utilisez si possible quatre à huit dimensions, chacune définie de sorte que modifier l’une ne modifie pas implicitement une autre.

## Do not use when

Ne l’utilisez pas si les dimensions ne peuvent être rendues cohérentes, si le problème relève d’une règle contraignante ou si quelques options connues répondent déjà à la question. Ne créez pas un espace gigantesque de combinaisons masquant l’infaisabilité ou submergeant la décision. N’attribuez pas à chaque cellule des utilités, probabilités ou pourcentages de faisabilité inventés. Si une combinaison peut nuire à la sécurité, au droit, à l’accessibilité ou à la vie privée, écartez-la ou saisissez l’autorité compétente avant d’en faire un candidat.

## Inputs to establish

Énoncez la question de conception, l’objectif, les utilisateurs ou acteurs concernés, les contraintes impératives, l’horizon et la décision que doit éclairer l’espace des options. Proposez des dimensions indépendantes avec leurs définitions et quelques valeurs pour chacune ; consignez preuves, hypothèses, incompatibilités et limites de ressources. Posez au plus deux questions décisives, comme « Quelle dimension représente un choix réel plutôt qu’une conséquence ? » ou « Quel couplage est impossible pour une raison connue de sécurité ou d’exploitation ? ».

## Procedure

1. **Délimitez l’espace de conception.** Énoncez problème, objectif, acteurs, contraintes et exclusions ; définissez ce qui constitue une solution distincte. **Résultat visible/changement d’état :** publiez les limites de conception et un critère pour séparer les dimensions.
2. **Définissez dimensions et valeurs.** Choisissez des dimensions cohérentes et des valeurs significatives, dont une référence et au moins une valeur non évidente lorsque cela se justifie. **Résultat visible/changement d’état :** publiez la matrice des paramètres, leurs définitions, les états des preuves et les hypothèses non résolues.
3. **Produisez des combinaisons.** Combinez les valeurs sans préférence prématurée ; utilisez un échantillon gérable si l’espace complet est vaste et expliquez la règle d’échantillonnage. **Résultat visible/changement d’état :** publiez les combinaisons candidates et les dimensions représentées dans chaque concept.
4. **Vérifiez la cohérence par paires.** Éliminez les combinaisons violant des contraintes impératives, contredisant des dépendances connues, dupliquant une option ou nécessitant des ressources indisponibles. Signalez les combinaisons incertaines plutôt que de les effacer silencieusement. **Résultat visible/changement d’état :** publiez les combinaisons rejetées avec leurs motifs et une liste d’incertitudes.
5. **Choisissez des concepts représentatifs.** Sélectionnez des configurations conventionnelles, exploratoires et équilibrées couvrant différents compromis ; décrivez bénéficiaires, porteurs de coûts et vérifications de faisabilité importantes. **Résultat visible/changement d’état :** publiez une liste restreinte filtrée et ses critères de comparaison, sans scores fabriqués.
6. **Testez et décidez.** Choisissez un prototype réversible, une simulation, une consultation ou un petit pilote pour l’inconnue la plus déterminante. **Résultat visible/changement d’état :** publiez le candidat privilégié ou la suspension, le responsable du test, les preuves nécessaires et la condition qui changerait la sélection.

## Public output contract

Renvoyez la question de conception, la matrice des paramètres, la règle de combinaison, les exclusions de cohérence, les concepts représentatifs, l’examen de faisabilité et le prochain test. Précisez quelles dimensions sont étayées et lesquelles sont supposées. La Conclusion Card indique le candidat à tester et le compromis ou la contrainte déterminante, avec une condition observable de basculement ; gardez l’espace complet des combinaisons dans la trace ou l’artefact produit.

## Evidence and uncertainty rules

La matrice organise des possibilités ; elle n’établit ni demande, ni sécurité, ni coût, ni performance. N’inférez pas la validité d’une combinaison du seul fait que chaque valeur est valide séparément. Consignez incompatibilités par paires, dépendances et inconnues. Les termes ordinaux comme plausible, bloqué ou à vérifier exigent une règle explicite ; évitez la fausse précision. Si une combinaison non testée peut modifier substantiellement la recommandation, maintenez la conclusion provisoire et nommez la plus petite évaluation sûre.

## Stop conditions

Arrêtez si les dimensions se recoupent, les valeurs ne peuvent être définies, les contraintes impératives sont inconnues ou la croissance des combinaisons empêche un examen pertinent. Suspendez la sélection si la faisabilité dépend d’une dépendance non vérifiée ou qu’un candidat peut causer un préjudice évitable. Soumettez les contraintes spécialisées de sécurité, d’accessibilité, juridiques ou de confidentialité à l’autorité compétente avant tout test.

## Complement handoff

Passez le relais à first-principles si les dimensions reposent sur des hypothèses conventionnelles à réduire à des contraintes irréductibles. Transmettez les limites publiques de conception, la matrice, les paires incompatibles, la liste restreinte et les vérifications ouvertes ; la méthode complémentaire doit remettre les hypothèses en cause sans reconstruire tout l’espace de combinaisons.

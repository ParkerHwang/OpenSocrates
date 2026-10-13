## Purpose

Utilisez cette procédure si le résultat d'une décision dépend de la réponse d'un autre acteur, dont le résultat dépend en retour de cette décision. Elle rend visibles joueurs, actions, incitations, informations, temporalité et engagements crédibles avant une recommandation. Elle n'autorise pas à inventer une matrice de gains, des probabilités ou un équilibre que les éléments disponibles ne soutiennent pas.

## Use when

Utilisez-la pour concurrence, négociation, enchères, prix, entrée ou dissuasion, conception de contrats, normes partagées et autres choix où une partie peut s'adapter stratégiquement. Elle aide si la question manquante est « que feront-ils si nous faisons cela ? », ou si promesse, menace, réputation ou avantage informationnel peut changer le résultat. Explicitez interaction répétée et possibilité de coopération au lieu de les supposer.

## Do not use when

Ne l'utilisez pas pour optimiser un acteur unique dans un environnement sans réponse stratégique significative. Ne l'utilisez pas pour une règle obligatoire sans latitude, un choix mécanique ou un prétendu adversaire sans effet sur le résultat. Ne réduisez pas une relation négociée à une concurrence à somme nulle sans éléments. N'inférez rationalité, motivations cachées ou gain numérique parce qu'une action paraît commode.

## Inputs to establish

Établissez décision centrale, joueurs et droits décisionnels, actions faisables, résultats valorisés, informations disponibles à chacun, ordre des coups et caractère unique ou répété de l'interaction. Consignez engagements crédibles, contraintes et comportements passés seulement s'ils sont sourcés ou fournis. Les gains peuvent rester ordinaux ou qualitatifs sans échelle défendable. Posez au maximum deux questions concises, uniquement si acteur, action, incitation, information ou temporalité manquante peut changer le coup recommandé.

## Procedure

1. Publiez décision et registre des joueurs : qui agit, qui est touché, qui peut bloquer ou retarder. Marquez les rôles observés, fournis par l'utilisateur, inférés ou supposés ; cela établit le périmètre visible du jeu. Résultat visible/changement d'état : périmètre publié.
2. Publiez actions et informations de chaque joueur. Montrez actions faisables, observations accessibles, coups simultanés ou séquentiels et récurrence de l'interaction ; cela précise un concours vague. Résultat visible/changement d'état : structure publiée.
3. Publiez un registre d'incitations pour les résultats importants. Utilisez les conséquences sourcées ou fournies, marquées verified, computed, inferred, assumed, unverified ou conflicted ; gardez les comparaisons ordinales si les gains exacts ne sont pas défendables. Résultat visible/changement d'état : incitations publiées.
4. Publiez l'examen des réponses : comparez les meilleures réponses crédibles en simultané ou remontez depuis la dernière décision en séquentiel. Justifiez une action dominante si elle est étayée ; sinon, montrez les paires de réponses pertinentes sans prétendre connaître toutes les motivations. Résultat visible/changement d'état : examen des réponses publié.
5. Publiez les résultats stables candidats et s'il y en a un, plusieurs ou aucun étayé. N'utilisez « équilibre » que si les hypothèses d'actions, incitations, informations et temporalité sont suffisamment étayées ; sinon, dites conditionnel et nommez le manque. Résultat visible/changement d'état : résultats publiés.
6. Publiez leviers d'intervention et coup recommandé. Précisez ce qu'il modifie : incitations, informations, temporalité, actions ou crédibilité d'engagement ; joignez un signal observable de réponse pour rendre la stratégie exploitable. Résultat visible/changement d'état : coup et signal publiés.
7. Publiez conclusion, incertitude principale et condition observable inversant le coup. Sans gain, joueur ou fait temporel décisif, suspendez et indiquez la plus petite vérification levant la suspension, plutôt que désigner un gagnant fictif. Résultat visible/changement d'état : suspension publiée.

## Public output contract

Renvoyez un résultat compact avec `players`, `actions`, `incentives`, `information`, `timing`, `response_analysis`, `candidate_outcome`, `equilibrium_caveat`, `move` et `flip_condition`. Un résultat candidat n'est pas automatiquement souhaitable, équitable, efficace ou inévitable. Précisez son statut étayé, conditionnel, conflictuel ou suspendu. Les fondements emploient les étiquettes probantes de la fiche ; les alternatives résument coups ou engagements sensiblement différents. N'exposez pas de transcription de raisonnement privé.

## Evidence and uncertainty rules

Séparez comportement observé et théorie des motivations. Une affirmation de gain exige source, registre utilisateur, calcul reproductible ou hypothèse explicite ; étiquetez source et périmètre. N'inventez probabilités, taux d'actualisation, informations cachées ou rationalité. Une réponse stable signifie qu'aucun changement unilatéral étayé n'améliore le résultat déclaré sous les hypothèses données ; elle ne prouve pas sa valeur sociale. Une menace ou promesse ne compte que si l'acteur aurait encore une raison de l'exécuter au moment pertinent. Marquez incitations manquantes, contradictoires ou anciennes non vérifiées ou conflictuelles et affaiblissez la conclusion.

## Stop conditions

Arrêtez-vous et posez une question bloquante si deux ensembles plausibles de joueurs, actions ou temporalités conduisent à des coups sensiblement différents sans choix possible selon l'objectif utilisateur. Suspendez si incitation, condition informationnelle ou séquence décisive manque. Arrêtez sans orientation s'il n'existe pas d'interdépendance stratégique significative. Terminez lorsque structure, réponse conditionnelle, coup, état probant et signal de révision sont publics ; ne continuez pas les calculs pour créer une fausse précision.

## Complement handoff

Passez à `stakeholder-analysis` uniquement si le jeu révèle des questions importantes de pouvoir, consentement, légitimité, soutien de mise en œuvre ou groupes touchés non représentés. Transmettez joueurs, incitations, conflits, engagements et incertitude non résolue. Le complément doit cartographier acteurs et besoins d'engagement, sans refaire l'analyse des réponses ni fabriquer de gains manquants.

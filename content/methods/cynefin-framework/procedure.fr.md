## Purpose

Utilisez cette procédure pour choisir un mode de réponse d'après la forme observée d'une situation. Elle distingue une relation cause-effet reproductible d'une situation exigeant expertise, expériences sûres, confinement urgent ou meilleur cadrage. L'objectif n'est pas de décorer une recommandation avec une étiquette de domaine, mais de rendre visibles les éléments de classification, l'action qui en découle et le signal susceptible de changer cette classification.

## Use when

Utilisez-la lorsque la réponse proposée peut être inadaptée : processus fixe appliqué à un problème adaptatif, analyse attendue pendant une perturbation rapide ou problèmes distincts traités comme un seul. Elle est utile lorsque choisir entre standardiser, analyser, sonder et agir constitue la décision. Elle peut aussi séparer une situation mixte en parties exigeant des réponses différentes.

## Do not use when

Ne l'utilisez pas pour une tâche purement mécanique, une règle établie sans latitude significative ou une demande de calcul connu ou de transcription. Ne forcez pas une classification si l'utilisateur veut seulement une étiquette décorative sans changement d'action. Une situation complexe n'est pas automatiquement plus importante, ni une situation claire automatiquement sûre ; la classification décrit la relation décisionnelle, pas la gravité des conséquences.

## Inputs to establish

Établissez question de décision, périmètre, horizon temporel, phénomène observé et contrainte immédiate de sécurité ou continuité. Recueillez observations, exemples antérieurs, expertise et faits utilisateur, en indiquant ce qui est vérifié, inféré, supposé ou non vérifié. Posez au maximum deux questions concises, seulement si leur réponse peut changer le mode d'action. Si l'observation décisive est indisponible, énoncez un périmètre provisoire et poursuivez uniquement jusqu'à une suspension clairement marquée.

## Procedure

1. Publiez en une phrase question de décision, périmètre, horizon et contrainte immédiate. Marquez chaque élément fourni par l'utilisateur ou supposé ; cela établit le cadrage visible. Résultat visible/changement d'état : cadrage publié.
2. Publiez un registre d'observations causales séparant relations reproductibles, relations dépendant d'experts, rétroactions émergentes, perturbation aiguë et observations encore ininterprétables. Joignez un état probant à chaque observation importante. Résultat visible/changement d'état : registre d'observations publié.
3. Publiez une classification provisoire — clair, compliqué, complexe, chaotique ou confus — avec les deux ou trois observations la soutenant. Si les éléments conduisent à des classifications distinctes pour différentes parties, scindez la situation et publiez les périmètres séparés plutôt que de les moyenner. Résultat visible/changement d'état : classification publiée.
4. Publiez le mode d'action adapté : observer–catégoriser–répondre pour un phénomène reproductible ; observer–analyser–répondre pour un phénomène expert ; sonder–observer–répondre pour une dynamique adaptative ; agir–observer–répondre pour une perturbation urgente. Pour une classification confuse, publiez la plus petite tâche de cadrage ou observation levant la confusion. Résultat visible/changement d'état : mode d'action publié.
5. Publiez une prochaine action sûre et ses signaux d'apprentissage ou transition. Précisez ce qui sera observé, par qui et quand ; un signal doit être observable, pas l'espoir général d'une amélioration. Résultat visible/changement d'état : registre de signaux publié.
6. Publiez l'état de conclusion, ses éléments, une incertitude importante et la condition inversant classification ou mode d'action. Choisir une étiquette ne justifie pas la certitude. Résultat visible/changement d'état : conclusion publiée.
7. Si une limite, observation ou contrainte manquante peut changer le mode d'action, publiez un résultat suspendu ou provisoire et la question ou vérification bloquante. Cela suspend l'état au lieu de remplir la lacune d'un fait inventé. Résultat visible/changement d'état : suspension publiée.

## Public output contract

Renvoyez un résultat compact prêt pour la fiche avec `decision_question`, `domain`, `classification_evidence`, `action_mode`, `transition_signals`, `next_action` et `flip_condition`. Le domaine est une conclusion soutenue par des observations visibles, pas un badge. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** selon le cas. Incluez au maximum trois hypothèses importantes et deux incertitudes non résolues. Si le résultat est suspendu, indiquez le manque et la vérification levant la suspension.

## Evidence and uncertainty rules

Observations directes, sources identifiées, registres utilisateur et calculs reproductibles ne prouvent que ce qu'ils soutiennent effectivement. Une étiquette est normalement inférée du phénomène ; elle n'est pas vérifiée parce qu'une source utilise le même mot. N'inventez pas de probabilités de transition, d'impact ou de réussite. Séparez l'existence de rétroactions de l'inférence sur leur sens. Marquez changement de périmètre, classification concurrente ou observation ancienne comme conflictuels ou non vérifiés ; affaiblissez la conclusion si l'incertitude peut changer l'action suivante.

## Stop conditions

Arrêtez-vous et posez une question bloquante si deux périmètres ou observations plausibles demandent des actions sensiblement différentes sans choix possible à partir de l'objectif utilisateur ou d'une contrainte faisant autorité. Suspendez si relation décisive, contrainte immédiate ou signal de transition ne peuvent être établis. Terminez lorsque sont publiés un mode exploitable, un signal observable et une condition de révision. En urgence, n'attendez pas une analyse exhaustive ; consignez l'action de confinement et réexaminez la classification après de nouvelles observations.

## Complement handoff

Passez à `scenario-planning` uniquement si la classification révèle plusieurs futurs externes cohérents exigeant des préparations différentes. Transmettez périmètre publié, éléments de classification, mode d'action, signaux de transition et incertitude non résolue. Ne refaites pas toute la classification et ne demandez pas au complément un fait manquant devant d'abord lever la suspension de cette procédure.

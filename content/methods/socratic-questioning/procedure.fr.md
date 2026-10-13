## Purpose

Utilisez cette procédure lorsque quelques réponses de l’utilisateur peuvent modifier substantiellement la question, le niveau de preuve ou la recommandation. Les questions font apparaître hypothèses, sens, fondements, alternatives et implications tout en gardant la responsabilité d’une réponse délimitée. Elles aident la décision ; elles ne servent ni à éviter de répondre ni à conduire l’utilisateur vers une conclusion prédéterminée.

## Use when

Utilisez-la si affirmation, termes, périmètre, preuves ou conséquence souhaitée sont flous et qu’une petite clarification changerait l’orientation. Elle convient à l’accompagnement, l’enseignement, la délibération, l’auto-examen et la définition collaborative d’un problème. Ne l’utilisez pour un jugement que si les réponses manquantes sont réellement décisives ; sinon, énoncez une hypothèse raisonnable et poursuivez.

## Do not use when

Ne l’utilisez pas pour une tâche mécanique, une demande pouvant être traitée sans risque avec une hypothèse délimitée ou une situation où les questions répétées ne feraient que retarder l’action. Ne demandez ni raisonnement privé, ni information personnelle inutile à la décision, ni entretien ouvert. N’utilisez pas de questions orientées présupposant la réponse désirée.

## Inputs to establish

Établissez affirmation ou décision de l’utilisateur, termes à préciser, périmètre actuel, preuves disponibles, alternatives déjà envisagées et conséquence importante pour lui. Sélectionnez au plus trois questions décisives. Pour chacune, indiquez ce que la réponse changerait : cadrage, statut probant, ordre des options ou état d’achèvement. Définissez un repli sûr si l’utilisateur ne répond pas.

## Procedure

1. Publiez une reformulation neutre de l’affirmation ou décision et du point irrésolu. Cela crée une question partagée sans suggérer un accord.
2. Publiez jusqu’à trois questions délimitées, chacune avec effet décisionnel et format court ou plage de réponse. Cet ensemble visible est l’unique demande de clarification ; n’ajoutez pas de questionnaire caché.
3. Consignez chaque réponse comme fournie par l’utilisateur, sans réponse ou ambiguë, et publiez son effet immédiat sur périmètre, termes, preuves ou alternatives. Cela rend le changement du jugement visible.
4. Publiez le fondement favorable le plus fort et un contre-exemple crédible ou une alternative soulevé par les réponses. Distinguez une réponse d’une preuve sur le monde.
5. Publiez une conclusion provisoire ou la prochaine action délimitée, avec ce qui peut être fait sans autre question. Si une réponse change l’orientation, énoncez la nouvelle en langage clair plutôt que de cacher le changement.
6. Publiez l’incertitude restante et la condition observable pouvant faire basculer la conclusion. Ne marquez les questions sans réponse comme hypothèses que si celles-ci sont sûres et réversibles.
7. Publiez la réponse actuelle, sa justification à partir des entrées répondues et l’état achevé, provisoire ou suspendu de la tâche. Si la question décisive reste sans réponse, ne fabriquez pas de certitude.

## Public output contract

Renvoyez `no_more_than_three_decisive_questions`, `decisive_questions` (trois maximum), `why_each_matters`, `answers_and_status`, `decision_effects`, `provisional_conclusion`, `remaining_uncertainty`, `next_action` et `flip_condition`. Les questions sont visibles et délimitées ; la fiche finale ne doit pas exposer une transcription de délibération privée. Au plus deux incertitudes irrésolues vont dans la fiche. Les fondements portent **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

Les réponses utilisateur établissent préférences, périmètre ou contexte, sauf si elles fournissent aussi des preuves vérifiables. Ne les promouvez pas à **verified** sans source d’appui identifiable. Une question décisive sans réponse laisse l’affirmation concernée **assumed**, **unverified** ou **held**, selon son importance. Si les réponses se contredisent, montrez le conflit et ne posez aucune question supplémentaire sauf si une brève question peut le résoudre sans risque.

## Stop conditions

Arrêtez et posez les questions sélectionnées si poursuivre sans réponses modifierait substantiellement l’action. N’en posez pas plus de trois ; si l’utilisateur ne peut répondre, poursuivez avec une hypothèse réversible ou suspendez le jugement. Cessez de questionner dès que l’orientation et la conclusion sont assez stables pour agir, ou que la tâche est mécanique sans jugement restant.

## Complement handoff

Passez le relais à `assumption-mapping` uniquement si les réponses exposent plusieurs hypothèses substantielles à hiérarchiser et tester. Transmettez ensemble des questions répondues et sans réponse, statut des hypothèses et condition actuelle de basculement. La méthode complémentaire ne doit pas répéter les questions socratiques ni les transformer en entretien sans limite.

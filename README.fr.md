<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Mettez 48 méthodes de raisonnement au service de vos conversations avec l’IA.**

OpenSocrates propose des procédures de raisonnement réutilisables dans **Claude,
Codex et Antigravity**. Comparez des options, démêlez des informations
contradictoires et examinez un plan sous un autre angle. Décrivez votre tâche avec
vos propres mots ; les méthodes fournissent des questions, des vérifications et
des étapes sur lesquelles vous appuyer.

[Commencer avec votre application](#start-with-your-app) · [Voir un exemple](#see-it-in-a-task) · [Explorer les méthodes](#a-method-for-the-question)

**48 méthodes · 10 langues d’instructions · Licence MIT**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · **Français** · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## Des outils pour votre tâche du moment

- **Partez de votre tâche.** Chaque méthode contient déjà des questions et des vérifications, prêtes à être réutilisées d’une conversation à l’autre.
- **Trouvez un angle utile.** Appuyez-vous sur des méthodes pour comparer des options, évaluer des preuves, explorer des hypothèses et préparer la suite.
- **Adaptez-les à votre travail.** Lisez chaque procédure, étudiez ses exemples et adaptez ce contenu open source à vos besoins.

<a id="see-it-in-a-task"></a>

## Un exemple concret

Après la configuration, essayez une demande comme celle-ci :

> Nous allions acheter un outil hébergé, mais notre processus doit maintenant fonctionner hors ligne.
> Faut-il acheter un outil, développer le nôtre ou travailler manuellement pour le moment ?

Pour ce type de décision, l’[analyse des compromis](content/methods/trade-off-analysis/procedure.fr.md)
propose une démarche réutilisable : identifier les exigences, comparer les options
réalisables, séparer les faits établis des hypothèses et expliquer ce qui ferait
changer la recommandation. La méthode apporte cette structure à votre demande
habituelle.

<a id="start-with-your-app"></a>

## Commencer avec votre application

Choisissez où vous souhaitez utiliser OpenSocrates.
[Télécharger v1.5.3](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3).

<details>
<summary><strong>Claude Chat et Cowork</strong> — téléverser une compétence et commencer une conversation</summary>

Pour Claude web, Desktop Chat et Cowork :

1. Dans **Settings → Capabilities**, activez **Code execution and file creation**. Pour un compte géré par une organisation, vérifiez que sa politique autorise les Skills et l’exécution de code.
2. Téléchargez le [ZIP de la compétence de compte](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip) et son [fichier SHA-256](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip.sha256).
3. Ouvrez **Customize → Skills → + → Create skill → Upload a skill**, téléversez le ZIP et activez la compétence. Sauvegardez toute compétence OpenSocrates existante avant de la remplacer.
4. Ajoutez la [consigne de compte à configurer une seule fois](docs/setup-guide.md#claude-standing-instructions) à chaque compte Claude utilisé, sans effacer vos consignes existantes. Commencez une nouvelle conversation et décrivez votre tâche.

Le ZIP portable de la compétence contient les méthodes et les exemples complets.
[Guide visuel de configuration](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Guide officiel des Skills de Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Mac Apple Silicon</summary>

Vous avez besoin de [Node.js 20 ou ultérieur](https://nodejs.org/en/download), de
la CLI Claude et d’un compte Claude connecté. Cela fonctionne avec Claude Code
dans le terminal et le mode Code local de Claude Desktop. Exécutez dans le
**Terminal** :

```sh
npx --yes opensocrates@1.5.3 install --host claude
npx --yes opensocrates@1.5.3 diagnose --host claude
```

Vérifiez `enabled: true`, `integrity: verified` et `registration: confirmed`.
Examinez toute demande de confiance du projet, puis démarrez une nouvelle session locale.
[Guide visuel de configuration](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Mac Apple Silicon ou Windows x64</summary>

Vous avez besoin de [Node.js 20 ou ultérieur](https://nodejs.org/en/download) et de
Codex. Le moteur natif est fourni avec le paquet. Exécutez dans le **Terminal sur
Mac** ou dans **PowerShell sous Windows** :

```sh
npx --yes opensocrates@1.5.3 install --host codex
npx --yes opensocrates@1.5.3 status --host codex
```

Ouvrez Codex en mode interactif et saisissez `/hooks` dans le champ de saisie.
Examinez les sept définitions de hooks OpenSocrates et approuvez celles auxquelles
vous faites confiance, puis commencez une nouvelle conversation.
[Guide visuel de configuration](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

Pour mettre à jour une installation Codex existante :

```sh
npx --yes opensocrates@1.5.3 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Mac Apple Silicon ou Windows x64</summary>

Vous avez besoin de [Node.js 20 ou ultérieur](https://nodejs.org/en/download).
Choisissez un espace de travail et remplacez l’exemple par le chemin absolu d’un
dossier existant. Exécutez dans le **Terminal sur Mac** ou dans **PowerShell sous
Windows** :

```sh
npx --yes opensocrates@1.5.3 install --host antigravity --workspace "/absolute/path/to/workspace"
```

Sous Windows, utilisez un chemin de lecteur local entre guillemets, comme
`"C:\Work\Reading Workshop"`. Pour une configuration globale, omettez
`--workspace`. Pour un même projet, choisissez une installation globale ou dans
l’espace de travail, puis commencez une nouvelle conversation.
[Vérifier la compétence et la règle](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**Vous confiez la configuration à un agent ?** Utilisez la [demande de configuration](docs/setup-guide.md#ask-an-agent-to-finish-setup)
ou le [guide d’installation actuel](docs/agent-discovery.md). Sélectionnez chaque
application avec son option `--host` ; la valeur par défaut et `--host all`
sélectionnent Codex.

<a id="a-method-for-the-question"></a>

## Une méthode adaptée à la question

| Votre tâche | Une méthode à explorer |
| --- | --- |
| Choisir entre des options aux priorités concurrentes | [Analyse des compromis](content/methods/trade-off-analysis/procedure.fr.md) |
| Comprendre les hypothèses qu’un plan tient pour acquises | [Cartographie des hypothèses](content/methods/assumption-mapping/procedure.fr.md) |
| Évaluer ce qui étaye une affirmation | [Pensée critique](content/methods/critical-thinking/procedure.fr.md) |
| Se préparer aux difficultés possibles d’un plan | [Analyse prémortem](content/methods/premortem-analysis/procedure.fr.md) |

Chaque méthode comprend son objectif, ses conditions d’utilisation, sa procédure
complète, des exemples et des questions destinées à l’assistant. Explorez le
texte, suivez les étapes du raisonnement et réutilisez les méthodes dans vos tâches.

[Parcourir les 48 méthodes](content/methods/)

## Le texte complet des méthodes en dix langues

Anglais, coréen, chinois simplifié, japonais, français, allemand, italien,
espagnol, portugais et thaï. Chaque langue comprend les procédures et les
exemples complets des 48 méthodes.

Ce sont les langues du texte des méthodes que lit votre assistant.
[Guide linguistique](docs/v1.5.2.md) · [Langue des instructions de Codex](docs/settings.md)

## Un projet open source à explorer

Lisez les méthodes et le code source complets, adaptez-les à votre travail ou
contribuez avec un nouvel exemple. OpenSocrates est un projet indépendant,
disponible sous [licence MIT](LICENSE).

[Versions](https://github.com/ParkerHwang/OpenSocrates/releases) · [Guide de configuration](docs/setup-guide.md) · [Confidentialité et sécurité](SECURITY.md) · [Contribuer](CONTRIBUTING.md) · [Signaler un problème](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Historique des versions](CHANGELOG.md)

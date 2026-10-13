<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Une aide au raisonnement pour des résultats que vous pouvez comprendre, évaluer et utiliser.**

OpenSocrates propose 48 méthodes de raisonnement pour synthétiser des sources,
comprendre les points de vue, comparer des choix et rédiger des messages utiles.
La version 1.5.2 ajoute le français (`fr`), l’allemand, l’italien, l’espagnol,
le portugais et le thaï aux contenus anglais, coréen, chinois simplifié et japonais.
Les dix langues comprennent 480 procédures complètes, 3 840 cas canoniques et
1 440 questions adressées à l’agent, soit trois par méthode et par langue.
La révision de contenu passe à 5 : les textes et valeurs des quatre langues
existantes sont conservés, mais l’identité de révision de chaque méthode passe
de 4 à 5. Aucune méthode spécialisée de programmation n’est ajoutée.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | **Français** | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português](README.pt.md) | [ไทย](README.th.md)

## Applications et plateformes

| Application | Mode de livraison | Plateforme et activation |
| --- | --- | --- |
| Codex | Hooks existants et moteur natif de décision | Mac Apple Silicon et Windows x64 ; vérifier la confiance des 7 hooks en session interactive |
| Claude Code CLI / Code local de Desktop | Entrée native sans état et références complètes | Mac Apple Silicon ; CLI Claude, connexion et autorisations du plugin/hooks |
| Claude Web / Desktop Chat / Cowork | ZIP de compétence de compte sans code exécutable | Export sur Mac ou Windows, puis téléversement et activation séparés dans le compte |
| Antigravity | Règle et compétence modulaires | Mac Apple Silicon et Windows x64 ; portée projet ou globale |

Le périmètre de plateformes reste celui de v1.5.0. Claude Code natif sous
Windows n’est pas inclus. Windows ARM64 et la migration Go relèvent du travail
séparé de v1.6.0. Une compétence de compte n’installe pas une intégration native.

## Installer ou mettre à jour

Installez Node.js 20 ou ultérieur et connectez-vous à l’application choisie.
Les moteurs natifs sont fournis : Python n’est pas requis pour l’installation.
Les archives et sommes SHA-256 sont disponibles sur la
[page v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
npx --yes opensocrates@1.5.2 update --host codex
```

Pour une installation existante, utilisez `update` plutôt que `install`.
Dans Codex interactif, ouvrez `/hooks`, examinez les 7 hooks OpenSocrates et
accordez les approbations nécessaires par le mécanisme de confiance de l’hôte.
Commencez ensuite une nouvelle conversation. `status` vérifie l’installation
et l’intégrité, sans prouver l’approbation des hooks ni l’application réelle.

Sur Mac Apple Silicon, utilisez `install --host claude` pour Claude Code.
Pour Antigravity, choisissez un répertoire existant avec un chemin absolu ;
sans `--workspace`, la portée est globale. Évitez deux installations actives
pour le même travail. Sous Windows, utilisez un chemin de lecteur local entre
guillemets, par exemple `"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Exportez la compétence de compte vers un fichier ZIP absolu dans un dossier
existant, puis téléversez-la et activez-la dans Claude, **Customize → Skills**.
Avant de remplacer une compétence OpenSocrates, sauvegardez son ZIP et son état
d’activation. L’export ne constitue ni téléversement, ni activation, ni preuve
de sélection automatique. Ajoutez cette consigne à **Settings → General →
Instructions for Claude**, sans effacer vos consignes existantes :

```text
Pour les demandes qui nécessitent une interprétation ou un jugement, comme
la synthèse de sources, la comparaison d’options, une décision ou la rédaction
d’un message, chargez la compétence OpenSocrates activée et suivez ses consignes,
même si je ne la nomme pas. Lisez la procédure complète et vérifiez ses conditions
d’application avant d’utiliser une méthode. N’ajoutez pas de procédure inutile
aux tâches mécaniques comme la mise en forme.
```

Dans les anciennes interfaces Cowork, utilisez **Settings → Cowork → Global
instructions**. Configurez chaque compte utilisé si Web et Desktop diffèrent,
puis ouvrez une nouvelle conversation. La sélection dépend du modèle et peut
être omise ; aucun hook natif ni usage garanti à chaque message n’est ajouté.
La valeur par défaut et `--host all` sélectionnent uniquement Codex.

## Choisir la langue des instructions

Le français partage l’alphabet latin avec plusieurs langues : il faut une
préférence explicite ou enregistrée, et non une détection supposée du français.
À la racine du paquet Codex installé sur Mac, définissez la préférence :

```sh
bin/launch.sh locale codex set fr
bin/launch.sh locale codex get
bin/launch.sh locale codex reset
```

Sous Windows, utilisez `node bin/launch.mjs locale codex set fr`.
`set follow` ou `reset` efface la préférence de langue sans effacer les autres
réglages. Cette préférence concerne le sélecteur conservé. Les requêtes de décision
sans état exigent leur champ JSON `locale`; elles ne lisent pas les réglages.
Les paquets de compte/contenu utilisent le guide et les références de la langue.

Ordre de choix : langue explicite fiable, préférence enregistrée, puis caractères
de l’entrée actuelle. Les kana donnent priorité au japonais ; sinon les caractères
thaïs, hangul ou han dominants sélectionnent le thaï, le coréen ou le chinois.
Les égalités, entrées vides et écritures inconnues reviennent à l’anglais. Le japonais
sans kana est ambigu et nécessite `ja`. Le portugais utilise le code générique `pt`
et l’orthographe brésilienne, sans prise en charge distincte de toutes les variantes.
La langue des instructions est distincte de celle de la réponse, de l’interface
et des messages de l’installateur npm. Il n’existe pas d’option npm `--locale`.

## Attribution, confidentialité et limites

La ligne finale exacte `Powered by OpenSocrates` n’apparaît que si une méthode
canonique admissible a été lue entièrement et réellement appliquée à la réponse.
Une simple aide à la lecture ou une tâche mécanique ne suffit pas. L’attribution
ne prouve ni l’application native ni une amélioration de la qualité.

Le chemin de décision par défaut ne fait aucun appel supplémentaire à un modèle
de sélection et ne stocke ni prompts bruts, conversations, captures d’écran, ni
raisonnement caché. L’entrée native Claude ne lit pas de conversations et ne crée
pas de base de données. Les comptes et conversations restent régis par les règles
de l’hôte. Installation, chargement, lecture complète, application et utilité sont
des niveaux de preuve distincts ; aucun gain universel de qualité, coût ou vitesse
n’est revendiqué.

Consultez le [guide linguistique](docs/v1.5.2.md), les [réglages](docs/settings.md),
le [guide visuel](docs/setup-guide.md) et la [politique de sécurité](SECURITY.md).
Les guides [Mac](docs/macos-v1.5.md) et [Windows](docs/windows-v1.5.md) conservent
leurs observations historiques ; utilisez ici les commandes 1.5.2.

OpenSocrates est un projet indépendant sous [licence MIT](LICENSE), sans affiliation
ni approbation d’OpenAI, Anthropic ou Google. [Historique des versions](CHANGELOG.md).

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

## Migration native v1.6.0

Cette branche est un candidat v1.6.0 non publié. Le contenu reprend v1.5.2 et ses dix langues, mais les exécutables Go remplacent Python, Node.js et npm. Les utilisateurs n’installent aucun de ces outils, ni Go. Windows ARM64 utilise ses propres fichiers natifs ; Claude Code natif reste réservé à macOS ARM64. Les preuves de signature, notarisation et publication restent des conditions séparées. Les nouvelles méthodes sont reportées à v1.6.1 ou plus tard.

## Applications et plateformes

[v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2) · [v1.6.0](docs/native-v1.6.md) · [Setup](docs/setup-guide.md) · [Security](SECURITY.md)

| Application | Mode de livraison | Plateforme et activation |
| --- | --- | --- |
| Codex | Hooks existants et moteur natif de décision | Mac Apple Silicon et Windows x64/ARM64 ; vérifier la confiance des 7 hooks en session interactive |
| Claude Code CLI / Code local de Desktop | Entrée native sans état et références complètes | Mac Apple Silicon ; CLI Claude, connexion et autorisations du plugin/hooks |
| Claude Web / Desktop Chat / Cowork | ZIP de compétence de compte sans code exécutable | Export sur Mac ou Windows, puis téléversement et activation séparés dans le compte |
| Antigravity | Règle et compétence modulaires | Mac Apple Silicon et Windows x64/ARM64 ; portée projet ou globale |

## Installer ou mettre à jour

Téléchargez l’exécutable et le paquet natif correspondants depuis une release approuvée. Avant publication, les paquets du candidat sont des constructions locales. Pour reprendre une installation v1.5 gérée par npm, utilisez explicitement `adopt`; les réglages, permissions et intégrations désactivées sont conservés. Utilisez `update` avec un paquet vérifié pour les mises à jour suivantes.

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/bundle.zip
```

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

Dans Codex interactif, ouvrez `/hooks`, examinez les 7 hooks OpenSocrates et
accordez les approbations nécessaires par le mécanisme de confiance de l’hôte.
Commencez ensuite une nouvelle conversation. `status` vérifie l’installation
et l’intégrité, sans prouver l’approbation des hooks ni l’application réelle.

Sur Mac Apple Silicon, utilisez `install --host claude` pour Claude Code.
Pour Antigravity, choisissez un répertoire existant avec un chemin absolu ;
sans `--workspace`, la portée est globale. Évitez deux installations actives
pour le même travail. Sous Windows, utilisez un chemin de lecteur local entre
guillemets, par exemple `"C:\Work\Reading Workshop"`.

```text
./opensocrates install --host claude --package /absolute/path/to/claude-bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/antigravity-bundle.zip --workspace /absolute/path/to/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
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

Avec l’exécutable natif sur Mac :

```text
./opensocrates locale set fr
./opensocrates locale get
./opensocrates locale reset
```

Sous Windows x64/ARM64, utilisez `.\opensocrates.exe`; les commandes `locale` n’ont pas d’argument d’hôte.
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
et des messages de gestion. Aucune option `--locale` d’installation n’est ajoutée.

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

Consultez le [guide natif](docs/native-v1.6.md) pour les mises à jour automatiques, la récupération et les preuves encore requises. Les guides v1.5.2 et npm restent propres au canal de maintenance publié.

OpenSocrates est un projet indépendant sous [licence MIT](LICENSE), sans affiliation
ni approbation d’OpenAI, Anthropic ou Google. [Historique des versions](CHANGELOG.md).

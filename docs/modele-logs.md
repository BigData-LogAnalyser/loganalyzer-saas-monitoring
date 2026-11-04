# Modèle de logs — LogAnalyzer

SCRUM-10 · Contrat v1.0 · 4 novembre 2026 · Prêt pour revue.

## 1. Référence et périmètre

Référence fixe : **ECS 8.17.0**, choisie pour disposer d’un contrat versionné dans la famille 8.x envisagée. Ce choix ne prétend pas utiliser la dernière version et ne fixe pas les versions Docker des produits Elastic. La référence est archivée ; toute migration du schéma devra être explicite.

Ce contrat complète SCRUM-8. Il concerne des logs synthétiques de SaaS, importés manuellement. Les fichiers d’entrée utilisent des clés simples ; les documents indexés utilisent des objets JSON imbriqués. Les maquettes restent illustratives.

ECS définit les noms, types et significations des champs standard. Le projet impose en plus ses formats, ses champs requis par famille, ses niveaux et sa gestion des rejets. « Core » et « Extended » ne signifient pas « obligatoire » et « facultatif ». Le modèle prévoit `@timestamp` et `ecs.version` sur tous les événements.

## 2. Dictionnaire des champs d’entrée

O = obligatoire pour tous ; H = obligatoire pour HTTP ; S = obligatoire pour SQL ; B = obligatoire pour métier ; F = facultatif. Les types cibles ci-dessous sont ceux du mapping Elasticsearch. Une chaîne d’identifiant reste une chaîne même si elle contient uniquement des chiffres.

| Entrée | Cible | Signification / exemple | Type entrée → cible | Unité | Présence |
|---|---|---|---|---|---|
| timestamp | @timestamp | Date de l’événement : `2026-11-04T10:00:00.000Z` | chaîne → date | instant UTC | O |
| level | log.level | Niveau : `INFO` | chaîne → keyword | — | O |
| service | service.name | Service émetteur : `task-service` | chaîne → keyword | — | O |
| message | message | Texte : `Tâche créée` | chaîne → match_only_text | — | O |
| event_type | event.dataset, via table §3 | Famille interne : `http` | chaîne → keyword dérivé | — | O |
| endpoint | url.path | Chemin réel sans query string : `/api/tasks` | chaîne → wildcard | — | H |
| http_method | http.request.method | Méthode : `GET` | chaîne → keyword | — | H |
| status_code | http.response.status_code | Statut : `200` | entier → long | code HTTP | H |
| response_time_ms | event.duration | Durée HTTP : `125` | entier → long après conversion | ms → ns | H |
| user_id | user.id | Utilisateur fictif : `U1` | chaîne → keyword | — | F |
| organization_id | organization.id | Organisation fictive : `ORG1` | chaîne → keyword | — | F |
| request_id | http.request.id | Corrélation HTTP : `REQ1` | chaîne → keyword | — | F, HTTP uniquement |
| error_code | error.code | Code source : `REPORT_TIMEOUT` | chaîne → keyword | — | F |
| error_message | error.message | Description source de l’erreur | chaîne → match_only_text | — | F |
| db_query | saas.database.query_name | Nom logique : `list_tasks` ; pas de SQL brut | chaîne → keyword personnalisé | — | S |
| sql_duration_ms | event.duration | Durée SQL : `1200` | entier → long après conversion | ms → ns | S |
| action | event.action | Action : `task-created` | chaîne → keyword | — | B ; F pour application |
| feature | saas.feature | Fonctionnalité : `tasks` | chaîne → keyword personnalisé | — | B |

Les autres champs évoqués en exploration (`ip`, `session_id`, `cpu_percent`, `memory_mb`, etc.) ne font pas partie du contrat v1 ; ils nécessitent une extension documentée avant leur acceptation. Les champs `saas.*` sont personnalisés, même s’ils ressemblent à des noms standard.

## 3. Familles d’événements

| event_type d’entrée | event.dataset cible | Champs propres requis | Champs propres interdits |
|---|---|---|---|
| http | saas.http | endpoint, http_method, status_code, response_time_ms | db_query, sql_duration_ms, action, feature |
| application | saas.application | Aucun en plus du socle | champs HTTP, db_query, sql_duration_ms, feature |
| sql | saas.database | db_query, sql_duration_ms | champs HTTP, action, feature |
| business | saas.business | action, feature | champs HTTP, db_query, sql_duration_ms |

Les erreurs ne sont pas une famille supplémentaire : elles peuvent survenir dans chaque famille et sont décrites par le niveau et les champs `error.*`. Un niveau ERROR ne force pas un code HTTP 500, et inversement.

`event_type` est un nom interne d’entrée, **jamais copié dans `event.type`**. Le contrat v1 omet `event.type`, `event.category` et `event.outcome` pour éviter des catégorisations déduites sans règle métier. Il ajoute `event.kind = "event"`.

Pour les événements métier du générateur : `project-viewed` → `projects`, `task-created` et `task-updated` → `tasks`, `report-generated` → `reports`. Ce sont les seuls couples action/fonctionnalité acceptés dans v1. Une action échouée peut garder ce couple avec un niveau ERROR ; le compteur d’utilisation mesure les tentatives d’usage, pas seulement les succès. Une action utilisateur produit un seul événement métier d’utilisation ; les traces intermédiaires sont des événements `application`.

## 4. Durées et dates

Règle projet pour simplifier v1 : durées d’entrée entières en millisecondes, positives ou nulles, au plus `9223372036854`. Les fractions sont rejetées, sans arrondi. La multiplication doit utiliser des entiers, pas un flottant.

`event.duration = durée_ms × 1 000 000` ; affichage en ms = `event.duration / 1 000 000`.

Exemples : 125 ms → 125000000 ns ; 1200 ms → 1200000000 ns. Un événement HTTP porte uniquement sa durée HTTP ; un événement SQL distinct porte uniquement sa durée SQL. Un enregistrement contenant les deux durées est rejeté. Ne pas additionner ni écraser les durées. Les logs application et métier n’ont pas de durée dans v1.

Date d’entrée : `YYYY-MM-DDTHH:mm:ss[.SSS](Z|±HH:mm)` ; fraction facultative de 1 à 3 chiffres ; calendrier valide, secondes 00–59, décalage jusqu’à ±14:00. Une date sans fuseau est rejetée. Convertir en UTC et sérialiser avec trois décimales et `Z`. L’affichage journalier reste Africa/Tunis selon le cadrage. Ne pas remplacer une date absente par l’heure d’import.

## 5. Traçabilité ajoutée par le système

Ces champs sont générés côté serveur et ne sont pas acceptés dans les entrées.

| Champ cible | Statut | Type | Exemple et règle |
|---|---|---|---|
| ecs.version | ECS, requis | keyword | Constante `8.17.0` |
| event.kind | ECS, requis par projet | keyword | Constante `event` |
| event.dataset | ECS, requis par projet | keyword | Table §3 |
| event.id | ECS, requis par projet | keyword | `<upload_id>:<source_line>` ; ex. `upload-demo:2` |
| event.ingested | ECS, requis à l’indexation | date | Date d’arrivée dans Elasticsearch, renseignée par un processeur d’ingestion à partir de `_ingest.timestamp` |
| log.file.path | ECS, requis par projet | keyword | Chemin absolu du fichier réellement lu : `/data/uploads/upload-demo/source.csv` |
| loganalyzer.upload_id | Personnalisé, requis | keyword | UUID d’import créé par le serveur ; `upload-demo` dans les exemples pédagogiques |
| loganalyzer.source_line | Personnalisé, requis | long | Numéro physique de ligne à partir de 1 ; en CSV le premier événement est ligne 2 |
| loganalyzer.original_filename | Personnalisé, requis | keyword | Nom affichable sans chemin : `logs.csv` |
| loganalyzer.schema_version | Personnalisé, requis | keyword | Constante `1.0` du contrat projet |

Un import est relié à ses métadonnées MongoDB par `upload_id`. Le nom d’origine n’est ni un chemin fiable ni une clé unique. `source_line` n’est pas `log.origin.file.line`, qui désigne une ligne du code source applicatif. Le fichier confirmé doit rester immuable pendant le traitement.

Utiliser `event.id` comme `_id` Elasticsearch pour rendre une réindexation du même import et de la même ligne idempotente. Un nouvel import du même fichier reçoit un nouvel identifiant et peut produire des doublons métier : la déduplication inter-imports est hors périmètre.

L’identifiant d’organisation ne garantit aucune isolation des accès. Les espaces de noms personnalisés retenus sont `saas` pour le métier et `loganalyzer` pour l’import ; ils ne sont pas présentés comme des champs ECS officiels.

## 6. Règles transversales

- Chaînes non vides après contrôle des espaces ; valeurs conservées sans trim silencieux. Noms de service : `[a-z][a-z0-9-]{0,63}`.
- Niveaux acceptés exactement : DEBUG, INFO, WARNING, ERROR, CRITICAL. Cette liste appartient au projet, pas à ECS ; aucune conversion silencieuse de FATAL ou WARN.
- Les méthodes HTTP sont des chaînes alphabétiques de 1 à 20 caractères, casse conservée comme fournie ; le générateur produit GET, POST, PUT, PATCH ou DELETE.
- Statut HTTP : entier entre 100 et 599. Pas de booléen ni de chaîne numérique en JSON.
- Endpoint : chemin commençant par `/`, sans `?`, `#` ni espace. Regroupement des KPI par chemin réel dans v1, sans prétendre normaliser `/tasks/12` en `/tasks/{id}`.
- Champs facultatifs absents : omis dans le document cible, jamais remplacés par zéro, `null` ou une valeur inventée. Un champ facultatif présent mais invalide entraîne le rejet de l’événement.
- Chaînes sans caractères de contrôle U+0000 à U+001F. Texte limité à 4096 caractères pour message/error_message, endpoint à 2048, autres chaînes à 256, sauf service limité à 64. Ces limites sont des choix de projet.
- Champs inconnus, objets imbriqués en entrée, clés JSON dupliquées et types incorrects : rejet. Le modèle d’entrée n’est pas le modèle cible.
- Aucun champ vide ni objet vide dans les sorties. Les objets `service`, `http`, `event`, etc. sont imbriqués, pas des clés littérales contenant des points.

## 7. Lien avec les KPI

HTTP : `event.dataset=saas.http`, statut dans `http.response.status_code`, durée dans `event.duration`, endpoint dans `url.path`. SQL : `event.dataset=saas.database`, durée > 1000000000 ns pour le seuil de 1000 ms. Utilisateurs actifs : union des familles HTTP et métier, décompte distinct de `user.id` présent. Fonctionnalités : famille `saas.business`, groupement sur `saas.feature`. Erreurs : niveaux ERROR ou CRITICAL, toutes familles confondues. Fichiers importés : métadonnées MongoDB, pas nombre de valeurs distinctes dans les seuls logs réussis.

## 8. Références officielles vérifiées

- [Référence ECS 8.17.0](https://www.elastic.co/guide/en/ecs/8.17/ecs-field-reference.html)
- [Champs de base : date et message](https://www.elastic.co/guide/en/ecs/8.17/ecs-base.html)
- [Version ECS](https://www.elastic.co/guide/en/ecs/8.17/ecs-ecs.html)
- [Événements : durée, dataset et catégorisation](https://www.elastic.co/guide/en/ecs/8.17/ecs-event.html)
- [HTTP](https://www.elastic.co/guide/en/ecs/8.17/ecs-http.html)
- [URL](https://www.elastic.co/guide/en/ecs/8.17/ecs-url.html)
- [Logs et chemin du fichier](https://www.elastic.co/guide/en/ecs/8.17/ecs-log.html)
- [Erreurs](https://www.elastic.co/guide/en/ecs/8.17/ecs-error.html)
- [Champs personnalisés](https://www.elastic.co/guide/en/ecs/8.17/ecs-custom-fields-in-ecs.html)

Les types exacts retenus corrigent les raccourcis des premières notes : statut HTTP `long`, message et error.message `match_only_text`, url.path `wildcard`. Le modèle n’impose pas `keyword` à tous les champs.

## 9. Preuves et suite

Les documents cibles de `samples/cibles/` illustrent les quatre familles avec des objets imbriqués et des métadonnées fictives. Les règles de sérialisation et de rejet figurent dans `formats-import.md`. Le ticket définit le contrat ; il ne prétend pas avoir déployé le mapping ou testé une chaîne Logstash réelle. Conserver ces livrables localement puis les intégrer au dépôt dans SCRUM-12.

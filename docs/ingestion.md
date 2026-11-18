# Ingestion et normalisation — SCRUM-16

## Objectif

Lire les événements CSV, JSON Lines et TXT, vérifier leur conformité
au contrat SCRUM-10, les normaliser vers ECS et indexer les événements
valides dans Elasticsearch.

Références :
- [Modèle de logs](modele-logs.md)
- [Formats d’import](formats-import.md)
- [Import et prévisualisation](import.md)

## Répartition des rôles

- Flask reçoit les fichiers et prépare leur prévisualisation.
- La confirmation conserve le fichier original dans uploads et
  enregistre l’import dans MongoDB avec l’état EN_ATTENTE.
- Logstash décode les lignes, valide leurs valeurs et normalise
  les événements valides.
- Elasticsearch indexe les événements et ajoute event.ingested.
- Les événements invalides sont conservés séparément avec leurs motifs.

Dans SCRUM-16, les tests transmettent explicitement les lignes à
Logstash. Depuis SCRUM-17, le tracker prend automatiquement en charge
les imports confirmés, transmet leurs lignes à Logstash et vérifie
les résultats avant de finaliser leur état.

Voir [Suivi des imports](suivi-imports.md).

Logstash ne parcourt pas automatiquement les brouillons ni tous
les fichiers du volume uploads.

## Fichiers de configuration

| Fichier | Rôle |
|---|---|
| elasticsearch/templates/loganalyzer-logs.json | Paramètres et types des champs |
| elasticsearch/pipelines/loganalyzer-ingested.json | Ajout de la date de réception |
| logstash/pipeline/main.conf | Réception, enchaînement et destinations |
| logstash/scripts/parse.rb | Décodage CSV, JSON Lines et TXT |
| logstash/scripts/validate.rb | Contrôles du contrat SCRUM-10 |
| logstash/scripts/normalize.rb | Transformation vers ECS |
| logstash/checks/chain.conf | Chaîne de test avec entrée et sortie terminal |

## Template Elasticsearch

Nom : loganalyzer-logs-v1.

Le template s’applique aux nouveaux index loganalyzer-logs-*.

Configuration locale :
- Un shard primaire.
- Zéro réplique, car le déploiement comporte un seul nœud.
- dynamic: strict pour refuser les champs non déclarés.
- coerce: false pour les champs numériques concernés.
- Pipeline final : loganalyzer-ingested-v1.

Principaux types :
- @timestamp et event.ingested : date.
- event.duration et http.response.status_code : long.
- Identifiants, niveaux et familles : keyword.
- message et error.message : match_only_text.
- url.path : wildcard.

Le mapping ne remplace pas les contrôles de validation :
il ne vérifie pas, à lui seul, toutes les obligations du contrat.

## Installation des configurations Elasticsearch

Depuis la racine du dépôt, avec Elasticsearch démarré.

Installer d’abord le pipeline :

```bash
docker compose exec -T elasticsearch curl -fsS \
  -X PUT 'http://localhost:9200/_ingest/pipeline/loganalyzer-ingested-v1?pretty' \
  -H 'Content-Type: application/json' \
  --data-binary @- \
  < elasticsearch/pipelines/loganalyzer-ingested.json
```

Installer ensuite le template :

```bash
docker compose exec -T elasticsearch curl -fsS \
  -X PUT 'http://localhost:9200/_index_template/loganalyzer-logs-v1?pretty' \
  -H 'Content-Type: application/json' \
  --data-binary @- \
  < elasticsearch/templates/loganalyzer-logs.json
```

La réponse attendue est acknowledged: true.

Une modification du template ne change pas automatiquement
le mapping des index déjà créés.

## Entrée du pipeline Logstash

Le service écoute sur http://logstash:8080 dans le réseau Docker.
Ce port n’est pas publié sur Ubuntu.

Chaque requête contient une enveloppe JSON avec :
- format : csv, json, jsonl ou txt.
- raw : la ligne source, sans sa fin de ligne.
- context.upload_id : identifiant de l’import.
- context.source_line : numéro physique de la ligne.
- context.source_path : chemin absolu du fichier réellement lu.
- context.original_filename : nom affichable du fichier.

L’enveloppe transporte la ligne originale ; elle ne remplace
pas son décodage par Logstash.

Pour CSV, l’en-tête est vérifié avant la transmission des événements
et n’est pas envoyé comme événement. Le premier événement porte
le numéro de ligne 2.

La limite HTTP Logstash est de 1 Mio par requête, enveloppe comprise.
Elle est distincte de la limite de 100 Mio par fichier dans Flask.

## Lecture et validation

parse.rb :
- CSV : point-virgule, citations strictes et 18 colonnes.
- JSON Lines : un objet par ligne et détection des clés dupliquées.
- TXT : 18 champs séparés par des tabulations.
- Conversion des nombres CSV/TXT en entiers.
- Conservation de la position des cellules vides.

validate.rb vérifie notamment :
- Les champs obligatoires et les champs inconnus.
- Les types, les chaînes vides et les caractères interdits.
- La validité des dates et de leur fuseau.
- Les niveaux DEBUG, INFO, WARNING, ERROR et CRITICAL.
- Les statuts HTTP entre 100 et 599.
- Les durées entières positives ou nulles dans les limites du contrat.
- Les champs requis ou interdits pour chaque famille.
- Les couples action/fonctionnalité autorisés.

Un événement illisible ou invalide ne passe pas à la normalisation.

## Normalisation ECS

Référence de schéma : ECS 8.17.0.
Version des images Elastic du projet : 8.19.0.

Exemples de transformations :
- timestamp → @timestamp, converti en UTC.
- level → log.level, sans changement silencieux de niveau.
- service → service.name.
- endpoint → url.path.
- status_code → http.response.status_code.
- Durée en millisecondes → event.duration en nanosecondes.

La conversion des durées utilise des entiers :
125 ms devient 125000000 ns.

Les familles deviennent :
- http → saas.http.
- application → saas.application.
- sql → saas.database.
- business → saas.business.

Les champs facultatifs absents restent absents.
Les champs de traçabilité sont ajoutés depuis le contexte de l’import.

## Indexation et dates

Les index sont nommés loganalyzer-logs-yyyy.MM.dd
selon la date UTC de l’événement.

event.id vaut <upload_id>:<source_line>.
Cette valeur est également utilisée comme _id Elasticsearch.

Renvoyer la même ligne du même import met à jour le même document.
Un nouvel import reçoit un autre identifiant.

Deux dates ont des rôles distincts :
- @timestamp : date de l’événement dans le SaaS.
- event.ingested : date de réception de la requête d’indexation
  par Elasticsearch, ajoutée depuis _ingest.timestamp.

event.ingested est renseigné à chaque passage par le pipeline final.

Une réponse HTTP de Logstash confirme la réception de la requête.
Elle ne prouve pas, à elle seule, la réussite de l’indexation.

## Conservation des rejets

Chemin dans le conteneur Logstash :

```text
/usr/share/logstash/data/rejections/rejections.jsonl
```

Ce fichier est conservé dans le volume logstash_data.

Un rejet de données conserve notamment :
- upload_id et source_line.
- original_filename.
- failure_kind: data.
- errors : codes, champs et motifs.
- raw : contenu original de la ligne.

Un événement peut avoir plusieurs diagnostics mais représente
une seule ligne rejetée.

Un renvoi peut ajouter une nouvelle ligne au fichier de rejets.
Depuis SCRUM-17, le tracker compte les événements distincts par
identifiant d’import et numéro de ligne. Les répétitions identiques
ne sont pas comptées plusieurs fois.

Les rejets ne sont pas envoyés dans les index de logs valides.

## Échecs techniques d’indexation

La dead letter queue est activée avec :

```yaml
DEAD_LETTER_QUEUE_ENABLE: "true"
```

Elle conserve les échecs pris en charge par cette fonctionnalité,
notamment certains refus de documents par Elasticsearch.

Une panne de service ne signifie pas que la ligne source est invalide.
Depuis SCRUM-17, le tracker vérifie les documents présents dans
Elasticsearch et les rejets enregistrés avant de finaliser l’import.
Des résultats manquants après le délai prévu provoquent un échec
technique explicite.

Les imports restés EN_COURS peuvent être repris. Les imports déjà
en ECHEC ne sont pas automatiquement relancés.

Le tracker ne lit pas directement la dead letter queue. Un refus
d’indexation sans résultat exploitable est détecté par l’absence
du document attendu et l’expiration du délai de vérification.

Le test des 42 événements valide les rejets de données ;
il ne constitue pas un test de panne ou de reprise technique.

## Vérifications réalisées

### Tests des scripts

- parse.rb : 6 tests réussis.
- validate.rb : 12 tests réussis.
- normalize.rb : 2 tests réussis.
- Chargement des trois scripts ensemble : Configuration OK.

### Comparaison avec les références

Sur les fichiers samples :
- CSV : 4 documents conformes aux cibles et 6 rejets attendus.
- JSON Lines : 4 documents conformes aux cibles et 6 rejets attendus.
- TXT : 4 documents conformes aux cibles et 6 rejets attendus.
- Fichier mixte : 10 événements valides et 2 rejets aux lignes 11 et 12.

Total : 42 événements, dont 22 normalisés et 20 rejetés.

### Indexation réelle

- 22 documents retrouvés dans Elasticsearch.
- Aucun événement des trois fichiers invalides indexé.
- _id conforme à event.id.
- event.ingested présent sur les 22 documents.
- 20 rejets distincts retrouvés dans le fichier de rejets,
  avec les motifs attendus et le contenu original.

## Vérifier et démarrer Logstash

Vérification de la configuration :

```bash
docker compose run --rm --no-deps -T logstash \
  --path.data /tmp/scrum16-main-check \
  --config.test_and_exit \
  -f /usr/share/logstash/pipeline/main.conf
```

Appliquer les modifications du service :

```bash
docker compose up -d --wait --force-recreate logstash
```

Consulter les derniers messages :

```bash
docker compose logs --tail=50 logstash
```

## Consulter les données dans Kibana

Dans Dev Tools :

```http
GET _cat/indices/loganalyzer-logs-*?v
```

Puis :

```http
GET loganalyzer-logs-*/_search
{
  "size": 10
}
```
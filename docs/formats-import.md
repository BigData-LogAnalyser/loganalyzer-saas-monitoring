# Formats d’import — LogAnalyzer

SCRUM-10 · Contrat v1.0 · 4 novembre 2026. Référence : [modèle de logs](modele-logs.md).

## 1. Règles communes

UTF-8 sans BOM ; fins de ligne LF ou CRLF ; dernier saut de ligne facultatif. Pas d’archive compressée. Extensions autorisées : `.csv`, `.json`, `.jsonl`, `.txt` (insensibles à la casse). `.json` et `.jsonl` signifient tous deux JSON Lines. Le format n’est pas autodétecté. Une limite `MAX_UPLOAD_BYTES` sera configurée : valeur initiale retenue 104857600 octets (100 Mio), choix projet modifiable.

Une ligne physique contient exactement un événement, sauf l’en-tête CSV. Les lignes vides internes sont des événements invalides ; un saut de ligne final ne crée pas une ligne vide supplémentaire. Fichier vide ou CSV contenant uniquement un en-tête : refus. Aucune ligne de commentaire.

Les 18 noms de champs autorisés, dans l’ordre CSV/TXT, sont :

```text
timestamp,level,service,message,event_type,endpoint,http_method,status_code,response_time_ms,user_id,organization_id,request_id,error_code,error_message,db_query,sql_duration_ms,action,feature
```

Les cinq premiers sont toujours requis. Les obligations et interdictions conditionnelles par famille sont définies dans `modele-logs.md`. Une colonne interdite pour une famille est laissée vide dans CSV/TXT et absente dans JSON.

## 2. CSV

- Séparateur unique : point-virgule `;`.
- Première ligne : les 18 noms ci-dessus dans cet ordre, séparés par `;`, sans espace ajouté, doublon ou colonne supplémentaire.
- Chaque ligne suivante contient exactement 18 cellules.
- Guillemets doubles pour entourer une cellule contenant `;` ou `"`. Un guillemet dans une cellule citée s’écrit `""`. Pas d’échappement par antislash.
- Interdiction des retours à la ligne à l’intérieur d’une cellule, même entre guillemets. Parsing strict ligne par ligne : une citation non fermée ne doit pas engloutir les lignes suivantes.
- Cellule vide : champ absent. La chaîne littérale `null` n’est pas une absence.
- Nombres : chiffres décimaux ASCII sans signe, espace, virgule ou exposant, selon `0|[1-9][0-9]*`. Conversion en entier avant validation.

Exemples complets : `samples/valides/logs.csv` et `samples/invalides/logs.csv`.

## 3. JSON Lines

- Un objet JSON complet par ligne ; aucun tableau englobant.
- Clés simples exclusivement ; aucun objet ni tableau comme valeur.
- L’ordre des clés n’a pas d’importance ; une clé dupliquée est rejetée, pas écrasée.
- Les champs textuels sont des chaînes. Les trois champs numériques (`status_code`, `response_time_ms`, `sql_duration_ms`) sont des entiers JSON, pas des chaînes, booléens, fractions ou valeurs NaN/Infinity.
- Un champ facultatif absent est omis. Les valeurs `null` et les chaînes vides sont rejetées.
- Les caractères de contrôle décodés, y compris un `\n` dans un message, sont interdits dans ce contrat v1.
- Une ligne JSON mal formée est rejetée indépendamment ; la ligne suivante reste lisible.

Exemple valide HTTP :

```json
{"timestamp":"2026-11-04T10:00:00.000Z","level":"INFO","service":"task-service","message":"Liste des tâches consultée","event_type":"http","endpoint":"/api/tasks","http_method":"GET","status_code":200,"response_time_ms":125,"user_id":"U1","organization_id":"ORG1"}
```

Les tableaux JSON et le JSON formaté sur plusieurs lignes ne sont pas acceptés, même avec l’extension `.json`.

## 4. TXT

Profil texte délimité par tabulations, sans en-tête : exactement 18 champs dans l’ordre commun. Séparateur : une tabulation réelle U+0009, et non les deux caractères `\t`.

Les champs facultatifs sont vides, mais leurs positions sont conservées, y compris les tabulations finales. Aucun mécanisme de citation ou d’échappement. Une tabulation ou un saut de ligne dans un champ est interdit. Les guillemets sont du texte ordinaire. Les nombres suivent la même grammaire que CSV.

Ce choix permet un format TXT déterministe avec message contenant des espaces. Les anciennes maquettes présentant un TXT libre ne définissent pas le contrat. Voir les fichiers `.txt` de `samples/` pour les tabulations réelles.

## 5. Étapes de validation et erreurs

1. Vérifier extension, taille, UTF-8, absence de BOM et présence de données. Pour CSV, vérifier l’en-tête exact. Une erreur à ce niveau refuse le fichier entier, sans ingestion.
2. Analyser jusqu’aux dix premiers événements et appliquer les règles de structure, types et métier. Une erreur dans cet aperçu bloque la confirmation. Afficher numéro de ligne, champ, code et motif. Ne pas annoncer un bilan global à partir de l’aperçu.
3. Après confirmation, analyser toutes les lignes avec les mêmes règles. Une ligne invalide est conservée en rejet ; les événements valides continuent leur traitement.
4. Les événements valides sont normalisés puis indexés. Un accusé d’indexation en échec n’est pas compté comme un succès. Les erreurs de service sont suivies séparément des rejets de données ; une panne n’est pas une preuve qu’une ligne source est invalide.
5. Finaliser uniquement après fin de lecture ET résolution du traitement de chaque ligne. Un timeout technique conduit à un échec explicite, jamais à un faux TERMINE.

Un fichier de démonstration mixte fourni contient 12 événements : les dix premiers sont valides, puis deux invalides. Il permet de tester les rejets après confirmation, contrairement aux fichiers invalides de six lignes qui sont bloqués dès l’aperçu.

### Codes de diagnostic

| Code | Cas | Effet |
|---|---|---|
| FILE_FORMAT / FILE_SIZE / FILE_ENCODING / FILE_EMPTY | Extension, taille, encodage ou fichier sans événement | Refus du fichier |
| CSV_HEADER | En-tête incorrect | Refus du fichier |
| ROW_STRUCTURE / JSON_SYNTAX / JSON_DUPLICATE_KEY | Ligne non décodable, mauvaise arité, clé dupliquée | Rejet de ligne |
| UNKNOWN_FIELD / INVALID_TYPE | Champ hors contrat ou mauvais type | Rejet de ligne |
| REQUIRED_FIELD / EMPTY_FIELD | Champ requis absent ou champ présent vide | Rejet de ligne |
| INVALID_TIMESTAMP / INVALID_LEVEL / INVALID_FAMILY | Date, niveau ou famille non conforme | Rejet de ligne |
| INVALID_VALUE / INVALID_DURATION | Valeur hors domaine ou durée non conforme | Rejet de ligne |
| FIELD_NOT_ALLOWED | Champ incompatible avec la famille | Rejet de ligne |
| INDEXING_ERROR | Échec d’indexation non résolu | Échec technique, distinct du rejet de données |

Un événement peut avoir plusieurs diagnostics mais n’incrémente le compteur de rejets qu’une seule fois. Aucun rejet silencieux. Les erreurs sont conservées dans un fichier JSON Lines distinct des fichiers à ingérer, pour éviter de réingérer les rejets.

Exemple de rejet (format de diagnostic personnalisé, non événement ECS) :

```json
{"upload_id":"upload-demo","source_line":12,"errors":[{"code":"REQUIRED_FIELD","field":"service","message":"Champ requis absent"}],"raw":"ligne originale"}
```

`upload_id` et `source_line` permettent de retrouver le fichier et l’événement. Le brut est échappé comme chaîne JSON et affiché comme texte dans l’interface.

### Compteurs et états

Le nombre attendu correspond aux lignes de données, hors en-tête CSV. Après fin de lecture, un bilan sans échec technique vérifie : `attendus = indexés + rejetés`. Tant que des écritures ou rejets restent non confirmés, l’état demeure EN_COURS. Les compteurs d’indexés utilisent les documents distincts par identifiant d’événement, pas le nombre de tentatives d’écriture.

- EN_ATTENTE : import confirmé, pas encore pris en charge.
- EN_COURS : traitement ou contrôle du bilan en cours.
- TERMINE : au moins un événement, tous indexés, aucun rejet ni échec technique.
- PARTIEL : au moins un événement indexé et au moins un rejet de données, bilan complet sans échec technique.
- ECHEC : aucun événement indexé après traitement complet, ou erreur technique bloquante. Des documents déjà indexés peuvent subsister ; leur nombre reste visible.

Le tracker Python coordonne ce suivi avec MongoDB, les rejets et Elasticsearch, conformément au rôle représenté dans les séquences. Ce contrat n’implémente pas ce service.

## 6. Exemples fournis et intégration

`samples/valides/` contient les mêmes quatre événements dans les trois formats. `samples/invalides/` contient six erreurs sémantiques dans chaque format, ainsi que des erreurs structurelles ciblées. `samples/mixte.jsonl` teste une ingestion partielle après aperçu valide. `samples/cibles/` illustre les sorties imbriquées. `samples/attendus.json` fournit les résultats attendus et `samples/README.md` leur lecture.

Les horodatages d’ingestion, identifiants d’import et chemins des exemples cibles sont fictifs et doivent être remplacés à l’exécution. Les cibles ne sont pas des fichiers à charger avec l’importeur de données brutes.

Conserver `docs/` et `samples/` dans le dossier local puis les versionner dans SCRUM-12. Les mappings et pipelines seront implémentés dans les tickets de développement ; ces fichiers n’attestent pas d’un déploiement Elasticsearch/Logstash.

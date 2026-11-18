# Suivi des imports — SCRUM-17

## Déroulement du suivi

Le tracker prend en charge les imports EN_ATTENTE et les passe
en EN_COURS. Il lit les fichiers confirmés et transmet chaque ligne
à Logstash par HTTP.

Logstash réalise le parsing, la validation et la normalisation.
Le tracker vérifie les documents indexés et les rejets enregistrés,
puis conserve le bilan et l’état final dans MongoDB.

Flask consulte MongoDB pour afficher la progression, les compteurs
et les diagnostics dans l’interface.

## Fonctionnement

Après confirmation dans Flask, le fichier original reste dans le volume
uploads. MongoDB conserve les métadonnées et l’état initial EN_ATTENTE.

Le tracker prend en charge l’import et le passe en EN_COURS. Il vérifie
le fichier, compte ses événements et transmet chaque ligne à Logstash
par HTTP, avec son format et ses informations de provenance.

Logstash réalise le parsing, la validation et la normalisation.
Les événements valides sont envoyés à Elasticsearch. Les événements
rejetés sont conservés dans le fichier de diagnostics Logstash.

Le tracker vérifie ensuite les documents présents dans Elasticsearch
et les diagnostics enregistrés avant de mettre à jour le bilan MongoDB.

## Fichiers du tracker

- main.py : coordination du traitement et mises à jour MongoDB.
- import_state.py : règles de décision de l’état.
- source_reader.py : vérification et lecture du fichier original.
- logstash_client.py : transmission des lignes à Logstash.
- result_reader.py : lecture des résultats d’indexation et des rejets.

## Stockage

- uploads : fichiers originaux confirmés et verrou du tracker.
- logstash_data : diagnostics Logstash, accessibles au tracker
  en lecture seule.
- Elasticsearch : événements normalisés et indexés.
- MongoDB, collection imports : métadonnées, état, compteurs,
  progression et motif d’échec.
- MongoDB, collection import_rejections : diagnostics par événement,
  avec numéro de ligne et contenu original.

Le tracker accède aux bases par le réseau Docker. Il ne lit pas
directement les volumes es_data et mongo_data.

## États

- EN_ATTENTE : import confirmé, pas encore pris en charge.
- EN_COURS : lecture, transmission ou vérification des résultats.
- TERMINE : au moins un événement, tous indexés, aucun rejet
  ni échec technique.
- PARTIEL : au moins un événement indexé et au moins un rejet
  de données, avec un bilan complet et sans échec technique.
- ECHEC : aucun événement indexé après résolution du bilan,
  ou erreur technique bloquante.

La fin de lecture du fichier ne suffit jamais à produire TERMINE.

Sans échec technique, la finalisation exige :

```text
lecture terminée
ET
événements attendus = événements indexés + événements rejetés
```

Une réponse HTTP réussie de Logstash confirme la réception du message,
pas son indexation dans Elasticsearch.

## Compteurs et progression

expected_count compte les lignes de données, hors en-tête CSV.
Une ligne vide interne compte comme événement à traiter.

indexed_count correspond aux lignes retrouvées dans Elasticsearch
avec les identifiants attendus.

rejected_count compte les rejets de données distincts.
Plusieurs diagnostics sur une même ligne ne comptent qu’une fois.
Les erreurs techniques ne sont pas ajoutées à ce compteur.

L’identifiant d’un événement est upload_id:source_line.
Il permet de reconnaître les répétitions et de vérifier le bilan.

La progression repose sur les résultats constatés :

```text
(indexed_count + rejected_count) / expected_count × 100
```

Elle reste inconnue tant que le total n’est pas déterminé et est
plafonnée à 99 % pendant EN_COURS.

Un pourcentage de 100 % ne signifie pas forcément succès :
un import PARTIEL comporte des événements rejetés.

## Erreurs et reprise

Une panne HTTP, une impossibilité de vérifier les résultats ou un délai
de vérification dépassé produit un échec technique explicite.

Les compteurs déjà constatés restent visibles. Après un échec technique,
des écritures transmises auparavant peuvent encore aboutir :
le bilan enregistré représente les derniers résultats observés,
pas une annulation des écritures Elasticsearch.

Si MongoDB devient indisponible pendant le suivi, le tracker réessaie.
Un import resté EN_COURS peut être repris avec les mêmes identifiants.

Une empreinte SHA-256 permet de détecter un changement du fichier
entre deux prises en charge ou pendant le traitement.

Un verrou partagé dans uploads empêche deux trackers de fonctionner
simultanément sur ce volume.

## Configuration

- MAX_UPLOAD_BYTES : 104857600 octets par défaut.
- LOGSTASH_URL : http://logstash:8080/ par défaut.
- IMPORT_RESULT_TIMEOUT : 180 secondes par défaut, pour attendre
  les résultats après transmission et fin de lecture.
- Contrôle des résultats pendant les envois : toutes les 50 lignes
  ou après au moins deux secondes.
- Attente entre les contrôles après lecture : deux secondes.

## API et interface

GET /api/imports/<upload_id> retourne l’état, les compteurs,
la progression et le motif d’échec éventuel.

GET /api/imports/<upload_id>/rejections retourne les diagnostics.

La consultation des diagnostics est paginée :
- limit : 20 par défaut, entre 1 et 100.
- after_line : numéro de ligne après lequel poursuivre la lecture.
- next_after_line : valeur à transmettre pour la page suivante.
- has_more : indique si une autre page est disponible.

L’interface actualise le suivi toutes les deux secondes.
Elle affiche les diagnostics et les lignes originales comme du texte.
Le dernier identifiant consulté est mémorisé dans le navigateur
pour retrouver son suivi après rechargement.

Une erreur de consultation du suivi n’est pas présentée comme
un échec du traitement de l’import.

## Vérifications réalisées

Les contrôles des fichiers auxiliaires couvrent les décisions d’état,
la lecture des sources, la transmission HTTP et la lecture des résultats.

Le test d’intégration utilise trois fichiers valides de quatre événements
et un fichier mixte de douze événements :

- CSV : TERMINE, 4 indexés et 0 rejeté.
- JSON Lines : TERMINE, 4 indexés et 0 rejeté.
- TXT : TERMINE, 4 indexés et 0 rejeté.
- Mixte JSON Lines : PARTIEL, 10 indexés et 2 rejetés.

Le total vérifié est de 22 documents dans Elasticsearch et
2 rejets dans MongoDB, aux lignes 11 et 12 du fichier mixte.

Les tests API vérifient les bilans, la pagination et les réponses
400 et 404.

Six tests du coordinateur simulent les résultats retardés ou manquants,
les pannes HTTP et MongoDB, la conservation des indexations déjà
constatées et le cas où tous les événements sont rejetés.

Commande de lancement :

```bash
docker compose run --rm --no-deps -T \
  -v "$PWD/tracker/checks:/checks:ro" \
  tracker \
  python -m unittest discover \
  -s /checks -p 'test_followup.py' -v
```

Ces six tests utilisent des services simulés et ne modifient pas
les données des bases.

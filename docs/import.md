# Import et prévisualisation — SCRUM-15

## Objectif

Déposer un fichier de logs, vérifier son aperçu, puis confirmer
ou annuler son import.

Les règles appliquées proviennent de :
- [Formats d’import](formats-import.md)
- [Modèle de logs](modele-logs.md)

## Démarrage

Depuis la racine du dépôt :

```bash
docker compose up -d --build --wait webapp
```

Ouvrir http://localhost:8000.

MongoDB, Redis et Elasticsearch sont démarrés si nécessaire
selon les dépendances définies dans Docker Compose.

## Formats acceptés

- CSV : séparateur point-virgule et en-tête exact de 18 colonnes.
- JSON Lines : un objet JSON par ligne, extension .json ou .jsonl.
- TXT : 18 champs séparés par des tabulations, sans en-tête.

Les trois formats suivent le même contrat de validation.
L’extension détermine le format ; aucune autodétection.

Encodage : UTF-8 sans BOM.

## Taille configurable

La variable MAX_UPLOAD_BYTES fixe la taille maximale du fichier.

Valeur initiale dans .env et .env.example :

```dotenv
MAX_UPLOAD_BYTES=104857600
```

Cette valeur correspond à 100 Mio.

Après modification de .env :

```bash
docker compose up -d --wait webapp
```

Le navigateur vérifie la taille avant l’envoi.
Le serveur vérifie également la taille réelle du fichier reçu.
Une marge supplémentaire de 1 Mio est réservée à l’enveloppe
HTTP du formulaire ; elle n’augmente pas la limite du fichier.

## Parcours utilisateur

1. Choisir un fichier ou le glisser dans la zone de dépôt.
2. Observer la progression de son envoi.
3. Attendre la vérification du serveur.
4. Consulter au maximum dix événements.
5. Confirmer l’import ou annuler le dépôt.

100 % signifie que l’envoi est terminé, pas que l’ingestion
est terminée.

Une erreur de fichier ou une erreur dans les dix premiers
événements bloque la confirmation et affiche son motif.
Les erreurs de ligne indiquent le numéro physique, le champ
concerné et un code de diagnostic.

En CSV, la première ligne de données porte le numéro 2.

L’aperçu ne constitue pas un bilan du fichier complet.
Les erreurs situées après les dix premiers événements seront
traitées pendant l’ingestion.

## Routes

| Méthode | Route | Rôle |
|---|---|---|
| GET | / | Afficher l’interface d’import |
| GET | /health | Vérifier que Flask répond |
| POST | /api/imports/preview | Déposer un fichier et préparer son aperçu |
| POST | /api/imports/<upload_id>/confirm | Confirmer et enregistrer l’import |
| POST | /api/imports/<upload_id>/cancel | Supprimer un brouillon |

La route de prévisualisation attend un formulaire multipart
contenant exactement un fichier dans le champ file.

### Principales réponses HTTP

- 201 : brouillon créé ou nouvel import enregistré.
- 200 : annulation réussie ou import déjà enregistré.
- 400 : dépôt incorrect ou extension non autorisée.
- 404 : identifiant invalide ou brouillon absent.
- 413 : taille maximale dépassée.
- 422 : fichier ou aperçu non conforme.
- 503 : erreur technique de stockage ou de base de données.

## Stockage et confirmation

Les fichiers sont conservés dans le volume Docker uploads.

Depuis le conteneur webapp :
- Brouillon : /app/uploads/drafts/<upload_id>/source.<extension>
- Fichier confirmé : /app/uploads/confirmed/<upload_id>/source.<extension>

Le serveur génère un UUID pour chaque dépôt.
Le nom d’origine est nettoyé et conservé comme métadonnée ;
il ne sert pas à construire le chemin de stockage.

La confirmation vérifie à nouveau l’aperçu, déplace le fichier
dans le dossier confirmed et enregistre ses métadonnées dans
la collection MongoDB imports.

L’état initial est EN_ATTENTE.
Le nombre total attendu reste inconnu ; indexed_count et
rejected_count commencent à zéro.

Une nouvelle tentative de confirmation du même identifiant
ne crée pas un second enregistrement.

En cas de résultat technique incertain, réessayer la
confirmation avec le même identifiant.

## Annulation et fichiers refusés

L’annulation supprime le dossier du brouillon et son fichier.
Elle n’enregistre aucun import et ne déclenche aucune ingestion.

Un fichier refusé pendant la prévisualisation est supprimé
du stockage des brouillons.

Le fichier original sur l’ordinateur de l’utilisateur reste intact.

Fermer ou recharger la page ne remplace pas une annulation :
le nettoyage automatique des brouillons abandonnés n’est pas
implémenté à cette étape.

## Vérifications réalisées

- Quatre événements valides lus dans chacun des trois formats.
- Six événements invalides détectés dans chacun des trois formats.
- Aperçu limité à dix événements avec samples/mixte.jsonl.
- Confirmation bloquée lorsque l’aperçu contient des erreurs.
- Confirmation enregistrée dans MongoDB avec l’état EN_ATTENTE.
- Annulation et suppression du dossier du brouillon.
- Refus des extensions non autorisées.
- Refus des fichiers vides, non UTF-8 ou contenant un BOM.
- Refus d’un en-tête CSV incorrect.
- Limite configurable testée dans un conteneur temporaire :
  1024 octets acceptés, 1025 octets refusés.
- Progression d’envoi observée avec ralentissement réseau
  dans le navigateur.

## Suite du développement

SCRUM-15 prépare et enregistre les imports.
La normalisation et l’indexation seront développées dans
SCRUM-16 ; le suivi du traitement sera développé dans SCRUM-17.

Seuls les imports confirmés devront être pris en charge.
Les dossiers de brouillons ne doivent jamais être ingérés.
# Jeux de référence SCRUM-10

- `valides/logs.csv`, `valides/logs.jsonl`, `valides/logs.txt` : les mêmes quatre événements, une famille par événement. Importer un seul format pour vérifier les KPI attendus ; importer les trois crée trois imports et multiplie les événements par trois.
- `invalides/logs.*` : six lignes invalides. Erreurs attendues par ligne dans `attendus.json`. La cellule vide CSV/TXT représente une clé omise en JSON.
- Autres fichiers de `invalides/` : erreurs structurelles ou de type ciblées. Chaque fichier doit échouer selon son motif attendu ; les fichiers ne représentent pas des données à corriger automatiquement.
- `mixte.jsonl` : dix lignes valides suivies de deux rejets ; à utiliser pour vérifier le statut PARTIEL après confirmation.
- `cibles/` : quatre documents normalisés après ingestion, pas des fichiers d’entrée de l’importeur. Chemins et identifiants fictifs.
- `attendus.json` : résultats pour un import isolé du jeu valide, sans filtre excluant des événements. Pour les logs du jour, fixer la date de test au 4 novembre 2026, fuseau Africa/Tunis : 4 événements attendus. Le nombre de fichiers importés est 1 si un seul fichier a été confirmé.

Les fichiers TXT contiennent de vraies tabulations et des champs vides finaux : ne pas les remplacer par des espaces ni les supprimer.

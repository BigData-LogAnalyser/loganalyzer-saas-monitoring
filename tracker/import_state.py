"""Règles de finalisation des imports, selon le contrat d'import."""


def determine_status(
    *,
    expected_count,
    indexed_count,
    rejected_count,
    reading_complete,
    technical_failure=False,
):
    # Une valeur incorrecte indique un problème de suivi.
    for name, value in (
        ("indexed_count", indexed_count),
        ("rejected_count", rejected_count),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} doit être un entier positif ou nul.")

    if expected_count is not None:
        if type(expected_count) is not int or expected_count < 0:
            raise ValueError(
                "expected_count doit être un entier positif ou nul."
            )

        if indexed_count + rejected_count > expected_count:
            raise ValueError(
                "Le bilan dépasse le nombre d'événements attendus."
            )

    if technical_failure:
        return "ECHEC"

    # Le total reste inconnu ou la lecture n'est pas terminée.
    if expected_count is None or not reading_complete:
        return "EN_COURS"

    resolved_count = indexed_count + rejected_count

    # Fin de lecture ne signifie pas fin d'indexation.
    if resolved_count < expected_count:
        return "EN_COURS"

    # Fichier sans événement, ou tous les événements rejetés.
    if indexed_count == 0:
        return "ECHEC"

    if rejected_count > 0:
        return "PARTIEL"

    return "TERMINE"
"""Jonction de l'archive et du dump : quelle source fait foi pour un jour donné."""

from pkgpulse.ingest.bronze import Partition


def should_write(existing: Partition | None, candidate: Partition) -> bool:
    """Vrai si la partition candidate doit remplacer celle du même jour.

    L'archive, définitive, l'emporte toujours sur le dump ; sinon on réécrit seulement si la
    source ou le contenu a changé. Un jour étant un seul fichier, aucun doublon n'est possible.
    """
    if existing is None:
        return True
    if existing.source == "archive" and candidate.source == "dump":
        return False
    return candidate != existing

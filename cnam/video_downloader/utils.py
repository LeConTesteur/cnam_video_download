"""
Contient les fichiers utiles à tous.
"""
import contextvars
from pathlib import Path
import urllib

youtube_dl_bin = contextvars.ContextVar("youtube_dl_bin")


def build_local_file(el_id, filename):
    """
    Construit le chemin de travail pour fichier et une tâche.
    """
    return f"tmp/{el_id}/{filename}"

def save_request(request, ident):
    """
    Sauvegarde une requête Request afin de pouvoir mieux analyser les problèmes.
    """
    folder = Path('tmp', ident)
    folder.mkdir(0o755, parents=True, exist_ok=True)
    file_path = Path(folder, urllib.parse.quote_plus(request.url)[0:254])
    with open(file_path, 'w', encoding='utf-8') as fd:
        fd.write(request.text)

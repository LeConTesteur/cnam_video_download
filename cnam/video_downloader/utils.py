import contextvars
from pathlib import Path
import urllib

youtube_dl_bin = contextvars.ContextVar("youtube_dl_bin")


def build_local_file(el_id, filename):
    return f"tmp/{el_id}/{filename}"

def save_request(request, ident):
    folder = Path('tmp', ident)
    folder.mkdir(0o755, parents=True, exist_ok=True)
    with open(Path(folder, urllib.parse.quote_plus(request.url)[0:254]), 'w', encoding='utf-8') as fd:
        fd.write(request.text)
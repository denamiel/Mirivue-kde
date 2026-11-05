"""Shared file-name and no-overwrite publication utilities; transfers use KIO."""
from .i18n import tr
from collections import Counter
import os
from pathlib import Path
import re
from .platform_services import services
TECHNICAL = {tr('hdr'), tr('sdr'), tr('uhd'), tr('hd'), tr('fhd'), tr('hevc'), tr('avc'), tr('aac'), tr('ac'), tr('dts'), tr('truehd'), tr('atmos'), tr('bluray'), tr('bdrip'), tr('brrip'), tr('webrip'), tr('web'), tr('dl'), tr('dvdrip'), tr('remux'), tr('multi'), tr('vostfr'), tr('vf'), tr('vff'), tr('vfq'), tr('french'), tr('eng'), tr('mkv'), tr('mp4'), tr('avi'), tr('saison'), tr('season'), tr('episode'), tr('ep')}

def suggest_folder(paths):
    sequences = []
    for path in paths:
        tokens = re.findall(tr('[^\\W_]+'), Path(path).stem, flags=re.UNICODE)
        sequences.append([t for t in tokens if len(t) > 1 and (not any((c.isdigit() for c in t))) and (t.casefold() not in TECHNICAL) and (not (t.isupper() and re.fullmatch(tr('[IVXLCDM]+'), t)))])
    counts = Counter((word for tokens in sequences for word in {t.casefold() for t in tokens}))
    repeated = {t for t, count in counts.items() if count >= 2}
    if not repeated:
        return tr('Nouveau dossier')
    best = max((counts[t] for t in repeated))
    chosen = {t for t in repeated if counts[t] >= max(2, best - 1)}
    ordered = []
    for tokens in sequences:
        for token in tokens:
            if token.casefold() in chosen and token.casefold() not in {t.casefold() for t in ordered}:
                ordered.append(token)
    return tr(' ').join(ordered[:6])[:100].strip() or tr('Nouveau dossier')

def valid_name(name):
    return services.validate_portable_name(name) is None

def invalid_name_reason(name):
    return services.validate_portable_name(name) or tr('Nom invalide.')

def exists(path):
    return os.path.lexists(path)

def normalize_sources(paths):
    paths = list(dict.fromkeys((Path(p).absolute() for p in paths)))
    selected = set(paths)
    return [p for p in paths if not any((parent in selected and (not parent.is_symlink()) for parent in p.parents))]

def rename_noreplace(source, target):
    tr('Atomically rename without replacing a destination on the current OS.')
    services.rename_no_replace(Path(source), Path(target))

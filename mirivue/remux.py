from .i18n import tr, trf
tr('Conservative all-track MKV copy. Never change or remove the source.')
import os, shutil, tempfile
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .persistence import probe, stream_command, verify_structure, packet_digest
from .extensions import fingerprint
from .file_moves import rename_noreplace, exists

def mkv_copy(source, target, cancelled=lambda: False, progress=lambda text: None):
    source = Path(source)
    target = Path(target)
    if source.is_symlink() or not source.is_file():
        raise ValueError(tr('Choisissez un fichier ordinaire.'))
    if exists(target):
        raise FileExistsError(tr('Ce nom existe déjà. Aucun remplacement effectué.'))
    initial = fingerprint(source)
    before = probe(source, cancelled)
    streams = before.get(tr('streams'), [])
    if not streams or any((s.get(tr('codec_name')) in (None, tr('none'), tr('unknown')) or s.get(tr('codec_type')) in (None, tr('data'), tr('unknown')) for s in streams)):
        raise ValueError(tr('Une piste est inconnue ou contient des données que cette copie MKV ne peut pas garantir de conserver. Aucune piste n’a été supprimée ; original conservé.'))
    if shutil.disk_usage(target.parent).free < source.stat().st_size + 16 * 1024 * 1024:
        raise ValueError(tr('Espace insuffisant pour la copie MKV.'))
    with tempfile.TemporaryDirectory(prefix=tr('.mirivue-mkv-'), dir=target.parent) as directory:
        temporary = Path(directory) / tr('copy.mkv')
        progress(tr('Copie de toutes les pistes, sans réencodage…'))
        stream_command([tr('ffmpeg'), tr('-v'), tr('error'), tr('-nostdin'), tr('-copyts'), tr('-protocol_whitelist'), tr('file'), tr('-i'), str(source), tr('-map'), tr('0'), tr('-map_metadata'), tr('0'), tr('-map_chapters'), tr('0'), tr('-c'), tr('copy'), tr('-copy_unknown'), tr('-avoid_negative_ts'), tr('disabled'), tr('-f'), tr('matroska'), str(temporary)], lambda data: None, cancelled)
        progress(tr('Contrôle des pistes et des données…'))
        after = probe(temporary, cancelled)
        import copy
        comparison = copy.deepcopy(before)
        for old, new in zip(comparison.get(tr('streams'), []), after.get(tr('streams'), [])):
            tags = old.get(tr('tags'), {})
            other = {k.lower(): v for k, v in new.get(tr('tags'), {}).items()}
            if tags.get(tr('language')) == tr('und') and tr('language') not in other:
                tags.pop(tr('language'))
        verify_structure(comparison, after, allow_timing_changes=True)
        if packet_digest(source, cancelled, include_timing=False) != packet_digest(temporary, cancelled, include_timing=False):
            raise ValueError(tr('Les données d’une piste ont changé. Copie refusée ; original conservé.'))
        if fingerprint(source) != initial:
            raise ValueError(tr('La source a changé pendant la copie ; recommencez.'))
        if cancelled():
            raise InterruptedError()
        shutil.copystat(source, temporary)
        with temporary.open(tr('rb')) as file:
            os.fsync(file.fileno())
        rename_noreplace(temporary, target)
    return target

class RemuxWorker(QThread):
    progress = Signal(str)

    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target
        self.error = ''
        self.success = False

    def run(self):
        try:
            mkv_copy(self.source, self.target, self.isInterruptionRequested, self.progress.emit)
            self.success = True
        except InterruptedError:
            self.error = tr('Copie annulée ; original conservé.')
        except Exception as error:
            self.error = str(error)

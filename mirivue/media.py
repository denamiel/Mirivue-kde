from .i18n import tr, trf
tr('Local media discovery, descriptive tags, and signature-validated technical cache.')
import hashlib, json, os, tempfile
from pathlib import Path
from .platform_services import services
from .metadata import Video, basic_entry, quantity, duration, number, probe_duration
from .extensions import fingerprint
from .diagnostics import record_tool_failure
AUDIO_EXT = set(tr('.mp3 .flac .ogg .oga .opus .wav .wave .aiff .aif .m4a .m4b .aac .wma .ape .wv .ac3 .a52 .mka').split())
IMAGE_EXT = set(tr('.jpg .jpeg .png .webp .gif .bmp .tif .tiff .avif .heic .heif .jxl .svg .psd .psb .dng .cr2 .cr3 .nef .arw .orf .rw2 .pef .raf').split())
LABELS = {tr('video'): tr('Vidéo'), tr('audio'): tr('Audio'), tr('image'): tr('Image'), tr('folder'): tr('Dossier'), tr('other'): tr('Autre fichier')}
FIELDS = {tr('title'): tr('Titre'), tr('artist'): tr('Artiste'), tr('album'): tr('Album'), tr('albumartist'): tr('Artiste de l’album'), tr('tracknumber'): tr('Piste'), tr('discnumber'): tr('Disque'), tr('date'): tr('Année / date'), tr('genre'): tr('Genre'), tr('composer'): tr('Compositeur'), tr('author'): tr('Auteur'), tr('copyright'): tr('Droits d’auteur'), tr('description'): tr('Description'), tr('keywords'): tr('Mots-clés'), tr('date_taken'): tr('Date de prise de vue')}
COLUMNS = {18: tr('title'), 19: tr('artist'), 20: tr('album'), 21: tr('tracknumber'), 22: tr('date'), 23: tr('genre'), 26: tr('date_taken'), 27: tr('keywords'), 28: tr('author'), 31: tr('albumartist'), 32: tr('discnumber'), 33: tr('composer'), 34: tr('copyright'), 35: tr('description')}

def kind(row):
    return row.media_type or (tr('folder') if row.is_dir else tr('video') if row.is_video else tr('other'))

def expected_kind(path):
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXT:
        return tr('image')
    if suffix in AUDIO_EXT:
        return tr('audio')
    from .metadata import EXTENSIONS
    return tr('video') if suffix in EXTENSIONS else tr('other')

def companion(path):
    return Path(str(path) + tr('.xmp'))

def companion_signature(path):
    try:
        return fingerprint(companion(path))
    except OSError:
        return None

def read_companion(path):
    from .media_tags import read_xmp
    return read_xmp(companion(path)) if companion(path).exists() else {}

def sync_columns(row):
    row.__post_init__()
    media = kind(row)
    if row.is_dir and row.total_duration is not None:
        row.values[2] = duration(row.total_duration)
        row.sort_values[2] = row.total_duration
    row.values[17] = row.sort_values[17] = LABELS[media]
    for column, key in COLUMNS.items():
        value = str(row.media_tags.get(key, ''))
        row.values[column] = value
        row.sort_values[column] = value.casefold()
    for column, key, units in [(24, tr('sample_rate'), [tr('Hz'), tr('kHz')]), (25, tr('bitrate'), [tr('bit/s'), tr('kbit/s'), tr('Mbit/s')])]:
        value = row.media_technical.get(key)
        row.values[column] = quantity(value, units, 1000) if value else ''
        row.sort_values[column] = value or -1
    row.values[29] = str(row.media_technical.get(tr('format'), row.container_info.get(tr('Format'), '')))
    row.sort_values[29] = row.values[29].casefold()
    bits = row.media_technical.get(tr('bits'))
    row.values[30] = str(bits) if bits else ''
    row.sort_values[30] = bits or -1
    row.values[36] = tr(' • ').join((trf('\x1f0\x1f \x1f1\x1f', v, LABELS[k].lower()) + (tr('s') if v != 1 else '') for k, v in row.media_counts.items()))
    row.sort_values[36] = sum(row.media_counts.values()) if row.media_counts else -1

def text_value(value):
    if isinstance(value, (list, tuple)):
        return tr('; ').join((str(v) for v in value))
    return str(value) if value is not None else ''

def audio_tags(path):
    import mutagen
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4
    file = mutagen.File(path)
    if file is None:
        return ({}, None)
    tags = {}
    raw = file.tags
    if isinstance(raw, ID3):
        ids = {tr('title'): tr('TIT2'), tr('artist'): tr('TPE1'), tr('album'): tr('TALB'), tr('albumartist'): tr('TPE2'), tr('tracknumber'): tr('TRCK'), tr('discnumber'): tr('TPOS'), tr('date'): tr('TDRC'), tr('genre'): tr('TCON'), tr('composer'): tr('TCOM'), tr('copyright'): tr('TCOP')}
        tags = {k: text_value(raw.get(v)) for k, v in ids.items() if raw.get(v)}
        comments = raw.getall(tr('COMM'))
        if comments:
            tags[tr('description')] = text_value(comments[0].text)
        for frame in raw.getall(tr('TXXX')):
            if frame.desc in (tr('Mirivue Keywords'), tr('MFM Keywords')):
                tags[tr('keywords')] = text_value(frame.text)
    elif isinstance(file, MP4):
        ids = {tr('title'): tr('©nam'), tr('artist'): tr('©ART'), tr('album'): tr('©alb'), tr('albumartist'): tr('aART'), tr('date'): tr('©day'), tr('genre'): tr('©gen'), tr('composer'): tr('©wrt'), tr('copyright'): tr('cprt'), tr('description'): tr('©cmt')}
        tags = {k: text_value(file.get(v)) for k, v in ids.items() if file.get(v)}
        for key, atom in [(tr('tracknumber'), tr('trkn')), (tr('discnumber'), tr('disk'))]:
            if file.get(atom):
                a, b = file[atom][0]
                tags[key] = str(a) + (trf('/\x1f0\x1f', b) if b else '')
        if file.get(tr('----:com.apple.iTunes:KEYWORDS')):
            tags[tr('keywords')] = bytes(file[tr('----:com.apple.iTunes:KEYWORDS')][0]).decode(tr('utf-8'), tr('replace'))
    elif raw:
        keys = {tr('title'): tr('title'), tr('artist'): tr('artist'), tr('album'): tr('album'), tr('albumartist'): tr('albumartist'), tr('tracknumber'): tr('tracknumber'), tr('discnumber'): tr('discnumber'), tr('date'): tr('date'), tr('genre'): tr('genre'), tr('composer'): tr('composer'), tr('copyright'): tr('copyright'), tr('description'): tr('description'), tr('keywords'): tr('keywords')}
        for key, tag in keys.items():
            if raw.get(tag):
                tags[key] = text_value(raw[tag])
    return (tags, file)

def cache_path(path):
    root = services.cache_directory() / tr('metadata')
    return root / (hashlib.sha256(str(path.absolute()).encode()).hexdigest() + tr('.json'))

def cached_media(path, signature=None, sidecar=None, cancelled=lambda: False):
    """Return validated metadata, repairing legacy audio caches with no duration."""
    from . import library
    signature = fingerprint(path) if signature is None else signature
    sidecar = companion_signature(path) if sidecar is None else sidecar
    cache = cache_path(path)
    try:
        data = json.loads(cache.read_text(encoding=tr('utf-8')))
        if data.get(tr('schema')) in (1, 2) and data.get(tr('signature')) == list(signature) and data.get(tr('sidecar')) == (list(sidecar) if sidecar else None):
            row = library.decode_row(data[tr('row')])
            if row.path == path and row.file_signature == signature and row.companion_signature == sidecar:
                if row.media_type == tr('audio') and row.sort_values[2] < 0 and not data.get(tr('duration_probe_attempted'), False):
                    try:
                        seconds = probe_duration(path, cancelled)
                        if seconds is not None:
                            row.values[2] = duration(seconds)
                            row.sort_values[2] = seconds
                    except InterruptedError:
                        raise
                    except (OSError, ValueError, TimeoutError, TypeError):
                        pass
                    save_media_cache(path, row, signature, sidecar)
                row.metadata_loaded = True
                sync_columns(row)
                return row
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None

def save_media_cache(path, row, signature=None, sidecar=None):
    from . import library
    signature = fingerprint(path) if signature is None else signature
    sidecar = companion_signature(path) if sidecar is None else sidecar
    cache = cache_path(path)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding=tr('utf-8'), dir=cache.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump({tr('schema'): 2, tr('signature'): signature, tr('sidecar'): sidecar,
                       tr('duration_probe_attempted'): True, tr('row'): library.encode_row(row)}, out, ensure_ascii=False)
        temporary.replace(cache)
    except (OSError, TypeError, ValueError) as error:
        record_tool_failure(tr('cache multimédia'), trf('\x1f0\x1f : \x1f1\x1f', cache, error))

def inspect_media(path, cancelled=lambda: False):
    from . import library
    if cancelled():
        raise InterruptedError()
    signature = fingerprint(path)
    sidecar = companion_signature(path)
    cache = cache_path(path)
    cached = cached_media(path, signature, sidecar, cancelled)
    if cached is not None:
        return cached
    row = basic_entry(path)
    row.media_type = tr('image') if path.suffix.lower() in IMAGE_EXT else tr('audio')
    if row.media_type == tr('image'):
        from PIL import Image, ExifTags
        try:
            with Image.open(path) as image:
                width, height = image.size
                exif = image.getexif()
                orientation = exif.get(274, 1)
                if orientation in (5, 6, 7, 8):
                    width, height = (height, width)
                row.media_technical = {tr('width'): width, tr('height'): height, tr('format'): image.format, tr('mode'): image.mode, tr('frames'): getattr(image, tr('n_frames'), 1)}
                row.media_tags = {key: str(exif[tag]) for key, tag in [(tr('description'), 270), (tr('author'), 315), (tr('copyright'), 33432)] if exif.get(tag)}
                for key, tag in [(tr('camera_make'), 271), (tr('camera_model'), 272)]:
                    if exif.get(tag):
                        row.media_technical[key] = str(exif[tag])
                try:
                    exif_ifd = exif.get_ifd(34665)
                    date = exif_ifd.get(36867)
                    for key, tag in [(tr('exposure'), 33434), (tr('aperture'), 33437), (tr('iso'), 34855), (tr('focal_length'), 37386)]:
                        if exif_ifd.get(tag) is not None:
                            row.media_technical[key] = str(exif_ifd[tag])
                except (KeyError, TypeError, ValueError):
                    date = None
                if date:
                    row.media_tags[tr('date_taken')] = str(date)
                for key, field in [(tr('Title'), tr('title')), (tr('Description'), tr('description')), (tr('Author'), tr('author'))]:
                    if image.info.get(key):
                        row.media_tags.setdefault(field, str(image.info[key]))
        except Exception:
            from PySide6.QtGui import QImageReader
            reader = QImageReader(str(path))
            size = reader.size()
            if not size.isValid():
                row.values[10] = tr('Format image non pris en charge')
                row.sort_values[10] = row.values[10]
                row.media_technical = {tr('format'): path.suffix.lstrip(tr('.')).upper()}
            else:
                row.media_technical = {tr('width'): size.width(), tr('height'): size.height(), tr('format'): bytes(reader.format()).decode()}
        if not row.media_technical.get(tr('width')):
            import shutil
            from .media_tags import exiftool_path
            if exiftool_path():
                from .media_tags import run_exif
                data = json.loads(run_exif([tr('-j'), tr('-n'), tr('-ImageWidth'), tr('-ImageHeight'), tr('-Orientation'), str(path.absolute())], cancelled))[0]
                width = number(data.get(tr('ImageWidth')))
                height = number(data.get(tr('ImageHeight')))
                if width and height:
                    if data.get(tr('Orientation')) in (5, 6, 7, 8):
                        width, height = (height, width)
                    row.media_technical.update(width=int(width), height=int(height))
                    row.values[10] = row.sort_values[10] = tr('OK')
        width = row.media_technical.get(tr('width'))
        height = row.media_technical.get(tr('height'))
        if width and height:
            row.values[3] = trf('\x1f0\x1f × \x1f1\x1f', width, height)
            row.sort_values[3] = width * height
        try:
            from .media_tags import embedded_image_tags
            row.media_tags.update(embedded_image_tags(path, cancelled))
        except (OSError, ValueError):
            pass
    else:
        tags, file = audio_tags(path)
        if file is None:
            from .persistence import capture
            info = capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-show_format'), tr('-show_streams'), tr('-of'), tr('json'), str(path)], cancelled)
            stream = next((s for s in info.get(tr('streams'), []) if s.get(tr('codec_type')) == tr('audio')), {})
            general = info.get(tr('format'), {})
            seconds = number(general.get(tr('duration'))) or number(stream.get(tr('duration')))
            row.media_technical = {tr('format'): stream.get(tr('codec_name'), ''), tr('sample_rate'): number(stream.get(tr('sample_rate'))), tr('bitrate'): number(stream.get(tr('bit_rate'), general.get(tr('bit_rate')))), tr('channels'): number(stream.get(tr('channels')))}
            tags = {k: text_value(v) for k, v in general.get(tr('tags'), {}).items() if k in FIELDS}
        else:
            info = file.info
            seconds = getattr(info, tr('length'), None)
            row.media_technical = {tr('format'): file.__class__.__name__, tr('sample_rate'): getattr(info, tr('sample_rate'), None), tr('bitrate'): getattr(info, tr('bitrate'), None), tr('channels'): getattr(info, tr('channels'), None), tr('bits'): getattr(info, tr('bits_per_sample'), None)}
        if number(seconds) is None or number(seconds) <= 0:
            try:
                seconds = probe_duration(path, cancelled)
            except InterruptedError:
                raise
            except (OSError, ValueError, TimeoutError, TypeError):
                pass
        if not row.media_technical.get(tr('sample_rate')):
            from .persistence import capture
            info = capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-select_streams'), tr('a:0'), tr('-show_entries'), tr('stream=sample_rate,bit_rate,codec_name'), tr('-of'), tr('json'), str(path)], cancelled)
            stream = next(iter(info.get(tr('streams'), [])), {})
            row.media_technical[tr('sample_rate')] = number(stream.get(tr('sample_rate')))
            if stream.get(tr('bit_rate')):
                row.media_technical[tr('bitrate')] = number(stream[tr('bit_rate')])
        row.media_tags = tags
        row.values[2] = duration(seconds)
        row.sort_values[2] = seconds if seconds is not None else -1
        row.values[8] = row.media_technical.get(tr('format'), '')
        row.sort_values[8] = row.values[8].casefold()
        channels = row.media_technical.get(tr('channels'))
        row.values[9] = str(int(channels)) if channels else ''
        row.sort_values[9] = channels or -1
    row.media_tags.update(read_companion(path))
    row.companion_signature = sidecar
    if row.values[10] == tr('Autre fichier'):
        row.values[10] = row.sort_values[10] = tr('OK')
    sync_columns(row)
    row.metadata_loaded = True
    if cancelled():
        raise InterruptedError()
    if fingerprint(path) == signature and companion_signature(path) == sidecar:
        save_media_cache(path, row, signature, sidecar)
    return row

def suggestions(row):
    tr('Conservative, local suggestions. Never invent an artist or capture date.')
    import re
    result = {}
    stem = row.path.stem
    if kind(row) == tr('audio'):
        pieces = [p.strip() for p in stem.split(tr(' - '))]
        if len(pieces) == 3 and pieces[0].isdigit():
            result.update(tracknumber=pieces[0], artist=pieces[1], title=pieces[2])
        elif len(pieces) == 2 and pieces[0].isdigit():
            result.update(tracknumber=pieces[0], title=pieces[1])
        elif len(pieces) == 2:
            result.update(artist=pieces[0], title=pieces[1])
        if row.path.parent.name:
            result[tr('album')] = row.path.parent.name
    result.setdefault(tr('title'), stem)
    return {k: v for k, v in result.items() if v and (not row.media_tags.get(k))}

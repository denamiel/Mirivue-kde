from .i18n import tr, trf, configured_language
tr('MediaInfo JSON uses seconds, bytes and bits/second (not display strings).')
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib
import math
import tempfile
from fractions import Fraction
from PySide6.QtCore import QLocale
import subprocess
from .platform_services import services
from .extensions import suggest_extension, fingerprint
from .diagnostics import record_tool_failure
from .date_display import modification_text as _modification_text, normalized_date_format
EXTENSIONS = set(tr('.mkv .mp4 .m4v .avi .mov .webm .wmv .flv .mpg .mpeg .m2v .ts .mts .m2ts .vob .ogv .3gp .3g2 .divx .asf .mxf .rm .rmvb .f4v .qt').split())
HEADERS = [tr('Nom'), tr('Taille'), tr('Durée'), tr('Résolution'), tr('Codec vidéo'), tr('FPS'), tr('Débit vidéo'), tr('HDR/SDR'), tr('Codec audio'), tr('Canaux'), '', tr('Extension suggérée'), tr('Emplacement'), '', tr('Date de modification'), tr('Durée totale'), '', tr('Type de média'), tr('Titre'), tr('Artiste'), tr('Album'), tr('Piste'), tr('Année / date'), tr('Genre'), tr('Fréquence audio'), tr('Débit audio'), tr('Date de prise de vue'), tr('Mots-clés'), tr('Auteur'), tr('Format'), tr('Profondeur audio (bits)'), tr('Artiste de l’album'), tr('Disque'), tr('Compositeur'), tr('Droits d’auteur'), tr('Description'), '', tr('Emplacement d’origine'), tr('Date d’accès'), tr('Date de suppression')]

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None

def quantity(value, units, base):
    if value is None:
        return tr('—')
    if base == 1024 and len(units) > 1 and units[0] == tr('o'):
        formatted = services.format_bytes(value)
        if formatted is not None:
            return formatted
    locale = QLocale('en_US' if configured_language() == 'en' else 'fr_FR')
    for unit in units[:-1]:
        if value < base:
            displayed = locale.toString(round(value)) if unit == tr('o') else locale.toString(float(value), 'f', 1)
            return trf('\x1f0\x1f \x1f1\x1f', displayed, unit)
        value /= base
    return trf('\x1f0\x1f \x1f1\x1f', locale.toString(float(value), 'f', 1), units[-1])

def duration(value):
    if value is None:
        return tr('—')
    seconds = round(value)
    return trf('\x1f0\x1f:\x1f1\x1f:\x1f2\x1f', format(seconds // 3600, '02'), format(seconds // 60 % 60, '02'), format(seconds % 60, '02'))

def probe_duration(path, cancelled=lambda: False):
    """Read duration from the container or its first usable media stream."""
    from .persistence import capture
    document = capture([
        tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'),
        tr('-show_entries'), tr('format=duration:stream=codec_type,duration,duration_ts,time_base'),
        tr('-of'), tr('json'), str(Path(path).absolute()),
    ], cancelled)
    format_seconds = number(document.get(tr('format'), {}).get(tr('duration')))
    if format_seconds and format_seconds > 0:
        return format_seconds
    streams = document.get(tr('streams'), [])
    for preferred in (tr('video'), tr('audio')):
        for stream in streams:
            if stream.get(tr('codec_type')) != preferred:
                continue
            seconds = number(stream.get(tr('duration')))
            if seconds and seconds > 0:
                return seconds
            ticks = number(stream.get(tr('duration_ts')))
            base = stream.get(tr('time_base'))
            if ticks is not None and base:
                try:
                    seconds = ticks * float(Fraction(str(base)))
                    if math.isfinite(seconds) and seconds > 0:
                        return seconds
                except (ValueError, ZeroDivisionError):
                    pass
    return None

def cached_duration(path, cancelled=lambda: False):
    """Read and cache only the media duration, without loading full metadata."""
    path = Path(path)
    signature = fingerprint(path)
    key = hashlib.sha256(str(path.absolute()).encode(tr('utf-8'))).hexdigest()
    cache = services.cache_directory() / tr('media-durations') / (key + tr('.json'))
    try:
        data = json.loads(cache.read_text(encoding=tr('utf-8')))
        seconds = number(data.get(tr('seconds')))
        if data.get(tr('signature')) == list(signature):
            if seconds is not None and seconds > 0:
                return seconds
            if data.get(tr('attempted')):
                return None
    except (OSError, ValueError, TypeError):
        pass
    seconds = probe_duration(path, cancelled)
    if cancelled():
        raise InterruptedError()
    try:
        if fingerprint(path) == signature:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding=tr('utf-8'), dir=cache.parent, delete=False) as output:
                temporary = Path(output.name)
                json.dump({tr('signature'): signature, tr('seconds'): seconds, tr('attempted'): True}, output)
            temporary.replace(cache)
    except (OSError, TypeError, ValueError):
        pass
    return seconds

def _quick_metadata_cache_path(path):
    key = hashlib.sha256(str(Path(path).absolute()).encode('utf-8')).hexdigest()
    return services.cache_directory() / 'quick-media-metadata' / (key + '.json')

def _baloo_quick_metadata(path, cancelled=lambda: False):
    """Read already indexed technical properties without invoking extractors."""
    import shutil
    executable = shutil.which('balooshow6') or shutil.which('balooshow')
    if not executable or cancelled():
        return {}
    try:
        process = subprocess.Popen([executable, str(Path(path).absolute())], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        import time
        deadline = time.monotonic() + 2.0
        while process.poll() is None:
            if cancelled():
                process.terminate()
                raise InterruptedError()
            if time.monotonic() >= deadline:
                process.kill()
                return {}
            time.sleep(0.025)
        if process.returncode:
            return {}
        text = process.stdout.read().decode('utf-8', 'replace')
    except (OSError, ValueError):
        return {}
    properties = {}
    for line in text.splitlines():
        if ':' not in line:
            continue
        label, raw = (part.strip() for part in line.split(':', 1))
        key = label.casefold().replace(' ', '').replace('_', '')
        if key in ('duration', 'width', 'height', 'bitrate', 'framerate', 'samplerate', 'channels'):
            value = number(raw)
            if value is not None:
                properties[key] = value
        elif key in ('videocodec', 'audiocodec') and raw:
            properties[key] = raw
    result = {}
    if properties.get('duration', 0) > 0:
        result['duration'] = properties['duration']
    if properties.get('width', 0) > 0 and properties.get('height', 0) > 0:
        result['width'], result['height'] = int(properties['width']), int(properties['height'])
    for source, target in (('framerate', 'fps'), ('samplerate', 'sample_rate'), ('channels', 'channels')):
        if properties.get(source, 0) > 0:
            result[target] = properties[source]
    result.update({key: properties[key] for key in ('videocodec', 'audiocodec') if properties.get(key)})
    if properties.get('bitrate', 0) > 0:
        result['video_bitrate' if Path(path).suffix.casefold() in EXTENSIONS else 'audio_bitrate'] = properties['bitrate']
    return result

def _probe_quick_metadata(path, cancelled=lambda: False):
    """Probe only stream/container headers needed by visible technical columns."""
    from .persistence import capture
    document = capture([
        'ffprobe', '-v', 'error', '-protocol_whitelist', 'file',
        '-show_entries', 'format=duration,bit_rate:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,bit_rate,duration,duration_ts,time_base,channels,sample_rate',
        '-of', 'json', str(Path(path).absolute()),
    ], cancelled)
    result = {}
    streams = document.get('streams', [])
    video = next((stream for stream in streams if stream.get('codec_type') == 'video'), {})
    audio = next((stream for stream in streams if stream.get('codec_type') == 'audio'), {})
    general = document.get('format', {})
    seconds = number(general.get('duration'))
    if seconds is None or seconds <= 0:
        for stream in (video, audio):
            seconds = number(stream.get('duration'))
            if seconds and seconds > 0:
                break
            ticks, base = number(stream.get('duration_ts')), stream.get('time_base')
            if ticks is not None and base:
                try:
                    seconds = ticks * float(Fraction(str(base)))
                    if seconds > 0 and math.isfinite(seconds):
                        break
                except (ValueError, ZeroDivisionError):
                    seconds = None
        else:
            seconds = None
    if seconds and seconds > 0:
        result['duration'] = seconds
    width, height = number(video.get('width')), number(video.get('height'))
    if width and height:
        result['width'], result['height'] = int(width), int(height)
    if video.get('codec_name'):
        result['video_codec'] = str(video['codec_name'])
    rate = video.get('avg_frame_rate') or video.get('r_frame_rate')
    try:
        fps = float(Fraction(str(rate))) if rate and rate != '0/0' else None
        if fps and math.isfinite(fps):
            result['fps'] = fps
    except (ValueError, ZeroDivisionError):
        pass
    video_rate = number(video.get('bit_rate')) or number(general.get('bit_rate'))
    audio_rate = number(audio.get('bit_rate')) or (number(general.get('bit_rate')) if not video else None)
    if video_rate:
        result['video_bitrate'] = video_rate
    if audio_rate:
        result['audio_bitrate'] = audio_rate
    if audio.get('codec_name'):
        result['audio_codec'] = str(audio['codec_name'])
    for key in ('channels', 'sample_rate'):
        value = number(audio.get(key))
        if value:
            result[key] = value
    return result

def cached_quick_metadata(path, cancelled=lambda: False, *, consult_baloo=True):
    """Resolve duration/dimensions/rates via Baloo first, then a signature cache and a targeted probe."""
    path = Path(path)
    signature = fingerprint(path)
    cache = _quick_metadata_cache_path(path)
    cached, attempted, baloo_checked = {}, False, 0
    try:
        data = json.loads(cache.read_text(encoding='utf-8'))
        if data.get('signature') == list(signature):
            cached = data.get('values', {}) if isinstance(data.get('values'), dict) else {}
            attempted = bool(data.get('probe_attempted'))
            baloo_checked = number(data.get('baloo_checked')) or 0
    except (OSError, ValueError, TypeError):
        pass
    # Baloo is queried on each listing so a file indexed after its first open
    # can provide its metadata without running ffprobe again.
    result = dict(cached)
    import time
    if consult_baloo and time.time() - baloo_checked >= 86400:
        result.update(_baloo_quick_metadata(path, cancelled))
        baloo_checked = time.time()
    if cancelled():
        raise InterruptedError()
    if not attempted:
        suffix = path.suffix.casefold()
        if suffix in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif', '.heic', '.heif', '.jxl'):
            try:
                from PySide6.QtGui import QImageReader
                size = QImageReader(str(path)).size()
                if size.isValid():
                    result.setdefault('width', size.width())
                    result.setdefault('height', size.height())
            except (ImportError, OSError, RuntimeError):
                pass
        else:
            # Reuse successful cached values, probing only if requested fields
            # remain unavailable (e.g. the current file was not in Baloo yet).
            if suffix in EXTENSIONS:
                missing = (not result.get('duration') or not (result.get('width') and result.get('height'))
                           or not result.get('video_bitrate'))
            else:
                missing = not result.get('duration') or not result.get('audio_bitrate')
            if missing:
                try:
                    result.update({key: value for key, value in _probe_quick_metadata(path, cancelled).items() if value not in (None, '', 0)})
                except InterruptedError:
                    raise
                except (OSError, ValueError, TimeoutError, TypeError, KeyError):
                    pass
    if cancelled():
        raise InterruptedError()
    try:
        if fingerprint(path) == signature:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=cache.parent, delete=False) as output:
                temporary = Path(output.name)
                json.dump({'signature': signature, 'values': result, 'probe_attempted': True, 'baloo_checked': baloo_checked}, output)
            temporary.replace(cache)
    except (OSError, TypeError, ValueError):
        pass
    return result

def hdr_label(video):
    hdr = str(video.get(tr('HDR_Format'), ''))
    transfer = str(video.get(tr('transfer_characteristics'), '')).lower()
    if hdr:
        return hdr
    if tr('2084') in transfer or tr('pq') in transfer:
        return tr('HDR (PQ)')
    if tr('hlg') in transfer or tr('arib') in transfer:
        return tr('HDR (HLG)')
    if any((token in transfer for token in (tr('709'), tr('601'), tr('470'), tr('170m'), tr('240m'), tr('gamma'), tr('srgb'), tr('61966'), tr('2020')))):
        return tr('SDR')
    return tr('Indéterminé')

@dataclass
class Video:
    path: Path
    values: list = field(default_factory=list)
    sort_values: list = field(default_factory=list)
    error: str = ''
    bitrate_note: str = ''
    bitrate_error: str = ''
    validation_error: str = ''
    validation_status: str = ''
    duplicate_group: int = 0
    preview_dir: str = ''
    analysis_dates: dict = field(default_factory=dict)
    modified_ns: int | None = None
    accessed_ns: int | None = None
    deleted_ns: int | None = None
    # Legacy metadata API; personal rating controls and local notes are disabled.
    rating: int = 0
    rating_source: str = 'disabled'
    hdr_note: str = tr('Détection fondée sur les métadonnées de la première piste vidéo. Sans indication fiable, HDR ou SDR ne peut pas être confirmé.')
    suggested_extension: str = ''
    extension_note: str = ''
    file_signature: tuple | None = None
    bitrate_result: tuple | None = None
    bitrate_saved: bool = False
    original_bitrate: float | None = None
    total_duration: float | None = None
    duration_note: str = ''
    is_dir: bool = False
    is_video: bool = True
    container_info: dict = field(default_factory=dict)
    media_type: str = ''
    media_tags: dict = field(default_factory=dict)
    media_technical: dict = field(default_factory=dict)
    metadata_loaded: bool = False
    media_counts: dict = field(default_factory=dict)
    folder_size_note: str = ''
    companion_signature: tuple | None = None
    personal_label: str = ''
    personal_label_color: str = ''
    is_hidden: bool | None = None
    real_name: str = ''

    def __post_init__(self):
        if self.is_hidden is None:
            from .file_visibility import local_is_hidden, kio_is_hidden
            self.is_hidden = (local_is_hidden(self.path) if isinstance(self.path, Path)
                              else kio_is_hidden({'url': str(self.path)}))
        while len(self.values) < len(HEADERS):
            self.values.append('')
        while len(self.sort_values) < len(HEADERS):
            self.sort_values.append(-1)

def remote_entry(uri, name, is_dir=False, size=0, modified=0, mime='', accessed=0, original_path='', deleted='', local_path='', hidden=None, real_name=''):
    """Build a read-only row returned by the KIO listing backend."""
    from urllib.parse import urlparse
    from .locations import ARCHIVE_PROTOCOLS
    parsed = urlparse(str(uri))
    path = Path(uri) if parsed.scheme.casefold() in ARCHIVE_PROTOCOLS else uri
    row = Video(path, is_dir=is_dir, is_video=False, media_type=tr('folder') if is_dir else tr('other'), is_hidden=hidden, real_name=real_name)
    size_value = None if is_dir else int(size or 0)
    row.values = [name, quantity(size_value, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024)] + [''] * 8 + [tr('Dossier') if is_dir else mime or tr('Autre fichier'), '', '', '', '']
    row.sort_values = [name.casefold(), size_value or 0, -1, -1, '', -1, -1, '', '', -1, row.values[10], '', -1, -1, -1]
    row.modified_ns = int(modified or 0) * 1000000000 if modified else None
    row.__post_init__()
    from PySide6.QtCore import QDateTime, Qt, QUrl
    row.accessed_ns = int(accessed or 0) * 1000000000 or None
    deletion = QDateTime.fromString(str(deleted), Qt.DateFormat.ISODate)
    row.deleted_ns = deletion.toMSecsSinceEpoch() * 1000000 if deletion.isValid() else None
    location = original_path or local_path or QUrl(str(uri)).path()
    row.values[37] = str(Path(location).parent) if location else ''
    row.sort_values[37] = row.values[37]
    row.sort_values[14] = row.modified_ns or -1
    row.sort_values[38] = row.accessed_ns or -1
    row.sort_values[39] = row.deleted_ns or -1
    return row

def parse(path, document):
    tracks = document.get(tr('media'), {}).get(tr('track'), [])
    general = next((t for t in tracks if t.get(tr('@type')) == tr('General')), {})
    video = next((t for t in tracks if t.get(tr('@type')) == tr('Video')), None)
    audio = [t for t in tracks if t.get(tr('@type')) == tr('Audio')]
    if video is None:
        if any((t.get(tr('@type')) in (tr('Audio'), tr('Image')) for t in tracks)):
            from .media import inspect_media
            return inspect_media(path)
        raise ValueError(tr('Aucune piste vidéo reconnue'))
    size = number(general.get(tr('FileSize')))
    if size is None:
        size = path.stat().st_size
    size = int(size)
    seconds = number(video.get(tr('Duration'))) or number(general.get(tr('Duration')))
    width, height = (number(video.get(tr('Width'))), number(video.get(tr('Height'))))
    fps, bitrate = (number(video.get(tr('FrameRate'))), number(video.get(tr('BitRate'))))
    channels = [number(a.get(tr('Channels'))) for a in audio]
    values = [path.name, quantity(size, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024), duration(seconds), trf('\x1f0\x1f × \x1f1\x1f', int(width), int(height)) if width and height else tr('—'), video.get(tr('Format'), tr('—')), trf('\x1f0\x1f', format(fps, '.3f')).rstrip(tr('0')).rstrip(tr('.')) if fps is not None else tr('—'), quantity(bitrate, [tr('bit/s'), tr('kbit/s'), tr('Mbit/s'), tr('Gbit/s')], 1000), hdr_label(video), tr(' / ').join((a.get(tr('Format'), tr('Inconnu')) for a in audio)) or tr('Aucun'), tr(' / ').join((str(int(c)) if c is not None else tr('—') for c in channels)) or tr('—'), tr('OK')]
    sort = [path.name.casefold(), size, seconds, width * height if width and height else None, str(values[4]).casefold(), fps, bitrate, str(values[7]).casefold(), str(values[8]).casefold(), channels[0] if channels else None, tr('OK')]
    suggested, note = suggest_extension(general, path.suffix)
    label = suggested + (tr(' (correcte)') if path.suffix.lower() == suggested else tr(' (à corriger)')) if suggested else tr('Indéterminée')
    values.extend([label, '', '', ''])
    sort.extend([label.casefold(), -1, -1, -1])
    try:
        signature = fingerprint(path)
    except OSError:
        signature = None
    tags = {}
    for key, names in {tr('title'): (tr('Title'),), tr('description'): (tr('Description'),), tr('author'): (tr('Performer'), tr('Artist'), tr('WrittenBy')), tr('copyright'): (tr('Copyright'),), tr('keywords'): (tr('Keywords'),), tr('date_taken'): (tr('Recorded_Date'), tr('Date_Recorded'), tr('Date'))}.items():
        value = next((general.get(name) for name in names if general.get(name)), None)
        if value is not None:
            tags[key] = str(value)
    return Video(path, values, [v if v is not None else -1 for v in sort], suggested_extension=suggested, extension_note=note, file_signature=signature, original_bitrate=bitrate, container_info={k: general.get(k, '') for k in (tr('Format'), tr('Format_Profile'), tr('CodecID'))}, media_type=tr('video'), media_tags=tags, media_technical={tr('width'): width, tr('height'): height}, metadata_loaded=True)

def inspect(path, cancelled=lambda: False):
    tr('Poll the child so cancel/close never waits for a complete MediaInfo scan.')
    from .media import AUDIO_EXT, IMAGE_EXT, inspect_media, read_companion, companion_signature, sync_columns
    if path.suffix.lower() in AUDIO_EXT | IMAGE_EXT:
        return inspect_media(path, cancelled)
    signature = fingerprint(path)
    sidecar = companion_signature(path)
    embedded_setting = None
    if path.suffix.lower() == tr('.mkv'):
        # Embedded Matroska tags are authoritative; an XMP companion only
        # fills fields that are absent from the container.
        embedded_setting = True
    cache = _video_cache_path(path)
    cached = cached_video(path, signature, sidecar, embedded_setting, cancelled)
    if cached is not None:
        return cached
    from . import library
    import time
    process = subprocess.Popen([tr('mediainfo'), tr('--Output=JSON'), str(path.absolute())], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 30
    try:
        while True:
            if cancelled():
                raise InterruptedError()
            if time.monotonic() >= deadline:
                raise TimeoutError(tr('Analyse trop longue (30 secondes)'))
            try:
                output, error = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            message = error.decode(tr('utf-8'), tr('replace')).strip() or tr('MediaInfo a échoué')
            record_tool_failure(tr('mediainfo'), message)
            raise ValueError(message)
        row = parse(path, json.loads(output))
        if not row.is_video:
            return row
        if row.sort_values[2] < 0:
            try:
                seconds = probe_duration(path, cancelled)
                if seconds is not None:
                    row.values[2] = duration(seconds)
                    row.sort_values[2] = seconds
            except InterruptedError:
                raise
            except (OSError, ValueError, TimeoutError, TypeError):
                pass
        row.media_type = tr('video')
        try:
            from .media import audio_tags
            row.media_tags.update(audio_tags(path)[0])
        except Exception as error:
            record_tool_failure(tr('métadonnées audio'), trf('\x1f0\x1f : \x1f1\x1f', path, error))
        sidecar_tags = read_companion(path)
        if path.suffix.lower() == tr('.mkv'):
            if embedded_setting:
                for key, value in sidecar_tags.items():
                    row.media_tags.setdefault(key, value)
            else:
                row.media_tags.update(sidecar_tags)
        else:
            row.media_tags.update(sidecar_tags)
        row.companion_signature = sidecar
        sync_columns(row)
        from .persistence import read_saved, capture
        import shutil
        try:
            saved = read_saved(path, cancelled)
            if saved:
                rate, seconds, packets, clock = saved
                row.bitrate_result = saved
                row.bitrate_saved = True
                row.original_bitrate = rate
                row.sort_values[6] = rate
                row.values[6] = quantity(rate, [tr('bit/s'), tr('kbit/s'), tr('Mbit/s'), tr('Gbit/s')], 1000)
                row.values[10] = row.sort_values[10] = tr('Débit enregistré')
                row.bitrate_note = trf('Débit calculé relu dans les métadonnées du fichier : \x1f0\x1f paquets / \x1f1\x1f s (\x1f2\x1f).', packets, format(seconds, '.6f'), clock)
        except InterruptedError:
            raise
        except Exception as error:
            row.bitrate_note = trf('Lecture du débit enregistré indisponible : \x1f0\x1f', error)
        if row.values[7] == tr('Indéterminé') and shutil.which(tr('ffprobe')):
            try:
                document = capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-select_streams'), tr('v:0'), tr('-show_streams'), tr('-of'), tr('json'), str(path)], cancelled)
                streams = document.get(tr('streams'), [])
                if streams:
                    row.values[7] = hdr_from_probe(streams[0])
                    row.sort_values[7] = row.values[7].casefold()
                    if row.values[7] != tr('Indéterminé'):
                        row.hdr_note = tr('Identifié à partir des métadonnées de la première piste vidéo lues par FFprobe.')
            except InterruptedError:
                raise
            except Exception as error:
                row.hdr_note += trf(' Lecture complémentaire indisponible : \x1f0\x1f', error)
        if not cancelled() and row.file_signature == signature and row.companion_signature == sidecar:
            _save_video_cache(cache, row, signature, sidecar, embedded_setting)
        return row
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()

def _video_cache_path(path):
    return services.cache_directory() / tr('video-metadata') / (hashlib.sha256(str(path.absolute()).encode()).hexdigest() + tr('.json'))

def cached_video(path, signature=None, sidecar=None, embedded_setting=None, cancelled=lambda: False):
    """Return validated metadata, repairing legacy cache entries with no duration."""
    signature = fingerprint(path) if signature is None else signature
    from .media import companion_signature, sync_columns
    sidecar = companion_signature(path) if sidecar is None else sidecar
    if embedded_setting is None and path.suffix.lower() == tr('.mkv'):
        embedded_setting = True
    try:
        data = json.loads(_video_cache_path(path).read_text(encoding=tr('utf-8')))
        if (data.get(tr('schema')) in (1, 2) and data.get(tr('signature')) == list(signature)
                and data.get(tr('sidecar')) == (list(sidecar) if sidecar else None)
                and data.get(tr('embedded')) == embedded_setting):
            from . import library
            row = library.decode_row(data[tr('row')])
            if row.path == path and row.media_type == tr('video') and row.file_signature == signature and row.companion_signature == sidecar:
                if row.sort_values[2] < 0 and not data.get(tr('duration_probe_attempted'), False):
                    try:
                        seconds = probe_duration(path, cancelled)
                        if seconds is not None:
                            row.values[2] = duration(seconds)
                            row.sort_values[2] = seconds
                    except InterruptedError:
                        raise
                    except (OSError, ValueError, TimeoutError, TypeError):
                        pass
                    _save_video_cache(_video_cache_path(path), row, signature, sidecar, embedded_setting)
                row.metadata_loaded = True
                sync_columns(row)
                return row
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None

def _save_video_cache(cache, row, signature, sidecar, embedded_setting):
    from . import library
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding=tr('utf-8'), dir=cache.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump({tr('schema'): 2, tr('signature'): signature, tr('sidecar'): sidecar,
                       tr('duration_probe_attempted'): True,
                       tr('embedded'): embedded_setting, tr('row'): library.encode_row(row)}, output, ensure_ascii=False)
        temporary.replace(cache)
    except (OSError, TypeError, ValueError):
        pass

def failed(path, error):
    return Video(path, [path.name] + [tr('—')] * 9 + [tr('Erreur'), tr('Indéterminée'), '', '', ''], [path.name.casefold(), -1, -1, -1, '', -1, -1, '', '', -1, tr('Erreur'), tr('indéterminée'), -1, -1, -1], str(error), metadata_loaded=True)

def basic_entry(path, is_dir=False, *, hidden=None):
    row = Video(path, is_dir=is_dir, is_video=False, media_type=tr('folder') if is_dir else tr('other'), is_hidden=hidden)
    size = None if is_dir else path.stat().st_size
    row.values = [path.name, quantity(size, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024)] + [''] * 8 + [tr('Dossier') if is_dir else tr('Autre fichier'), '', '', '', '']
    row.sort_values = [path.name.casefold(), size or 0, -1, -1, '', -1, -1, '', '', -1, row.values[10], '', -1, -1, -1]
    row.file_signature = fingerprint(path)
    row.__post_init__()
    update_modification(row)
    return row

def hdr_from_probe(stream):
    side = stream.get(tr('side_data_list'), [])
    if any((tr('dovi') in str(item.get(tr('side_data_type'), '')).lower() or tr('dolby vision') in str(item.get(tr('side_data_type'), '')).lower() for item in side)):
        return tr('Dolby Vision')
    transfer = str(stream.get(tr('color_transfer'), '')).lower()
    if transfer == tr('smpte2084'):
        return tr('HDR (PQ)')
    if transfer == tr('arib-std-b67'):
        return tr('HDR (HLG)')
    if transfer in (tr('bt709'), tr('gamma22'), tr('gamma28'), tr('smpte170m'), tr('smpte240m'), tr('iec61966-2-1'), tr('bt2020-10'), tr('bt2020-12')):
        return tr('SDR')
    return tr('Indéterminé')

def modification_text(timestamp_ns, now=None, mode='locale'):
    return _modification_text(timestamp_ns, now=now, mode=mode, translate=tr)

def update_modification(row):
    while len(row.values) < len(HEADERS):
        row.values.append('')
    while len(row.sort_values) < len(HEADERS):
        row.sort_values.append(-1)
    try:
        info = row.path.stat()
        row.modified_ns = info.st_mtime_ns
        row.accessed_ns = info.st_atime_ns
    except OSError:
        row.modified_ns = None
    row.values[14] = modification_text(row.modified_ns)
    row.sort_values[14] = row.modified_ns if row.modified_ns is not None else -1
    row.sort_values[38] = row.accessed_ns or -1
    row.values[37] = str(row.path.parent)
    row.sort_values[37] = row.values[37]

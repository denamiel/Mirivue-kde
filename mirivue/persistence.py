from .i18n import tr, trf
tr('Native container tags, validated stream copy, and an original-file backup.')
import re
import uuid
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import threading
import shutil
import stat
import subprocess
import tempfile
from .atomic_io import durable_replace, fsync_directory
from .backup_policy import reserve_backup, record_backup, discard_new_backup
import time
import xml.etree.ElementTree as ET
from .extensions import fingerprint
from .diagnostics import record_tool_failure
TAG = tr('VIDEOINFOTABLE_BITRATE_V1')
MARKER = tr('Mirivue-bitrate-v1:')
LEGACY_MARKER = tr('MFM-bitrate-v1:')

def stream_command(command, callback, cancelled=lambda: False, timeout=None):
    tr('Run a media tool without relying on Unix-only pipe selectors.\n\n    Two small readers make the same cancellation and bounded-output behaviour\n    available on Windows, macOS and Linux.\n    ')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    events = queue.Queue()

    def read_stream(stream, channel):
        try:
            while True:
                data = stream.read(65536)
                if not data:
                    break
                events.put((channel, data))
        finally:
            events.put((channel, None))
    readers = [threading.Thread(target=read_stream, args=(process.stdout, tr('out')), daemon=True), threading.Thread(target=read_stream, args=(process.stderr, tr('err')), daemon=True)]
    for reader in readers:
        reader.start()
    started = time.monotonic()
    error = b''
    closed = set()
    try:
        while len(closed) < 2 or process.poll() is None:
            if cancelled():
                raise InterruptedError()
            if timeout and time.monotonic() - started > timeout:
                raise TimeoutError(tr('Lecture des métadonnées trop longue'))
            try:
                channel, data = events.get(timeout=0.1)
            except queue.Empty:
                continue
            if data is None:
                closed.add(channel)
            elif channel == tr('out'):
                callback(data)
            else:
                error = (error + data)[:16384]
        if cancelled():
            raise InterruptedError()
        if process.returncode or error.strip():
            message = error.decode(tr('utf-8'), tr('replace')).strip() or tr('Échec de l’outil vidéo')
            record_tool_failure(command[0] if command else tr('outil vidéo'), message)
            raise ValueError(message)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()

def capture(command, cancelled=lambda: False):
    parts = []
    size = 0

    def add(data):
        nonlocal size
        size += len(data)
        if size > 32 * 1024 * 1024:
            raise ValueError(tr('Métadonnées trop volumineuses'))
        parts.append(data)
    stream_command(command, add, cancelled, timeout=30)
    return json.loads(b''.join(parts))

def probe(path, cancelled=lambda: False):
    return capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-show_format'), tr('-show_streams'), tr('-show_chapters'), tr('-show_data_hash'), tr('sha256'), tr('-of'), tr('json'), str(path)], cancelled)

def decode_saved(tags):
    normalized = {key.upper(): value for key, value in tags.items()}
    value = normalized.get(TAG)
    if value is None:
        comment = normalized.get(tr('COMMENT'), '')
        for line in str(comment).splitlines():
            for marker in (MARKER, LEGACY_MARKER):
                if line.startswith(marker):
                    value = line[len(marker):]
                    break
            if value is not None:
                break
    if not isinstance(value, str) or len(value) > 16384:
        return None
    try:
        data = json.loads(value)
        result = data[tr('result')]
        rate, seconds, packets, clock = result
        if data.get(tr('version')) != 1 or clock not in (tr('pts_time'), tr('dts_time')) or (not all((isinstance(x, (int, float)) and math.isfinite(x) and (x > 0) for x in (rate, seconds, packets)))) or (int(packets) != packets):
            return None
        return (rate, seconds, int(packets), clock)
    except (ValueError, TypeError, KeyError):
        return None

def read_saved(path, cancelled=lambda: False):
    if not shutil.which(tr('ffprobe')):
        return None
    document = capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-show_entries'), tr('format_tags'), tr('-of'), tr('json'), str(path)], cancelled)
    return decode_saved(document.get(tr('format'), {}).get(tr('tags'), {}))

def packet_digest(path, cancelled=lambda: False, include_timing=True):
    pending = b''
    streams = {}

    def add(data):
        nonlocal pending
        pending += data
        lines = pending.split(b'\n')
        pending = lines.pop()
        if len(pending) > 131072:
            raise ValueError(tr('Paquet de contrôle inattendu'))
        for line in lines:
            if cancelled():
                raise InterruptedError()
            if not line.startswith(b'packet|'):
                continue
            fields = dict((part.split(b'=', 1) for part in line.split(b'|')[1:] if b'=' in part))
            index = fields[b'stream_index']
            digest, count = streams.setdefault(index, (hashlib.sha256(), 0))
            if b'data_hash' not in fields:
                raise ValueError(tr('Empreinte de paquet absente'))
            values = [fields[b'size'], fields[b'data_hash']]
            if include_timing:
                for key in (b'pts_time', b'dts_time', b'duration_time'):
                    value = fields.get(key, b'N/A')
                    try:
                        value = str(round(float(value), 3)).encode()
                    except ValueError:
                        pass
                    values.append(value)
            digest.update(b'|'.join(values) + b'\n')
            streams[index] = (digest, count + 1)
    stream_command([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-show_packets'), tr('-show_data_hash'), tr('sha256'), tr('-show_entries'), tr('packet=stream_index,size,data_hash,pts_time,dts_time,duration_time'), tr('-of'), tr('compact=p=1:nk=0'), str(path)], add, cancelled)
    if pending.strip():
        add(b'\n')
    if not streams:
        raise ValueError(tr('Aucune piste contrôlable'))
    return {key: (digest.hexdigest(), count) for key, (digest, count) in streams.items()}

def verify_structure(before, after, allow_timing_changes=False):
    old, new = (before.get(tr('streams'), []), after.get(tr('streams'), []))
    if len(old) != len(new):
        raise ValueError(tr('Le nombre de pistes a changé ; original conservé'))
    keys = (tr('codec_type'), tr('codec_name'), tr('width'), tr('height'), tr('pix_fmt'), tr('sample_rate'), tr('channels'), tr('channel_layout'), tr('extradata_hash'), tr('side_data_list'))
    ignored = {tr('encoder'), tr('duration'), tr('bps'), tr('number_of_bytes'), tr('number_of_frames'), tr('_statistics_writing_app'), tr('_statistics_writing_date_utc'), tr('_statistics_tags')}
    for a, b in zip(old, new):
        if any((a.get(k) != b.get(k) for k in keys)):
            raise ValueError(tr('Les caractéristiques d’une piste ont changé ; original conservé'))
        if a.get(tr('disposition'), {}) != b.get(tr('disposition'), {}):
            raise ValueError(tr('Les dispositions des pistes ont changé ; original conservé'))
        after_tags = {k.lower(): v for k, v in b.get(tr('tags'), {}).items()}
        for key, value in a.get(tr('tags'), {}).items():
            if key.lower() not in ignored and after_tags.get(key.lower()) != value:
                raise ValueError(trf('Métadonnée de piste non conservée : \x1f0\x1f', key))

    def chapters(document):
        if allow_timing_changes:
            return [c.get(tr('tags'), {}) for c in document.get(tr('chapters'), [])]
        return [(round(float(c[tr('start_time')]), 3), round(float(c[tr('end_time')]), 3), c.get(tr('tags'), {})) for c in document.get(tr('chapters'), [])]
    if chapters(before) != chapters(after):
        raise ValueError(tr('Les chapitres ont changé ; original conservé'))
    after_tags = {k.lower(): v for k, v in after.get(tr('format'), {}).get(tr('tags'), {}).items()}
    for key, value in before.get(tr('format'), {}).get(tr('tags'), {}).items():
        if key.lower() in {tr('encoder'), TAG.lower(), tr('major_brand'), tr('minor_version'), tr('compatible_brands')}:
            continue
        actual = after_tags.get(key.lower(), '')
        if key.lower() == tr('comment'):
            clean = lambda text: tr('\n').join((line for line in str(text).splitlines() if not line.startswith(MARKER)))
            if clean(actual) == clean(value):
                continue
        if actual != value:
            raise ValueError(trf('Métadonnée globale non conservée : \x1f0\x1f', key))

def parse_mkv_tags(data):
    prefix = tr('Mirivue_XML_') + uuid.uuid4().hex + tr('_')
    while prefix.encode() in data:
        prefix = tr('Mirivue_XML_') + uuid.uuid4().hex + tr('_')
    references = {}

    def protect(match):
        token = match.group(1)
        value = int(token[1:], 16) if token[:1].lower() == b'x' else int(token)
        valid = value in (9, 10, 13) or 32 <= value <= 55295 or 57344 <= value <= 65533 or (65536 <= value <= 1114111)
        if valid:
            return match.group(0)
        key = (prefix + str(len(references))).encode()
        references[key] = match.group(0)
        return key
    protected = re.sub(b'&#(x[0-9a-fA-F]+|[0-9]+);', protect, data)
    try:
        root = ET.fromstring(protected)
    except ET.ParseError as error:
        raise ValueError(trf('Métadonnées MKV illisibles (\x1f0\x1f) ; original conservé', error)) from error
    return (root, references)

def serialize_mkv_tags(document, references):
    data = ET.tostring(document, encoding=tr('utf-8'), xml_declaration=True)
    for key in sorted(references, key=len, reverse=True):
        data = data.replace(key, references[key])
    return data

def native_matroska(path, temporary, value, cancelled):
    if not shutil.which(tr('mkvpropedit')) or not shutil.which(tr('mkvextract')):
        raise ValueError(tr('MKVToolNix manque : relancez Installer.sh de Mirivue pour activer l’enregistrement MKV sans réécriture des pistes.'))
    with path.open(tr('rb')) as source, temporary.open(tr('wb')) as destination:
        while True:
            if cancelled():
                raise InterruptedError()
            chunk = source.read(4 * 1024 * 1024)
            if not chunk:
                break
            destination.write(chunk)
    parts = []
    length = 0

    def collect(data):
        nonlocal length
        length += len(data)
        if length > 32 * 1024 * 1024:
            raise ValueError(tr('Métadonnées MKV trop volumineuses ; original conservé'))
        parts.append(data)
    stream_command([tr('mkvextract'), str(temporary), tr('tags')], collect, cancelled)
    document, references = parse_mkv_tags(b''.join(parts))
    if document.tag != tr('Tags'):
        raise ValueError(tr('Métadonnées MKV non reconnues ; original conservé'))
    for tag in document.findall(tr('Tag')):
        targets = tag.find(tr('Targets'))
        if targets is not None and any((targets.find(k) is not None for k in (tr('TrackUID'), tr('ChapterUID'), tr('AttachmentUID'), tr('EditionUID')))):
            continue
        for simple in list(tag.findall(tr('Simple'))):
            if simple.findtext(tr('Name'), '').upper() == TAG:
                tag.remove(simple)
        if not tag.findall(tr('Simple')):
            document.remove(tag)
    tag = ET.SubElement(document, tr('Tag'))
    ET.SubElement(tag, tr('Targets'))
    simple = ET.SubElement(tag, tr('Simple'))
    ET.SubElement(simple, tr('Name')).text = TAG
    ET.SubElement(simple, tr('String')).text = value
    with tempfile.TemporaryDirectory(prefix=tr('mirivue-tags-')) as directory:
        xml = Path(directory) / tr('tags.xml')
        xml.write_bytes(serialize_mkv_tags(document, references))
        stream_command([tr('mkvpropedit'), str(temporary), tr('--tags'), tr('all:') + str(xml)], lambda data: None, cancelled)

def persist(path, result, cancelled=lambda: False, progress=lambda message: None, expected=None):
    path = Path(path).absolute()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(tr('Écriture réservée aux fichiers ordinaires sans liens supplémentaires'))
    initial = fingerprint(path)
    if expected is not None and expected != initial:
        raise ValueError(tr('Le fichier a changé depuis le calcul ; original conservé'))
    before = probe(path, cancelled)
    media = capture([tr('mediainfo'), tr('--Output=JSON'), str(path)], cancelled)
    general = next((t for t in media[tr('media')][tr('track')] if t.get(tr('@type')) == tr('General')))
    fmt = general.get(tr('Format'), '')
    muxer = {tr('Matroska'): tr('matroska'), tr('WebM'): tr('webm'), tr('AVI'): tr('avi')}.get(fmt)
    if fmt == tr('MPEG-4'):
        brand = general.get(tr('CodecID'), '').strip().lower()
        if brand.startswith((tr('3g'), tr('mjp'))):
            raise ValueError(tr('Intégration non prise en charge pour ce conteneur spécialisé'))
        muxer = tr('mov') if brand == tr('qt') or tr('QuickTime') in general.get(tr('Format_Profile'), '') else tr('mp4')
    if muxer is None:
        raise ValueError(trf('Intégration non prise en charge pour le conteneur \x1f0\x1f', fmt))
    if shutil.disk_usage(path.parent).free < info.st_size + 16 * 1024 * 1024:
        raise ValueError(tr('Espace insuffisant pour préparer la copie vidéo'))
    value = json.dumps({tr('version'): 1, tr('result'): list(result)}, separators=(tr(','), tr(':')), allow_nan=False)
    if decode_saved({TAG: value}) is None:
        raise ValueError(tr('Débit calculé invalide'))
    fd, temporary = tempfile.mkstemp(prefix=tr('.mirivue-'), suffix=tr('.tmp'), dir=path.parent)
    os.close(fd)
    temporary = Path(temporary)
    backup = None
    backup_created = False
    committed = False
    try:
        progress(tr('Vérification des pistes de l’original…'))
        original_digest = packet_digest(path, cancelled)
        if muxer == tr('matroska'):
            progress(tr('Copie puis écriture des balises MKV, sans réécriture des pistes…'))
            native_matroska(path, temporary, value, cancelled)
        else:
            progress(tr('Écriture des métadonnées dans une copie, sans réencodage…'))
            command = [tr('ffmpeg'), tr('-v'), tr('error'), tr('-nostdin'), tr('-y'), tr('-copyts'), tr('-protocol_whitelist'), tr('file'), tr('-i'), str(path), tr('-map'), tr('0'), tr('-map_metadata'), tr('0'), tr('-map_chapters'), tr('0'), tr('-c'), tr('copy'), tr('-copy_unknown'), tr('-avoid_negative_ts'), tr('disabled')]
            if muxer == tr('avi'):
                tags = before.get(tr('format'), {}).get(tr('tags'), {})
                comment = next((v for k, v in tags.items() if k.lower() == tr('comment')), '')
                comment = tr('\n').join((line for line in comment.splitlines() if not line.startswith(MARKER)))
                command += [tr('-metadata'), tr('comment=') + (comment + tr('\n') if comment else '') + MARKER + value]
            else:
                command += [tr('-metadata'), TAG + tr('=') + value]
            if muxer in (tr('mp4'), tr('mov')):
                command += [tr('-movflags'), tr('use_metadata_tags')]
            command += [tr('-f'), muxer, str(temporary)]
            stream_command(command, lambda data: None, cancelled)
        progress(tr('Validation de la copie et des métadonnées…'))
        after = probe(temporary, cancelled)
        verify_structure(before, after)
        if decode_saved(after.get(tr('format'), {}).get(tr('tags'), {})) != tuple(result):
            raise ValueError(tr('Les métadonnées calculées n’ont pas été enregistrées correctement'))
        if original_digest != packet_digest(temporary, cancelled):
            raise ValueError(tr('Les données ou horodatages des pistes ont changé ; original conservé'))
        if fingerprint(path) != initial:
            raise ValueError(tr('Le fichier a changé pendant l’écriture ; original conservé'))
        shutil.copystat(path, temporary)
        with temporary.open(tr('rb')) as file:
            os.fsync(file.fileno())
        if cancelled():
            raise InterruptedError()
        backup, backup_created = reserve_backup(path)
        if fingerprint(path) != initial:
            raise ValueError(tr('Le fichier a changé avant remplacement ; original conservé'))
        fsync_directory(path.parent)
        durable_replace(temporary, path)
        committed = True
        record_backup(path, backup)
        return str(backup)
    finally:
        if temporary.exists():
            temporary.unlink()
        if backup is not None and (not committed):
            discard_new_backup(path, backup, backup_created)

from .i18n import tr, trf
tr('Metadata-only editing with explicit destinations, backups and atomic publication.')
import base64, errno, os, shutil, subprocess, tempfile, uuid, json
from .atomic_io import durable_replace, fsync_directory
from .backup_policy import reserve_backup, record_backup, discard_new_backup
from pathlib import Path
import xml.etree.ElementTree as ET
from PySide6.QtCore import QThread, Signal
from .extensions import fingerprint
from .platform_services import services
from .diagnostics import record_tool_failure
NS = {tr('x'): tr('adobe:ns:meta/'), tr('rdf'): tr('http://www.w3.org/1999/02/22-rdf-syntax-ns#'), tr('dc'): tr('http://purl.org/dc/elements/1.1/'), tr('xmp'): tr('http://ns.adobe.com/xap/1.0/'), tr('exif'): tr('http://ns.adobe.com/exif/1.0/'), tr('mfm'): tr('https://mfm.local/metadata/1.0/')}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
XMP_KEYS = {tr('title'): (tr('dc'), tr('title')), tr('description'): (tr('dc'), tr('description')), tr('author'): (tr('dc'), tr('creator')), tr('copyright'): (tr('dc'), tr('rights')), tr('keywords'): (tr('dc'), tr('subject')), tr('date_taken'): (tr('exif'), tr('DateTimeOriginal')), tr('rating'): (tr('xmp'), tr('Rating'))}

def q(prefix, name):
    return tr('{') + NS[prefix] + tr('}') + name

def xml_root(data):
    if len(data) > 8 * 1024 * 1024 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError(tr('Le fichier XMP contient une structure non prise en charge.'))
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(tr('Le fichier XMP existant est illisible ; il ne sera pas remplacé.')) from error

def read_xmp(path):
    with Path(path).open(tr('rb')) as stream:
        root = xml_root(stream.read(8 * 1024 * 1024 + 1))
    result = {}
    from .media import FIELDS
    for key in [*FIELDS, tr('rating')]:
        prefix, name = XMP_KEYS.get(key, (tr('mfm'), key))
        tag = q(prefix, name)
        node = root.find(tr('.//') + tag)
        if node is not None:
            items = node.findall(tr('.//') + q(tr('rdf'), tr('li')))
            result[key] = tr('; ').join((''.join(item.itertext()) for item in items)) if items else ''.join(node.itertext())
        else:
            for description in root.iter(q(tr('rdf'), tr('Description'))):
                if tag in description.attrib:
                    result[key] = description.attrib[tag]
                    break
    if tr('rating') in result:
        try:
            result[tr('rating')] = str(max(0, min(4, round(float(result[tr('rating')]) * 4 / 5))))
        except ValueError:
            result.pop(tr('rating'), None)
    return result

def write_xmp(path, changes):
    path = Path(path)
    if path.exists():
        root = xml_root(path.read_bytes())
    else:
        root = ET.Element(q(tr('x'), tr('xmpmeta')))
        rdf = ET.SubElement(root, q(tr('rdf'), tr('RDF')))
        ET.SubElement(rdf, q(tr('rdf'), tr('Description')), {q(tr('rdf'), tr('about')): ''})
    descriptions = list(root.iter(q(tr('rdf'), tr('Description'))))
    if not descriptions:
        raise ValueError(tr('La structure XMP ne contient pas de description modifiable.'))
    target = descriptions[0]
    for key, value in changes.items():
        if key == tr('cover'):
            raise ValueError(tr('La pochette doit être intégrée à un format audio compatible.'))
        prefix, name = XMP_KEYS.get(key, (tr('mfm'), key))
        tag = q(prefix, name)
        for description in descriptions:
            description.attrib.pop(tag, None)
            for child in list(description):
                if child.tag == tag:
                    description.remove(child)
        element = ET.SubElement(target, tag)
        if key in (tr('title'), tr('description'), tr('copyright')):
            alt = ET.SubElement(element, q(tr('rdf'), tr('Alt')))
            ET.SubElement(alt, q(tr('rdf'), tr('li')), {tr('{http://www.w3.org/XML/1998/namespace}lang'): tr('x-default')}).text = str(value)
        elif key in (tr('author'), tr('keywords')):
            group = ET.SubElement(element, q(tr('rdf'), tr('Seq') if key == tr('author') else tr('Bag')))
            for part in str(value).split(tr(';')):
                ET.SubElement(group, q(tr('rdf'), tr('li'))).text = part.strip()
        else:
            element.text = str(round(int(value) * 5 / 4)) if key == tr('rating') else str(value)
    ET.ElementTree(root).write(path, encoding=tr('utf-8'), xml_declaration=True)
EXIF = {tr('title'): tr('XMP-dc:Title'), tr('description'): tr('XMP-dc:Description'), tr('author'): tr('XMP-dc:Creator'), tr('copyright'): tr('XMP-dc:Rights'), tr('keywords'): tr('XMP-dc:Subject'), tr('date_taken'): tr('EXIF:DateTimeOriginal')}

def exiftool_path():
    return services.tool_path(tr('exiftool')) or (tr('/usr/bin/vendor_perl/exiftool') if services.name == tr('linux') and Path(tr('/usr/bin/vendor_perl/exiftool')).is_file() else None)

def run_exif(args, cancelled=lambda: False):
    tool = exiftool_path()
    if not tool:
        raise ValueError(tr('ExifTool est absent. Relancez l’installateur pour l’ajouter.'))
    process = subprocess.Popen([tool, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        import time
        deadline = time.monotonic() + 60
        while True:
            if cancelled():
                raise InterruptedError()
            if time.monotonic() > deadline:
                raise ValueError(tr('L’outil de métadonnées n’a pas répondu dans le délai prévu.'))
            try:
                out, err = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            message = tr('ExifTool n’a pas pu enregistrer les informations : ') + err.decode(tr('utf-8'), tr('replace'))[:1500]
            record_tool_failure(tr('exiftool'), message)
            raise ValueError(message)
        return out
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

def embedded_image_tags(path, cancelled=lambda: False):
    if not exiftool_path():
        return {}
    data = json.loads(run_exif([tr('-j'), tr('-s'), *[tr('-') + v for v in EXIF.values()], str(Path(path).absolute())], cancelled))[0]
    result = {}
    for key, name in EXIF.items():
        value = data.get(name.split(tr(':'))[-1])
        if value is not None:
            result[key] = tr('; ').join(map(str, value)) if isinstance(value, list) else str(value)
    return result

def native_route(row, force_xmp=False, embed_mkv=True):
    from .media import kind
    media = kind(row)
    suffix = row.path.suffix.lower()
    from .media import companion
    if media == tr('video') and suffix == tr('.mkv') and embed_mkv:
        return tr('mkv')
    if companion(row.path).exists():
        return tr('xmp')
    if force_xmp and media == tr('image'):
        return tr('xmp')
    if media == tr('image') and suffix in (tr('.jpg'), tr('.jpeg'), tr('.png'), tr('.tif'), tr('.tiff'), tr('.webp')) and exiftool_path():
        return tr('image')
    if media in (tr('audio'), tr('video')) and suffix in (tr('.mp3'), tr('.flac'), tr('.ogg'), tr('.oga'), tr('.opus'), tr('.m4a'), tr('.m4b'), tr('.mp4'), tr('.m4v'), tr('.wav'), tr('.wave'), tr('.aif'), tr('.aiff')):
        return tr('audio')
    return tr('xmp')
MkvKeyNames = {tr('title'): tr('TITLE'), tr('description'): tr('DESCRIPTION'), tr('author'): tr('ARTIST'), tr('copyright'): tr('COPYRIGHT'), tr('keywords'): tr('KEYWORDS'), tr('date_taken'): tr('DATE_RELEASED')}

def _mkv_document(path, cancelled=lambda: False):
    tr('Read Matroska tags safely, preserving unusual but valid XML references.')
    if not shutil.which(tr('mkvextract')):
        raise ValueError(tr('MKVToolNix manque : relancez l’installateur pour activer l’écriture interne aux MKV.'))
    from .persistence import stream_command, parse_mkv_tags
    parts = []
    stream_command([tr('mkvextract'), str(Path(path)), tr('tags')], parts.append, cancelled, timeout=60)
    document, references = parse_mkv_tags(b''.join(parts))
    if document.tag != tr('Tags'):
        raise ValueError(tr('Les balises MKV ne sont pas reconnues ; l’original est conservé.'))
    return (document, references)

def _mkv_global_tags(document):
    tr('Return only file-level tags; track and chapter tags stay untouched.')
    for tag in document.findall(tr('Tag')):
        targets = tag.find(tr('Targets'))
        if targets is not None and any((targets.find(name) is not None for name in (tr('TrackUID'), tr('ChapterUID'), tr('AttachmentUID'), tr('EditionUID')))):
            continue
        yield tag

def read_mkv_tags(path, cancelled=lambda: False):
    try:
        document, _ = _mkv_document(path, cancelled)
    except (OSError, ValueError, InterruptedError):
        if cancelled():
            raise
        return {}
    names = {name: key for key, name in MkvKeyNames.items()}
    result = {}
    for tag in _mkv_global_tags(document):
        for simple in tag.findall(tr('Simple')):
            key = names.get(simple.findtext(tr('Name'), '').upper())
            if key and key not in result:
                value = simple.findtext(tr('String'), '')
                if value:
                    result[key] = value
    return result

def write_mkv(path, changes, cancelled=lambda: False):
    tr('Write selected file-level Matroska tags into a temporary copy only.')
    if not shutil.which(tr('mkvpropedit')):
        raise ValueError(tr('MKVToolNix manque : relancez l’installateur pour activer l’écriture interne aux MKV.'))
    unknown = set(changes) - set(MkvKeyNames)
    if unknown:
        raise ValueError(tr('Ces champs ne peuvent pas être enregistrés directement dans un MKV : ') + tr(', ').join(sorted(unknown)))
    document, references = _mkv_document(path, cancelled)
    wanted = {MkvKeyNames[key]: str(value) for key, value in changes.items()}
    remaining = dict(wanted)
    for tag in _mkv_global_tags(document):
        for simple in list(tag.findall(tr('Simple'))):
            name = simple.findtext(tr('Name'), '').upper()
            if name not in wanted:
                continue
            value = remaining.pop(name)
            if value:
                string = simple.find(tr('String'))
                if string is None:
                    string = ET.SubElement(simple, tr('String'))
                string.text = value
            else:
                tag.remove(simple)
    if remaining:
        tag = next(_mkv_global_tags(document), None)
        if tag is None:
            tag = ET.SubElement(document, tr('Tag'))
            ET.SubElement(tag, tr('Targets'))
        for name, value in remaining.items():
            if not value:
                continue
            simple = ET.SubElement(tag, tr('Simple'))
            ET.SubElement(simple, tr('Name')).text = name
            ET.SubElement(simple, tr('String')).text = value
    from .persistence import stream_command, serialize_mkv_tags
    with tempfile.TemporaryDirectory(prefix=tr('mirivue-mkv-tags-')) as directory:
        xml = Path(directory) / tr('tags.xml')
        xml.write_bytes(serialize_mkv_tags(document, references))
        stream_command([tr('mkvpropedit'), str(Path(path)), tr('--tags'), tr('all:') + str(xml)], lambda data: None, cancelled, timeout=60)
    actual = read_mkv_tags(path, cancelled)
    for key, value in changes.items():
        if str(actual.get(key, '')) != str(value):
            raise ValueError(tr('La relecture ne confirme pas le champ « ') + key + tr(' ». L’original est conservé.'))
    return actual

def read_cover(path):
    from .media import audio_tags
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4
    from mutagen.flac import Picture
    _, file = audio_tags(path)
    if file is None:
        return b''
    if hasattr(file, tr('pictures')) and file.pictures:
        return file.pictures[0].data
    if isinstance(file.tags, ID3):
        pictures = file.tags.getall(tr('APIC'))
        return pictures[0].data if pictures else b''
    if isinstance(file, MP4):
        return bytes(file[tr('covr')][0]) if file.get(tr('covr')) else b''
    if file.get(tr('metadata_block_picture')):
        try:
            return Picture(base64.b64decode(file[tr('metadata_block_picture')][0])).data
        except (ValueError, TypeError):
            return b''
    return b''

def write_audio(path, changes):
    from .media import audio_tags
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, TCON, TCOM, TCOP, COMM, TXXX, APIC
    from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
    from mutagen.flac import Picture
    _, file = audio_tags(path)
    if file is None:
        raise ValueError(tr('Ce format ne permet pas une écriture intégrée avec les composants disponibles.'))
    if file.tags is None:
        file.add_tags()
    text = {k: v for k, v in changes.items() if k != tr('cover')}
    if isinstance(file.tags, ID3):
        frames = {tr('title'): TIT2, tr('artist'): TPE1, tr('album'): TALB, tr('albumartist'): TPE2, tr('tracknumber'): TRCK, tr('discnumber'): TPOS, tr('date'): TDRC, tr('genre'): TCON, tr('composer'): TCOM, tr('copyright'): TCOP}
        for key, value in text.items():
            if key in frames:
                frame = frames[key]
                file.tags.delall(frame.__name__)
                if value:
                    file.tags.add(frame(encoding=3, text=[value]))
            elif key == tr('description'):
                file.tags.delall(tr('COMM'))
                if value:
                    file.tags.add(COMM(encoding=3, lang=tr('fra'), desc='', text=[value]))
            elif key == tr('keywords'):
                file.tags.delall(tr('TXXX:Mirivue Keywords'))
                file.tags.delall(tr('TXXX:MFM Keywords'))
                if value:
                    file.tags.add(TXXX(encoding=3, desc=tr('Mirivue Keywords'), text=[value]))
            else:
                raise ValueError(tr('Ce champ n’est pas compatible avec les métadonnées audio : ') + key)
    elif isinstance(file, MP4):
        atoms = {tr('title'): tr('©nam'), tr('artist'): tr('©ART'), tr('album'): tr('©alb'), tr('albumartist'): tr('aART'), tr('date'): tr('©day'), tr('genre'): tr('©gen'), tr('composer'): tr('©wrt'), tr('copyright'): tr('cprt'), tr('description'): tr('©cmt'), tr('keywords'): tr('----:com.apple.iTunes:KEYWORDS')}
        for key, value in text.items():
            if key in (tr('tracknumber'), tr('discnumber')):
                atom = tr('trkn') if key == tr('tracknumber') else tr('disk')
                file.pop(atom, None)
                if value:
                    parts = value.split(tr('/'))
                    file[atom] = [(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)]
            elif key in atoms:
                atom = atoms[key]
                file.pop(atom, None)
                if value:
                    file[atom] = [MP4FreeForm(value.encode())] if key == tr('keywords') else [value]
            else:
                raise ValueError(tr('Champ non pris en charge dans ce conteneur : ') + key)
    else:
        for key, value in text.items():
            file.pop(key, None)
            if value:
                file[key] = [value]
    if tr('cover') in changes:
        cover = Path(changes[tr('cover')]).read_bytes() if changes[tr('cover')] else b''
        if len(cover) > 20 * 1024 * 1024:
            raise ValueError(tr('La pochette dépasse 20 Mio.'))
        if cover:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(cover)) as image:
                if image.format not in (tr('JPEG'), tr('PNG')):
                    raise ValueError(tr('Choisissez une pochette JPEG ou PNG.'))
                mime = tr('image/jpeg') if image.format == tr('JPEG') else tr('image/png')
        if isinstance(file.tags, ID3):
            file.tags.delall(tr('APIC'))
            if cover:
                file.tags.add(APIC(encoding=3, mime=mime, type=3, desc=tr('Pochette'), data=cover))
        elif isinstance(file, MP4):
            file.pop(tr('covr'), None)
            if cover:
                file[tr('covr')] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG if mime == tr('image/jpeg') else MP4Cover.FORMAT_PNG)]
        else:
            picture = Picture()
            picture.type = 3
            if cover:
                picture.mime = mime
                picture.data = cover
            if hasattr(file, tr('clear_pictures')):
                file.clear_pictures()
                if cover:
                    file.add_picture(picture)
            else:
                file.pop(tr('metadata_block_picture'), None)
                if cover:
                    file[tr('metadata_block_picture')] = [base64.b64encode(picture.write()).decode()]
    file.save()

def safe_edit(row, changes, route, backup=True, cancelled=lambda: False):
    from .media import companion, read_companion, audio_tags
    source = row.path
    if source.is_symlink() or not source.is_file():
        raise ValueError(tr('Choisissez un fichier ordinaire, pas un lien symbolique.'))
    if fingerprint(source) != row.file_signature:
        raise ValueError(tr('Le fichier a changé depuis l’affichage. Actualisez le dossier avant de réessayer.'))
    target = companion(source) if route == tr('xmp') else source
    if target.is_symlink():
        raise ValueError(tr('Le fichier compagnon est un lien symbolique ; écriture refusée.'))
    old_signature = fingerprint(target) if target.exists() else None
    if route == tr('xmp') and old_signature != getattr(row, tr('companion_signature'), None):
        raise ValueError(tr('Le fichier compagnon a changé. Actualisez le dossier.'))
    if target.exists() and shutil.disk_usage(target.parent).free < target.stat().st_size + 16 * 1024 * 1024:
        raise ValueError(tr('Espace insuffisant pour préparer la modification des métadonnées.'))
    fd, name = tempfile.mkstemp(prefix=tr('.mirivue-'), suffix=target.suffix, dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    backup_path = None
    backup_created = False
    publishing = False
    try:
        if target.exists():
            shutil.copy2(target, temporary)
        else:
            temporary.unlink()
        if cancelled():
            raise InterruptedError()
        if route == tr('xmp'):
            write_xmp(temporary, changes)
            actual = read_xmp(temporary)
        elif route == tr('audio'):
            write_audio(temporary, changes)
            actual, _ = audio_tags(temporary)
        elif route == tr('mkv'):
            actual = write_mkv(temporary, changes, cancelled)
        else:
            if any((key not in EXIF for key in changes)):
                raise ValueError(tr('Un champ demandé n’est pas compatible avec cette image.'))
            args = [tr('-overwrite_original')]
            for key, value in changes.items():
                args.append(tr('-') + EXIF[key] + tr('='))
                if key in (tr('keywords'), tr('author')):
                    args.extend((tr('-') + EXIF[key] + tr('+=') + part.strip() for part in str(value).split(tr(';')) if part.strip()))
                elif value:
                    args.append(tr('-') + EXIF[key] + tr('=') + str(value))
            run_exif([*args, str(temporary.absolute())], cancelled)
            actual = embedded_image_tags(temporary, cancelled)
        for key, value in changes.items():
            if key == tr('cover'):
                continue
            if str(actual.get(key, '')) != str(value):
                raise ValueError(tr('La relecture ne confirme pas le champ « ') + key + tr(' ». L’original est conservé.'))
        if cancelled():
            raise InterruptedError()
        if fingerprint(source) != row.file_signature or (fingerprint(target) if target.exists() else None) != old_signature:
            raise ValueError(tr('Le fichier a été modifié par un autre logiciel ; l’enregistrement est annulé.'))
        if backup and target.exists():
            backup_path, backup_created = reserve_backup(target)
        if cancelled():
            raise InterruptedError()
        with temporary.open(tr('rb')) as stream:
            os.fsync(stream.fileno())
        # Flush the completed temporary file before the last signature check.
        # This narrows the window in which a concurrent external edit could
        # otherwise be overwritten by the atomic publication below.
        if fingerprint(source) != row.file_signature or (fingerprint(target) if target.exists() else None) != old_signature:
            raise ValueError(tr('Le fichier a changé pendant la sauvegarde ; l’original reste en place.'))
        durable_replace(temporary, target)
        publishing = True
        if backup_path:
            record_backup(target, backup_path)
        return str(backup_path) if backup_path else ''
    finally:
        temporary.unlink(missing_ok=True)
        if backup_path and not publishing:
            discard_new_backup(target, backup_path, backup_created)

class TagWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, plans):
        super().__init__()
        self.plans = plans
        self.paths = [r.path for r, _, _ in plans]
        self.errors = []
        self.done = []
        self.backups = []

    def run(self):
        for index, (row, changes, route) in enumerate(self.plans):
            if self.isInterruptionRequested():
                break
            self.progress.emit(index, len(self.plans), tr('Enregistrement de ') + row.path.name + tr('…'))
            try:
                backup = safe_edit(row, changes, route, True, self.isInterruptionRequested)
                self.done.append(row.path)
                if backup:
                    self.backups.append(backup)
            except InterruptedError:
                break
            except Exception as error:
                self.errors.append(trf('\x1f0\x1f : \x1f1\x1f', row.path.name, error))
            self.progress.emit(index + 1, len(self.plans), row.path.name + tr(' enregistré'))
        self.progress.emit(len(self.done), len(self.plans), tr('Enregistrement terminé'))

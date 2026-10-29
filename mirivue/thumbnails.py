from .i18n import tr, trf
tr('Local, bounded previews with shared-cache reuse and representative frame search.')
import hashlib
import json
import os
import base64
import select
from pathlib import Path
from .platform_services import services
import subprocess
import time
from PySide6.QtCore import QThread, Signal, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage
from .extensions import fingerprint

def cache_root():
    return services.cache_directory()

def shared_cache_root():
    return services.shared_cache_directory()

def preview_key(path, signature):
    return hashlib.sha256((path.absolute().as_uri() + repr(signature) + tr('v2')).encode()).hexdigest()

def image_score(image):
    if image.isNull():
        return -1
    gray = image.scaled(48, 48).convertToFormat(QImage.Format.Format_Grayscale8)
    data = bytes(gray.constBits())
    stride = gray.bytesPerLine()
    values = [data[y * stride + x] for y in range(gray.height()) for x in range(gray.width())]
    average = sum(values) / len(values)
    variance = sum(((v - average) ** 2 for v in values)) / len(values)
    visible = sum((20 < v < 245 for v in values)) / len(values)
    if average < 12 or average > 245 or variance < 30 or (visible < 0.08):
        return -1
    return variance ** 0.5 * visible

def png_bytes(image):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, tr('PNG'))
    buffer.close()
    return bytes(data)

def cached_preview(path, signature, score_frame=True, own_cache=True):
    own = cache_root() / tr('mirivue') / tr('thumbnails') / (preview_key(path, signature) + tr('.png'))
    image = QImage(str(own)) if own_cache and own.exists() else QImage()
    valid = (lambda candidate: image_score(candidate) >= 0) if score_frame else (lambda candidate: not candidate.isNull())
    if own_cache and valid(image):
        return own.read_bytes()
    uri = path.absolute().as_uri()
    name = hashlib.md5(uri.encode()).hexdigest() + tr('.png')
    stat = path.stat()
    for size in (tr('large'), tr('x-large'), tr('xx-large'), tr('normal')):
        candidate = shared_cache_root() / tr('thumbnails') / size / name
        if not candidate.exists():
            continue
        image = QImage(str(candidate))
        if image.text(tr('Thumb::URI')) != uri or image.text(tr('Thumb::MTime')) != str(int(stat.st_mtime)):
            continue
        if image.text(tr('Thumb::Size')) and image.text(tr('Thumb::Size')) != str(stat.st_size):
            continue
        if valid(image):
            return candidate.read_bytes()
    return None

def store_preview(path, signature, data):
    folder = cache_root() / tr('mirivue') / tr('thumbnails')
    target = folder / (preview_key(path, signature) + tr('.png'))
    import tempfile
    temporary = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.replace(target)
    except OSError:
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

def capture(command, cancelled, timeout=8):
    if cancelled():
        raise InterruptedError()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled():
                raise InterruptedError()
            if time.monotonic() > deadline:
                raise TimeoutError()
            try:
                data, _ = process.communicate(timeout=0.1)
                return data if process.returncode == 0 else b''
            except subprocess.TimeoutExpired:
                pass
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

def make_preview(path, cancelled=lambda: False, force=False):
    path = Path(path)
    signature = fingerprint(path)
    from .media import AUDIO_EXT, IMAGE_EXT
    from .metadata import EXTENSIONS as VIDEO_EXT
    static_media = path.suffix.lower() in AUDIO_EXT | IMAGE_EXT
    if not force:
        try:
            cached = cached_preview(path, signature, score_frame=not static_media)
        except OSError:
            cached = None
        if cached and fingerprint(path) == signature:
            return (signature, cached)
    if path.suffix.lower() in AUDIO_EXT | IMAGE_EXT:
        from .media_preview import media_preview
        data = media_preview(path, tr('image') if path.suffix.lower() in IMAGE_EXT else tr('audio'), cancelled)
        if fingerprint(path) != signature:
            raise ValueError(tr('Fichier modifié pendant la création de l’aperçu'))
        if data:
            store_preview(path, signature, data)
        return (signature, data)
    if path.suffix.lower() not in VIDEO_EXT:
        return (signature, None)
    duration = 0
    try:
        info = json.loads(capture([tr('ffprobe'), tr('-v'), tr('error'), tr('-protocol_whitelist'), tr('file'), tr('-show_entries'), tr('format=duration'), tr('-of'), tr('json'), str(path)], cancelled, 5))
        duration = float(info.get(tr('format'), {}).get(tr('duration'), 0))
    except (ValueError, TypeError, TimeoutError):
        pass
    positions = [duration * p for p in (0.1, 0.35, 0.6, 0.85)] if duration > 0 else [5, 20, 60, 0]
    best = None
    best_score = -1
    for position in positions:
        try:
            data = capture([tr('ffmpeg'), tr('-v'), tr('error'), tr('-nostdin'), tr('-ss'), str(position), tr('-protocol_whitelist'), tr('file'), tr('-i'), str(path), tr('-map'), tr('0:v:0'), tr('-frames:v'), tr('1'), tr('-vf'), tr('scale=320:200:force_original_aspect_ratio=decrease'), tr('-threads'), tr('1'), tr('-f'), tr('image2pipe'), tr('-vcodec'), tr('png'), tr('pipe:1')], cancelled)
        except TimeoutError:
            continue
        score = image_score(QImage.fromData(data))
        if score > best_score:
            best_score, best = (score, data)
        if score >= 18:
            break
    if fingerprint(path) != signature or cancelled():
        return (signature, None)
    if best:
        store_preview(path, signature, best)
    return (signature, best)

class ThumbnailWorker(QThread):
    ready = Signal(object, object, bytes)

    def __init__(self, paths, force_paths=()):
        super().__init__()
        self.paths = paths
        self.force_paths = set(force_paths)

    def run(self):
        pending = []
        signatures = {}
        # Serve either Mirivue's cache or the shared freedesktop cache before
        # starting thumbnailers. This keeps directory changes visibly fast.
        for path in self.paths:
            if self.isInterruptionRequested():
                return
            try:
                signature = fingerprint(path)
                signatures[path] = signature
                from .media import AUDIO_EXT, IMAGE_EXT
                from .metadata import EXTENSIONS as VIDEO_EXT
                static_media = path.suffix.lower() in AUDIO_EXT | IMAGE_EXT
                # A private video fallback cache must never mask a newly
                # available KDE thumbnailer. KIO gets first refusal.
                data = None if path in self.force_paths else cached_preview(
                    path, signature, score_frame=not static_media,
                    own_cache=path.suffix.lower() not in VIDEO_EXT)
                if data:
                    self.ready.emit(path, signature, data)
                else:
                    pending.append(path)
            except (OSError, ValueError):
                pending.append(path)

        # KIO::PreviewJob uses KDE's configured thumbnail plugins and the
        # standard shared cache. Its signals let us publish each result as it
        # arrives instead of waiting for one subprocess per file.
        kio_results = {}
        native_completed = False
        helper = services.tool_path('mirivue-kio-preview')
        if helper and pending and not self.isInterruptionRequested():
            try:
                process = subprocess.Popen(
                    [helper, '--video-fallback', *(str(Path(path).absolute()) for path in pending)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0,
                )
                assert process.stdout is not None
                output = bytearray()
                while True:
                    if self.isInterruptionRequested():
                        process.kill()
                        process.wait()
                        return
                    readable, _, _ = select.select([process.stdout], [], [], 0.1)
                    if readable:
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            if process.poll() is not None:
                                break
                            continue
                        output.extend(chunk)
                    while b'\n' in output:
                        line, _, remainder = output.partition(b'\n')
                        output = bytearray(remainder)
                        try:
                            item = json.loads(line.decode('utf-8'))
                            path = Path(item['path'])
                            data = base64.b64decode(item['png'], validate=True)
                            signature = signatures.get(path)
                            if signature is not None and fingerprint(path) == signature and data:
                                kio_results[path] = data
                                self.ready.emit(path, signature, data)
                        except (KeyError, TypeError, ValueError, OSError):
                            continue
                    if process.poll() is not None and not readable:
                        break
                if output.strip():
                    try:
                        item = json.loads(output.decode('utf-8'))
                        path = Path(item['path'])
                        data = base64.b64decode(item['png'], validate=True)
                        signature = signatures.get(path)
                        if signature is not None and fingerprint(path) == signature and data:
                            kio_results[path] = data
                            self.ready.emit(path, signature, data)
                    except (KeyError, TypeError, ValueError, OSError):
                        pass
                process.wait()
                native_completed = process.returncode == 0
            except (OSError, subprocess.SubprocessError):
                pass

        # Keep the existing generators as a fallback for files without an
        # installed KIO thumbnail plugin, and as a cross-desktop fallback.
        for path in pending:
            if self.isInterruptionRequested():
                return
            if path in kio_results:
                continue
            from .media import AUDIO_EXT, IMAGE_EXT
            from .metadata import EXTENSIONS as VIDEO_EXT
            if Path(path).suffix.lower() not in AUDIO_EXT | IMAGE_EXT | VIDEO_EXT:
                continue
            if native_completed and Path(path).suffix.lower() in VIDEO_EXT:
                # The native helper has already tried the video fallback
                # after KIO. Repeat in Python only if the helper failed.
                continue
            try:
                signature, data = make_preview(path, self.isInterruptionRequested, path in self.force_paths)
                if data:
                    self.ready.emit(path, signature, data)
            except InterruptedError:
                return
            except (OSError, ValueError):
                pass

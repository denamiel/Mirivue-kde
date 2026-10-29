from .i18n import tr
tr('Bounded, local still-image and artwork previews; video uses existing frame selection.')
from pathlib import Path
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImageReader, QImage, QPainter, QColor, QFontDatabase, QTextDocument, QTextOption
from .thumbnails import png_bytes

def render_pdf_page(path, page_number=0, target_width=640):
    """Render one PDF page locally, on an opaque page-sized canvas."""
    from PySide6.QtPdf import QPdfDocument
    document = QPdfDocument()
    try:
        if document.load(str(path)) != QPdfDocument.Error.None_:
            return QImage(), 0
        count = document.pageCount()
        if not 0 <= page_number < count:
            return QImage(), count
        page = document.pagePointSize(page_number)
        if page.isEmpty():
            return QImage(), count
        width = max(160, min(3840, int(target_width)))
        scale = min(width / page.width(), 3840 / page.height())
        target = QSize(max(1, round(page.width() * scale)), max(1, round(page.height() * scale)))
        image = document.render(page_number, target)
        # QPdfDocument keeps alpha for transparent PDF pages.  Documents are
        # conventionally rendered on paper, so compose them on white before
        # showing them against Mirivue's dark preview surface.
        if not image.isNull() and image.hasAlphaChannel():
            opaque = QImage(image.size(), QImage.Format.Format_RGB32)
            opaque.fill(Qt.GlobalColor.white)
            painter = QPainter(opaque)
            painter.drawImage(0, 0, image)
            painter.end()
            image = opaque
        return image, count
    finally:
        document.close()

def _document_text(path):
    """Extract readable text from common OpenDocument/OpenXML text packages."""
    import zipfile
    import xml.etree.ElementTree as ET

    path = Path(path)
    extension = path.suffix.lower()
    members = {
        '.docx': ('word/document.xml',),
        '.docm': ('word/document.xml',),
        '.odt': ('content.xml',),
    }.get(extension)
    if not members or path.is_symlink() or not path.is_file():
        return ''
    try:
        if path.stat().st_size > 64 * 1024 * 1024:
            return ''
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(members[0])
            if info.file_size > 16 * 1024 * 1024:
                return ''
            root = ET.fromstring(archive.read(members[0]))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError):
        return ''

    paragraphs = []
    for paragraph in root.iter():
        if paragraph.tag.rsplit('}', 1)[-1] not in ('p', 'h'):
            continue
        parts = []
        for node in paragraph.iter():
            local_name = node.tag.rsplit('}', 1)[-1]
            if local_name == 't' and node.text:
                parts.append(node.text)
            elif local_name in ('tab',):
                parts.append('    ')
            elif local_name in ('br', 'cr'):
                parts.append('\n')
        line = ''.join(parts).strip()
        if line:
            paragraphs.append(line)
            if sum(map(len, paragraphs)) >= 16000:
                break
    return '\n'.join(paragraphs)[:16000]


def _render_text_content(text, target_size):
    """Render bounded text on a paper-like page for the preview panel."""
    if not text:
        return QImage()
    text = text[:16000]
    width = max(320, min(4096, int(target_size.width())))
    height = max(240, min(4096, int(target_size.height())))
    image = QImage(QSize(width, height), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(tr('#30343a')))
    painter = QPainter(image)
    margin = max(20, round(min(width, height) * 0.055))
    page = image.rect().adjusted(margin, margin, -margin, -margin)
    painter.fillRect(page.translated(0, max(3, margin // 10)), QColor(tr('#171a1e')))
    painter.fillRect(page, QColor(tr('#fbfbfa')))
    painter.setPen(QColor(tr('#c6cbd0')))
    painter.drawRect(page.adjusted(0, 0, -1, -1))
    text_rect = page.adjusted(margin, margin, -margin, -margin)
    document = QTextDocument()
    document.setDefaultFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    document.setDefaultStyleSheet(tr('body { color: #25292d; }'))
    document.setPlainText(text)
    option = document.defaultTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    document.setDefaultTextOption(option)
    document.setTextWidth(text_rect.width())
    # QTextDocument uses its own (0, 0) origin. Translate to the inset page
    # area before clipping; otherwise the clip can retain the paper while
    # cutting away all of the glyphs, producing a blank preview.
    painter.save()
    painter.setClipRect(text_rect)
    painter.translate(text_rect.topLeft())
    document.drawContents(painter, QRectF(0, 0, text_rect.width(), text_rect.height()))
    painter.restore()
    painter.end()
    return image


def render_text_page(path, target_size):
    """Render local text or office-document content if KIO has no thumbnail."""
    import locale
    import mimetypes
    path = Path(path)
    if path.suffix.lower() in ('.docx', '.odt'):
        return _render_text_content(_document_text(path), target_size)
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith(tr('text/')) or path.is_symlink() or not path.is_file():
        return QImage()
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            return QImage()
        with path.open(tr('rb')) as stream:
            raw = stream.read(256 * 1024)
    except OSError:
        return QImage()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = raw.decode(tr('utf-16'), errors=tr('replace'))
    else:
        if b'\x00' in raw:
            return QImage()
        try:
            text = raw.decode(tr('utf-8-sig'))
        except UnicodeDecodeError:
            encoding = locale.getpreferredencoding(False) or tr('utf-8')
            text = raw.decode(encoding, errors=tr('replace'))
    return _render_text_content(text, target_size)


def media_preview(path, media_type, cancelled=lambda: False, target_size=None):
    if cancelled():
        raise InterruptedError()
    image = QImage()
    suffix = Path(path).suffix.lower()
    text_document = suffix in (tr('.txt'), tr('.text'), tr('.docx'), tr('.docm'), tr('.odt'))
    if text_document:
        # The file extension is authoritative here. Some listing paths can
        # misclassify ordinary documents as videos; sending those to the video
        # frame generator produces a blank preview. Text-capable documents use
        # Mirivue's local renderer directly, avoiding blank KIO paper thumbnails.
        image = render_text_page(path, target_size or QSize(960, 720))
        if image.isNull():
            return b''
    elif suffix == tr('.pdf'):
        # QtPdf renders locally and is bundled with PySide6, so PDF previews
        # do not need a browser, a network request, or an external program.
        image, _ = render_pdf_page(path)
    elif media_type == tr('video'):
        from .thumbnails import make_preview
        return make_preview(path, cancelled)[1]
    elif media_type == tr('audio'):
        from .media_tags import read_cover
        data = read_cover(path)
        if len(data) > 20 * 1024 * 1024:
            return b''
        image = QImage.fromData(data)
    elif media_type not in (tr('video'), tr('image')):
        # Use Plasma's configured KIO thumbnailers for documents and text.
        # Unsupported MIME types simply return no preview, as they do in KDE.
        from .platform_services import services
        import base64
        import json
        from .thumbnails import capture
        helper = services.tool_path(tr('mirivue-kio-preview'))
        size = target_size or QSize(960, 720)
        width = max(160, min(4096, int(size.width())))
        height = max(160, min(4096, int(size.height())))
        if helper:
            try:
                output = capture([helper, tr('--size'), str(width), str(height), str(Path(path).absolute())], cancelled, 20)
                for line in output.splitlines():
                    try:
                        item = json.loads(line.decode(tr('utf-8')))
                        if Path(item.get(tr('path'), '')).absolute() == Path(path).absolute():
                            data = base64.b64decode(item.get(tr('png'), ''), validate=True)
                            if data:
                                image = QImage.fromData(data)
                                break
                    except (UnicodeError, ValueError, TypeError):
                        continue
            except (OSError, TimeoutError, InterruptedError):
                if cancelled():
                    raise InterruptedError()
        if image.isNull():
            image = render_text_page(path, size)
    else:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        bound = target_size or QSize(640, 640)
        bound = QSize(max(160, min(3840, bound.width())), max(160, min(3840, bound.height())))
        if size.isValid():
            scaled = size.scaled(bound, __import__(tr('PySide6.QtCore'), fromlist=[tr('Qt')]).Qt.AspectRatioMode.KeepAspectRatio)
            # Never upsample a small original while decoding: that would only
            # make it softer and cannot add detail.
            reader.setScaledSize(scaled if scaled.width() <= size.width() and scaled.height() <= size.height() else size)
        image = reader.read()
        if image.isNull():
            from PIL import Image, ImageOps
            import io
            try:
                with Image.open(path) as source:
                    source.draft(tr('RGB'), (bound.width(), bound.height()))
                    source = ImageOps.exif_transpose(source)
                    source.thumbnail((bound.width(), bound.height()))
                    buffer = io.BytesIO()
                    source.convert(tr('RGBA')).save(buffer, format=tr('PNG'))
                    image = QImage.fromData(buffer.getvalue())
            except Exception:
                import shutil
                from .media_tags import exiftool_path
                if exiftool_path():
                    from .media_tags import run_exif
                    for tag in (tr('PreviewImage'), tr('JpgFromRaw'), tr('ThumbnailImage')):
                        data = run_exif([tr('-b'), tr('-') + tag, str(Path(path).absolute())], cancelled)
                        if len(data) <= 20 * 1024 * 1024:
                            image = QImage.fromData(data)
                        if not image.isNull():
                            break
    if cancelled():
        raise InterruptedError()
    if not image.isNull():
        bound = target_size if target_size is not None and (text_document or media_type not in (tr('video'), tr('audio'), tr('image')) or media_type == tr('image')) else QSize(640, 640)
        scaled = image.size().scaled(bound, __import__(tr('PySide6.QtCore'), fromlist=[tr('Qt')]).Qt.AspectRatioMode.KeepAspectRatio)
        if scaled.width() <= image.width() and scaled.height() <= image.height():
            image = image.scaled(scaled, __import__(tr('PySide6.QtCore'), fromlist=[tr('Qt')]).Qt.AspectRatioMode.KeepAspectRatio)
    return png_bytes(image) if not image.isNull() else b''

from .i18n import tr, trf
tr('Media profiles, local search, previews and reviewed metadata edits.')
from pathlib import Path
import re, urllib.parse
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl, QSize, QPointF, QRectF, QMimeDatabase
from PySide6.QtGui import QImage, QPixmap, QAction, QDesktopServices, QIcon, QCursor, QPainter, QPalette, QKeySequence
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QCheckBox, QLabel, QPushButton, QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QFileDialog, QScrollArea, QWidget, QDockWidget, QComboBox, QSpinBox, QProgressBar, QTextBrowser, QInputDialog, QSizePolicy, QSplitter, QSlider, QStackedWidget, QToolButton, QMenu, QWidgetAction, QToolTip, QGraphicsOpacityEffect, QStyle
from .media import FIELDS, kind, suggestions, companion
from .media_tags import native_route, TagWorker, read_cover
from . import library
from .iconography import themed_icon, set_themed_action_icon, context_help_button
from .diagnostics import record_tool_failure
from .platform_services import services
from .preview_cache import PreviewCache
PROFILES = {tr('Médiathèque'): {0, 1, 2, 3, 6, 13, 14, 17}, tr('Général'): {0, 1, 2, 3, 14, 17, 18, 27}, tr('Vidéo'): {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14}, tr('Audio'): {0, 1, 2, 8, 9, 18, 19, 20, 21, 22, 23, 24, 25, 30}, tr('Images'): {0, 1, 3, 14, 18, 26, 27, 28, 29}, tr('Personnel'): {0, 1, 2, 3, 14, 17}}

def is_pdf(row):
    return row is not None and not row.is_dir and row.path.suffix.lower() == tr('.pdf')


DOCUMENT_EXTENSIONS = {
    tr('.txt'), tr('.text'), tr('.rtf'), tr('.csv'),
    tr('.doc'), tr('.docx'), tr('.docm'), tr('.odt'),
    tr('.xls'), tr('.xlsx'), tr('.xlsm'), tr('.ods'),
    tr('.ppt'), tr('.pptx'), tr('.pptm'), tr('.odp'),
}

def document_mime(path):
    """Identify a document by its content too, for extensionless files."""
    database = QMimeDatabase()
    # Office Open XML formats are ZIP containers.  For a named .docx/.xlsx
    # file, the extension carries the user-facing document type; content-only
    # probing would instead return application/zip and show an archive icon.
    if Path(path).suffix:
        return database.mimeTypeForFile(str(path))
    return database.mimeTypeForFile(str(path), QMimeDatabase.MatchMode.MatchContent)


def is_openable_document(row):
    """Documents are opened by their desktop-default application from preview."""
    if row is None or row.is_dir:
        return False
    if row.path.suffix.lower() in DOCUMENT_EXTENSIONS:
        return True
    mime = document_mime(row.path)
    name = mime.name()
    return (
        name.startswith(tr('text/'))
        or name in {tr('application/rtf'), tr('application/msword')}
        or name.startswith(tr('application/vnd.openxmlformats-officedocument.'))
        or name.startswith(tr('application/vnd.ms-'))
        or name.startswith(tr('application/vnd.oasis.opendocument.'))
    )


def default_application_icon(path):
    """Resolve the preferred KDE application just as the Open With menu does."""
    mime = document_mime(path)
    icon = QIcon()
    helper = services.tool_path('mirivue-kio-applications')
    if helper:
        try:
            import json
            import subprocess
            result = subprocess.run([helper, '--default', mime.name()],
                                    capture_output=True, text=True, timeout=3, check=True)
            icon_name = json.loads(result.stdout).get('icon', '')
            if icon_name:
                icon = QIcon.fromTheme(icon_name)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    if icon.isNull():
        icon = QIcon.fromTheme(mime.iconName())
    return icon

class SeekSlider(QSlider):
    tr('A timeline that seeks precisely where the user clicks.')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum():
            super().mousePressEvent(event)
            available = max(1, self.width() - 1)
            ratio = max(0.0, min(1.0, event.position().x() / available))
            value = round(self.minimum() + (self.maximum() - self.minimum()) * ratio)
            self.setSliderPosition(value)
            self.setValue(value)
            self.sliderMoved.emit(value)
            event.accept()
            return
        super().mousePressEvent(event)

class PreviewLabel(QLabel):
    tr('Render the preview at a focal zoom position instead of always at its centre.')

    def __init__(self):
        super().__init__()
        self._image = QImage()
        self._zoom = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._uses_checkerboard = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._empty_state = QWidget(self)
        self._empty_state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.setContentsMargins(20, 20, 20, 20)
        empty_layout.setSpacing(12)
        empty_layout.addStretch(1)
        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout.addWidget(self._empty_icon)
        self._empty_message = QLabel()
        self._empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_message.setWordWrap(True)
        self._empty_message.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout.addWidget(self._empty_message)
        empty_layout.addStretch(1)
        self._empty_state.hide()

    def set_preview(self, image):
        self._image = image
        self._zoom = 1.0
        self._offset_x = self._offset_y = 0.0
        self._uses_checkerboard = image.hasAlphaChannel()
        self.setText('')
        self.setPixmap(QPixmap())
        self._empty_state.hide()
        self.fit_preview()

    def clear_preview(self):
        self._image = QImage()
        self._zoom = 1.0
        self._offset_x = self._offset_y = 0.0
        self._uses_checkerboard = False
        self._empty_state.hide()
        self.clear()

    def show_unavailable_document(self, icon):
        """Use a quiet in-panel state instead of a blank office page."""
        self.clear_preview()
        self._empty_icon.setPixmap(icon.pixmap(56, 56) if not icon.isNull() else QPixmap())
        self._empty_message.setText(tr('Double-cliquez pour ouvrir ce document dans son application.'))
        self._empty_state.setGeometry(self.rect())
        self._empty_state.show()

    def show_folder_hint(self):
        """Describe the preview action that is actually available for folders."""
        self.clear_preview()
        icon = QIcon.fromTheme(tr('folder'))
        self._empty_icon.setPixmap(icon.pixmap(56, 56) if not icon.isNull() else QPixmap())
        self._empty_message.setText(tr('Dossier\n\nDouble-cliquez pour l’ouvrir.'))
        self._empty_state.setGeometry(self.rect())
        self._empty_state.show()

    def empty_message(self):
        return self._empty_message.text()

    def _base_preview_rect(self, zoom=None):
        if self._image.isNull() or self.width() <= 0 or self.height() <= 0:
            return QRectF()
        scale = min(self.width() / self._image.width(), self.height() / self._image.height()) * (self._zoom if zoom is None else zoom)
        width, height = self._image.width() * scale, self._image.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def _preview_rect(self, zoom=None):
        rect = self._base_preview_rect(zoom)
        rect.translate(self._offset_x, self._offset_y)
        return rect

    def _clamp_offsets(self):
        rect = self._base_preview_rect()
        self._offset_x = max(-max(0., (rect.width() - self.width()) / 2), min(max(0., (rect.width() - self.width()) / 2), self._offset_x))
        self._offset_y = max(-max(0., (rect.height() - self.height()) / 2), min(max(0., (rect.height() - self.height()) / 2), self._offset_y))

    def paintEvent(self, event):
        if self._image.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        if self._uses_checkerboard:
            base = self.palette().color(QPalette.ColorRole.Base)
            alternate = self.palette().color(QPalette.ColorRole.AlternateBase)
            step = max(8, min(20, round(min(self.width(), self.height()) / 20)))
            for y in range(0, self.height(), step):
                for x in range(0, self.width(), step):
                    painter.fillRect(x, y, step, step, base if (x // step + y // step) % 2 == 0 else alternate)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self._preview_rect(), self._image, QRectF(self._image.rect()))
        painter.end()

    def fit_preview(self):
        if not self._image.isNull():
            self._clamp_offsets()
            self.update()

    def adjust_zoom_at(self, delta, position=None):
        if self._image.isNull() or not delta:
            return False
        factor = 1.18 if delta > 0 else 1 / 1.18
        return self.zoom_at(self._zoom * factor, position)

    def zoom_at(self, zoom, position=None):
        if self._image.isNull():
            return False
        zoom = max(0.25, min(8.0, zoom))
        if zoom == self._zoom:
            return False
        old_rect = self._preview_rect()
        point = self.rect().center() if position is None else position
        point = QPointF(max(0., min(float(self.width()), point.x())), max(0., min(float(self.height()), point.y())))
        image_x = (point.x() - old_rect.left()) / max(1., old_rect.width())
        image_y = (point.y() - old_rect.top()) / max(1., old_rect.height())
        self._zoom = zoom
        new_base = self._base_preview_rect()
        self._offset_x = point.x() - (new_base.left() + image_x * new_base.width())
        self._offset_y = point.y() - (new_base.top() + image_y * new_base.height())
        self._clamp_offsets()
        self.update()
        return True

    def adjust_zoom(self, delta):
        return self.adjust_zoom_at(delta, self.rect().center())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._empty_state.setGeometry(self.rect())
        self.fit_preview()

class PreviewWorker(QThread):
    ready = Signal(object)

    def __init__(self, row, target_size=None):
        super().__init__()
        self.row = row
        self.target_size = target_size

    def run(self):
        try:
            from .media_preview import media_preview
            data = media_preview(self.row.path, kind(self.row), self.isInterruptionRequested, self.target_size)
            if not self.isInterruptionRequested():
                self.ready.emit(data)
        except Exception as error:
            record_tool_failure(tr('aperçu'), trf('\x1f0\x1f : \x1f1\x1f', self.row.path, error))
            if not self.isInterruptionRequested():
                self.ready.emit(b'')


class PdfPageWorker(QThread):
    ready = Signal(object, int)

    def __init__(self, path, page, width):
        super().__init__()
        self.path, self.page, self.width = path, page, width

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            from .media_preview import render_pdf_page
            image, count = render_pdf_page(self.path, self.page, self.width)
            if not self.isInterruptionRequested():
                self.ready.emit(image, count)
        except Exception as error:
            record_tool_failure(tr('aperçu PDF'), str(error))
            if not self.isInterruptionRequested():
                self.ready.emit(QImage(), 0)

class MediaMixin:

    def show_preview_message(self, message, timeout=0):
        """Keep playback, PDF and preview feedback inside the preview panel."""
        if not hasattr(self, 'preview_status') or not self.preview_dock.isVisible():
            self.show_activity_message(message, timeout)
            return
        message = str(message or '')
        self.preview_status.setText(message)
        self.preview_status.setToolTip(message)
        self.preview_status.setVisible(bool(message))
        self.preview_status_timer.stop()
        if message and timeout:
            self.preview_status_timer.start(timeout)

    def clear_preview_message(self):
        if hasattr(self, 'preview_status'):
            self.preview_status.clear()
            self.preview_status.hide()

    def profile_definitions(self):
        saved = library.read(self.settings, tr('media/profile-definitions'), {})
        result = {name: set(columns) for name, columns in PROFILES.items()}
        if isinstance(saved, dict):
            for name, columns in saved.items():
                if name in result and isinstance(columns, list):
                    result[name] = {int(c) for c in columns if 0 <= int(c) < self.model.columnCount() and int(c) not in (10, 12, 13, 15, 16, 36)} or {0}
        return result

    def profile_names(self):
        return list(PROFILES)

    def default_profile(self, name):
        return PROFILES.get(name, {0})

    def save_profile_definitions(self, profiles):
        clean = {name: sorted((set(profiles.get(name, PROFILES[name])) - {10, 12, 13, 15, 16, 36}) | {0}) for name in PROFILES}
        library.write(self.settings, tr('media/profile-definitions'), clean)
        self.refresh_profile_menu()

    def refresh_profile_menu(self):
        if not hasattr(self, tr('media_profile_menu')):
            return
        self.media_profile_menu.clear()
        for title in self.profile_names():
            self.media_profile_menu.addAction(title, lambda checked=False, name=title: self.apply_media_profile(name))

    def init_media(self, view_menu, settings_menu, organize_menu, navigation):
        new_columns = not self.settings.value('media/columns-initialized', False, type=bool)
        if new_columns:
            for col in range(18, self.model.columnCount()):
                self.table.setColumnHidden(col, True)
            self.settings.setValue('media/columns-initialized', True)
        self.media_profiles = library.read(self.settings, tr('media-profiles'), {})
        self._metadata_worker = None
        self._preview_worker = None
        self._pdf_worker = None
        self._pdf_requested_key = None
        self._pdf_pending_steps = 0
        self._preview_pending = None
        self._media_preview_cache = PreviewCache()
        self._preview_document_image = False
        self._pdf_preview_path = None
        self._pdf_preview_page = 0
        self._pdf_page_count = 0
        self._pdf_wheel_ready = True
        self.media_profile_menu = view_menu.addMenu(tr('Profil de colonnes'))
        self.refresh_profile_menu()
        self.metadata_action = organize_menu.addAction(tr('Métadonnées…'), self.edit_metadata)
        # These choices used to live in Configuration.  They now belong to
        # each explicit metadata edit, next to the action they affect.
        self.settings.remove('media/image-xmp')
        self.settings.remove('media/mkv-embedded')
        self.preview_dock = QDockWidget(tr('Panneau d’aperçu'), self)
        self.preview_dock.setObjectName(tr('media-preview'))
        self.preview_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.preview_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.preview_dock.installEventFilter(self)
        self._preview_fullscreen = False
        self._fullscreen_row = None
        self._preview_was_maximized = False
        self._preview_window_geometry = None
        self._preview_dock_width = None
        self._fullscreen_content_widget = None
        self._preview_fullscreen_overlay = QWidget(self)
        self._preview_fullscreen_overlay.setObjectName(tr('mirivueFullscreenPreview'))
        self._preview_fullscreen_overlay.setStyleSheet(tr('background: black;'))
        self._preview_fullscreen_layout = QVBoxLayout(self._preview_fullscreen_overlay)
        self._preview_fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_fullscreen_overlay.installEventFilter(self)
        self._preview_fullscreen_overlay.setMouseTracking(True)
        self._fullscreen_controls = QWidget(self._preview_fullscreen_overlay)
        self._fullscreen_controls.setObjectName(tr('mirivueFullscreenControls'))
        self._fullscreen_controls.setMinimumHeight(58)
        self._fullscreen_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._fullscreen_opacity = QGraphicsOpacityEffect(self._fullscreen_controls)
        self._fullscreen_controls.setGraphicsEffect(self._fullscreen_opacity)
        self._fullscreen_controls.setStyleSheet(tr('\n            QWidget#mirivueFullscreenControls { background: rgba(20,20,20,225); }\n            QWidget#mirivueFullscreenControls QLabel { color: white; min-width: 92px; }\n            QWidget#mirivueFullscreenControls QToolButton { color: white; border: 1px solid transparent; border-radius: 4px; padding: 3px 5px; }\n            QWidget#mirivueFullscreenControls QToolButton:hover { background: rgba(255,255,255,38); }\n            QWidget#mirivueFullscreenControls QSlider::groove:horizontal { height: 5px; background: rgba(255,255,255,105); border-radius: 2px; }\n            QWidget#mirivueFullscreenControls QSlider::handle:horizontal { width: 13px; margin: -5px 0; background: white; border-radius: 6px; }\n            QWidget#mirivueFullscreenControls QSlider::sub-page:horizontal { background: palette(highlight); border-radius: 2px; }\n        '))
        self._fullscreen_controls.installEventFilter(self)
        self._fullscreen_controls.setMouseTracking(True)
        fullscreen_layout = QHBoxLayout(self._fullscreen_controls)
        fullscreen_layout.setContentsMargins(12, 6, 12, 6)
        fullscreen_layout.setSpacing(8)
        self.fullscreen_play = QToolButton()
        self.fullscreen_play.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.fullscreen_play.setToolTip(tr('Lire ou mettre en pause'))
        self.fullscreen_play.clicked.connect(self.toggle_media_playback)
        fullscreen_layout.addWidget(self.fullscreen_play)
        self.fullscreen_previous = QToolButton()
        self.fullscreen_previous.setText(tr('⏮'))
        self.fullscreen_previous.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.fullscreen_previous.setToolTip(tr('Média précédent'))
        self.fullscreen_previous.clicked.connect(lambda: self.play_adjacent_media(-1))
        fullscreen_layout.addWidget(self.fullscreen_previous)
        self.fullscreen_next = QToolButton()
        self.fullscreen_next.setText(tr('⏭'))
        self.fullscreen_next.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.fullscreen_next.setToolTip(tr('Média suivant'))
        self.fullscreen_next.clicked.connect(lambda: self.play_adjacent_media(1))
        fullscreen_layout.addWidget(self.fullscreen_next)
        self.fullscreen_playlist_label = QLabel('')
        fullscreen_layout.addWidget(self.fullscreen_playlist_label)
        self.fullscreen_position = SeekSlider(Qt.Orientation.Horizontal)
        self.fullscreen_position.setRange(0, 0)
        self.fullscreen_position.setEnabled(False)
        self.fullscreen_position.setToolTip(tr('Cliquez pour aller à cet instant'))
        self.fullscreen_position.sliderMoved.connect(self.seek_media)
        self.fullscreen_position.sliderPressed.connect(self._hold_fullscreen_controls)
        self.fullscreen_position.sliderReleased.connect(self.show_fullscreen_controls)
        fullscreen_layout.addWidget(self.fullscreen_position, 1)
        self.fullscreen_time = QLabel(tr('0:00 / 0:00'))
        fullscreen_layout.addWidget(self.fullscreen_time)
        self.fullscreen_volume = QToolButton()
        self.fullscreen_volume.setIcon(themed_icon(tr('audio-volume-high'), self, QStyle.StandardPixmap.SP_MediaVolume))
        self.fullscreen_volume.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.fullscreen_volume.setToolTip(tr('Volume'))
        fullscreen_layout.addWidget(self.fullscreen_volume)
        self._fullscreen_controls_timer = QTimer(self)
        self._fullscreen_controls_timer.setSingleShot(True)
        self._fullscreen_cursor_timer = QTimer(self)
        self._fullscreen_cursor_timer.setInterval(80)
        self._fullscreen_cursor_timer.timeout.connect(self.poll_fullscreen_cursor)
        self._fullscreen_reveal_zone = QWidget(self._preview_fullscreen_overlay)
        self._fullscreen_reveal_zone.setObjectName(tr('mirivueFullscreenRevealZone'))
        self._fullscreen_reveal_zone.setStyleSheet(tr('background: transparent;'))
        self._fullscreen_reveal_zone.setMouseTracking(True)
        self._fullscreen_reveal_zone.installEventFilter(self)
        self._fullscreen_controls.hide()
        self._fullscreen_reveal_zone.hide()
        self._preview_fullscreen_overlay.hide()
        body = QWidget()
        box = QVBoxLayout(body)
        split = QSplitter(Qt.Orientation.Vertical)
        self.preview_stack = QStackedWidget()
        self.preview_stack.installEventFilter(self)
        self.preview_stack.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview_stack.customContextMenuRequested.connect(self.show_preview_context)
        self.media_image = PreviewLabel()
        self.media_image.installEventFilter(self)
        self.media_image.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.media_image.customContextMenuRequested.connect(self.show_preview_context)
        self.preview_stack.addWidget(self.media_image)
        self.media_video = None
        split.addWidget(self.preview_stack)
        self.media_info = QTextBrowser()
        self.media_info.setMinimumHeight(100)
        split.addWidget(self.media_info)
        split.setSizes([420, 180])
        box.addWidget(split, 1)
        self.media_player = None
        self.media_audio = None
        self.media_devices = None
        self._media_play_path = None
        self._preview_playlist = []
        self._preview_index = 0
        controls = QHBoxLayout()
        self.media_play = QToolButton()
        self.media_play.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.media_play.setToolTip(tr('Lire'))
        self.media_play.setAccessibleName(tr('Lire'))
        self.media_play.setEnabled(False)
        self.media_play.clicked.connect(self.toggle_media_playback)
        controls.addWidget(self.media_play)
        self.media_previous = QToolButton()
        self.media_previous.setIcon(themed_icon(tr('media-skip-backward'), self, QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.media_previous.setToolTip(tr('Média précédent'))
        self.media_previous.setAccessibleName(tr('Média précédent'))
        self.media_previous.clicked.connect(lambda: self.play_adjacent_media(-1))
        controls.addWidget(self.media_previous)
        self.media_next = QToolButton()
        self.media_next.setIcon(themed_icon(tr('media-skip-forward'), self, QStyle.StandardPixmap.SP_MediaSkipForward))
        self.media_next.setToolTip(tr('Média suivant'))
        self.media_next.setAccessibleName(tr('Média suivant'))
        self.media_next.clicked.connect(lambda: self.play_adjacent_media(1))
        controls.addWidget(self.media_next)
        self.media_playlist_label = QLabel('')
        controls.addWidget(self.media_playlist_label)
        self.media_info_toggle = QToolButton()
        self.media_info_toggle.setIcon(themed_icon(tr('dialog-information'), self, QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.media_info_toggle.setCheckable(True)
        self.media_info_toggle.setChecked(self.settings.value('media/preview-info-visible', True, type=bool))
        self.media_info_toggle.setToolTip(tr('Afficher ou masquer les informations'))
        self.media_info_toggle.setAccessibleName(tr('Afficher ou masquer les informations'))
        self.media_info_toggle.toggled.connect(self.set_preview_information_visible)
        controls.addWidget(self.media_info_toggle)
        self.media_volume_button = QToolButton()
        self.media_volume_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.media_volume_button.setToolTip(tr('Volume — la molette habituelle règle aussi le volume sur l’aperçu'))
        self.media_volume_button.setAccessibleName(tr('Réglage du volume'))
        self.media_volume_button.installEventFilter(self)
        self.media_volume_menu = QMenu(self)
        volume_body = QWidget()
        volume_layout = QVBoxLayout(volume_body)
        volume_layout.setContentsMargins(10, 8, 10, 8)
        self.media_volume_label = QLabel()
        self.media_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.media_volume_slider.setRange(0, 100)
        self.media_volume_slider.setValue(self.settings.value('media/volume', 80, type=int))
        self.media_volume_slider.valueChanged.connect(self.change_media_volume)
        volume_layout.addWidget(self.media_volume_label)
        volume_layout.addWidget(self.media_volume_slider)
        volume_layout.addWidget(QLabel(tr('Sortie audio :')))
        self.media_audio_device_combo = QComboBox()
        self.media_audio_device_combo.setToolTip(tr('Choisir la sortie utilisée par les aperçus audio et vidéo'))
        self.media_audio_device_combo.currentIndexChanged.connect(self.change_media_audio_device)
        volume_layout.addWidget(self.media_audio_device_combo)
        volume_action = QWidgetAction(self.media_volume_menu)
        volume_action.setDefaultWidget(volume_body)
        self.media_volume_menu.addAction(volume_action)
        self.media_volume_button.setMenu(self.media_volume_menu)
        self.fullscreen_volume.setMenu(self.media_volume_menu)
        self.update_media_volume_icon()
        controls.addWidget(self.media_volume_button)
        self.media_position = SeekSlider(Qt.Orientation.Horizontal)
        self.media_position.setRange(0, 0)
        self.media_position.setEnabled(False)
        self.media_position.sliderMoved.connect(self.seek_media)
        controls.addWidget(self.media_position, 1)
        self.media_time = QLabel(tr('0:00 / 0:00'))
        controls.addWidget(self.media_time)
        box.addLayout(controls)
        self.preview_status = QLabel()
        self.preview_status.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.preview_status.hide()
        box.addWidget(self.preview_status)
        self.preview_status_timer = QTimer(self)
        self.preview_status_timer.setSingleShot(True)
        self.preview_status_timer.timeout.connect(self.clear_preview_message)
        self.preview_open_button = QPushButton(tr('Ouvrir avec l’application par défaut'))
        self.preview_open_button.clicked.connect(self.open_selected)
        box.addWidget(self.preview_open_button)
        self.preview_dock.setWidget(body)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.preview_dock)
        action = self.preview_dock.toggleViewAction()
        self.preview_panel_action = action
        action.setText(tr('Panneau d’aperçu'))
        set_themed_action_icon(action, tr('sidebar-expand-right'))
        # Dolphin uses F11 for its information panel.  Mirivue's preview
        # panel is the corresponding contextual information surface.
        action.setShortcut(QKeySequence(tr('F11')))
        view_menu.addAction(action)
        self.preview_dock.setVisible(self.settings.value('media/start-preview-panel', self.settings.value('media/preview-panel', False, type=bool), type=bool))
        self.preview_dock.visibilityChanged.connect(self.preview_visibility_changed)
        self.preview_panel_button = QToolButton()
        self.preview_panel_button.setAutoRaise(True)
        self.preview_panel_button.setCheckable(True)
        self.preview_panel_button.setIcon(themed_icon(tr('sidebar-expand-right'), self, QStyle.StandardPixmap.SP_FileDialogInfoView))
        self.preview_panel_button.setToolTip(tr('Afficher ou masquer le panneau d’aperçu'))
        self.preview_panel_button.setAccessibleName(tr('Panneau d’aperçu'))
        self.preview_panel_button.setChecked(self.preview_dock.isVisible())
        self.preview_panel_button.toggled.connect(self.preview_dock.setVisible)
        self.preview_dock.visibilityChanged.connect(self.preview_panel_button.setChecked)
        navigation.addWidget(self.preview_panel_button)
        self.media_preview_timer = QTimer(self)
        self.media_preview_timer.setSingleShot(True)
        self.media_preview_timer.setInterval(80)
        self.media_preview_timer.timeout.connect(self.update_media_preview)
        self.update_playlist_controls()
        self.set_preview_information_visible(self.media_info_toggle.isChecked())
        self.metadata_status = QLabel()
        self.metadata_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.metadata_status.setMaximumWidth(600)
        self.metadata_status.setTextFormat(Qt.TextFormat.PlainText)
        self.metadata_status.hide()
        box.addWidget(self.metadata_status)
        self._metadata_dialog = None

    def apply_media_profile(self, name, save=True):
        definitions = self.profile_definitions()
        if name not in definitions:
            return
        for column in range(self.model.columnCount()):
            self.table.setColumnHidden(column, column in (10, 12, 13, 15, 16, 36) or
                                       (column != 0 and column not in definitions[name]))
        self.schedule_pane_column_save(self.bound_pane)
        if save and self.folder:
            self.media_profiles[str(self.folder)] = name
            library.write(self.settings, tr('media-profiles'), self.media_profiles)
        self.show_activity_message(tr('Configuration de colonnes : ') + name, 4000)

    def restore_media_profile(self, folder):
        name = self.media_profiles.get(str(folder))
        if name:
            self.apply_media_profile(name, False)

    def media_search(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Critères de métadonnées'))
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        layout.addLayout(form)
        layout.addWidget(QLabel(tr('Le type d’élément se choisit dans la barre de recherche.')))
        artist = QLineEdit()
        form.addRow(tr('Artiste contient'), artist)
        width = QSpinBox()
        width.setRange(0, 100000)
        width.setSpecialValueText(tr('Sans limite'))
        form.addRow(tr('Largeur minimale (pixels)'), width)
        seconds = QSpinBox()
        seconds.setRange(0, 864000)
        seconds.setSpecialValueText(tr('Sans limite'))
        form.addRow(tr('Durée maximale (secondes)'), seconds)
        size_mib = QSpinBox()
        size_mib.setRange(0, 1048576)
        size_mib.setSpecialValueText(tr('Sans limite'))
        size_mib.setSuffix(tr(' Mio'))
        form.addRow(tr('Taille minimale'), size_mib)
        current = getattr(self.proxy, tr('media_query'), {})
        artist.setText(current.get(tr('artist'), ''))
        width.setValue(current.get(tr('width'), 0))
        seconds.setValue(current.get(tr('duration'), 0))
        size_mib.setValue(current.get(tr('size_mib'), 0))
        reset = QPushButton(tr('Effacer ces critères'))
        layout.addWidget(reset)
        reset.clicked.connect(lambda: (artist.clear(), width.setValue(0), seconds.setValue(0), size_mib.setValue(0)))
        search_help = QHBoxLayout()
        search_help.addStretch(1)
        search_help.addWidget(context_help_button(dialog, tr('Ces critères s’appliquent à la recherche depuis le dossier actif et ses sous-dossiers selon la portée choisie. La taille minimale permet notamment de retrouver les fichiers volumineux. La recherche de doublons exacts lit le contenu complet des fichiers.')))
        layout.addLayout(search_help)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.proxy.media_query = {
                tr('artist'): artist.text().strip(),
                tr('width'): width.value(),
                tr('duration'): seconds.value(),
                tr('size_mib'): size_mib.value(),
            }
            if self.search_active:
                self.proxy.invalidateFilter()
            self.update_search_more_label()
            self.update_summary()

    def update_search_more_label(self):
        query = getattr(self.proxy, tr('media_query'), {})
        count = sum(bool(value) for value in query.values())
        self.search_more.setText(
            trf('Plus de critères (0)…', count) if count else tr('Plus de critères…')
        )

    def playback_history(self):
        raw = self.settings.value('media/play-history', [])
        if isinstance(raw, str):
            return [raw] if raw else []
        if isinstance(raw, (list, tuple)):
            return [str(path) for path in raw if str(path)]
        return []

    def remember_played_media(self, path):
        """Retired history: keep existing data, do not collect new entries."""
        return

    def clear_playback_history(self):
        self.settings.remove('media/play-history')
        self.settings.remove('media/last-played')
        self.settings.sync()

    def preview_visibility_changed(self, visible):
        self.settings.setValue('media/preview-panel', visible)
        if hasattr(self, tr('sync_path_toolbar_alignment')):
            # Dock visibility changes the central area without resizing the
            # main window.  Run once after the dock layout has settled.
            QTimer.singleShot(0, self.sync_path_toolbar_alignment)
            QTimer.singleShot(80, self.sync_path_toolbar_alignment)
        if visible:
            self.schedule_media_preview()
        else:
            self.stop_media_playback()
            self._pdf_requested_key = None
            if self._pdf_worker is not None:
                self._pdf_worker.requestInterruption()
            if self._preview_worker is not None:
                self._preview_worker.requestInterruption()
            self.media_image.clear_preview()
            self._media_preview_cache.clear()

    @staticmethod
    def _media_clock(milliseconds):
        seconds = max(0, int(milliseconds) // 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return trf('\x1f0\x1f:\x1f1\x1f:\x1f2\x1f', hours, format(minutes, '02d'), format(seconds, '02d')) if hours else trf('\x1f0\x1f:\x1f1\x1f', minutes, format(seconds, '02d'))

    def ensure_media_player(self):
        if self.media_player is not None:
            return self.media_player
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
            from PySide6.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            self.ensure_components([tr('qt-multimedia')])
            return None
        if self.media_video is None:
            self.media_video = QVideoWidget()
            self.media_video.setMinimumSize(180, 150)
            self.media_video.installEventFilter(self)
            self.media_video.setMouseTracking(True)
            self.media_video.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.media_video.customContextMenuRequested.connect(self.show_preview_context)
            self.preview_stack.addWidget(self.media_video)
        self.media_player = QMediaPlayer(self)
        self._playing_state = QMediaPlayer.PlaybackState.PlayingState
        self._end_media_status = QMediaPlayer.MediaStatus.EndOfMedia
        self._audio_ready_statuses = {QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia}
        self.media_devices = QMediaDevices(self)
        default_device = QMediaDevices.defaultAudioOutput()
        self.media_audio = QAudioOutput(default_device, self) if not default_device.isNull() else QAudioOutput(self)
        self.media_devices.audioOutputsChanged.connect(self.refresh_media_audio_devices)
        initial_volume = self.media_volume_slider.value()
        self.media_audio.setVolume(initial_volume / 100)
        self.media_audio.setMuted(initial_volume == 0)
        self.media_player.setAudioOutput(self.media_audio)
        self.media_player.setVideoOutput(self.media_video)
        self.media_player.durationChanged.connect(self.media_duration_changed)
        self.media_player.positionChanged.connect(self.media_position_changed)
        self.media_player.playbackStateChanged.connect(self.media_playback_changed)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed)
        self.media_player.hasAudioChanged.connect(self.media_has_audio_changed)
        self.media_player.errorOccurred.connect(self.media_playback_error)
        self.refresh_media_audio_devices()
        return self.media_player

    @staticmethod
    def _media_audio_device_key(device):
        return bytes(device.id()).hex()

    def refresh_media_audio_devices(self):
        """List Qt outputs and keep the chosen one across hot-plug changes."""
        try:
            from PySide6.QtMultimedia import QMediaDevices
        except (ImportError, RuntimeError):
            return False
        outputs = QMediaDevices.audioOutputs()
        default_device = QMediaDevices.defaultAudioOutput()
        wanted = str(self.settings.value('media/audio-device-id', '') or '')
        combo = self.media_audio_device_combo
        blocked = combo.blockSignals(True)
        combo.clear()
        default_name = default_device.description() if not default_device.isNull() else tr('indisponible')
        combo.addItem(tr('Sortie audio du système') + tr(' — ') + default_name, '')
        selected = 0
        for device in outputs:
            key = self._media_audio_device_key(device)
            combo.addItem(device.description(), key)
            if wanted and key == wanted:
                selected = combo.count() - 1
        combo.setCurrentIndex(selected)
        combo.blockSignals(blocked)
        self.apply_media_audio_device()
        return bool(outputs)

    def apply_media_audio_device(self):
        if self.media_audio is None:
            return False
        try:
            from PySide6.QtMultimedia import QMediaDevices
            outputs = QMediaDevices.audioOutputs()
            wanted = str(self.media_audio_device_combo.currentData() or '')
            device = next((candidate for candidate in outputs if self._media_audio_device_key(candidate) == wanted), None) if wanted else QMediaDevices.defaultAudioOutput()
        except (ImportError, RuntimeError):
            return False
        if device is None or device.isNull():
            return False
        if self.media_audio.device() != device:
            self.media_audio.setDevice(device)
        self.apply_media_audio_output()
        return True

    def change_media_audio_device(self, *_):
        if not hasattr(self, tr('media_audio_device_combo')):
            return
        key = str(self.media_audio_device_combo.currentData() or '')
        self.settings.setValue('media/audio-device-id', key)
        if self.apply_media_audio_device():
            self.show_preview_message(tr('Sortie audio : ') + self.media_audio_device_combo.currentText(), 2500)

    def update_media_volume_icon(self):
        value = self.media_volume_slider.value() if hasattr(self, tr('media_volume_slider')) else 80
        name = tr('audio-volume-muted') if value == 0 else tr('audio-volume-low') if value < 35 else tr('audio-volume-medium') if value < 70 else tr('audio-volume-high')
        fallback = QStyle.StandardPixmap.SP_MediaVolumeMuted if value == 0 else QStyle.StandardPixmap.SP_MediaVolume
        self.media_volume_button.setIcon(themed_icon(name, self, fallback))
        if hasattr(self, tr('fullscreen_volume')):
            self.fullscreen_volume.setIcon(themed_icon(name, self, fallback))
        self.media_volume_label.setText(tr('Volume : ') + str(value) + tr(' %'))

    def apply_media_audio_output(self):
        if self.media_audio is None:
            return
        value = self.media_volume_slider.value()
        self.media_audio.setVolume(value / 100)
        self.media_audio.setMuted(value == 0)
        if self.media_player is not None and self.media_player.audioOutput() != self.media_audio:
            self.media_player.setAudioOutput(self.media_audio)

    def set_media_volume(self, value, persist=True):
        value = max(0, min(100, int(value)))
        blocked = self.media_volume_slider.blockSignals(True)
        self.media_volume_slider.setValue(value)
        self.media_volume_slider.blockSignals(blocked)
        if persist:
            self.settings.setValue('media/volume', value)
        self.update_media_volume_icon()
        self.apply_media_audio_output()

    def change_media_volume(self, value):
        self.set_media_volume(value, True)

    def show_media_volume_feedback(self):
        value = self.media_volume_slider.value()
        QToolTip.showText(QCursor.pos(), tr('Volume : ') + str(value) + tr(' %'), self.preview_stack, self.preview_stack.rect(), 1200)

    def adjust_media_volume(self, delta):
        if not delta:
            return False
        step = self.settings.value('media/volume-step-percent', 5, type=int)
        self.set_media_volume(self.media_volume_slider.value() + (step if delta > 0 else -step), True)
        self.show_media_volume_feedback()
        return True

    def _preview_wheel_position(self, event):
        """Return the wheel location in the coordinate system of the image."""
        try:
            return self.media_image.mapFromGlobal(event.globalPosition().toPoint())
        except AttributeError:
            return self.media_image.rect().center()

    def _show_preview_zoom(self):
        self.show_preview_message(
            trf('Zoom : 0 %', round(self.media_image._zoom * 100)), 1200)

    def preview_wheel(self, event):
        row = self._preview_pending
        if row is not None and Path(urllib.parse.urlparse(str(row.path)).path).suffix.lower() in ('.txt', '.docx'):
            # Text/document previews are static pages: wheel gestures must not
            # accidentally change media volume or seek the media player.
            return True
        vertical = event.angleDelta().y() or event.pixelDelta().y()
        zoom_gesture = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if vertical and is_pdf(self._preview_pending):
            if zoom_gesture:
                if self.media_image.adjust_zoom_at(vertical, self._preview_wheel_position(event)):
                    self._show_preview_zoom()
                return True
            # Touchpads and free-spinning wheels often emit several wheel
            # events for one gesture.  A PDF should turn one page at a time.
            if self._pdf_wheel_ready:
                self._pdf_wheel_ready = False
                self.advance_pdf_page(1 if vertical < 0 else -1)
                QTimer.singleShot(280, lambda: setattr(self, tr('_pdf_wheel_ready'), True))
            return True
        if row is not None and kind(row) == tr('image'):
            horizontal = event.angleDelta().x() or event.pixelDelta().x()
            if horizontal and abs(horizontal) > abs(vertical):
                self.show_adjacent_image(-1 if horizontal > 0 else 1)
                return True
            if zoom_gesture and vertical and self.media_image.adjust_zoom_at(
                    vertical, self._preview_wheel_position(event)):
                self._show_preview_zoom()
            return True
        if row is None or kind(row) not in (tr('video'), tr('audio')):
            # Images and ordinary document previews are static.  Wheel input
            # must never leak through to the previous media player's volume
            # or position controls.
            return True
        if vertical:
            self.adjust_media_volume(vertical)
            return True
        horizontal = event.angleDelta().x() or event.pixelDelta().x()
        if not horizontal or self._media_play_path is None or self.media_player is None:
            return False
        seconds = self.settings.value('media/seek-step-seconds', 10, type=int)
        step = -(seconds * 1000) if horizontal > 0 else seconds * 1000
        self.media_player.setPosition(max(0, min(self.media_player.duration(), self.media_player.position() + step)))
        self.show_preview_message((tr('Avance') if step > 0 else tr('Retour')) + tr(' de ') + str(seconds) + tr(' secondes'), 1200)
        return True

    def _render_pdf_page(self, width=None):
        """Request the selected PDF page without blocking the interface."""
        row = self._fullscreen_row if self._preview_fullscreen and self._fullscreen_row is not None else self._preview_pending
        if row is None or not is_pdf(row) or (not self.preview_dock.isVisible() and not self._preview_fullscreen):
            return False
        if self._pdf_preview_path != row.path:
            self._pdf_preview_path = row.path
            self._pdf_preview_page = 0
            self._pdf_page_count = 0
            self._pdf_pending_steps = 0
        if width is None:
            surface = self._preview_fullscreen_overlay if self._preview_fullscreen else self.media_image
            width = surface.width() * surface.devicePixelRatioF()
        width = max(640, min(3840, round(width)))
        signature = getattr(row, tr('file_signature'), None)
        key = (tr('pdf-page'), str(row.path), signature, self._pdf_preview_page, width)
        self._pdf_requested_key = key
        cached = self._media_preview_cache.get(key)
        if cached is not None:
            self._show_pdf_result(key, *cached)
            return True
        if self._pdf_worker is not None:
            if self._pdf_worker_key != key:
                self._pdf_worker.requestInterruption()
            return True
        worker = PdfPageWorker(row.path, self._pdf_preview_page, width)
        self._pdf_worker = worker
        self._pdf_worker_key = key
        delivered = False

        def ready(image, count):
            nonlocal delivered
            delivered = True
            if self._pdf_requested_key == key:
                self._media_preview_cache[key] = (image, count)
                self._show_pdf_result(key, image, count)

        def finished():
            self._pdf_worker = None
            worker.deleteLater()
            if getattr(self, tr('_media_close_pending'), False):
                QTimer.singleShot(0, self.close)
            elif self._pdf_requested_key is not None and (self._pdf_requested_key != key or not delivered):
                QTimer.singleShot(0, self._render_pdf_page)

        worker.ready.connect(ready)
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Création de l’aperçu PDF'))
        return True

    def _show_pdf_result(self, key, image, count):
        if key != self._pdf_requested_key:
            return
        self._pdf_page_count = count
        if self._pdf_pending_steps:
            steps, self._pdf_pending_steps = self._pdf_pending_steps, 0
            wanted = max(0, min(max(0, count - 1), self._pdf_preview_page + steps))
            if wanted != self._pdf_preview_page:
                self._pdf_preview_page = wanted
                QTimer.singleShot(0, self._render_pdf_page)
                return
        if image.isNull():
            self.media_image.setText(tr('Aperçu indisponible'))
            return
        self.media_image.set_preview(image)
        if count > 1:
            self.show_preview_message(tr('Page ') + str(self._pdf_preview_page + 1) + tr(' / ') + str(count), 1400)

    def advance_pdf_page(self, direction):
        """Use the mouse wheel over a PDF to move through its pages."""
        row = self._fullscreen_row if self._preview_fullscreen and self._fullscreen_row is not None else self._preview_pending
        if row is None or not is_pdf(row):
            return False
        if self._pdf_preview_path != row.path:
            self._pdf_preview_path = row.path
            self._pdf_preview_page = 0
            self._pdf_page_count = 0
            self._pdf_pending_steps = 0
        if not self._pdf_page_count:
            self._pdf_pending_steps += direction
            self._render_pdf_page()
            return True
        wanted = max(0, min(max(0, self._pdf_page_count - 1), self._pdf_preview_page + direction))
        if wanted == self._pdf_preview_page:
            return True
        self._pdf_preview_page = wanted
        return self._render_pdf_page()

    def media_duration_changed(self, value):
        self.media_position.setRange(0, max(0, value))
        self.media_position.setEnabled(value > 0)
        self.fullscreen_position.setRange(0, max(0, value))
        self.fullscreen_position.setEnabled(value > 0)
        self.media_position_changed(self.media_player.position())

    def media_position_changed(self, value):
        if not self.media_position.isSliderDown():
            self.media_position.setValue(value)
        if not self.fullscreen_position.isSliderDown():
            self.fullscreen_position.setValue(value)
        text = self._media_clock(value) + tr(' / ') + self._media_clock(self.media_player.duration())
        self.media_time.setText(text)
        self.fullscreen_time.setText(text)

    def set_preview_information_visible(self, visible):
        self.settings.setValue('media/preview-info-visible', visible)
        self.media_info.setVisible(visible)

    def update_preview_information_visibility(self):
        self.set_preview_information_visible(self.media_info_toggle.isChecked())

    def media_playback_changed(self, state):
        playing = state == getattr(self, tr('_playing_state'), None)
        self.media_play.setIcon(themed_icon(tr('media-playback-pause') if playing else tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay))
        self.media_play.setToolTip(tr('Mettre en pause') if playing else tr('Lire'))
        self.media_play.setAccessibleName(tr('Mettre en pause') if playing else tr('Lire'))
        self.fullscreen_play.setIcon(themed_icon(tr('media-playback-pause') if playing else tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay))
        self.fullscreen_play.setToolTip(tr('Mettre en pause') if playing else tr('Lire'))
        self.update_preview_information_visibility()

    def media_status_changed(self, status):
        if status in getattr(self, tr('_audio_ready_statuses'), set()):
            self.apply_media_audio_output()
        if status == getattr(self, tr('_end_media_status'), None) and self._preview_index + 1 < len(self._preview_playlist):
            QTimer.singleShot(0, lambda: self.play_media_at(self._preview_index + 1))

    def media_has_audio_changed(self, available):
        if not available and self._media_play_path is not None:
            self.show_preview_message(tr('Aucune piste audio reconnue par le lecteur intégré pour ce fichier.'), 8000)

    def media_playback_error(self, *_):
        message = self.media_player.errorString().strip() or tr('Le système ne peut pas lire ce média dans le panneau d’aperçu.')
        self.show_preview_message(tr('Lecture indisponible : ') + message, 10000)
        self.media_play.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.media_play.setToolTip(tr('Lire'))
        self.media_play.setAccessibleName(tr('Lire'))

    def update_playlist_controls(self):
        total = len(self._preview_playlist)
        index = self._preview_index
        multiple = total > 1
        previous = multiple and index > 0
        following = multiple and index + 1 < total
        self.media_previous.setVisible(multiple)
        self.media_next.setVisible(multiple)
        self.media_previous.setEnabled(previous)
        self.media_next.setEnabled(following)
        self.fullscreen_previous.setVisible(multiple)
        self.fullscreen_next.setVisible(multiple)
        self.fullscreen_previous.setEnabled(previous)
        self.fullscreen_next.setEnabled(following)
        text = str(index + 1) + tr(' / ') + str(total) if multiple else ''
        self.media_playlist_label.setText(text)
        self.media_playlist_label.setVisible(multiple)
        self.fullscreen_playlist_label.setText(text)
        self.fullscreen_playlist_label.setVisible(multiple)
        row = self._fullscreen_row if self._preview_fullscreen and self._fullscreen_row is not None else self._preview_pending
        playable = row is not None and kind(row) in (tr('video'), tr('audio'))
        for widget in (self.media_play, self.media_volume_button, self.media_position, self.media_time):
            widget.setVisible(playable)
        self.media_play.setEnabled(playable)
        self.media_info_toggle.setVisible(row is not None)
        self.preview_open_button.setVisible(playable or is_openable_document(row))
        for widget in (self.fullscreen_play, self.fullscreen_volume, self.fullscreen_position, self.fullscreen_time):
            widget.setVisible(playable)
        if self._preview_fullscreen:
            self._fullscreen_controls.setVisible(playable or multiple)
            self.position_fullscreen_content()

    def _hold_fullscreen_controls(self):
        self._fullscreen_controls_timer.stop()

    def _hide_fullscreen_controls(self):
        if self._preview_fullscreen:
            self.show_fullscreen_controls()

    def show_fullscreen_controls(self):
        if not self._preview_fullscreen:
            return
        row = self._fullscreen_row if self._fullscreen_row is not None else self._preview_pending
        if row is None or (kind(row) not in (tr('video'), tr('audio')) and len(self._preview_playlist) < 2):
            self._fullscreen_controls.hide()
            self.position_fullscreen_content()
            return
        self._fullscreen_reveal_zone.hide()
        self.position_fullscreen_controls()
        self._fullscreen_controls.show()
        self._fullscreen_controls.raise_()
        self._fullscreen_opacity.setOpacity(1)
        self.set_fullscreen_controls_interactive(True)

    def set_fullscreen_controls_interactive(self, enabled):
        for child in self._fullscreen_controls.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not enabled)

    def reveal_fullscreen_at(self, position):
        if not self._preview_fullscreen:
            return False
        overlay = self._preview_fullscreen_overlay
        if not overlay.rect().contains(position):
            return False
        reveal_height = max(72, self._fullscreen_controls.height() + 20)
        if position.y() < overlay.height() - reveal_height:
            return False
        self.show_fullscreen_controls()
        return True

    def poll_fullscreen_cursor(self):
        if not self._preview_fullscreen:
            self._fullscreen_cursor_timer.stop()
            return
        self.reveal_fullscreen_at(self._preview_fullscreen_overlay.mapFromGlobal(QCursor.pos()))

    def position_fullscreen_controls(self):
        overlay = self._preview_fullscreen_overlay
        height = max(58, self._fullscreen_controls.sizeHint().height())
        self._fullscreen_controls.setGeometry(0, max(0, overlay.height() - height), overlay.width(), height)

    def position_fullscreen_content(self):
        tr('Reserve stable, native-safe areas for picture and control bar.')
        content = self._fullscreen_content_widget
        if not self._preview_fullscreen or content is None:
            return
        overlay = self._preview_fullscreen_overlay
        bar_height = self._fullscreen_controls.height() if self._fullscreen_controls.isVisible() else 0
        content.setGeometry(0, 0, overlay.width(), max(1, overlay.height() - bar_height))
        self.position_fullscreen_controls()

    def update_fullscreen_content(self):
        tr('Move the current visual preview without leaving fullscreen.')
        if not self._preview_fullscreen:
            return
        row = self._preview_pending
        wanted = self.media_video if row is not None and kind(row) == tr('video') and (self.media_video is not None) else self.media_image
        if wanted is self._fullscreen_content_widget:
            return
        previous = self._fullscreen_content_widget
        if previous is not None:
            previous.hide()
            previous.setParent(self.preview_stack)
            self.preview_stack.addWidget(previous)
        self.preview_stack.removeWidget(wanted)
        wanted.setParent(self._preview_fullscreen_overlay)
        wanted.show()
        self._fullscreen_content_widget = wanted
        self.position_fullscreen_content()

    def position_fullscreen_reveal_zone(self):
        overlay = self._preview_fullscreen_overlay
        height = min(24, max(12, overlay.height() // 20))
        self._fullscreen_reveal_zone.setGeometry(0, max(0, overlay.height() - height), overlay.width(), height)

    def show_preview_context(self, *_):
        if self._preview_pending is not None and kind(self._preview_pending) in (tr('video'), tr('audio')):
            self.toggle_media_playback()

    def play_media_at(self, index):
        if not 0 <= index < len(self._preview_playlist):
            return
        row = self._preview_playlist[index]
        self._preview_index = index
        self._preview_pending = row
        self.update_playlist_controls()
        if kind(row) not in (tr('video'), tr('audio')):
            self.stop_media_playback()
            self._preview_index = index
            self._preview_pending = row
            self.update_playlist_controls()
            self.update_fullscreen_content()
            self.media_image.clear_preview()
            self.start_media_preview()
            return
        player = self.ensure_media_player()
        if player is None:
            return
        if self._media_play_path == row.path:
            player.play()
            return
        self.stop_media_playback()
        self._preview_index = index
        self._preview_pending = row
        self.update_playlist_controls()
        # Videos intentionally begin silent, but the wheel and slider must be
        # able to unmute the existing audio sink immediately afterwards.
        if kind(row) == tr('video'):
            self.set_media_volume(0, False)
        else:
            self.set_media_volume(self.settings.value('media/volume', 80, type=int), False)
        self._media_play_path = row.path
        self.apply_media_audio_device()
        self.apply_media_audio_output()
        player.setSource(QUrl.fromLocalFile(str(row.path)))
        QTimer.singleShot(300, self.apply_media_audio_output)
        self.preview_stack.setCurrentWidget(self.media_video if kind(row) == tr('video') and self.media_video is not None else self.media_image)
        self.update_fullscreen_content()
        self.remember_played_media(row.path)
        player.play()
        self.start_media_preview()

    def play_adjacent_media(self, direction):
        self.play_media_at(self._preview_index + direction)

    def show_adjacent_image(self, direction):
        """Show the preceding or following image from the active folder."""
        row = self._preview_pending
        if row is None or kind(row) != tr('image'):
            return False
        images = [self.row(self.proxy.index(index, 0)) for index in range(self.proxy.rowCount())]
        images = [candidate for candidate in images if not candidate.is_dir and kind(candidate) == tr('image')]
        try:
            current = next(index for index, candidate in enumerate(images) if candidate.path == row.path)
        except StopIteration:
            return False
        target = current + direction
        if not 0 <= target < len(images):
            return False
        self.stop_media_playback()
        self._preview_playlist = images
        self._preview_index = target
        self._preview_pending = images[target]
        self.update_playlist_controls()
        self.media_image.clear_preview()
        self._preview_document_image = False
        self.start_media_preview()
        return True

    def toggle_media_playback(self):
        if not self._preview_playlist or self._preview_pending is None or kind(self._preview_pending) not in (tr('video'), tr('audio')):
            self.show_preview_message(tr('Sélectionnez une ou plusieurs vidéos ou sons pour les lire.'), 6000)
            return
        player = self.ensure_media_player()
        if player is None:
            return
        row = self._preview_pending
        if self._media_play_path == row.path:
            if player.playbackState() == self._playing_state:
                player.pause()
            else:
                player.play()
            return
        self.play_media_at(self._preview_index)

    def toggle_preview_fullscreen(self):
        tr('Toggle a full-screen overlay owned by the main Mirivue window.')
        row = self._fullscreen_row if self._preview_fullscreen and self._fullscreen_row is not None else self._preview_pending
        if row is None or (kind(row) not in (tr('video'), tr('image')) and not is_pdf(row) and not self._preview_document_image):
            return False
        if not self._preview_fullscreen:
            self._preview_fullscreen = True
            self._fullscreen_row = row
            self._preview_was_maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)
            self._preview_window_geometry = self.saveGeometry()
            self._preview_dock_width = max(1, self.preview_dock.width())
            self._preview_fullscreen_overlay.setGeometry(self.rect())
            content = self.media_video if kind(row) == tr('video') and self.media_video is not None else self.media_image
            self._fullscreen_content_widget = content
            self.preview_stack.removeWidget(content)
            self._preview_fullscreen_layout.removeWidget(content)
            content.setParent(self._preview_fullscreen_overlay)
            self._fullscreen_controls.setParent(self._preview_fullscreen_overlay)
            self._preview_fullscreen_overlay.show()
            self._preview_fullscreen_overlay.raise_()
            self.showFullScreen()
            self._preview_fullscreen_overlay.setGeometry(self.rect())
            self.position_fullscreen_content()
            content.show()
            if is_pdf(row):
                # The dock uses a compact rendition; redraw at the full-screen
                # surface resolution after Qt has completed its layout pass.
                QTimer.singleShot(0, self._render_pdf_page)
            elif self._preview_document_image:
                # Re-request through KIO after the fullscreen layout settles,
                # so the document thumbnail is rendered at the larger size.
                QTimer.singleShot(0, self.start_media_preview)
            elif kind(row) == tr('image'):
                # The dock deliberately uses a compact image.  Do not enlarge
                # that 640 px rendition on a full-screen surface: reload from
                # the original file after the full-screen geometry is known.
                QTimer.singleShot(0, self.start_media_preview)
            self.show_fullscreen_controls()
            self._fullscreen_cursor_timer.start()
            return True
        self._preview_fullscreen = False
        self._fullscreen_row = None
        self._fullscreen_controls_timer.stop()
        self._fullscreen_cursor_timer.stop()
        self._fullscreen_controls.hide()
        self._fullscreen_reveal_zone.hide()
        content = self._fullscreen_content_widget
        if content is not None:
            self._preview_fullscreen_layout.removeWidget(content)
            self.preview_stack.addWidget(content)
            self.preview_stack.setCurrentWidget(content)
        self._fullscreen_content_widget = None
        self._preview_fullscreen_overlay.hide()
        was_maximized = self._preview_was_maximized
        geometry = self._preview_window_geometry
        dock_width = self._preview_dock_width
        self.showNormal()
        if was_maximized:
            QTimer.singleShot(0, self.showMaximized)
        elif geometry:
            QTimer.singleShot(0, lambda saved=geometry: self.restoreGeometry(saved))
        if dock_width:

            def restore_dock_width(width=dock_width):
                dock = self.preview_dock
                dock.setMinimumWidth(width)
                dock.setMaximumWidth(width)
                self.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
                # Restoring the normal window and its toolbars can trigger a
                # later layout pass. Apply the saved dock width once more
                # after that pass, then release the temporary constraint.
                def finish_restore():
                    self.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
                    QTimer.singleShot(150, lambda: (dock.setMinimumWidth(0), dock.setMaximumWidth(16777215)))
                QTimer.singleShot(50, finish_restore)
            QTimer.singleShot(0, lambda: QTimer.singleShot(0, restore_dock_width))
        self._preview_window_geometry = None
        self._preview_dock_width = None
        return True

    def resize_preview_fullscreen_overlay(self):
        if self._preview_fullscreen and self._preview_fullscreen_overlay is not None:
            self._preview_fullscreen_overlay.setGeometry(self.rect())
            self.position_fullscreen_content()
            self.position_fullscreen_reveal_zone()

    def seek_media(self, value):
        if self._media_play_path is not None and self.media_player is not None:
            self.media_player.setPosition(value)

    def stop_media_playback(self):
        if self.media_player is not None:
            self.media_player.stop()
            self.media_player.setSource(QUrl())
        self._media_play_path = None
        self.media_position.setRange(0, 0)
        self.media_position.setEnabled(False)
        self.fullscreen_position.setRange(0, 0)
        self.fullscreen_position.setEnabled(False)
        self.media_time.setText(tr('0:00 / 0:00'))
        self.fullscreen_time.setText(tr('0:00 / 0:00'))
        self.media_play.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.media_play.setToolTip(tr('Lire'))
        self.media_play.setAccessibleName(tr('Lire'))
        self.fullscreen_play.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.fullscreen_play.setToolTip(tr('Lire'))
        self.update_preview_information_visibility()
        if hasattr(self, tr('preview_stack')):
            self.preview_stack.setCurrentWidget(self.media_image)

    def schedule_media_preview(self, *_):
        if hasattr(self, tr('media_preview_timer')) and self.preview_dock.isVisible():
            self.media_preview_timer.start()

    def update_media_preview(self):
        if not self.preview_dock.isVisible():
            return
        rows = [self.row(i) for i in self.selected_indexes()]
        if not rows and self.settings.value('media/preview-first-item', False, type=bool):
            for index in range(self.proxy.rowCount()):
                row = self.row(self.proxy.index(index, 0))
                if not row.is_dir:
                    rows = [row]
                    break
        playlist = rows
        current = self._media_play_path
        self._preview_playlist = playlist
        if current is not None:
            positions = [i for i, row in enumerate(playlist) if row.path == current]
            if positions:
                self._preview_index = positions[0]
            else:
                self.stop_media_playback()
                self._preview_index = 0
        elif self._preview_index >= len(playlist):
            self._preview_index = 0
        self._preview_pending = playlist[self._preview_index] if playlist else None
        self._pdf_requested_key = None
        if self._pdf_worker is not None:
            self._pdf_worker.requestInterruption()
        self.update_playlist_controls()
        if self._media_play_path is None:
            self.preview_stack.setCurrentWidget(self.media_image)
        self.media_image.clear_preview()
        self._preview_document_image = False
        if self._preview_worker:
            self._preview_worker.requestInterruption()
            return
        self.start_media_preview()

    def start_media_preview(self):
        row = self._preview_pending
        if row is None:
            self.media_info.setPlainText(tr('Sélectionnez un média pour afficher son aperçu.'))
            return
        lines = [row.path.name, row.values[17]]
        lines += [trf('\x1f0\x1f : \x1f1\x1f', name, row.values[col]) for name, col in [(tr('Taille'), 1), (tr('Durée'), 2), (tr('Résolution'), 3), (tr('Format'), 29)] if row.values[col]]
        if row.media_tags:
            lines += ['', tr('Métadonnées / EXIF') if kind(row) == tr('image') else tr('Métadonnées')] + [trf('\x1f0\x1f : \x1f1\x1f', FIELDS.get(key, key), value) for key, value in row.media_tags.items() if value]
        technical_names = {tr('width'): tr('Largeur'), tr('height'): tr('Hauteur'), tr('mode'): tr('Mode colorimétrique'), tr('frames'): tr('Nombre d’images'), tr('sample_rate'): tr('Fréquence audio'), tr('bitrate'): tr('Débit'), tr('channels'): tr('Canaux'), tr('bits'): tr('Profondeur audio'), tr('format'): tr('Format technique'), tr('camera_make'): tr('Fabricant de l’appareil'), tr('camera_model'): tr('Modèle de l’appareil'), tr('exposure'): tr('Temps de pose'), tr('aperture'): tr('Ouverture'), tr('iso'): tr('Sensibilité ISO'), tr('focal_length'): tr('Distance focale')}
        extra = [trf('\x1f0\x1f : \x1f1\x1f', technical_names.get(key, key), value) for key, value in row.media_technical.items() if value and key not in (tr('width'), tr('height'), tr('format'))]
        if extra:
            lines += ['', tr('Données techniques / EXIF')] + extra
        self.media_info.setPlainText(tr('\n').join(lines))
        if row.is_dir:
            self.media_image.show_folder_hint()
            return
        document_preview = is_openable_document(row) or (kind(row) not in (tr('video'), tr('audio'), tr('image')) and not is_pdf(row))
        fullscreen_image = self._preview_fullscreen and kind(row) == tr('image')
        # PDFs must be rendered at the preview surface's current resolution;
        # the generic 640 px worker thumbnail is only suitable for quick
        # image previews and becomes visibly soft when the dock is enlarged.
        if is_pdf(row):
            self._render_pdf_page()
            return
        if document_preview:
            # Office/text preview renderers frequently expose a bare white
            # sheet when the document has no usable thumbnail.  A concise
            # empty state is clearer and leaves the native application as the
            # place to read or edit the document.  PDFs keep their dedicated
            # renderer above.
            self.media_image.show_unavailable_document(default_application_icon(row.path))
            return
        target_size = QSize(max(640, round(self.media_image.width() * self.media_image.devicePixelRatioF())), max(480, round(self.media_image.height() * self.media_image.devicePixelRatioF()))) if document_preview or fullscreen_image else None
        key = (str(row.path), getattr(row, tr('file_signature'), None), (target_size.width(), target_size.height()) if target_size else None)
        cached = self._media_preview_cache.get(key)
        if cached is not None:
            if cached.isNull():
                self.media_image.setText(tr('Aperçu indisponible'))
            else:
                self._preview_document_image = document_preview
                self.media_image.set_preview(cached)
            return
        thumbnail = self.model.thumbnails.get(row.path)
        if not document_preview and not fullscreen_image and thumbnail is not None and (not thumbnail.isNull()):
            image = thumbnail.pixmap(640, 640).toImage()
            self._media_preview_cache[key] = image
            self.media_image.set_preview(image)
            return
        worker = PreviewWorker(row, target_size)
        self._preview_worker = worker

        def ready(data):
            if self._preview_pending is row and (self.preview_dock.isVisible() or self._preview_fullscreen):
                image = QImage.fromData(data)
                self._media_preview_cache[key] = image
                if image.isNull():
                    self.media_image.setText(tr('Aperçu indisponible'))
                else:
                    self._preview_document_image = document_preview
                    self.media_image.set_preview(image)

        def finished():
            self._preview_worker = None
            worker.deleteLater()
            if getattr(self, tr('_media_close_pending'), False):
                QTimer.singleShot(0, self.close)
            elif self.preview_dock.isVisible() and self._preview_pending is not row:
                QTimer.singleShot(0, self.start_media_preview)
        worker.ready.connect(ready)
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Création de l’aperçu'))

    def add_media_context(self, menu, rows):
        media = [r for r in rows if kind(r) in (tr('video'), tr('audio'), tr('image'))]
        if not media:
            return
        menu.addAction(tr('Rechercher des informations sur ce média'), self.online_media_search)

    def selected_media_rows(self):
        return [self.row(i) for i in self.selected_indexes() if kind(self.row(i)) in (tr('video'), tr('audio'), tr('image'))]

    def edit_metadata(self, *_):
        rows = self.selected_media_rows()
        if not rows:
            QMessageBox.information(self, tr('Métadonnées'), tr('Sélectionnez un ou plusieurs médias.'))
            return
        if self.scanning or self.movement_locked([r.path for r in rows]):
            QMessageBox.information(self, tr('Traitement en cours'), tr('Attendez la fin du chargement ou de l’opération sur ces médias.'))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Métadonnées'))
        dialog.resize(1080, 680)
        dialog.setMinimumSize(680, 430)
        layout = QVBoxLayout(dialog)
        allowed_by_row = []
        for row in rows:
            allowed_by_row.append(set(FIELDS) if kind(row) == tr('audio') else {tr('title'), tr('description'), tr('keywords'), tr('author'), tr('copyright'), tr('date_taken')})
        fields = [key for key in FIELDS if any((key in allowed for allowed in allowed_by_row))]
        table = QTableWidget(len(rows), len(fields) + 1)
        table.setObjectName(tr('metadata-table'))
        table.setHorizontalHeaderLabels([tr('Fichier')] + [FIELDS[key] for key in fields])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        table.setAlternatingRowColors(True)
        originals = {}
        for row_index, row in enumerate(rows):
            name = QTableWidgetItem(row.path.name)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name.setToolTip(str(row.path))
            table.setItem(row_index, 0, name)
            for column, key in enumerate(fields, 1):
                value = row.media_tags.get(key, '') if key in allowed_by_row[row_index] else ''
                item = QTableWidgetItem(value)
                originals[row_index, key] = value
                if key not in allowed_by_row[row_index]:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setText(tr('—'))
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)
        suggestion_button = QPushButton(tr('Proposer à partir des noms'))
        suggestion_button.setToolTip(tr('Remplit seulement les cellules vides à partir du nom du fichier et de son dossier, sans recherche en ligne.'))
        suggestion_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        write_in_file = QCheckBox(tr('Enregistrer dans le fichier lorsque le format le permet'))
        write_in_file.setChecked(True)
        write_in_file.setToolTip(tr('Décochez pour ne pas modifier le média et utiliser uniquement un fichier compagnon XMP.'))

        def add_suggestions():
            for row_index, row in enumerate(rows):
                for key, value in suggestions(row).items():
                    if key not in fields or key not in allowed_by_row[row_index]:
                        continue
                    item = table.item(row_index, fields.index(key) + 1)
                    if item and (not item.text().strip()):
                        item.setText(value)
        suggestion_button.clicked.connect(add_suggestions)
        options = QHBoxLayout()
        options.addWidget(suggestion_button)
        options.addStretch(1)
        options.addWidget(write_in_file)
        metadata_help = tr('Modifiez directement les cellules nécessaires : les champs inchangés ne sont pas réécrits. « Proposer à partir des noms » complète uniquement les cellules vides avec des suggestions locales. Mirivue ne réencode pas le média, vérifie le résultat avant remplacement et utilise un fichier compagnon XMP si l’écriture interne est désactivée ou impossible.')
        options.addWidget(context_help_button(dialog, metadata_help))
        layout.addLayout(options)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Voir les modifications…'))
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.deleteLater()
            return
        plans = []
        for row_index, row in enumerate(rows):
            values = {}
            for column, key in enumerate(fields, 1):
                if key not in allowed_by_row[row_index]:
                    continue
                value = table.item(row_index, column).text().strip()
                if value != originals[row_index, key]:
                    values[key] = value
            if not values:
                continue
            route = native_route(row) if write_in_file.isChecked() else tr('xmp')
            if route == tr('audio') and any((k in values for k in (tr('author'), tr('date_taken')))):
                route = tr('xmp')
            if route == tr('image'):
                from .media_tags import EXIF
                if any((k not in EXIF for k in values)):
                    route = tr('xmp')
            plans.append((row, values, route))
        dialog.deleteLater()
        self.review_metadata(plans)

    def review_metadata(self, plans, explanation=''):
        if not plans:
            QMessageBox.information(self, tr('Métadonnées'), tr('Aucune modification proposée.'))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Vérifier les modifications'))
        dialog.resize(1050, 600)
        layout = QVBoxLayout(dialog)
        count = len(plans)
        message = explanation or tr('Seuls les champs ci-dessous seront modifiés. Les originaux réécrits seront sauvegardés.')
        if count > 1:
            message = tr('Vous allez modifier les métadonnées de ') + str(count) + tr(' fichiers. Vérifiez la liste puis confirmez l’enregistrement.\n') + message
        layout.addWidget(QLabel(message))
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([tr('Fichier'), tr('Champ'), tr('Avant'), tr('Après'), tr('Enregistrement')])
        layout.addWidget(table)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        displayed = 0
        for row, changes, route in plans:
            for key, value in changes.items():
                if displayed >= 1000:
                    continue
                displayed += 1
                i = table.rowCount()
                table.insertRow(i)
                for j, text in enumerate((row.path.name, FIELDS.get(key, tr('Note personnelle') if key == tr('rating') else tr('Pochette')), row.media_tags.get(key, tr('—')), value or tr('(effacer)'), str(companion(row.path)) if route == tr('xmp') else tr('Intégré au MKV (avec sauvegarde)') if route == tr('mkv') else tr('Intégré au fichier'))):
                    table.setItem(i, j, QTableWidgetItem(str(text)))
        if sum((len(c) for _, c, _ in plans)) > 1000:
            layout.addWidget(QLabel(trf('Aperçu limité à 1 000 champs ; la validation porte sur les \x1f0\x1f fichiers sélectionnés.', len(plans))))
        table.resizeColumnsToContents()
        review_help = QHBoxLayout()
        review_help.addStretch(1)
        review_help.addWidget(context_help_button(dialog, tr('Les suggestions sont à vérifier. Aucun fichier n’est envoyé sur Internet.')))
        layout.addLayout(review_help)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        if count > 1:
            buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Enregistrer pour les ') + str(count) + tr(' fichiers'))
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self.start_metadata_write(plans)

    def start_metadata_write(self, plans):
        if self._metadata_worker or self._inline_operation is not None or any((p.scanning and any((Path(p.folder or '') == r.path.parent for r, _, _ in plans)) for p in self.panes)) or self.movement_locked([r.path for r, _, _ in plans]):
            QMessageBox.information(self, tr('Traitement en cours'), tr('Ces fichiers sont utilisés par une opération. Réessayez après sa fin.'))
            return
        from . import library
        plans = [(library.decode_row(library.encode_row(r)), dict(c), route) for r, c, route in plans]
        worker = TagWorker(plans)
        self._metadata_worker = worker
        self.begin_inline_operation(worker, tr('Métadonnées'))

        def update(done, total, name):
            self.update_inline_operation(tr('Métadonnées — ') + name, done, total)
        worker.progress.connect(update)

        def finished():
            self._metadata_worker = None
            self.finish_inline_operation(worker)
            from .extensions import fingerprint
            for row, _, _ in plans:
                if row.path in worker.done:
                    row.file_signature = fingerprint(row.path)
                    self.saved_results.pop(str(row.path), None)
                    self.result_cache.pop(row.path, None)
            library.write(self.settings, tr('results'), self.saved_results)
            if not getattr(self, tr('_media_close_pending'), False):
                self.refresh_visible_entries(worker.done)
            if worker.errors:
                box = QMessageBox(self)
                box.setWindowTitle(tr('Rapport des métadonnées'))
                box.setText(trf('\x1f0\x1f fichier(s) enregistrés ; \x1f1\x1f échec(s).', len(worker.done), len(worker.errors)))
                box.setDetailedText(tr('\n').join(worker.errors))
                box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                box.show()
            summary = trf('\x1f0\x1f fichier(s) enregistrés — \x1f1\x1f sauvegarde(s).', len(worker.done), len(worker.backups))
            from .backup_policy import legacy_backups
            old = sum(len(legacy_backups(row.path if route != tr('xmp') else companion(row.path)))
                      for row, _, route in plans if row.path in worker.done)
            if len(worker.backups) == 1:
                summary += tr(' Original conservé : ') + worker.backups[0]
            elif worker.backups:
                summary += tr(' Originaux conservés à côté des médias modifiés.')
            if old:
                summary += trf(' \x1f0\x1f ancienne(s) sauvegarde(s) conservée(s) : voir RECUPERATION.md.', old)
            self.show_activity_message(summary, 12000)
            worker.deleteLater()
            if getattr(self, tr('_media_close_pending'), False):
                QTimer.singleShot(0, self.close)
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Écriture des métadonnées'))

    def media_locked(self, paths):
        worker = getattr(self, tr('_metadata_worker'), None)
        if not worker:
            return False
        used = {p.resolve() for p in worker.paths} | {companion(p).resolve() for p in worker.paths}
        return any(((p := Path(path).resolve()) in used or any((p in u.parents or u in p.parents for u in used)) for path in paths))

    def allow_media_close(self):
        self.stop_media_playback()
        workers = [w for w in (getattr(self, tr('_metadata_worker'), None), getattr(self, tr('_preview_worker'), None), getattr(self, tr('_pdf_worker'), None)) if w is not None]
        if not workers:
            return True
        self._media_close_pending = True
        for worker in workers:
            worker.requestInterruption()
        self.show_activity_message(tr('Arrêt des traitements multimédias après sécurisation…'))
        return False

    def online_media_search(self):
        rows = self.selected_media_rows()
        if len(rows) != 1:
            QMessageBox.information(self, tr('Recherche en ligne'), tr('Sélectionnez un seul média.'))
            return
        row = rows[0]
        proposed = tr(' ').join((row.media_tags.get(k, '') for k in (tr('artist'), tr('title')))).strip() or row.path.stem
        query, ok = QInputDialog.getText(self, tr('Recherche en ligne sur demande'), tr('Seuls ces mots seront transmis au moteur de recherche dans votre navigateur. Aucun fichier média ne sera envoyé.'), text=proposed)
        if ok and query.strip():
            services.open_kio_location(tr('https://duckduckgo.com/?q=') + urllib.parse.quote(query.strip()))

    def rename_from_metadata(self):
        rows = self.selected_media_rows()
        if rows:
            self._rename_rows(rows, initial_method='metadata')

    def organize_media(self):
        rows = self.selected_media_rows()
        if not rows or self.movement_locked([r.path for r in rows]):
            return
        field, ok = QInputDialog.getItem(self, tr('Organiser les médias'), tr('Créer des sous-dossiers dans le dossier actuel selon :'), [tr('Artiste'), tr('Album'), tr('Date de prise de vue')], editable=False)
        if not ok:
            return
        key = {tr('Artiste'): tr('artist'), tr('Album'): tr('album'), tr('Date de prise de vue'): tr('date_taken')}[field]
        plans = []
        folders = set()
        for row in rows:
            value = row.media_tags.get(key, '').strip()
            if not value:
                QMessageBox.information(self, tr('Métadonnées manquantes'), trf('\x1f0\x1f : renseignez le champ « \x1f1\x1f » avant de regrouper cette sélection.', row.path.name, field))
                return
            if key == tr('date_taken'):
                value = value[:10].replace(tr(':'), tr('-'))
            name = re.sub(tr('[/\\\\\\x00-\\x1f]'), tr('_'), value).strip().strip(tr('.'))
            if not name or len(name.encode()) > 180:
                QMessageBox.warning(self, tr('Nom de dossier invalide'), tr('Une métadonnée ne permet pas de proposer un nom de dossier valide.'))
                return
            folder = Path(self.folder) / name
            target = folder / row.path.name
            if folder.is_symlink() or (folder.exists() and (not folder.is_dir())) or target.exists() or companion(target).exists():
                QMessageBox.warning(self, tr('Destination indisponible'), str(target) + tr(' existe déjà ou le dossier de destination n’est pas utilisable. Aucun déplacement effectué.'))
                return
            folders.add(folder)
            plans.append((row.path, target))
        if len({target for _, target in plans}) != len(plans):
            QMessageBox.warning(self, tr('Noms identiques'), tr('Plusieurs fichiers auraient le même nom de destination.'))
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr('Vérifier l’organisation'))
        box.setText(trf('Déplacer \x1f0\x1f média(s) dans \x1f1\x1f sous-dossier(s) ? Les fichiers compagnons XMP suivent les médias.', len(plans), len(folders)))
        box.setDetailedText(tr('\n').join((trf('\x1f0\x1f → \x1f1\x1f', source, target) for source, target in plans)))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        if self.movement_locked([r.path for r in rows]):
            return
        for folder in sorted(folders):
            if folder.exists():
                continue
            ok, error = services.create_directory(self.folder, folder.name, require_undo=True)
            if not ok:
                QMessageBox.warning(self, tr('Création impossible'), error)
                return
            self.record_kio_history()
        self.move_entries([r.path for r in rows], Path(self.folder), confirmed=True, plans_override=plans)

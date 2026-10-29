# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Original Mirivue XMLGUI adapter and lossless legacy toolbar migration."""
import ctypes
import json
import os
import xml.etree.ElementTree as ET
from PySide6.QtCore import QObject, QEvent, QSize, Qt, QSettings
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import (QWidget, QToolButton, QSizePolicy, QStyle,
                              QStyleOption, QDialog, QMessageBox)
import shiboken6
from .i18n import tr

BAR_NAMES = ('before_paths', 'after_paths')


def encode_legacy(order, hidden, before, labels):
    root = ET.Element('gui', {'name':'mirivue-toolbar-editor', 'version':'1', 'translationDomain':'mirivue'})
    for name, title in zip(BAR_NAMES, (tr('Commandes avant les chemins'), tr('Commandes après les chemins'))):
        bar = ET.SubElement(root, 'ToolBar', {'name':name})
        ET.SubElement(bar, 'text').text = title
        for command in order:
            if command in labels and command not in hidden and (command in before) == (name == 'before_paths'):
                ET.SubElement(bar, 'Action', {'name':command})
    return ET.tostring(root, encoding='unicode')


def decode(document, known):
    if not isinstance(document, str) or len(document.encode('utf-8')) > 1024*1024:
        raise ValueError('Invalid toolbar document')
    root = ET.fromstring(document)
    if root.tag != 'gui': raise ValueError('Invalid toolbar root')
    bars = {name:[] for name in BAR_NAMES}
    properties = {}
    for bar in root.findall('ToolBar'):
        name = bar.get('name')
        if name not in bars: continue
        for child in bar:
            if child.tag == 'Action' and child.get('name') in known:
                bars[name].append(('action', child.get('name')))
            elif child.tag in ('Separator', 'Spacer'):
                bars[name].append((child.tag.lower(), ''))
    for action in root.findall('./ActionProperties/Action'):
        if action.get('name') in known:
            properties[action.get('name')] = {key:value for key,value in action.attrib.items()
                                               if key in ('icon', 'iconText', 'priority')}
    return bars, properties


class Separator(QWidget):
    """Draw with the active QStyle, with its native separator metrics."""
    def sizeHint(self):
        return QSize(self.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarSeparatorExtent),
                     self.fontMetrics().height())
    def paintEvent(self, event):
        option = QStyleOption(); option.initFrom(self)
        option.state |= QStyle.StateFlag.State_Horizontal
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorToolBarSeparator, option, painter, self)


class Mirror(QObject):
    def __init__(self, source, target):
        super().__init__(target)
        self.source, self.target = source, target
        source.installEventFilter(self)
        target.clicked.connect(lambda checked=False: source.click())
        source.toggled.connect(target.setChecked)
        self.sync()
    def sync(self):
        self.target.setEnabled(self.source.isEnabled())
        self.target.setToolTip(self.source.toolTip())
        self.target.setCheckable(self.source.isCheckable())
        self.target.setChecked(self.source.isChecked())
        self.target.setVisible(not self.source.isHidden())
    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.EnabledChange, QEvent.Type.ToolTipChange, QEvent.Type.Show, QEvent.Type.Hide):
            self.sync()
        return False


def render(window, bars, properties):
    """Render the two XMLGUI command groups; leave the path containers intact."""
    from .desktop import TOOLBAR
    known = dict(TOOLBAR)
    for item in getattr(window, '_toolbar_xml_widgets', []):
        if item.property('_mirivue_native_menu_clone'):
            window.menu_visibility.open_action.releaseWidget(item)
        else:
            item.hide(); item.deleteLater()
    window._toolbar_xml_widgets = []
    if not hasattr(window, '_toolbar_presentations'):
        window._toolbar_presentations = {
            name:(getattr(window,name).icon(), getattr(window,name).text(),
                  getattr(window,name).toolButtonStyle() if isinstance(getattr(window,name),QToolButton)
                  else Qt.ToolButtonStyle.ToolButtonIconOnly) for name in known}
    # XMLGUI permits a command in both toolbars. Mirror widgets share its behavior.
    used = set()
    for name in known:
        widget = getattr(window, name)
        icon,text,style = window._toolbar_presentations[name]
        values = properties.get(name,{})
        widget.setIcon(QIcon.fromTheme(values['icon']) if 'icon' in values else icon)
        widget.setText(values.get('iconText', text))
        if isinstance(widget,QToolButton):
            widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly
                if values.get('priority') == '0' else
                window.navigation_bar.toolButtonStyle() if values else style)
        widget.hide()
    for bar_name,layout in zip(BAR_NAMES,(window.left_toolbar_layout,window.right_toolbar_layout)):
        for kind,name in bars[bar_name]:
            if kind == 'action':
                source = getattr(window,name)
                if name in used:
                    if name == 'menu_button' and getattr(getattr(window, 'menu_visibility', None), 'native', False):
                        widget = window.menu_visibility.open_action.requestWidget(window)
                        widget.setProperty('_mirivue_native_menu_clone', True)
                    else:
                        widget = QToolButton(window)
                        widget.setIcon(source.icon()); widget.setText(source.text())
                        if isinstance(source,QToolButton):
                            widget.setToolButtonStyle(source.toolButtonStyle())
                            widget.setMenu(source.menu()); widget.setPopupMode(source.popupMode())
                        Mirror(source,widget)
                        for action in source.actions():
                            widget.addAction(action)
                    window._toolbar_xml_widgets.append(widget)
                else:
                    widget = source
                    used.add(name)
                widget.show()
            else:
                widget = Separator(window) if kind == 'separator' else QWidget(window)
                if kind == 'spacer': widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
                window._toolbar_xml_widgets.append(widget)
            layout.addWidget(widget)
    # Keep a visible way to reopen menus when the menubar is hidden.
    if 'menu_button' not in used:
        window.right_toolbar_layout.addWidget(window.menu_button)
    window._toolbar_hidden_names = set(known)-used


def edit(window):
    from . import library
    from .desktop import TOOLBAR, DEFAULT_TOOLBAR_ORDER, DEFAULT_TOOLBAR_HIDDEN, DEFAULT_TOOLBAR_BEFORE_PATHS
    from .platform_services import services
    known = dict(TOOLBAR)
    order,hidden,before = window.toolbar_state()
    defaults = encode_legacy(DEFAULT_TOOLBAR_ORDER, DEFAULT_TOOLBAR_HIDDEN, set(DEFAULT_TOOLBAR_BEFORE_PATHS), known)
    saved = library.read(window.settings,'toolbar',{})
    current = saved.get('xml', '') if isinstance(saved,dict) else ''
    try: decode(current,known)
    except (ValueError, ET.ParseError): current = encode_legacy(order,hidden,before,known)
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if not path:
        QMessageBox.warning(window,tr('Composant KDE indisponible'),tr('La personnalisation nécessite les composants natifs de Mirivue recompilés. Vos réglages restent conservés.'))
        return
    try: native = ctypes.CDLL(path)
    except OSError:
        QMessageBox.warning(window,tr('Composant KDE indisponible'),tr('Le composant natif ne peut pas être chargé. Vos réglages restent conservés.'))
        return
    callback_type = ctypes.CFUNCTYPE(None,ctypes.c_char_p)
    try: create = native.mirivue_toolbar_editor_create
    except AttributeError:
        QMessageBox.warning(window,tr('Composant KDE à mettre à jour'),tr('Recompilez les composants natifs de Mirivue pour utiliser le dialogue KDE. Vos réglages restent conservés.'))
        return
    create.argtypes=[ctypes.c_void_p,ctypes.c_char_p,callback_type];create.restype=ctypes.c_void_p
    failures=[]
    def apply(document):
        previous = None
        written = False
        try:
            previous = library.read(window.settings, 'toolbar', {})
            text=document.decode('utf-8');bars,_props=decode(text,known)
            visible=[name for entries in bars.values() for kind,name in entries if kind=='action']
            layout_order=list(dict.fromkeys([*visible,*order]))
            library.write(window.settings,'toolbar',{'order':layout_order,
                'hidden':[name for name in known if name not in visible],
                'before_paths':[name for kind,name in bars['before_paths'] if kind=='action'], 'xml':text})
            written = True
            window.settings.sync()
            if window.settings.status() != QSettings.Status.NoError:
                raise OSError(tr('Impossible d’enregistrer les réglages de la barre d’outils.'))
            window.apply_toolbar()
        except Exception as error:
            # Never let a Python exception escape through a C callback.
            if written:
                try:
                    library.write(window.settings, 'toolbar', previous)
                    window.settings.sync()
                    window.apply_toolbar()
                except Exception as rollback_error:
                    failures.append(str(rollback_error))
            failures.append(str(error))
    callback=callback_type(apply)
    payload=dict(defaults=defaults,current=current,actions=[dict(id=name,text=text,
        widget=shiboken6.getCppPointer(getattr(window,name))[0],
        icon=getattr(window, '_toolbar_presentations', {}).get(name, (getattr(window,name).icon(),))[0].name()) for name,text in TOOLBAR])
    pointer=create(shiboken6.getCppPointer(window)[0],json.dumps(payload,ensure_ascii=False).encode(),callback)
    if not pointer:
        QMessageBox.warning(window,tr('Personnalisation indisponible'),tr('Le dialogue KDE n’a pas pu être créé. Vos réglages restent conservés.'))
        return
    dialog=shiboken6.wrapInstance(pointer,QDialog)
    try: dialog.exec()
    finally: dialog.deleteLater()
    if failures: QMessageBox.warning(window,tr('Réglages non enregistrés'),'\n'.join(failures))

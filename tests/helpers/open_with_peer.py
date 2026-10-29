"""Disposable desktop associations; compare the real menus without opening media."""
import ctypes,json,os,shutil,subprocess
from pathlib import Path
import shiboken6
from PySide6.QtCore import QUrl,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QWidget,QMenu
from mirivue.open_with import add_native_open_with

root=Path(os.environ['XDG_DATA_HOME']);apps=root/'applications';apps.mkdir()
for name,mimes in [('common','video/x-matroska;video/mp4;'),('mkv','video/x-matroska;'),('mp4','video/mp4;')]:
    (apps/f'mirivue-test-{name}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=Mirivue Test {name}\nExec=/bin/true %U\nMimeType={mimes}\nIcon=video-x-generic\nTerminal=false\nNoDisplay=false\n')
config=Path(os.environ['XDG_CONFIG_HOME'])
menus=config/'menus';menus.mkdir()
(menus/(os.environ.get('XDG_MENU_PREFIX','')+'applications.menu')).write_text('<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN" "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd"><Menu><Name>Applications</Name><DefaultAppDirs/><Include><All/></Include></Menu>')
(config/'mimeapps.list').write_text('[Default Applications]\nvideo/x-matroska=mirivue-test-common.desktop\nvideo/mp4=mirivue-test-common.desktop\n[Added Associations]\nvideo/x-matroska=mirivue-test-common.desktop;mirivue-test-mkv.desktop;\nvideo/mp4=mirivue-test-common.desktop;mirivue-test-mp4.desktop;\n')
sycoca=os.environ.get('MIRIVUE_TEST_KBUILDSYCOCA') or shutil.which('kbuildsycoca6')
assert sycoca,'kbuildsycoca6 unavailable'
subprocess.run([sycoca,'--noincremental'],check=True,capture_output=True,text=True,timeout=15)
app=QApplication([]);app.setDesktopFileName('org.pdenams.Mirivue.Qt');window=QWidget()
files=root/'media';files.mkdir()
for name,data in [('premier.mkv',b'\x1aE\xdf\xa3\x93B\x82\x88matroska'),('second é.mkv',b'\x1aE\xdf\xa3\x93B\x82\x88matroska'),('troisieme.mkv',b'\x1aE\xdf\xa3\x93B\x82\x88matroska'),('troisieme.mp4',b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42')]:
    (files/name).write_bytes(data)
reference=ctypes.CDLL(os.environ['MIRIVUE_TEST_OPEN_WITH_REFERENCE'])
factory=reference.mirivue_reference_open_with
factory.argtypes=[ctypes.c_void_p,ctypes.c_char_p];factory.restype=ctypes.c_void_p

def tree(menu):
    return [(action.text(),action.isEnabled(),action.isSeparator(),tree(action.menu()) if action.menu() else None) for action in menu.actions()]

for names in [('premier.mkv','second é.mkv','troisieme.mkv'),('premier.mkv','second é.mkv','troisieme.mp4')]:
    paths=[files/name for name in names];menu=QMenu(window)
    urls=[QUrl.fromLocalFile(str(path)).toString(QUrl.FullyEncoded) for path in paths]
    expected=shiboken6.wrapInstance(factory(shiboken6.getCppPointer(window)[0],json.dumps(urls).encode()),QMenu)
    assert add_native_open_with(window,menu,paths)
    actual=tree(menu)
    assert actual==tree(expected),(actual,tree(expected))
    flat=json.dumps(actual,ensure_ascii=False)
    assert 'Mirivue Test common' in flat,flat
    if any(name.endswith('.mp4') for name in names):
        assert 'Mirivue Test mkv' not in flat and 'Mirivue Test mp4' not in flat,flat
    print(json.dumps({'selection':list(names),'menu':actual},ensure_ascii=False))
    menu.deleteLater();expected.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
# Invalid inputs are rejected without leaving actions or an owner behind.
library=ctypes.CDLL(os.environ['MIRIVUE_TEST_PLACES_LIBRARY']);insert=library.mirivue_open_with_actions
insert.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p];insert.restype=ctypes.c_int
for invalid in [b'{}',b'[]',b'[7]',b'["smb://["]']:
    menu=QMenu(window);assert insert(shiboken6.getCppPointer(menu)[0],shiboken6.getCppPointer(window)[0],invalid)==0
    assert not menu.actions();menu.deleteLater()
window.close();print('KIO_REFERENCE_OK')

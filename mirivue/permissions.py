"""Safe, local Unix permission handling for the Properties dialog."""
from __future__ import annotations

import os
import stat
from pathlib import Path


READ_BITS = (stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH)
WRITE_BITS = (stat.S_IWUSR, stat.S_IWGRP, stat.S_IWOTH)
EXEC_BITS = (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH)
SPECIAL_BITS = stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX


def access_level(mode: int, category: int, directory: bool = False) -> int:
    """Return the compact access value used by the three Plasma-style lists."""
    value = 0
    if mode & READ_BITS[category]:
        value |= 4
    if mode & WRITE_BITS[category]:
        value |= 2
    if directory and mode & EXEC_BITS[category]:
        value |= 1
    return value


def replace_access_level(mode: int, category: int, value: int,
                         directory: bool = False) -> int:
    mask = READ_BITS[category] | WRITE_BITS[category]
    if directory:
        mask |= EXEC_BITS[category]
    mode &= ~mask
    if value & 4:
        mode |= READ_BITS[category]
    if value & 2:
        mode |= WRITE_BITS[category]
    if directory and value & 1:
        mode |= EXEC_BITS[category]
    return mode


def set_file_executable(mode: int, enabled: bool) -> int:
    mask = EXEC_BITS[0] | EXEC_BITS[1] | EXEC_BITS[2]
    return mode | mask if enabled else mode & ~mask


def permission_bits(mode: int) -> int:
    return stat.S_IMODE(mode)


def apply_permissions(path: Path, requested_mode: int) -> int:
    """Apply and verify permission bits without following a symbolic link."""
    path = Path(path)
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode):
        raise OSError('Les droits du lien symbolique ne sont pas modifiés ; ouvrez sa cible.')
    requested_mode = stat.S_IMODE(requested_mode)
    os.chmod(path, requested_mode, follow_symlinks=False)
    actual = stat.S_IMODE(path.lstat().st_mode)
    if actual != requested_mode:
        raise OSError(
            'Le système de fichiers ou ses options de montage n’autorisent pas ce changement '
            f'(demandé {requested_mode:04o}, obtenu {actual:04o}).')
    return actual


def add_permissions_tab(tabs, parent, info, requested_mode, tr, trf):
    """Add the Plasma-style permission editor without making Qt a core dependency."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                                   QDialogButtonBox, QFormLayout, QGridLayout,
                                   QLabel, QPushButton, QVBoxLayout, QWidget)
    page = QWidget(tabs)
    layout = QVBoxLayout(page)
    title = QLabel(tr('<b>Droits d’accès</b>'))
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(title)
    form = QFormLayout()
    layout.addLayout(form)
    directory = stat.S_ISDIR(info.st_mode)
    combos = []

    def add_combo(label, category):
        combo = QComboBox(page)
        choices = ((tr('Aucun accès'), 0), (tr('Peut traverser'), 1),
                   (tr('Peut uniquement consulter'), 5),
                   (tr('Peut consulter et modifier'), 7)) if directory else (
                       (tr('Aucun accès'), 0),
                       (tr('Peut uniquement consulter'), 4),
                       (tr('Peut consulter et modifier'), 6))
        current = access_level(requested_mode[0], category, directory)
        for text, value in choices:
            combo.addItem(text, value)
        index = combo.findData(current)
        if index < 0:
            combo.addItem(trf('Personnalisé (0)', format(current, 'o')), current)
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(
            lambda _index, c=combo, n=category: requested_mode.__setitem__(
                0, replace_access_level(requested_mode[0], n, int(c.currentData()), directory)))
        form.addRow(label, combo)
        combos.append((combo, category))

    add_combo(tr('Propriétaire :'), 0)
    add_combo(tr('Groupe :'), 1)
    add_combo(tr('Autres :'), 2)
    executable = None
    if stat.S_ISREG(info.st_mode):
        executable = QCheckBox(tr("Autoriser l’exécution du fichier en tant que programme."))
        executable.setChecked(bool(requested_mode[0] & sum(EXEC_BITS)))
        executable.toggled.connect(
            lambda enabled: requested_mode.__setitem__(0, set_file_executable(requested_mode[0], enabled)))
        form.addRow(tr('Exécuter :'), executable)

    def advanced_permissions():
        advanced = QDialog(parent)
        advanced.setWindowTitle(tr('Droits d’accès avancés'))
        advanced_layout = QVBoxLayout(advanced)
        grid = QGridLayout()
        for column, text in enumerate((tr('Lecture'), tr('Écriture'), tr('Exécution')), 1):
            grid.addWidget(QLabel(text), 0, column)
        checks = {}
        for category, text in enumerate((tr('Propriétaire'), tr('Groupe'), tr('Autres')), 1):
            grid.addWidget(QLabel(text), category, 0)
            for column, bits in enumerate((READ_BITS, WRITE_BITS, EXEC_BITS), 1):
                check = QCheckBox()
                check.setChecked(bool(requested_mode[0] & bits[category - 1]))
                grid.addWidget(check, category, column, Qt.AlignmentFlag.AlignHCenter)
                checks[(category - 1, column - 1)] = check
        advanced_layout.addLayout(grid)
        advanced_layout.addWidget(QLabel(trf('Mode actuel : 0', format(requested_mode[0], '04o'))))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(advanced.accept)
        buttons.rejected.connect(advanced.reject)
        advanced_layout.addWidget(buttons)
        if advanced.exec() != QDialog.DialogCode.Accepted:
            return
        mode = requested_mode[0]
        for category in range(3):
            for column, bits in enumerate((READ_BITS, WRITE_BITS, EXEC_BITS)):
                mode = mode | bits[category] if checks[(category, column)].isChecked() else mode & ~bits[category]
        requested_mode[0] = mode
        for combo, category in combos:
            index = combo.findData(access_level(mode, category, directory))
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        if executable is not None:
            executable.blockSignals(True)
            executable.setChecked(bool(mode & sum(EXEC_BITS)))
            executable.blockSignals(False)

    button = QPushButton(tr('Droits d’accès avancés…'))
    button.clicked.connect(advanced_permissions)
    layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
    try:
        import pwd, grp
        owner_name = pwd.getpwuid(info.st_uid).pw_name
        group_name = grp.getgrgid(info.st_gid).gr_name
    except (ImportError, KeyError):
        owner_name, group_name = str(info.st_uid), str(info.st_gid)
    layout.addSpacing(12)
    layout.addWidget(QLabel(tr('<b>Appartenance</b>')), 0, Qt.AlignmentFlag.AlignHCenter)
    ownership = QFormLayout()
    ownership.addRow(tr('Utilisateur :'), QLabel(owner_name))
    ownership.addRow(tr('Groupe :'), QLabel(group_name))
    layout.addLayout(ownership)
    layout.addStretch()
    tabs.addTab(page, tr("Droits d’accès"))

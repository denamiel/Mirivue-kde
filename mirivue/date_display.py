from __future__ import annotations

from datetime import datetime, timedelta
try:
    from PySide6.QtCore import QDateTime, QLocale
except ImportError:
    QDateTime = QLocale = None


DATE_FORMATS = {'locale', 'iso', 'informal'}


def normalized_date_format(mode):
    return str(mode) if str(mode) in DATE_FORMATS else 'locale'


def modification_text(timestamp_ns, now=None, mode='locale', translate=lambda text: text):
    if timestamp_ns is None:
        return translate('—')
    try:
        date = datetime.fromtimestamp(timestamp_ns / 1_000_000_000)
    except (ValueError, OverflowError, OSError):
        return translate('—')
    mode = normalized_date_format(mode)
    if mode == 'locale':
        if QDateTime is None:
            return date.strftime(translate('%c'))
        return QLocale().toString(QDateTime.fromMSecsSinceEpoch(timestamp_ns // 1_000_000),
                                  QLocale.FormatType.ShortFormat)
    if mode == 'iso':
        return date.strftime(translate('%Y-%m-%d %H:%M:%S'))
    if now is None:
        # The running KDE application initializes this bridge before its views.
        try:
            from .platform_services import services
        except ImportError:
            formatted = None
        else:
            formatted = services.format_relative_date(timestamp_ns)
        if formatted is not None:
            return formatted
    today = (now or datetime.now()).date()
    if date.date() == today:
        prefix = translate('Aujourd’hui')
    elif date.date() == today - timedelta(days=1):
        prefix = translate('Hier')
    elif today - timedelta(days=7) < date.date() < today:
        prefix = date.strftime(translate('%A')).capitalize()
    else:
        prefix = translate('le ') + date.strftime(translate('%d/%m/%Y'))
    return prefix + translate(' à ') + date.strftime(translate('%H:%M'))

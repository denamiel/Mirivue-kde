// SPDX-FileCopyrightText: 2007-2011 Peter Penz <peter.penz19@gmail.com>
// SPDX-FileCopyrightText: 2007 David Faure <faure@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later
// URL-match portion used by the upstream controller. KIO operations remain
// in Mirivue's existing service rather than the Dolphin application helper.
#pragma once
#include <QHash>
#include <QList>
#include <QUrl>
class DragAndDropHelper {
public:
    static bool urlListMatchesUrl(const QList<QUrl> &urls, const QUrl &destUrl);
    static void clearUrlListMatchesUrlCache();
private:
    static QHash<QUrl, bool> m_urlListMatchesUrlCache;
};

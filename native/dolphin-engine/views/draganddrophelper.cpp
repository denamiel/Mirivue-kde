// SPDX-FileCopyrightText: 2007-2011 Peter Penz <peter.penz19@gmail.com>
// SPDX-FileCopyrightText: 2007 David Faure <faure@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later
#include "draganddrophelper.h"
#include <algorithm>
QHash<QUrl, bool> DragAndDropHelper::m_urlListMatchesUrlCache;
bool DragAndDropHelper::urlListMatchesUrl(const QList<QUrl> &urls, const QUrl &destUrl)
{
    auto iteratorResult = m_urlListMatchesUrlCache.constFind(destUrl);
    if (iteratorResult != m_urlListMatchesUrlCache.constEnd()) return *iteratorResult;
    const bool match = std::any_of(urls.constBegin(), urls.constEnd(), [destUrl](const QUrl &url) {
        return url.matches(destUrl, QUrl::StripTrailingSlash);
    });
    return *m_urlListMatchesUrlCache.insert(destUrl, match);
}
void DragAndDropHelper::clearUrlListMatchesUrlCache()
{
    m_urlListMatchesUrlCache.clear();
}

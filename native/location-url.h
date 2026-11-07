// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
#pragma once

#include <QDir>
#include <QString>
#include <QUrl>

// Locations exchanged with Mirivue are absolute local paths or complete URLs.
// QUrl::fromUserInput() trims surrounding whitespace, so "Folder " would become
// "Folder" (C1). Parse those values exactly and keep the user-input heuristics
// only for anything else, such as text typed by the user.
inline QUrl mirivueLocationUrl(const QString &value)
{
    if (QDir::isAbsolutePath(value))
        return QUrl::fromLocalFile(value);
    const QUrl url(value, QUrl::TolerantMode);
    if (url.isValid() && !url.scheme().isEmpty())
        return url;
    return QUrl::fromUserInput(value);
}

// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
// Original public-API adapter. Dolphin v26.08.2 uses the same KIO entry point
// in src/dolphincontextmenu.cpp, DolphinContextMenu::addOpenWithActions().
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMenu>
#include <QUrl>
#include <KFileItem>
#include <KFileItemActions>
#include <KFileItemListProperties>

extern "C" int mirivue_open_with_actions(void *menuPointer, void *windowPointer, const char *urlsJson)
{
    if (!QApplication::instance() || !menuPointer || !windowPointer || !urlsJson) return 0;
    const auto document = QJsonDocument::fromJson(urlsJson);
    if (!document.isArray() || document.array().isEmpty()) return 0;
    KFileItemList items;
    for (const auto &value : document.array()) {
        if (!value.isString()) return 0;
        const QUrl url(value.toString());
        if (!url.isValid() || url.isEmpty()) return 0;
        items.append(KFileItem(url));
    }
    auto *menu = static_cast<QMenu *>(menuPointer);
    auto *actions = new KFileItemActions(menu);
    actions->setParentWidget(static_cast<QWidget *>(windowPointer));
    actions->setItemListProperties(KFileItemListProperties(items));
    actions->insertOpenWithActionsTo(nullptr, menu, QStringList{qApp->desktopFileName()});
    // Empty is also a handled result (for example, a Kiosk restriction).
    // Never replace that decision with Mirivue's generic Open command.
    return 1;
}

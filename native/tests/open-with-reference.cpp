// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
// Independent test of Dolphin v26.08.2's public KIO call (not installed).
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMenu>
#include <KFileItem>
#include <KFileItemActions>
#include <KFileItemListProperties>
extern "C" void *mirivue_reference_open_with(void *parent, const char *json) {
    auto *menu = new QMenu(static_cast<QWidget *>(parent));
    KFileItemList items;
    for (const auto &value : QJsonDocument::fromJson(json).array()) items.append(KFileItem(QUrl(value.toString())));
    auto *actions = new KFileItemActions(menu);
    actions->setParentWidget(static_cast<QWidget *>(parent));
    actions->setItemListProperties(KFileItemListProperties(items));
    actions->insertOpenWithActionsTo(nullptr, menu, QStringList{qApp->desktopFileName()});
    return menu;
}

// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
#include <KPropertiesDialog>
#include <KFileItem>
#include <KIO/StatJob>
#include <KJobWidgets>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrl>
#include <QWidget>
using PropertiesNotify = void (*)(const char *);

extern "C" void *mirivue_properties_create(void *parent, const char *urlsJson,
                                           int nameReadOnly, PropertiesNotify notify)
{
    QList<QUrl> urls;
    for (const auto &value : QJsonDocument::fromJson(urlsJson).array()) {
        const QUrl url(value.toString());
        if (!url.isValid() || url.isEmpty()) return nullptr;
        urls.append(url);
    }
    if (urls.isEmpty()) return nullptr;
    KFileItemList items;
    for (const QUrl &url : urls) {
        if (url.isLocalFile()) {
            items.append(KFileItem(url, KFileItem::NormalMimeTypeDetermination));
        } else {
            auto *job = KIO::stat(url);
            KJobWidgets::setWindow(job, static_cast<QWidget *>(parent));
            if (!job->exec()) return nullptr;
            items.append(KFileItem(job->statResult(), url));
        }
    }
    auto *dialog = new KPropertiesDialog(items, static_cast<QWidget *>(parent));
    dialog->setWindowModality(Qt::WindowModal);
    dialog->setFileNameReadOnly(nameReadOnly);
    QObject::connect(dialog, &KPropertiesDialog::applied, dialog, [dialog, urls, notify]() mutable {
        QJsonArray renamed, current;
        const auto items = dialog->items();
        for (int index = 0; index < items.size(); ++index) {
            const QUrl url = items[index].url();
            current.append(url.toString());
            if (index < urls.size() && urls[index] != url) {
                renamed.append(QJsonObject{{"source", urls[index].toString()}, {"target", url.toString()}});
            }
        }
        urls.clear();
        for (const auto &item : items) urls.append(item.url());
        const QByteArray data = QJsonDocument(QJsonObject{{"urls", current}, {"renamed", renamed}}).toJson(QJsonDocument::Compact);
        if (notify) notify(data.constData());
    });
    // KPropertiesDialog owns its lifetime and deletes itself when closed.
    dialog->show();
    return dialog;
}

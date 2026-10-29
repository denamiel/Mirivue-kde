// SPDX-License-Identifier: MIT
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrl>
#include <KCoreDirLister>
#include <KIO/Job>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (argc != 2) { qCritical("usage: mirivue-kio-list URI"); return 2; }
    const QUrl url = QUrl::fromUserInput(QString::fromLocal8Bit(argv[1]));
    if (!url.isValid() || url.scheme().isEmpty()) { qCritical("invalid URI"); return 2; }
    QJsonArray entries;
    KCoreDirLister lister;
    // As in Dolphin, let the lister combine UDS_HIDDEN, dot names and .hidden.
    // Return the fact, and let the requesting pane choose its visibility.
    lister.setAutoErrorHandlingEnabled(false);
    lister.setAutoUpdate(false);
    lister.setShowHiddenFiles(true);
    bool done = false;
    auto finish = [&](const QString &error) {
        if (done) return;
        done = true;
        QJsonObject result{{"ok", error.isEmpty()}};
        if (error.isEmpty()) result.insert("entries", entries);
        else result.insert("error", error);
        const auto output = QJsonDocument(result).toJson(QJsonDocument::Compact);
        fprintf(stdout, "%s\n", output.constData()); fflush(stdout);
        app.quit();
    };
    QObject::connect(&lister, &KCoreDirLister::newItems, [&](const KFileItemList &items) {
        for (const KFileItem &item : items) {
            const auto entry = item.entry();
            entries.append(QJsonObject{
                {"name", item.text()}, {"realName", item.name()}, {"url", item.url().toString()},
                {"hidden", item.isHidden()}, {"directory", item.isDir()},
                {"size", static_cast<qint64>(item.size())},
                {"modified", static_cast<qint64>(entry.numberValue(KIO::UDSEntry::UDS_MODIFICATION_TIME))},
                {"accessed", static_cast<qint64>(entry.numberValue(KIO::UDSEntry::UDS_ACCESS_TIME))},
                {"localPath", entry.stringValue(KIO::UDSEntry::UDS_LOCAL_PATH)},
                {"originalPath", entry.stringValue(KIO::UDSEntry::UDS_EXTRA)},
                {"deleted", entry.stringValue(KIO::UDSEntry::UDS_EXTRA + 1)},
                {"mime", entry.stringValue(KIO::UDSEntry::UDS_MIME_TYPE)}
            });
        }
    });
    QObject::connect(&lister, qOverload<>(&KCoreDirLister::completed), [&] { finish({}); });
    QObject::connect(&lister, &KCoreDirLister::jobError, [&](KIO::Job *job) { finish(job->errorString()); });
    QObject::connect(&lister, qOverload<>(&KCoreDirLister::canceled), [&] { finish(QStringLiteral("Listing cancelled")); });
    if (!lister.openUrl(url)) return 2;
    return app.exec();
}

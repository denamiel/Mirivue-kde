// SPDX-License-Identifier: MIT
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSet>
#include <QUrl>

#include <KApplicationTrader>
#include <KService>
#include <KIO/ApplicationLauncherJob>
#include <KIO/JobUiDelegateFactory>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    const QStringList args = app.arguments();
    if (args.size() < 3) {
        qCritical("usage: mirivue-kio-applications --list MIME... | --default MIME | --launch SERVICE FILE...");
        return 2;
    }
    if (args.at(1) == QStringLiteral("--default") && args.size() == 3) {
        const auto service = KApplicationTrader::preferredService(args.at(2));
        QJsonObject result;
        if (service) {
            result.insert("identifier", service->storageId());
            result.insert("icon", service->icon());
        }
        fprintf(stdout, "%s\n", QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
        return 0;
    }
    if (args.at(1) == QStringLiteral("--list")) {
        const auto offers = KApplicationTrader::queryByMimeType(args.at(2));
        QList<QSet<QString>> otherOffers;
        for (int i = 3; i < args.size(); ++i) {
            QSet<QString> ids;
            for (const auto &service : KApplicationTrader::queryByMimeType(args.at(i)))
                ids.insert(service->storageId());
            otherOffers.append(ids);
        }
        QJsonArray results;
        for (const auto &service : offers) {
            const QString id = service->storageId();
            bool common = !id.isEmpty();
            for (const auto &ids : otherOffers)
                common = common && ids.contains(id);
            if (common) {
                QJsonObject item;
                item.insert("identifier", id);
                item.insert("name", service->name());
                item.insert("icon", service->icon());
                results.append(item);
            }
        }
        fprintf(stdout, "%s\n", QJsonDocument(results).toJson(QJsonDocument::Compact).constData());
        return 0;
    }
    if (args.at(1) != QStringLiteral("--launch") || args.size() < 4)
        return 2;
    const auto service = KService::serviceByStorageId(args.at(2));
    if (!service) {
        qCritical("application unavailable");
        return 1;
    }
    QList<QUrl> urls;
    for (int i = 3; i < args.size(); ++i)
        urls.append(QUrl::fromLocalFile(args.at(i)));
    auto *job = new KIO::ApplicationLauncherJob(service);
    job->setUrls(urls);
    job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoHandlingEnabled, nullptr));
    QObject::connect(job, &KJob::result, &app, [&app](KJob *finished) {
        app.exit(finished->error() ? 1 : 0);
    });
    job->start();
    return app.exec();
}

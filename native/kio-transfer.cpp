// SPDX-License-Identifier: MIT
#include <QApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrl>
#include <KIO/CopyJob>
#include <KIO/MkdirJob>

#include <algorithm>

class ProgressRelay : public QObject
{
    Q_OBJECT
public:
    using QObject::QObject;

public slots:
    void progress(KJob *, unsigned long value)
    {
        QJsonObject output;
        output.insert("progress", static_cast<qint64>(value));
        fprintf(stdout, "%s\n", QJsonDocument(output).toJson(QJsonDocument::Compact).constData());
        fflush(stdout);
    }
};

// Arguments are complete URLs produced by Mirivue; never trim them (C1).
static QUrl argumentUrl(const char *argument)
{
    return QUrl(QString::fromLocal8Bit(argument), QUrl::TolerantMode);
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QGuiApplication::setDesktopFileName(QStringLiteral("org.pdenams.Mirivue.Qt"));
    const QString command = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QString();
    if (command == "mkdir") {
        if (argc != 3)
            return 2;
        const QUrl target = argumentUrl(argv[2]);
        if (!target.isValid() || target.scheme().isEmpty())
            return 2;
        auto *job = KIO::mkdir(target);
        QObject::connect(job, &KJob::result, [&app, job](KJob *) {
            QJsonObject result;
            result.insert("ok", !job->error());
            if (job->error())
                result.insert("error", job->errorText());
            fprintf(stdout, "%s\n", QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
            fflush(stdout);
            app.quit();
        });
        return app.exec();
    }
    const bool trashing = command == "trash";
    if ((trashing && argc < 3) || (!trashing && argc < 4) || (command != "copy" && command != "move" && command != "link" && command != "trash"))
        return 2;
    const bool moving = command == "move";
    QList<QUrl> sources;
    const int sourceEnd = trashing ? argc : argc - 1;
    for (int i = 2; i < sourceEnd; ++i)
        sources << argumentUrl(argv[i]);
    const QUrl destination = trashing ? QUrl(QStringLiteral("trash:/")) : argumentUrl(argv[argc - 1]);
    const auto complete = [](const QUrl &value) { return value.isValid() && !value.scheme().isEmpty(); };
    if (!complete(destination) || !std::all_of(sources.cbegin(), sources.cend(), complete)) {
        QJsonObject output;
        output.insert("ok", false);
        output.insert("error", QStringLiteral("Requête KIO invalide : une source ou la destination n'est pas une URL complète."));
        fprintf(stdout, "%s\n", QJsonDocument(output).toJson(QJsonDocument::Compact).constData());
        fflush(stdout);
        return 2;
    }
    KIO::CopyJob *job = nullptr;
    if (trashing)
        job = KIO::trash(sources);
    else if (command == "link")
        job = KIO::link(sources, destination);
    else if (moving)
        job = KIO::move(sources, destination);
    else
        job = KIO::copy(sources, destination);
    ProgressRelay relay;
    QObject::connect(job, SIGNAL(percentChanged(KJob*,ulong)), &relay, SLOT(progress(KJob*,ulong)));
    QObject::connect(job, &KJob::result, [&app, job](KJob *) {
        QJsonObject result;
        result.insert("ok", !job->error());
        if (job->error())
            result.insert("error", job->errorText());
        fprintf(stdout, "%s\n", QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
        fflush(stdout);
        app.quit();
    });
    return app.exec();
}

#include "kio-transfer.moc"

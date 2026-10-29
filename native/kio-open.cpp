// SPDX-License-Identifier: MIT
#include <QApplication>
#include <QFileInfo>
#include <QUrl>

#include <KIO/JobUiDelegateFactory>
#include <KIO/OpenUrlJob>
#include <KIO/StatJob>
#include <KProtocolInfo>
#include <KTerminalLauncherJob>
#include <QDir>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    const bool terminal = argc == 3 && QByteArray(argv[1]) == "--terminal";
    if (argc != 2 && !terminal) {
        qCritical("usage: mirivue-kio-open [--terminal] FILE_OR_URI");
        return 2;
    }

    const QString argument = QString::fromLocal8Bit(argv[terminal ? 2 : 1]);
    const QUrl url = QFileInfo(argument).isAbsolute()
        ? QUrl::fromLocalFile(argument) : QUrl::fromUserInput(argument);
    if (!url.isValid()) {
        qCritical("invalid URL");
        return 2;
    }

    const auto start = [&app](KJob *job) {
        job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoHandlingEnabled, nullptr));
        QObject::connect(job, &KJob::result, &app, [&app](KJob *finished) {
            app.exit(finished->error() ? 1 : 0);
        });
        job->start();
    };
    if (!terminal) {
        start(new KIO::OpenUrlJob(url));
    } else {
        const auto launch = [start](const QUrl &location) {
            auto *job = new KTerminalLauncherJob(QString());
            job->setWorkingDirectory(location.isLocalFile() ? location.toLocalFile() : QDir::homePath());
            start(job);
        };
        // Same resolution as DolphinMainWindow::openTerminalJob().
        if (!url.isLocalFile() && KProtocolInfo::protocolClass(url.scheme()) == QLatin1String(":local")) {
            auto *stat = KIO::mostLocalUrl(url);
            QObject::connect(stat, &KJob::result, &app, [stat, launch] {
                launch(stat->error() ? QUrl() : stat->mostLocalUrl());
            });
        } else {
            launch(url);
        }
    }
    return app.exec();
}

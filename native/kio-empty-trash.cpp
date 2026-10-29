// SPDX-License-Identifier: MIT
#include <QApplication>
#include <KIO/EmptyTrashJob>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    if (argc != 1)
        return 2;
    auto *job = KIO::emptyTrash();
    QObject::connect(job, &KJob::result, &app, [&app](KJob *finished) {
        if (finished->error())
            qCritical("%s", qPrintable(finished->errorText()));
        app.exit(finished->error() ? 1 : 0);
    });
    return app.exec();
}

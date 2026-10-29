// SPDX-License-Identifier: MIT
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSocketNotifier>
#include <QUrl>
#include <QHash>
#include <QTimer>

#include <KIO/CopyJob>
#include <KIO/DeleteJob>
#include <KIO/DeleteOrTrashJob>
#include <KIO/FileUndoManager>
#include <KIO/JobUiDelegateFactory>
#include <KIO/MkdirJob>
#include <KIO/RestoreJob>

#include <cerrno>
#include <fcntl.h>
#include <unistd.h>

class KioService final : public QObject
{
public:
    explicit KioService(QApplication &application, const QString &inputPath, const QString &outputPath)
        : QObject(&application)
        , app(application)
        , inputFd(::open(inputPath.toLocal8Bit().constData(), O_RDWR | O_NONBLOCK | O_CLOEXEC))
        , outputFd(::open(outputPath.toLocal8Bit().constData(), O_RDWR | O_NONBLOCK | O_CLOEXEC))
        , input(inputFd, QSocketNotifier::Read, this)
        , undo(KIO::FileUndoManager::self())
    {
        if (inputFd < 0 || outputFd < 0) {
            fprintf(stderr, "KIO service pipe unavailable.\n");
            app.exit(2);
            return;
        }
        QObject::connect(&input, &QSocketNotifier::activated, this, [this] { readInput(); });
        QObject::connect(undo, &KIO::FileUndoManager::undoAvailable, this, [this] { emitState(); });
        QObject::connect(undo, &KIO::FileUndoManager::undoTextChanged, this, [this] { emitState(); });
        QObject::connect(undo, &KIO::FileUndoManager::redoAvailable, this, [this] { emitState(); });
        QObject::connect(undo, &KIO::FileUndoManager::redoTextChanged, this, [this] { emitState(); });
        QObject::connect(undo, &KIO::FileUndoManager::undoJobFinished, this, [this] {
            if (!historyRequestId.isEmpty()) {
                QJsonObject result;
                result.insert("event", "complete");
                result.insert("id", historyRequestId);
                result.insert("ok", true);
                result.insert("undo_available", undo->isUndoAvailable());
                result.insert("undo_text", undo->undoText());
                result.insert("redo_available", undo->isRedoAvailable());
                result.insert("redo_text", undo->redoText());
                write(result);
                historyRequestId.clear();
            }
            emitState();
        });
    }

    bool ready() const { return inputFd >= 0 && outputFd >= 0; }

private:
    QApplication &app;
    int inputFd;
    int outputFd;
    QSocketNotifier input;
    KIO::FileUndoManager *undo;
    QByteArray buffer;
    QHash<QString, KJob *> jobs;
    QString historyRequestId;
    QString shutdownRequestId;

    static QUrl url(const QJsonValue &value)
    {
        return QUrl::fromUserInput(value.toString());
    }

    void write(const QJsonObject &object)
    {
        if (outputFd < 0)
            return;
        const QByteArray line = QJsonDocument(object).toJson(QJsonDocument::Compact) + '\n';
        qsizetype offset = 0;
        while (offset < line.size()) {
            const ssize_t count = ::write(outputFd, line.constData() + offset, static_cast<size_t>(line.size() - offset));
            if (count < 0 && errno == EINTR)
                continue;
            if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
                continue;
            }
            if (count <= 0)
                return;
            offset += static_cast<qsizetype>(count);
        }
    }

    void emitState()
    {
        QJsonObject state;
        state.insert("event", "state");
        state.insert("undo_available", undo->isUndoAvailable());
        state.insert("undo_text", undo->undoText());
        state.insert("redo_available", undo->isRedoAvailable());
        state.insert("redo_text", undo->redoText());
        write(state);
    }

    void complete(const QString &id, KJob *job)
    {
        jobs.remove(id);
        QJsonObject result;
        result.insert("event", "complete");
        result.insert("id", id);
        result.insert("ok", !job->error());
        result.insert("cancelled", job->error() == KJob::KilledJobError);
        if (job->error() == KIO::ERR_USER_CANCELED)
            result.insert("error", "Transfert annulé.");
        else if (job->error())
            result.insert("error", job->errorText());
        result.insert("undo_available", undo->isUndoAvailable());
        result.insert("undo_text", undo->undoText());
        result.insert("redo_available", undo->isRedoAvailable());
        result.insert("redo_text", undo->redoText());
        write(result);
        // FileUndoManager finishes recording from its own result handler. Let
        // that handler run before reporting the state back to Mirivue.
        QTimer::singleShot(0, this, [this] { emitState(); });
        job->deleteLater();
        if (jobs.isEmpty() && !shutdownRequestId.isEmpty()) {
            write({{"event", "complete"}, {"id", shutdownRequestId}, {"ok", true}});
            app.quit();
        }
    }

    void startJob(const QJsonObject &request)
    {
        const QString id = request.value("id").toString();
        const QString command = request.value("command").toString();
        const bool trashing = command == "trash";
        const bool destinationless = trashing || command == "restore" || command == "delete";
        const QUrl destination = trashing ? QUrl(QStringLiteral("trash:/")) : url(request.value("destination"));
        if (id.isEmpty() || jobs.contains(id) || (!destinationless && (!destination.isValid() || destination.scheme().isEmpty()))) {
            write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", "Requête KIO invalide."}});
            return;
        }

        if (command == "mkdir") {
            auto *job = KIO::mkdir(destination);
            job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoHandlingEnabled, nullptr));
            jobs.insert(id, job);
            undo->recordJob(KIO::FileUndoManager::Mkdir, {}, destination, job);
            QObject::connect(job, &KJob::result, this, [this, id](KJob *done) { complete(id, done); });
            return;
        }

        if (command != "copy" && command != "move" && command != "copyas" && command != "moveas" && command != "link" && command != "trash" && command != "restore" && command != "delete") {
            write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", "Commande KIO inconnue."}});
            return;
        }
        QList<QUrl> sources;
        for (const QJsonValue &value : request.value("sources").toArray()) {
            const QUrl source = url(value);
            if (source.isValid() && !source.scheme().isEmpty())
                sources.append(source);
        }
        if (sources.isEmpty()) {
            write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", "Aucune source KIO valide."}});
            return;
        }
        if ((command == "copyas" || command == "moveas") && sources.size() != 1) {
            write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", "Un seul élément est attendu pour ce nom de destination."}});
            return;
        }
        KJob *job = nullptr;
        if (command == "trash")
            job = new KIO::DeleteOrTrashJob(sources, KIO::AskUserActionInterface::Trash,
                                            KIO::AskUserActionInterface::DefaultConfirmation, this);
        else if (command == "restore")
            job = KIO::restoreFromTrash(sources);
        else if (command == "delete")
            job = new KIO::DeleteOrTrashJob(sources, KIO::AskUserActionInterface::Delete,
                                            KIO::AskUserActionInterface::DefaultConfirmation, this);
        else if (command == "link")
            job = KIO::link(sources, destination);
        else if (command == "copyas")
            job = KIO::copyAs(sources.first(), destination);
        else if (command == "moveas")
            job = KIO::moveAs(sources.first(), destination);
        else if (command == "move")
            job = KIO::move(sources, destination);
        else
            job = KIO::copy(sources, destination);
        // KIO owns conflict handling; attach its normal Plasma UI delegate so
        // name collisions can present the native merge/replace/skip choices.
        job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoHandlingEnabled, nullptr));
        jobs.insert(id, job);
        if (command == "copy" || command == "copyas")
            undo->recordCopyJob(static_cast<KIO::CopyJob *>(job));
        else if (command == "link")
            undo->recordJob(KIO::FileUndoManager::Link, sources, destination, static_cast<KIO::CopyJob *>(job));
        else if (command == "move" || command == "moveas")
            undo->recordJob(KIO::FileUndoManager::Move, sources, destination, static_cast<KIO::CopyJob *>(job));
        QObject::connect(job, &KJob::percentChanged, this, [this, id](KJob *, unsigned long percent) {
            write({{"event", "progress"}, {"id", id}, {"value", static_cast<qint64>(percent)}});
        });
        QObject::connect(job, &KJob::result, this, [this, id](KJob *done) { complete(id, done); });
        if (command == "trash" || command == "delete")
            static_cast<KIO::DeleteOrTrashJob *>(job)->start();
    }

    void handle(const QJsonObject &request)
    {
        const QString command = request.value("command").toString();
        const QString id = request.value("id").toString();
        if (command == "copy" || command == "move" || command == "copyas" || command == "moveas" || command == "link" || command == "trash" || command == "restore" || command == "delete" || command == "mkdir") {
            startJob(request);
        } else if (command == "cancel") {
            const QString target = request.value("target").toString();
            if (KJob *job = jobs.value(target, nullptr))
                job->kill(KJob::EmitResult);
        } else if (command == "state") {
            emitState();
            write({{"event", "complete"}, {"id", id}, {"ok", true}});
        } else if (command == "undo" || command == "redo") {
            const bool redo = command == "redo";
            if (redo ? !undo->isRedoAvailable() : !undo->isUndoAvailable()) {
                write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", redo ? "Aucune opération KIO ne peut être rétablie." : "Aucune opération KIO ne peut être annulée."}});
                return;
            }
            historyRequestId = id;
            redo ? undo->redo() : undo->undo();
        } else if (command == "shutdown") {
            shutdownRequestId = id;
            if (jobs.isEmpty()) {
                write({{"event", "complete"}, {"id", id}, {"ok", true}});
                app.quit();
            } else {
                const auto activeJobs = jobs.values();
                for (KJob *job : activeJobs)
                    job->kill(KJob::EmitResult);
            }
        } else {
            write({{"event", "complete"}, {"id", id}, {"ok", false}, {"error", "Commande de service inconnue."}});
        }
    }

    void readInput()
    {
        if (inputFd < 0)
            return;
        while (true) {
            char chunk[8192];
            const ssize_t count = ::read(inputFd, chunk, sizeof(chunk));
            if (count < 0 && errno == EINTR)
                continue;
            if (count <= 0)
                break;
            buffer.append(chunk, static_cast<qsizetype>(count));
            if (count < static_cast<ssize_t>(sizeof(chunk)))
                break;
        }
        while (true) {
            const qsizetype newline = buffer.indexOf('\n');
            if (newline < 0)
                break;
            const QByteArray line = buffer.left(newline);
            buffer.remove(0, newline + 1);
            const QJsonDocument document = QJsonDocument::fromJson(line);
            if (document.isObject())
                handle(document.object());
        }
    }
};

int main(int argc, char **argv)
{
    if (argc != 4 || QByteArray(argv[1]) != "--service")
        return 2;
    QApplication app(argc, argv);
    app.setApplicationName("Mirivue KIO service");
    QGuiApplication::setDesktopFileName(QStringLiteral("org.pdenams.Mirivue.Qt"));
    app.setQuitOnLastWindowClosed(false);
    QCoreApplication::setQuitLockEnabled(false);
    KioService service(app, QString::fromLocal8Bit(argv[2]), QString::fromLocal8Bit(argv[3]));
    if (!service.ready())
        return 2;
    return app.exec();
}

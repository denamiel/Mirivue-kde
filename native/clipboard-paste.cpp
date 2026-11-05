// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
// Public KIO API adapter, running in Mirivue's GUI process (also on Wayland).
#include <QApplication>
#include <QClipboard>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QMimeData>
#include <QTimer>
#include <QWidget>
#include <KIO/PasteJob>
#include <KIO/Paste>
#include <KIO/FileUndoManager>
#include <KIO/Global>
#include <KIO/Job>
#include <KJobWidgets>

class ClipboardOperation final : public QObject {
public:
    explicit ClipboardOperation() : QObject(qApp) {}
    QPointer<KJob> job;
    QJsonArray items;
    bool done = false, ok = false, cancelled = false;
    QString error;
};

static QPointer<ClipboardOperation> historyOperation;
class ClipboardUndoUi final : public KIO::FileUndoManager::UiInterface {
public:
    void jobError(KIO::Job *job) override {
        if (historyOperation) historyOperation->error = job->errorString();
        qWarning("Clipboard history failure: %s", qPrintable(job->errorString()));
        KIO::FileUndoManager::UiInterface::jobError(job);
    }
    bool copiedFileWasModified(const QUrl &src, const QUrl &dest,
                              const QDateTime &srcTime, const QDateTime &destTime) override {
        const bool accepted = KIO::FileUndoManager::UiInterface::copiedFileWasModified(src, dest, srcTime, destTime);
        if (!accepted && historyOperation) historyOperation->cancelled = true;
        return accepted;
    }
};

extern "C" void *mirivue_clipboard_start(void *window, const char *destination, int history)
{
    auto *operation = new ClipboardOperation;
    auto *manager = KIO::FileUndoManager::self();
    static bool uiInstalled = false;
    if (!uiInstalled) {
        manager->setUiInterface(new ClipboardUndoUi);
        uiInstalled = true;
    }
    manager->uiInterface()->setParentWidget(static_cast<QWidget *>(window));
    if (history) {
        if (history == 1 ? !manager->isUndoAvailable() : !manager->isRedoAvailable()) {
            delete operation;
            return nullptr;
        }
        historyOperation = operation;
        QObject::connect(manager, &KIO::FileUndoManager::undoJobFinished, operation, [operation] {
            operation->ok = operation->error.isEmpty() && !operation->cancelled;
            operation->done = true;
            historyOperation = nullptr;
        }, Qt::SingleShotConnection);
        if (history == 1) manager->undo(); else manager->redo();
        return operation;
    }
    const QUrl target(QString::fromUtf8(destination ? destination : ""));
    const auto *mime = QApplication::clipboard()->mimeData();
    if (!target.isValid() || target.isEmpty() || !mime || mime->hasUrls()) {
        delete operation;
        return nullptr;
    }
    // Exactly the public API used by Dolphin; no helper process reads or
    // replaces the user's clipboard and no Python writer encodes the file.
    auto *job = KIO::paste(mime, target);
    operation->job = job;
    KJobWidgets::setWindow(job, static_cast<QWidget *>(window));
    QObject::connect(job, &KIO::PasteJob::itemCreated, operation, [operation](const QUrl &url) {
        operation->items.append(url.toString());
    });
    QObject::connect(job, &KJob::result, operation, [operation](KJob *finished) {
        operation->ok = !finished->error();
        operation->cancelled = finished->error() == KIO::ERR_USER_CANCELED;
        operation->error = finished->error() ? finished->errorString() : QString();
        // The native FileUndoManager must finish recording the subjob first.
        QTimer::singleShot(0, operation, [operation] { operation->done = true; });
    });
    return operation;
}

extern "C" const char *mirivue_clipboard_status(void *pointer)
{
    static thread_local QByteArray data;
    auto *operation = static_cast<ClipboardOperation *>(pointer);
    auto *manager = KIO::FileUndoManager::self();
    QJsonObject result{{"done", operation->done}, {"ok", operation->ok},
                       {"cancelled", operation->cancelled}, {"error", operation->error},
                       {"items", operation->items}, {"undo", manager->isUndoAvailable()},
                       {"redo", manager->isRedoAvailable()}};
    data = QJsonDocument(result).toJson(QJsonDocument::Compact);
    return data.constData();
}

extern "C" void mirivue_clipboard_cancel(void *pointer)
{
    auto *operation = static_cast<ClipboardOperation *>(pointer);
    if (operation->job) operation->job->kill(KJob::EmitResult);
}
extern "C" void mirivue_clipboard_release(void *pointer)
{
    static_cast<ClipboardOperation *>(pointer)->deleteLater();
}

extern "C" int mirivue_clipboard_can_paste()
{
    const auto *mime = QApplication::clipboard()->mimeData();
    return mime && !mime->hasUrls() && KIO::canPasteMimeData(mime);
}

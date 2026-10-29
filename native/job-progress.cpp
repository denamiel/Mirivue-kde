// SPDX-License-Identifier: MIT
// Publish Mirivue's checked local transfers through KDE's own job tracker.
// The actual file operation remains in the Python worker; this process only
// mirrors its progress and forwards Plasma's cancel/pause/resume requests.
#include <QCoreApplication>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSocketNotifier>
#include <QTimer>
#include <KJob>
#include <KUiServerV2JobTracker>

#include <unistd.h>

class MirivueProgressJob final : public KJob
{
public:
    explicit MirivueProgressJob(QObject *parent = nullptr) : KJob(parent)
    {
        setCapabilities(KJob::Killable | KJob::Suspendable);
        setAutoDelete(false);
        setProperty("desktopFileName", QStringLiteral("org.pdenams.Mirivue.Qt"));
    }

    void start() override {}
    QString errorString() const override { return errorText(); }

    void begin(const QJsonObject &data)
    {
        title = data.value("title").toString();
        destination = data.value("destination").toString();
        setProperty("destUrl", data.value("destinationUrl").toString());
    }

    void describe(int count)
    {
        Q_EMIT description(this, title,
                           QPair<QString, QString>{QStringLiteral("Vers"), destination},
                           QPair<QString, QString>{});
        setTotalAmount(KJob::Items, static_cast<qulonglong>(qMax(1, count)));
        setProcessedAmount(KJob::Items, 0);
    }

    void update(const QJsonObject &data)
    {
        if (done)
            return;
        const auto total = data.value("total").toInt();
        const auto completed = data.value("completed").toInt();
        if (total > 0)
            setPercent(static_cast<unsigned long>(qBound(0, data.value("value").toInt(), 100)));
        setProcessedAmount(KJob::Items, static_cast<qulonglong>(qMax(0, completed)));
        const QString message = data.value("message").toString();
        if (!message.isEmpty())
            Q_EMIT infoMessage(this, message);
    }

    void end(const QJsonObject &data)
    {
        if (done)
            return;
        done = true;
        if (!data.value("ok").toBool()) {
            setError(data.value("cancelled").toBool() ? KJob::KilledJobError : KJob::UserDefinedError);
            setErrorText(data.value("error").toString());
        } else {
            setPercent(100);
        }
        emitResult();
    }

protected:
    bool doKill() override
    {
        control("cancel");
        // The worker must finish its atomic cleanup before the job terminates.
        return false;
    }

    bool doSuspend() override { control("pause"); return true; }
    bool doResume() override { control("resume"); return true; }

private:
    bool done = false;
    QString title;
    QString destination;
    void control(const char *action)
    {
        const QByteArray data = QJsonDocument(QJsonObject{{"action", QString::fromLatin1(action)}}).toJson(QJsonDocument::Compact) + '\n';
        ::write(STDOUT_FILENO, data.constData(), static_cast<size_t>(data.size()));
    }
};

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setDesktopFileName(QStringLiteral("org.pdenams.Mirivue.Qt"));
    app.setApplicationName(QStringLiteral("Mirivue KDE"));
    KUiServerV2JobTracker tracker;
    MirivueProgressJob job;
    QSocketNotifier input(STDIN_FILENO, QSocketNotifier::Read);
    QByteArray pending;
    QObject::connect(&input, &QSocketNotifier::activated, &app, [&] {
        char chunk[4096];
        const ssize_t size = ::read(STDIN_FILENO, chunk, sizeof(chunk));
        if (size <= 0) {
            input.setEnabled(false);
            job.end({{"ok", false}, {"error", "Mirivue s'est arrêté."}});
            QTimer::singleShot(1500, &app, &QCoreApplication::quit);
            return;
        }
        pending.append(chunk, static_cast<qsizetype>(size));
        while (true) {
            const auto newline = pending.indexOf('\n');
            if (newline < 0)
                break;
            const auto data = QJsonDocument::fromJson(pending.left(newline)).object();
            pending.remove(0, newline + 1);
            const QString event = data.value("event").toString();
            if (event == QStringLiteral("start")) {
                job.begin(data);
                tracker.registerJob(&job);
                job.start();
                job.describe(data.value("count").toInt());
            } else if (event == QStringLiteral("progress")) {
                job.update(data);
            } else if (event == QStringLiteral("finish")) {
                job.end(data);
                input.setEnabled(false);
                QTimer::singleShot(1500, &app, &QCoreApplication::quit);
            }
        }
    });
    return app.exec();
}

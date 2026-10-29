// SPDX-License-Identifier: MIT
#include <QBuffer>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QGuiApplication>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QList>
#include <QProcess>
#include <QPixmap>
#include <QSaveFile>
#include <QSet>
#include <QSize>
#include <QStandardPaths>
#include <QUrl>
#include <cmath>

#include <KFileItem>
#include <KConfigGroup>
#include <KIO/PreviewJob>
#include <KSharedConfig>

static bool writePreview(const QString &path, const QImage &preview)
{
    QByteArray bytes;
    QBuffer buffer(&bytes);
    if (!buffer.open(QIODevice::WriteOnly) || !preview.save(&buffer, "PNG")) {
        return false;
    }
    QJsonObject result;
    result.insert("path", path);
    result.insert("png", QString::fromLatin1(bytes.toBase64()));
    const QByteArray line = QJsonDocument(result).toJson(QJsonDocument::Compact);
    fwrite(line.constData(), 1, static_cast<size_t>(line.size()), stdout);
    fputc('\n', stdout);
    fflush(stdout);
    return true;
}

// The video fallback is only reached after PreviewJob has finished without an
// image. It never changes Dolphin's plugin settings or replaces a KIO result.
static QByteArray capture(const QString &program, const QStringList &arguments, int timeoutMs)
{
    QProcess process;
    process.setProcessChannelMode(QProcess::SeparateChannels);
    process.start(program, arguments, QIODevice::ReadOnly);
    if (!process.waitForStarted(1000)) {
        return {};
    }
    QElapsedTimer timer;
    timer.start();
    while (process.state() != QProcess::NotRunning && timer.elapsed() < timeoutMs) {
        process.waitForFinished(qMin(100, timeoutMs - static_cast<int>(timer.elapsed())));
        if (process.bytesAvailable() > 20 * 1024 * 1024) {
            break;
        }
    }
    if (process.state() != QProcess::NotRunning) {
        process.kill();
        process.waitForFinished();
        return {};
    }
    return process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0
        ? process.readAllStandardOutput() : QByteArray{};
}

static double imageScore(const QImage &image)
{
    if (image.isNull()) {
        return -1;
    }
    const QImage gray = image.scaled(48, 48).convertToFormat(QImage::Format_Grayscale8);
    double sum = 0, squareSum = 0, visible = 0;
    const double count = gray.width() * gray.height();
    for (int y = 0; y < gray.height(); ++y) {
        const uchar *line = gray.constScanLine(y);
        for (int x = 0; x < gray.width(); ++x) {
            const double value = line[x];
            sum += value;
            squareSum += value * value;
            visible += value > 20 && value < 245;
        }
    }
    const double mean = sum / count;
    const double variance = qMax(0.0, squareSum / count - mean * mean);
    const double fraction = visible / count;
    return mean < 12 || mean > 245 || variance < 30 || fraction < 0.08
        ? -1 : std::sqrt(variance) * fraction;
}

static bool isVideo(const QString &path)
{
    static const QSet<QString> extensions = {
        "mkv", "mp4", "m4v", "avi", "mov", "webm", "wmv", "flv", "mpg",
        "mpeg", "m2v", "ts", "mts", "m2ts", "vob", "ogv", "3gp", "3g2",
        "divx", "asf", "mxf", "rm", "rmvb", "f4v", "qt"
    };
    return extensions.contains(QFileInfo(path).suffix().toLower());
}

static QImage videoFallback(const QString &path)
{
    const QFileInfo before(path);
    if (!before.isFile() || !before.isReadable()) {
        return {};
    }
    const QString key = QString::fromLatin1(QCryptographicHash::hash(
        (path + QLatin1Char('\n') + QString::number(before.size()) + QLatin1Char('\n')
            + before.lastModified().toString(Qt::ISODateWithMs)).toUtf8(),
        QCryptographicHash::Sha256).toHex());
    const QString cacheDir = QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation)
        + QStringLiteral("/mirivue/native-video-thumbnails");
    const QString cachePath = cacheDir + QLatin1Char('/') + key + QStringLiteral(".png");
    const QImage cached(cachePath);
    if (imageScore(cached) >= 0) {
        return cached;
    }

    const QByteArray probe = capture(QStringLiteral("ffprobe"), {
        "-v", "error", "-protocol_whitelist", "file", "-show_entries", "format=duration",
        "-of", "json", path
    }, 5000);
    const QJsonObject format = QJsonDocument::fromJson(probe).object().value("format").toObject();
    bool validDuration = false;
    const double duration = format.value("duration").toString().toDouble(&validDuration);
    const QList<double> positions = validDuration && std::isfinite(duration) && duration > 0
        ? QList<double>{duration * 0.1, duration * 0.35, duration * 0.6, duration * 0.85}
        : QList<double>{5, 20, 60, 0};
    QImage best;
    double bestScore = -1;
    for (double position : positions) {
        const QByteArray data = capture(QStringLiteral("ffmpeg"), {
            "-v", "error", "-nostdin", "-ss", QString::number(position),
            "-protocol_whitelist", "file", "-i", path, "-map", "0:v:0",
            "-frames:v", "1", "-vf", "scale=320:200:force_original_aspect_ratio=decrease",
            "-threads", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"
        }, 8000);
        const QImage candidate = QImage::fromData(data);
        const double score = imageScore(candidate);
        if (score > bestScore) {
            bestScore = score;
            best = candidate;
        }
        if (score >= 18) {
            break;
        }
    }
    const QFileInfo after(path);
    if (after.size() != before.size() || after.lastModified() != before.lastModified()) {
        return {};
    }
    if (!best.isNull() && QDir().mkpath(cacheDir)) {
        QSaveFile file(cachePath);
        if (file.open(QIODevice::WriteOnly) && best.save(&file, "PNG")) {
            file.commit();
        }
    }
    return best;
}

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    QSize previewSize(320, 200);
    int firstFile = 1;
    bool videoFallbackEnabled = false;
    if (argc > 1 && QString::fromLocal8Bit(argv[firstFile]) == QStringLiteral("--video-fallback")) {
        videoFallbackEnabled = true;
        ++firstFile;
    }
    if (argc >= firstFile + 4 && QString::fromLocal8Bit(argv[firstFile]) == QStringLiteral("--size")) {
        bool widthOk = false;
        bool heightOk = false;
        const int width = QString::fromLocal8Bit(argv[firstFile + 1]).toInt(&widthOk);
        const int height = QString::fromLocal8Bit(argv[firstFile + 2]).toInt(&heightOk);
        if (!widthOk || !heightOk || width < 1 || height < 1) {
            qCritical("invalid preview size");
            return 2;
        }
        previewSize = QSize(qMin(width, 4096), qMin(height, 4096));
        firstFile += 3;
    }
    if (argc <= firstFile) {
        qCritical("usage: mirivue-kio-preview [--video-fallback] [--size WIDTH HEIGHT] FILE [FILE ...]");
        return 2;
    }

    KFileItemList items;
    QSet<QString> delivered;
    for (int i = firstFile; i < argc; ++i) {
        const QFileInfo info(QString::fromLocal8Bit(argv[i]));
        if (!info.isFile()) {
            continue;
        }
        const QUrl url = QUrl::fromLocalFile(info.absoluteFilePath());
        items.append(KFileItem(url, KFileItem::NormalMimeTypeDetermination));
    }
    if (items.isEmpty()) {
        return 0;
    }

    // Use the same explicit preview selection as Dolphin. KIO's
    // defaultPlugins() intentionally excludes textthumbnail, even when the
    // user has enabled it in Dolphin's Preview Settings.
    const KConfigGroup previewSettings(KSharedConfig::openConfig(QStringLiteral("dolphinrc")), QStringLiteral("PreviewSettings"));
    QStringList plugins = previewSettings.readEntry("Plugins", KIO::PreviewJob::defaultPlugins());
    if (plugins.isEmpty()) {
        plugins = KIO::PreviewJob::defaultPlugins();
    }
    auto *job = KIO::filePreview(items, previewSize, &plugins);
    QObject::connect(job, &KIO::PreviewJob::gotPreview, [&delivered](const KFileItem &item, const QPixmap &preview) {
        const QString path = item.url().toLocalFile();
        if (!delivered.contains(path) && writePreview(path, preview.toImage())) {
            delivered.insert(path);
        }
    });
    QObject::connect(job, &KIO::PreviewJob::generated, [&delivered](const KFileItem &item, const QImage &preview) {
        const QString path = item.url().toLocalFile();
        if (!delivered.contains(path) && writePreview(path, preview)) {
            delivered.insert(path);
        }
    });
    QObject::connect(job, &KJob::result, &app, [&app, &items, &delivered, videoFallbackEnabled](KJob *) {
        if (videoFallbackEnabled) {
            for (const KFileItem &item : items) {
                const QString path = item.url().toLocalFile();
                if (!delivered.contains(path) && isVideo(path)
                    && writePreview(path, videoFallback(path))) {
                    delivered.insert(path);
                }
            }
        }
        app.quit();
    });
    return app.exec();
}

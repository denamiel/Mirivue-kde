// SPDX-License-Identifier: MIT
// Run in a child process: no user's settings, files or desktop session needed.
#include "path-navigator.h"
#include <KUrlComboBox>
#include <KUrlNavigator>
#include <QApplication>
#include <QCursor>
#include <QEventLoop>
#include <QFont>
#include <QHBoxLayout>
#include <QImage>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QLineEdit>
#include <QDir>
#include <QDateTime>
#include <QMainWindow>
#include <QToolBar>
#include <QSplitter>
#include <QFrame>
#include <QPalette>
#include <QStyleFactory>
#include <QStyleOptionFrame>
#include <QTimer>
#include <QUrl>
#include <QWidget>
#include <iostream>
#include <stdexcept>

static void require(bool condition, const char *message)
{
    if (!condition) {
        throw std::runtime_error(message);
    }
}

static void settle()
{
    QEventLoop loop;
    QTimer::singleShot(180, &loop, &QEventLoop::quit);
    loop.exec();
}

struct Fixture {
    QWidget host;
    QHBoxLayout layout{&host};
    KUrlNavigator *actual;
    KUrlNavigator *reference;

    Fixture()
        : actual(createPathNavigator(nullptr, QUrl::fromLocalFile(QStringLiteral("/tmp")), &host))
        , reference(new KUrlNavigator(nullptr, QUrl::fromLocalFile(QStringLiteral("/tmp")), &host))
    {
        layout.setContentsMargins(0, 0, 0, 0);
        layout.setSpacing(0);
        layout.addWidget(actual);
        layout.addWidget(reference);
        host.setFocusPolicy(Qt::StrongFocus);
        host.resize(1000, 160);
        host.show();
        host.activateWindow();
        host.setFocus();
        QCursor::setPos(10000, 10000);
        settle();
    }

    void freshReference()
    {
        layout.removeWidget(reference);
        delete reference;
        reference = new KUrlNavigator(nullptr, QUrl::fromLocalFile(QStringLiteral("/tmp")), &host);
        layout.addWidget(reference);
        reference->show();
        host.setFocus();
        settle();
    }

    void sameRendering(bool frameOnly = false)
    {
        require(actual->height() == reference->height(), "height differs from a fresh KDE navigator");
        require(actual->width() == reference->width(), "fixture widths differ");
        const QImage actualImage = actual->grab().toImage();
        const QImage referenceImage = reference->grab().toImage();
        bool equal = actualImage == referenceImage;
        if (frameOnly) {
            // KF6 caches some button spacing when created. Compare the frame
            // and its empty fill, independently of those breadcrumb buttons.
            const int width = actualImage.width();
            const int height = actualImage.height();
            equal = true;
            for (const QRect &area : {QRect(0, 0, width, 2), QRect(width / 2, height - 2, width / 2, 2),
                                      QRect(0, 0, 2, height), QRect(width - 2, 0, 2, height),
                                      QRect(width / 2, 0, width / 4, height)}) {
                equal &= actualImage.copy(area) == referenceImage.copy(area);
            }
        }
        if (!equal) {
            const auto directory = qEnvironmentVariable("MIRIVUE_TEST_NAVIGATOR_IMAGE_DIR");
            if (!directory.isEmpty()) {
                actualImage.save(directory + QStringLiteral("/actual.png"));
                referenceImage.save(directory + QStringLiteral("/reference.png"));
            }
            throw std::runtime_error("rendering differs from KDE navigator");
        }
    }
};

static QPalette testPalette(bool dark)
{
    QPalette palette = qApp->palette();
    // Deliberately distinct roles detect the old AlternateBase=Base override.
    for (auto group : {QPalette::Active, QPalette::Inactive, QPalette::Disabled}) {
        palette.setColor(group, QPalette::Base, dark ? QColor(24, 26, 28) : QColor(250, 249, 248));
        palette.setColor(group, QPalette::AlternateBase, dark ? QColor(43, 45, 47) : QColor(229, 231, 233));
        palette.setColor(group, QPalette::Window, dark ? QColor(54, 56, 58) : QColor(215, 217, 219));
        palette.setColor(group, QPalette::Text, dark ? Qt::white : Qt::black);
        palette.setColor(group, QPalette::WindowText, dark ? Qt::white : Qt::black);
    }
    return palette;
}

int main(int argc, char **argv)
{
    QApplication application(argc, argv);
    // Pixel equality compares two consecutive focused captures. A blinking
    // caret is not an application-rendering difference; freeze only its clock.
    // Diagnostic override reproduces the old failure without changing widgets.
    QApplication::setCursorFlashTime(qEnvironmentVariableIsSet("MIRIVUE_TEST_CAPTURE_FLASH")
        ? qEnvironmentVariableIntValue("MIRIVUE_TEST_CAPTURE_FLASH") : 0);
    const QString pluginPath = qEnvironmentVariable("MIRIVUE_TEST_KDE_PLUGIN_PATH");
    if (!pluginPath.isEmpty()) {
        application.addLibraryPath(pluginPath);
    }
    const QString requestedStyle = qEnvironmentVariable("MIRIVUE_TEST_STYLE", "breeze");
    if (auto *requested = QStyleFactory::create(requestedStyle)) {
        application.setStyle(requested);
    } else if (requestedStyle == QLatin1String("breeze")) {
        application.setStyle(QStyleFactory::create(QStringLiteral("fusion")));
    } else {
        std::cerr << "requested style is unavailable" << std::endl;
        return 2;
    }
    const QString scenario = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QString();
    if (scenario == QLatin1String("styles")) {
        QJsonArray styles;
        for (const auto &name : QStyleFactory::keys()) styles.append(name.toLower());
        std::cout << QJsonDocument(QJsonObject{{"styles", styles}}).toJson(QJsonDocument::Compact).constData() << std::endl;
        return 0;
    }
    try {
        if (scenario == QLatin1String("toolbar")) {
            QMainWindow window;
            auto *toolbar = window.addToolBar(QStringLiteral("Navigation"));
            auto *bar = new QWidget(toolbar);
            auto *layout = new QHBoxLayout(bar);
            auto *actualHost = new QFrame(bar);
            actualHost->setFrameShape(QFrame::NoFrame);
            auto *actualLayout = new QHBoxLayout(actualHost);
            actualLayout->setContentsMargins(0, 0, 0, 0);
            auto *referenceSplitter = new QSplitter(Qt::Horizontal, bar);
            auto *referenceHost = new QWidget(referenceSplitter);
            auto *referenceLayout = new QHBoxLayout(referenceHost);
            referenceLayout->setContentsMargins(0, 0, 0, 0);
            auto *actual = createPathNavigator(nullptr, QUrl::fromLocalFile(QStringLiteral("/tmp")), actualHost);
            auto *reference = new KUrlNavigator(nullptr, QUrl::fromLocalFile(QStringLiteral("/tmp")), referenceHost);
            actualLayout->addWidget(actual);
            referenceLayout->addWidget(reference);
            layout->addWidget(actualHost);
            layout->addWidget(referenceSplitter);
            toolbar->addWidget(bar);
            actual->setHighlightFocusIndicator(false);
            reference->setHighlightFocusIndicator(false);
            window.resize(1100, 240);
            window.show();
            window.activateWindow();
            window.setFocus();
            QCursor::setPos(10000, 10000);
            settle();
            const int height = std::max(actual->height(), reference->height());
            actual->setFixedSize(500, height);
            reference->setFixedSize(500, height);
            settle();
            const auto actualImage = actual->grab().toImage();
            const auto referenceImage = reference->grab().toImage();
            const auto images = qEnvironmentVariable("MIRIVUE_TEST_NAVIGATOR_IMAGE_DIR");
            if (!images.isEmpty()) {
                actualImage.save(images + QStringLiteral("/actual-toolbar.png"));
                referenceImage.save(images + QStringLiteral("/reference-toolbar.png"));
            }
            require(actualImage == referenceImage, "toolbar navigator differs from Dolphin construction");
            std::cout << "{\"scenario\":\"toolbar\",\"ok\":true}" << std::endl;
            return 0;
        }
        Fixture f;
        if (scenario == QLatin1String("palette")) {
            for (bool dark : {false, true, false}) {
                application.setPalette(testPalette(dark));
                settle();
                require(f.actual->palette() == f.reference->palette(), "palette does not follow KDE inheritance");
                require(f.actual->palette().resolveMask() == f.reference->palette().resolveMask(), "navigator resolves its own palette roles");
                f.sameRendering();
            }
        } else if (scenario == QLatin1String("font")) {
            const QFont original = f.host.font();
            const int originalHeight = f.actual->height();
            for (int increment : {5, 12, 0}) {
                QFont font = original;
                font.setPointSize(original.pointSize() + increment);
                f.host.setFont(font);
                settle();
                f.freshReference();
                f.sameRendering(true);
                if (increment) {
                    require(f.actual->height() > originalHeight, "larger font did not enlarge the native frame");
                } else {
                    require(f.actual->height() == originalHeight, "height did not return after reducing font");
                }
            }
        } else if (scenario == QLatin1String("style")) {
            const QString initial = application.style()->name();
            for (const auto &name : {QStringLiteral("fusion"), initial}) {
                application.setStyle(QStyleFactory::create(name));
                settle();
                f.freshReference();
                f.sameRendering(true);
            }
        } else if (scenario == QLatin1String("editor")) {
            QFont font = f.host.font();
            font.setPointSize(font.pointSize() + 5);
            f.host.setFont(font);
            settle();
            f.freshReference();
            for (auto *navigator : {f.actual, f.reference}) {
                navigator->setUrlEditable(true);
                navigator->editor()->lineEdit()->setFocus();
                settle();
            }
            f.actual->editor()->lineEdit()->setFocus();
            settle();
            if (const int delay = qEnvironmentVariableIntValue("MIRIVUE_TEST_CAPTURE_DELAY")) {
                QEventLoop delayLoop;
                QTimer::singleShot(delay, &delayLoop, &QEventLoop::quit);
                delayLoop.exec();
            }
            const QImage actual = f.actual->grab().toImage();
            f.reference->editor()->lineEdit()->setFocus();
            settle();
            const auto expected = f.reference->grab().toImage();
            if (actual != expected) {
                const QString directory = qEnvironmentVariable("MIRIVUE_TEST_NAVIGATOR_IMAGE_DIR");
                if (!directory.isEmpty()) {
                    QDir().mkpath(directory);
                    const QString prefix = directory + QLatin1Char('/') + requestedStyle + QLatin1Char('-') + QString::number(QDateTime::currentMSecsSinceEpoch());
                    actual.save(prefix + QStringLiteral("-actual.png"));
                    expected.save(prefix + QStringLiteral("-reference.png"));
                    QImage difference = actual;
                    for (int y = 0; y < actual.height(); ++y)
                        for (int x = 0; x < actual.width(); ++x)
                            difference.setPixel(x, y, actual.pixel(x,y) == expected.pixel(x,y) ? qRgb(0,0,0) : qRgb(255,255,255));
                    difference.save(prefix + QStringLiteral("-difference.png"));
                }
                std::cerr << "focus actual=" << f.actual->editor()->lineEdit()->hasFocus()
                          << " reference=" << f.reference->editor()->lineEdit()->hasFocus()
                          << " cursorFlashTime=" << QApplication::cursorFlashTime() << std::endl;
            }
            require(actual == expected, "editable mode differs from KDE");
            f.actual->setUrlEditable(false);
            f.reference->setUrlEditable(false);
            f.host.setFocus();
            settle();
            f.sameRendering();
        } else if (scenario == QLatin1String("active")) {
            f.actual->setHighlightFocusIndicator(false);
            f.actual->setActive(false);
            f.host.setFocus();
            settle();
            const auto image = f.actual->grab().toImage();
            const QRect frameArea(image.width() / 2, 0, image.width() / 4, image.height());
            f.actual->setActive(true);
            settle();
            require(image.copy(frameArea) == f.actual->grab().toImage().copy(frameArea), "pane activation changes the neutral frame");
            f.reference->setActive(true);
            f.sameRendering();
        } else {
            throw std::runtime_error("unknown navigator check");
        }
        const QJsonObject result{{QStringLiteral("scenario"), scenario},
                                 {QStringLiteral("style"), application.style()->name()},
                                 {QStringLiteral("height"), f.actual->height()},
                                 {QStringLiteral("ok"), true}};
        std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
        return 0;
    } catch (const std::exception &error) {
        std::cerr << scenario.toStdString() << ": " << error.what() << std::endl;
        return 1;
    }
}

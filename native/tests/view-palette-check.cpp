// SPDX-License-Identifier: MIT
// Compare the real view adapter with DolphinView::updatePalette's viewport policy.
#include <KColorScheme>
#include <QAbstractScrollArea>
#include <QApplication>
#include <QEventLoop>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QHBoxLayout>
#include <QImage>
#include <QItemSelectionModel>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPalette>
#include <QStandardItemModel>
#include <QStyleFactory>
#include <QStyle>
#include <QTimer>
#include <iostream>
#include <stdexcept>

extern "C" {
void *mirivue_dolphin_create(void *, void *, void *, int (*)(const char *));
void *mirivue_dolphin_widget(void *);
void mirivue_dolphin_set_active(void *, int);
void mirivue_dolphin_configure(void *, const char *);
}

static void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}

static void settle()
{
    QEventLoop loop;
    QTimer::singleShot(35, &loop, &QEventLoop::quit);
    loop.exec();
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    const QString pluginPath = qEnvironmentVariable("MIRIVUE_TEST_KDE_PLUGIN_PATH");
    if (!pluginPath.isEmpty()) app.addLibraryPath(pluginPath);
    const QString requested = qEnvironmentVariable("MIRIVUE_TEST_STYLE", "breeze");
    auto *style = QStyleFactory::create(requested);
    if (!style && requested == QLatin1String("breeze")) style = QStyleFactory::create(QStringLiteral("fusion"));
    if (!style) return 2;
    app.setStyle(style);
    const QString scenario = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QString();
    try {
        QWidget host;
        host.setAutoFillBackground(true);
        QHBoxLayout layout(&host);
        layout.setContentsMargins(0, 0, 0, 0);
        QStandardItemModel model(0, 1);
        model.setHorizontalHeaderLabels({QStringLiteral("Name")});
        QItemSelectionModel selection(&model);
        void *backend = mirivue_dolphin_create(&model, &selection, &host, nullptr);
        auto *actual = static_cast<QAbstractScrollArea *>(mirivue_dolphin_widget(backend));
        auto *actualGraphics = qobject_cast<QGraphicsView *>(actual->viewport());
        require(actualGraphics, "actual viewport is not a graphics view");
        // Dolphin applies its View colour to this QGraphicsView background role.
        // Use the same pinned KItemListContainer for the reference. Its nested
        // viewport and native style handling cannot be represented by a plain
        // QGraphicsView. Apply DolphinView::updatePalette independently below.
        QItemSelectionModel referenceSelection(&model);
        void *referenceBackend = mirivue_dolphin_create(&model, &referenceSelection, &host, nullptr);
        auto *referenceContainer = static_cast<QAbstractScrollArea *>(mirivue_dolphin_widget(referenceBackend));
        auto *reference = qobject_cast<QGraphicsView *>(referenceContainer->viewport());
        require(actual->frameShape() == QFrame::StyledPanel,
                "the file container lost Dolphin's native frame");
        layout.addWidget(actual);
        layout.addWidget(referenceContainer);
        host.resize(1000, 400);
        mirivue_dolphin_configure(backend, "{\"mode\":0,\"columns\":[0],\"iconSize\":22,\"automatic\":true,\"fill\":true,\"alternate\":true}");
        mirivue_dolphin_configure(referenceBackend, "{\"mode\":0,\"columns\":[0],\"iconSize\":22,\"automatic\":true,\"fill\":true,\"alternate\":true}");
        host.show();
        host.activateWindow();
        settle();
        bool active = true;
        const auto check = [&] {
            QColor expected = KColorScheme(host.isActiveWindow() ? QPalette::Active : QPalette::Inactive,
                                           KColorScheme::View).background().color();
            if (!active) expected.setAlpha(150); // DolphinView::updatePalette().
            QPalette referencePalette;
            referencePalette.setColor(reference->backgroundRole(), expected);
            reference->setPalette(referencePalette);
            settle();
            require(actualGraphics->palette().color(actualGraphics->backgroundRole()) == expected,
                    "viewport colour or opacity differs from Dolphin");
            // Grab the common parent so translucent child backgrounds are
            // composited over the same Window brush, as in a desktop screenshot.
            const auto image = host.grab().toImage();
            const QPoint point(100, 200);
            const auto actualPixel = image.pixelColor(actualGraphics->viewport()->mapTo(&host, point));
            const auto referencePixel = image.pixelColor(reference->viewport()->mapTo(&host, point));
            if (actualPixel != referencePixel) {
                std::cerr << "expected " << expected.name(QColor::HexArgb).toStdString()
                          << " actual " << actualPixel.name(QColor::HexArgb).toStdString()
                          << " reference " << referencePixel.name(QColor::HexArgb).toStdString()
                          << " actual-viewport-role " << actualGraphics->viewport()->backgroundRole()
                          << " ref-viewport-role " << reference->viewport()->backgroundRole()
                          << " graphics-role " << actualGraphics->backgroundRole()
                          << " graphics-auto " << actualGraphics->autoFillBackground()
                          << " canvas-auto " << actualGraphics->viewport()->autoFillBackground()
                          << " canvas-window " << actualGraphics->viewport()->palette().window().color().name().toStdString()
                          << " actual-base " << actualGraphics->palette().base().color().name().toStdString()
                          << " ref-base " << reference->palette().base().color().name().toStdString() << std::endl;
            }
            require(actualPixel == referencePixel, "painted viewport differs from Dolphin reference");
        };
        if (scenario == QLatin1String("background")) {
            for (bool state : {true, false, true}) {
                active = state;
                mirivue_dolphin_set_active(backend, state);
                check();
            }
        } else if (scenario == QLatin1String("activation")) {
            QWidget other;
            other.resize(100, 100);
            other.show();
            other.activateWindow();
            settle();
            require(!host.isActiveWindow(), "test window did not become inactive");
            check();
            active = false;
            mirivue_dolphin_set_active(backend, false);
            check();
            host.activateWindow();
            settle();
            require(host.isActiveWindow(), "test window did not reactivate");
            check();
        } else if (scenario == QLatin1String("themes")) {
            const QPalette original = app.palette();
            // Deliberately unrelated Window colours detect propagation of that
            // role into the file background. These are fixture colours only.
            for (const QColor &window : {QColor(230, 235, 240), QColor(38, 45, 52)}) {
                QPalette palette = original;
                palette.setColor(QPalette::Window, window);
                app.setPalette(palette);
                settle();
                check();
                active = false;
                mirivue_dolphin_set_active(backend, false);
                check();
                active = true;
                mirivue_dolphin_set_active(backend, true);
            }
            app.setPalette(original);
        } else if (scenario == QLatin1String("modes")) {
            for (int mode : {0, 1, 2, 0}) {
                const auto bytes = QJsonDocument(QJsonObject{{"mode", mode}, {"columns", QJsonArray{0}},
                    {"iconSize", 22}, {"automatic", true}, {"fill", true}, {"alternate", true}}).toJson();
                mirivue_dolphin_configure(backend, bytes.constData());
                check();
            }
        } else throw std::runtime_error("unknown palette scenario");
        std::cout << QJsonDocument(QJsonObject{{"ok", true}, {"scenario", scenario}, {"style", app.style()->name()}})
                         .toJson(QJsonDocument::Compact).constData() << std::endl;
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
    return 0;
}

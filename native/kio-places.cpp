// SPDX-License-Identifier: MIT
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QEventLoop>
#include <QMimeData>
#include <QTimer>

#include <memory>
#include <QUrl>

#include <KFilePlacesModel>

static QJsonArray placesJson(KFilePlacesModel &model)
{
    QJsonArray places;
    for (int row = 0; row < model.rowCount(); ++row) {
        const QModelIndex index = model.index(row, 0);
        if (!index.isValid()) {
            continue;
        }
        const QUrl url = model.url(index);
        if (!url.isValid() || url.isEmpty()) {
            continue;
        }

        QJsonObject place;
        place.insert(QStringLiteral("name"), model.text(index));
        place.insert(QStringLiteral("url"), url.toString(QUrl::FullyEncoded));
        place.insert(QStringLiteral("icon"), model.data(index, KFilePlacesModel::IconNameRole).toString());
        place.insert(QStringLiteral("group"), static_cast<int>(model.groupType(index)));
        place.insert(QStringLiteral("device"), model.isDevice(index));
        place.insert(QStringLiteral("fixed"), model.data(index, KFilePlacesModel::FixedDeviceRole).toBool());
        place.insert(QStringLiteral("setupNeeded"), model.setupNeeded(index));
        place.insert(QStringLiteral("teardownAllowed"), model.isTeardownAllowed(index));
        place.insert(QStringLiteral("ejectAllowed"), model.isEjectAllowed(index));
        place.insert(QStringLiteral("sharedHidden"), model.isHidden(index) && !model.isGroupHidden(index));
        place.insert(QStringLiteral("sharedGroupHidden"), model.isGroupHidden(model.groupType(index)));
        places.append(place);
    }
    return places;
}

static QModelIndex findUrl(KFilePlacesModel &model, const QUrl &url)
{
    for (int row = 0; row < model.rowCount(); ++row) {
        const QModelIndex index = model.index(row, 0);
        if (index.isValid() && model.url(index) == url) {
            return index;
        }
    }
    return {};
}

int main(int argc, char **argv)
{
    // KFilePlacesModel is part of KIO FileWidgets and resolves both themed
    // icons and widget-level desktop integration.  QCoreApplication aborts
    // before producing JSON on some Plasma setups; QApplication supplies the
    // required Qt GUI and Widgets services.  It remains headless-compatible
    // through Qt's normal offscreen platform plugin used by automated tests.
    QApplication app(argc, argv);
    // Solid populates device places on the event loop, after construction.
    // Keep it running for mount/unmount requests as well.
    app.setQuitLockEnabled(false);
    app.setApplicationName(QStringLiteral("mirivue"));
    KFilePlacesModel model;
    const QStringList args = app.arguments();
    QJsonObject result;

    if (args.size() == 2 && args.at(1) == QStringLiteral("watch")) {
        const auto changed = []() {
            fprintf(stdout, "{\"event\":\"changed\"}\n");
            fflush(stdout);
        };
        QObject::connect(&model, &QAbstractItemModel::rowsInserted, &app, changed);
        QObject::connect(&model, &QAbstractItemModel::rowsRemoved, &app, changed);
        QObject::connect(&model, &QAbstractItemModel::dataChanged, &app, changed);
        QObject::connect(&model, &QAbstractItemModel::modelReset, &app, changed);
        return app.exec();
    }

    QEventLoop initialization;
    QTimer::singleShot(50, &initialization, &QEventLoop::quit);
    initialization.exec();

    if (args.size() == 2 && args.at(1) == QStringLiteral("list")) {
        result.insert(QStringLiteral("ok"), true);
        result.insert(QStringLiteral("places"), placesJson(model));
    } else if (args.size() == 5 && args.at(1) == QStringLiteral("add")) {
        const QUrl url = QUrl::fromUserInput(args.at(3));
        if (!url.isValid() || url.isEmpty()) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("invalid URL"));
        } else if (!findUrl(model, url).isValid()) {
            model.addPlace(args.at(2), url, args.at(4));
            result.insert(QStringLiteral("ok"), true);
        } else {
            result.insert(QStringLiteral("ok"), true);
        }
    } else if (args.size() == 3 && args.at(1) == QStringLiteral("remove")) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        if (index.isValid() && !model.isDevice(index)) {
            model.removePlace(index);
        }
        result.insert(QStringLiteral("ok"), true);
    } else if (args.size() == 3 && (args.at(1) == QStringLiteral("teardown") || args.at(1) == QStringLiteral("eject"))) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        if (!index.isValid() || !model.isDevice(index)) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("device is unavailable"));
        } else {
            QObject::connect(&model, &KFilePlacesModel::teardownDone, &app,
                             [&app, &result](const QModelIndex &, Solid::ErrorType error, const QVariant &) {
                                 const bool success = error == Solid::NoError;
                                 result.insert(QStringLiteral("ok"), success);
                                 if (!success) {
                                     result.insert(QStringLiteral("error"), QStringLiteral("device could not be unmounted"));
                                 }
                                 const QByteArray output = QJsonDocument(result).toJson(QJsonDocument::Compact);
                                 fprintf(stdout, "%s\n", output.constData());
                                 fflush(stdout);
                                 app.quit();
                             });
            if (args.at(1) == QStringLiteral("eject")) {
                model.requestEject(index);
            } else {
                model.requestTeardown(index);
            }
            return app.exec();
        }
    } else if (args.size() == 4 && args.at(1) == QStringLiteral("rename")) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        if (!index.isValid() || model.isDevice(index)) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("place cannot be renamed"));
        } else {
            model.editPlace(index, args.at(3), model.url(index), model.data(index, KFilePlacesModel::IconNameRole).toString());
            result.insert(QStringLiteral("ok"), true);
        }
    } else if (args.size() == 4 && args.at(1) == QStringLiteral("relocate")) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        const QUrl destination = QUrl::fromUserInput(args.at(3));
        if (!index.isValid() || model.isDevice(index) || !destination.isValid()) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("place cannot be relocated"));
        } else {
            model.editPlace(index, model.text(index), destination, model.data(index, KFilePlacesModel::IconNameRole).toString());
            result.insert(QStringLiteral("ok"), true);
        }
    } else if (args.size() == 3 && args.at(1) == QStringLiteral("reorder")) {
        const QJsonDocument order = QJsonDocument::fromJson(args.at(2).toUtf8());
        if (!order.isArray()) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("invalid order"));
        } else {
            int targetRow = 0;
            QJsonArray moves;
            for (const QJsonValue &value : order.array()) {
                const QModelIndex index = findUrl(model, QUrl::fromUserInput(value.toString()));
                if (index.isValid() && model.groupType(index) == KFilePlacesModel::PlacesType && index.row() != targetRow) {
                    const QModelIndexList selected{index};
                    std::unique_ptr<QMimeData> mime(model.mimeData(selected));
                    moves.append(mime && model.dropMimeData(mime.get(), Qt::MoveAction, targetRow, 0, QModelIndex()));
                } else {
                    moves.append(true);
                }
                ++targetRow;
            }
            result.insert(QStringLiteral("ok"), true);
            result.insert(QStringLiteral("moves"), moves);
        }
    } else if (args.size() == 4 && args.at(1) == QStringLiteral("place-hidden")) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        if (!index.isValid()) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("place is unavailable"));
        } else {
            model.setPlaceHidden(index, args.at(3) == QStringLiteral("true"));
            result.insert(QStringLiteral("ok"), true);
        }
    } else if (args.size() == 4 && args.at(1) == QStringLiteral("group-hidden")) {
        bool validGroup = false;
        const int rawGroup = args.at(2).toInt(&validGroup);
        if (!validGroup) {
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("invalid places group"));
        } else {
            const auto group = static_cast<KFilePlacesModel::GroupType>(rawGroup);
            model.setGroupHidden(group, args.at(3) == QStringLiteral("true"));
            result.insert(QStringLiteral("ok"), true);
        }
    } else if (args.size() == 3 && args.at(1) == QStringLiteral("setup")) {
        const QModelIndex index = findUrl(model, QUrl::fromUserInput(args.at(2)));
        if (!index.isValid() || !model.setupNeeded(index)) {
            result.insert(QStringLiteral("ok"), index.isValid());
        } else {
            QObject::connect(&model, &KFilePlacesModel::setupDone, &app,
                             [&app, &result](const QModelIndex &, bool success) {
                                 result.insert(QStringLiteral("ok"), success);
                                 if (!success) {
                                     result.insert(QStringLiteral("error"), QStringLiteral("device setup failed"));
                                 }
                                 const QByteArray output = QJsonDocument(result).toJson(QJsonDocument::Compact);
                                 fprintf(stdout, "%s\n", output.constData());
                                 fflush(stdout);
                                 app.quit();
                             });
            model.requestSetup(index);
            return app.exec();
        }
    } else {
        result.insert(QStringLiteral("ok"), false);
        result.insert(QStringLiteral("error"), QStringLiteral("invalid arguments"));
    }

    const QByteArray output = QJsonDocument(result).toJson(QJsonDocument::Compact);
    fprintf(stdout, "%s\n", output.constData());
    return result.value(QStringLiteral("ok")).toBool() ? 0 : 1;
}

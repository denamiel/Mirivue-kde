// SPDX-FileCopyrightText: 2009-2010 Peter Penz <peter.penz19@gmail.com>
// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: GPL-2.0-or-later
// Service discovery/configuration adapted from Dolphin v26.08.2
// src/settings/contextmenu/contextmenusettingspage.cpp.
// Adaptations: native Qt item model, JSON bridge, Mirivue-owned builtin flags.
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QFileInfo>
#include <QLineEdit>
#include <QListView>
#include <QPushButton>
#include <QScroller>
#include <QSet>
#include <QSortFilterProxyModel>
#include <QStandardItemModel>
#include <QStandardPaths>
#include <QVBoxLayout>
#include <KConfig>
#include <KConfigGroup>
#include <KDesktopFile>
#include <KFileUtils>
#include <KPluginMetaData>
#include <KService>
#include <KServiceAction>
#include <KSharedConfig>
#include <KNSWidgets/Button>

namespace {
enum Roles { IdRole = Qt::UserRole + 1, BuiltinRole, DefaultRole, InitialRole };
using Callback = void (*)(const char *);

// Stable identities, independent of translations; no commands are executed.
QJsonArray serviceCatalog() {
    QJsonArray result;
    QSet<QString> seen;
    const auto locations = QStandardPaths::locateAll(QStandardPaths::GenericDataLocation,
        QStringLiteral("kio/servicemenus"), QStandardPaths::LocateDirectory);
    for (const auto &file : KFileUtils::findAllUniqueFiles(locations)) {
        const KDesktopFile desktop(file);
        const KService service(file);
        const auto submenu = desktop.desktopGroup().readEntry("X-KDE-Submenu");
        for (const auto &action : service.actions()) {
            if (action.noDisplay() || action.isSeparator() || seen.contains(action.name())) continue;
            seen.insert(action.name());
            QString origin = service.name();
            if (origin.isEmpty()) origin = QFileInfo(file).fileName();
            if (action.name() == QStringLiteral("runInKonsole")) origin = QStringLiteral("Konsole");
            result.append(QJsonObject{{"id", action.name()}, {"text", submenu.isEmpty() ? action.text() : submenu + QStringLiteral(": ") + action.text()},
                {"icon", action.icon()}, {"source", file}, {"origin", origin}, {"default", true}});
        }
    }
    for (const auto &plugin : KPluginMetaData::findPlugins(QStringLiteral("kf6/kfileitemaction"))) {
        const auto id = plugin.pluginId();
        if (seen.contains(id)) continue;
        seen.insert(id);
        QString text = plugin.name();
        QString origin = QFileInfo(plugin.fileName()).completeBaseName();
        if (id == QStringLiteral("compressfileitemaction")) { text = QStringLiteral("Compresser"); origin = QStringLiteral("Ark"); }
        if (id == QStringLiteral("extractfileitemaction")) { text = QStringLiteral("Extraire"); origin = QStringLiteral("Ark"); }
        result.append(QJsonObject{{"id", id}, {"text", text}, {"icon", plugin.iconName()},
            {"source", plugin.fileName()}, {"origin", origin}, {"default", id != QStringLiteral("hidefileitemaction")}});
    }
    return result;
}

class ContextSettings final : public QWidget {
public:
    QStandardItemModel model;
    class Filter final : public QSortFilterProxyModel {
    public:
        using QSortFilterProxyModel::QSortFilterProxyModel;
        bool filterAcceptsRow(int row, const QModelIndex &parent) const override {
            return !sourceModel()->index(row, 0, parent).data(Qt::UserRole + 20).toBool()
                && QSortFilterProxyModel::filterAcceptsRow(row, parent);
        }
    } proxy;
    Callback callback;

    ContextSettings(QWidget *parent, const QJsonObject &input, Callback notify)
        : QWidget(parent), model(this), proxy(this), callback(notify) {
        setObjectName(QStringLiteral("contextMenuSettings"));
        const auto labels = input.value("labels").toObject();
        auto *layout = new QVBoxLayout(this);
        layout->setContentsMargins(0, 0, 0, 0);
        auto *top = new QHBoxLayout;
        auto *search = new QLineEdit(this);
        search->setObjectName(QStringLiteral("contextMenuSearch"));
        search->setPlaceholderText(labels.value("search").toString());
        search->setClearButtonEnabled(true);
        top->addWidget(search, 1);
        auto *download = new KNSWidgets::Button(labels.value("download").toString(), input.value("knsrc").toString(), this);
        download->setObjectName(QStringLiteral("contextMenuDownload"));
        // Dolphin's installer handles archives and scripts with its own checks.
        // Do not substitute a shell invocation or a different installer.
        const bool installer = !QStandardPaths::findExecutable(QStringLiteral("servicemenuinstaller")).isEmpty();
        download->setEnabled(installer);
        if (!installer) download->setToolTip(labels.value("installerMissing").toString());
        connect(download, &KNSWidgets::Button::dialogFinished, this, [this](const auto &changed) {
            if (!changed.isEmpty()) loadServices(true);
        });
        top->addWidget(download);
        auto *shortcuts = new QPushButton(QIcon::fromTheme(QStringLiteral("configure-shortcuts")), labels.value("shortcuts").toString(), this);
        shortcuts->setObjectName(QStringLiteral("contextMenuShortcuts"));
        connect(shortcuts, &QPushButton::clicked, this, [this] { if (callback) callback("shortcuts"); });
        top->addWidget(shortcuts);
        layout->addLayout(top);

        auto *view = new QListView(this);
        view->setObjectName(QStringLiteral("contextMenuEntries"));
        view->setEditTriggers(QAbstractItemView::NoEditTriggers);
        view->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);
        QScroller::grabGesture(view->viewport(), QScroller::TouchGesture);
        proxy.setSourceModel(&model);
        proxy.setSortLocaleAware(true);
        proxy.setFilterCaseSensitivity(Qt::CaseInsensitive);
        proxy.setFilterRole(Qt::DisplayRole);
        view->setModel(&proxy);
        connect(search, &QLineEdit::textChanged, &proxy, &QSortFilterProxyModel::setFilterFixedString);
        layout->addWidget(view, 1);
        auto *notice = new QLabel(labels.value("notice").toString(), this);
        notice->setWordWrap(true);
        layout->addWidget(notice);
        auto *bottom = new QHBoxLayout;
        auto *defaults = new QPushButton(QIcon::fromTheme(QStringLiteral("document-revert")), labels.value("defaults").toString(), this);
        defaults->setObjectName(QStringLiteral("contextMenuDefaults"));
        connect(defaults, &QPushButton::clicked, this, [this] { restoreDefaults(); });
        bottom->addWidget(defaults);
        bottom->addStretch();
        layout->addLayout(bottom);

        for (const auto &value : input.value("entries").toArray()) {
            const auto row = value.toObject();
            add(row.value("id").toString(), row.value("text").toString(), row.value("icon").toString(),
                row.value("checked").toBool(), row.value("default").toBool(), true, labels.value("builtin").toString());
        }
        loadServices(false);
    }

    void add(const QString &id, const QString &text, const QString &icon,
             bool checked, bool standard, bool builtin, const QString &source) {
        auto *item = new QStandardItem(QIcon::fromTheme(icon), text);
        item->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsUserCheckable);
        item->setCheckState(checked ? Qt::Checked : Qt::Unchecked);
        item->setData(id, IdRole);
        item->setData(builtin, BuiltinRole);
        item->setData(standard, DefaultRole);
        item->setData(checked, InitialRole);
        item->setToolTip(source);
        model.appendRow(item);
    }

    void loadServices(bool preserveDraft) {
        QHash<QString, QPair<bool, bool>> draft;
        for (int row = model.rowCount() - 1; row >= 0; --row) {
            auto *item = model.item(row);
            if (!item->data(BuiltinRole).toBool()) {
                if (preserveDraft) draft.insert(item->data(IdRole).toString(),
                    {item->checkState() == Qt::Checked, item->data(InitialRole).toBool()});
                model.removeRow(row);
            }
        }
        KConfig config(QStringLiteral("kservicemenurc"), KConfig::NoGlobals);
        const auto show = config.group(QStringLiteral("Show"));
        QSet<QString> seen;
        auto service = [&](const QString &id, const QString &text, const QString &icon, const QString &source, bool standard) {
            if (id.isEmpty() || seen.contains(id)) return;
            seen.insert(id);
            const bool saved = show.readEntry(id, standard);
            const auto previous = draft.constFind(id);
            add(id, text, icon, previous == draft.cend() ? saved : previous->first, standard, false, source);
            if (previous != draft.cend()) model.item(model.rowCount()-1)->setData(previous->second, InitialRole);
        };
        const auto catalog = serviceCatalog();
        bool nativeKonsole = false;
        bool nativeCompression = false;
        for (const auto &value : catalog) nativeKonsole |= value.toObject().value("id").toString() == QStringLiteral("runInKonsole");
        for (const auto &value : catalog) nativeCompression |= value.toObject().value("id").toString() == QStringLiteral("compressfileitemaction");
        for (int row = 0; row < model.rowCount(); ++row) {
            auto *item = model.item(row);
            if (item->data(BuiltinRole).toBool() && (item->data(IdRole).toString() == QStringLiteral("run_in_konsole") || item->data(IdRole).toString() == QStringLiteral("create_archive"))) {
                // Keep the fallback row for disappearance/reinstallation, but
                // expose a single checkbox owned by KDE while installed.
                item->setData(item->data(IdRole).toString() == QStringLiteral("run_in_konsole") ? nativeKonsole : nativeCompression, Qt::UserRole + 20);
            }
        }
        for (const auto &value : catalog) {
            const auto row = value.toObject();
            const auto id = row.value("id").toString();
            // Mirivue's operation goes through its KIO service/undo history.
            if (id == QStringLiteral("movetonewfolderitemaction")) continue;
            auto label = row.value("text").toString();

            service(id, label, row.value("icon").toString(), row.value("source").toString(), row.value("default").toBool());
        }
        proxy.invalidate();
        proxy.sort(0);
    }

    void restoreDefaults() {
        for (int row = 0; row < model.rowCount(); ++row) {
            auto *item = model.item(row);
            item->setCheckState(item->data(DefaultRole).toBool() ? Qt::Checked : Qt::Unchecked);
        }
    }

    QJsonObject result(bool save) {
        QJsonObject builtins, services;
        QJsonArray labels;
        auto config = KSharedConfig::openConfig(QStringLiteral("kservicemenurc"), KConfig::NoGlobals);
        if (save) config->reparseConfiguration();
        auto show = config->group(QStringLiteral("Show"));
        QList<QStandardItem *> changed;
        for (int row = 0; row < model.rowCount(); ++row) {
            auto *item = model.item(row);
            if (!item->data(Qt::UserRole + 20).toBool()) labels.append(item->text());
            const auto id = item->data(IdRole).toString();
            const bool checked = item->checkState() == Qt::Checked;
            if (item->data(BuiltinRole).toBool()) {
                if (!item->data(Qt::UserRole + 20).toBool()) builtins.insert(id, checked);
            }
            else {
                services.insert(id, checked);
                if (save && checked != item->data(InitialRole).toBool()) {
                    show.writeEntry(id, checked);
                    changed.append(item);
                }
            }
        }
        const bool success = !save || changed.isEmpty() || show.sync();
        if (success && save)
            for (auto *item : changed) item->setData(item->checkState() == Qt::Checked, InitialRole);
        return {{"ok", success}, {"builtins", builtins}, {"services", services}, {"labels", labels}};
    }
};
}

extern "C" {
void *mirivue_context_settings_create(void *parent, const char *input, Callback callback) {
    if (!parent || !input || !QApplication::instance()) return nullptr;
    return new ContextSettings(static_cast<QWidget *>(parent), QJsonDocument::fromJson(input).object(), callback);
}
const char *mirivue_context_settings_result(void *pointer, int save) {
    static thread_local QByteArray result;
    if (!pointer) return nullptr;
    result = QJsonDocument(static_cast<ContextSettings *>(pointer)->result(save != 0)).toJson(QJsonDocument::Compact);
    return result.constData();
}
const char *mirivue_context_service_catalog() {
    static thread_local QByteArray result;
    result = QJsonDocument(serviceCatalog()).toJson(QJsonDocument::Compact);
    return result.constData();
}
int mirivue_context_service_enabled(const char *id, int standard) {
    if (!id) return standard;
    KConfig config(QStringLiteral("kservicemenurc"), KConfig::NoGlobals);
    return config.group(QStringLiteral("Show")).readEntry(QString::fromUtf8(id), standard != 0);
}
}

// SPDX-FileCopyrightText: 2007 Peter Penz <peter.penz19@gmail.com>
// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: GPL-2.0-or-later
// Location captions adapt Dolphin v26.08.2 DolphinViewContainer::caption().
// Original: src/dolphinviewcontainer.cpp, KDE/system/dolphin.
// Earlier original Mirivue portions remain available under their MIT grant.
#include <QApplication>
#include <QAction>
#include <QDropEvent>
#include <QDragMoveEvent>
#include <QIcon>
#include <QMenu>
#include <QMimeData>
#include <QSize>
#include <QUrl>
#include <QWidget>
#include <QSignalBlocker>
#include <QTimer>
#include <QLineEdit>
#include <QTabBar>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrlQuery>
#include <QFileInfo>
#include <cstring>
#include <KColorScheme>
#include <KWindowSystem>
#include <KStartupInfo>
#include <QWindow>
#include <KFormat>
#include <QDateTime>
#include <QLocale>
#include <KStringHandler>
#include <KFileItem>
#include <KFileItemActions>
#include <KServiceAction>
#include <KService>
#include <KPluginMetaData>
#if __has_include(<KDesktopFileAction>)
#include <KDesktopFileAction>
#endif
#include <KFileItemListProperties>
#include <sys/stat.h>

#include <KConfigGroup>
#include <KFilePlacesModel>
#include <KFilePlacesView>
#include <KIconTheme>
#include <KStyleManager>
#include <KToolBar>
#include <KUrlNavigator>
#include <KUrlComboBox>
#include <KProtocolManager>
#include <KSharedConfig>
#include <KIO/DropJob>
#include <KIO/Global>
#include <KIO/DeleteOrTrashJob>
#include <KJobWidgets>
#include "path-navigator.h"

// Keep the view in the same Qt process as PySide. A separate window cannot
// be embedded reliably under Wayland. The Python callbacks are invoked on
// the GUI thread and remain owned by the Python-side adapter.
using PlaceCallback = void (*)(const char *);
using TrashHasItemsCallback = int (*)();

class MirivuePlacesView final : public KFilePlacesView {
public:
    using KFilePlacesView::KFilePlacesView;

protected:
    void dragMoveEvent(QDragMoveEvent *event) override {
        const QModelIndex index = indexAt(event->position().toPoint());
        if (index.isValid() && event->mimeData()->hasUrls()) {
            bool internal = false;
            for (const QString &format : event->mimeData()->formats()) {
                internal |= format.startsWith(QStringLiteral("application/x-kfileplacesmodel-"));
            }
            if (!internal && !KProtocolManager::supportsWriting(
                    static_cast<KFilePlacesModel *>(model())->url(index))) {
                event->setDropAction(Qt::IgnoreAction);
                event->ignore();
                return;
            }
        }
        KFilePlacesView::dragMoveEvent(event);
    }
};

extern "C" {

// Same order as DolphinTabWidget::tabName: escape accelerators, then rsqueeze.
const char *mirivue_tab_text(const char *text) {
    static thread_local QByteArray result;
    const auto escaped = QString::fromUtf8(text ? text : "").replace(QLatin1Char('&'), QStringLiteral("&&"));
    result = KStringHandler::rsqueeze(escaped, 40).toUtf8();
    return result.constData();
}

// Keep QString UTF-16 units intact, even if rsqueeze cuts a surrogate pair.
// A UTF-8 round trip through Python would discard that unpaired unit.
int mirivue_tab_set_text(void *bar, int index, const char *text) {
    auto *tabs = static_cast<QTabBar *>(bar);
    if (!tabs || index < 0 || index >= tabs->count()) return -1;
    const auto escaped = QString::fromUtf8(text ? text : "").replace(QLatin1Char('&'), QStringLiteral("&&"));
    tabs->setTabText(index, KStringHandler::rsqueeze(escaped, 40));
    return tabs->tabText(index).size();
}

void *mirivue_service_actions_create(void *parent, void *window, const char *urlsJson)
{
    if (!QApplication::instance() || !parent || !urlsJson) {
        return nullptr;
    }
    const QJsonDocument document = QJsonDocument::fromJson(urlsJson);
    if (!document.isArray()) {
        return nullptr;
    }
    KFileItemList items;
    for (const QJsonValue &value : document.array()) {
        const QUrl url(value.toString());
        if (url.isValid() && !url.isEmpty()) {
            const QFileInfo info(url.toLocalFile());
            const mode_t mode = url.isLocalFile() && info.isDir() ? S_IFDIR : 0;
            items.append(KFileItem(url, QString(), mode));
        }
    }
    if (items.isEmpty()) {
        return nullptr;
    }
    auto *menu = new QMenu(static_cast<QWidget *>(parent));
    auto *actions = new KFileItemActions(menu);
    actions->setItemListProperties(KFileItemListProperties(items));
    actions->setParentWidget(static_cast<QWidget *>(window));
    // Keep KIO responsible for MIME/protocol/authorization checks and loading.
    // Fetch the two archive providers separately to attach stable identities;
    // each provider is requested once, never detected by translated text.
    const QStringList known = {QStringLiteral("compressfileitemaction"), QStringLiteral("extractfileitemaction")};
    QStringList all;
    for (const auto &plugin : KPluginMetaData::findPlugins(QStringLiteral("kf6/kfileitemaction"))) all.append(plugin.pluginId());
    // Keep ordinary services and plugins in one KIO grouping, so their
    // combined Actions submenu is not duplicated by separate calls.
    auto excludedOrdinary = known;
    excludedOrdinary.append(QStringLiteral("movetonewfolderitemaction"));
    actions->addActionsTo(menu, KFileItemActions::MenuActionSource::All, {}, excludedOrdinary);
    auto tagServices = [](auto &&self, QMenu *current) -> void {
        for (auto *action : current->actions()) {
            QString id;
#if __has_include(<KDesktopFileAction>)
            if (action->data().canConvert<KDesktopFileAction>()) id = action->data().value<KDesktopFileAction>().actionsKey();
#endif
            if (action->data().canConvert<KServiceAction>()) id = action->data().value<KServiceAction>().name();
            if (!id.isEmpty()) action->setProperty("_mirivue_kde_id", id);
            if (action->menu()) self(self, action->menu());
        }
    };
    tagServices(tagServices, menu);
    for (const auto &id : known) {
        if (!all.contains(id)) continue;
        auto excluded = all;
        excluded.removeAll(id);
        const auto previous = menu->actions();
        actions->addActionsTo(menu, KFileItemActions::MenuActionSource::Plugins, {}, excluded);
        for (auto *action : menu->actions())
            if (!previous.contains(action) && !action->isSeparator()) action->setProperty("_mirivue_kde_id", id);
    }
    if (menu->actions().isEmpty()) {
        delete menu;
        return nullptr;
    }
    return menu;
}

// Match KF6 applications: install the KDE icon engine before QApplication.
void mirivue_icon_theme_init()
{
    KIconTheme::initTheme();
}

// KDE's own style selection: a no-op when the KDE platform theme is active,
// the configured KDE widget style with Breeze fallback in other sessions.
void mirivue_application_style_init()
{
    if (QApplication::instance()) {
        KStyleManager::initStyle();
    }
}

// The same semantic foreground roles and byte dialect as KF6 applications.
// Keep this bridge in-process: file views request these values frequently.
unsigned int mirivue_semantic_foreground(int role, int inactive)
{
    if (!QApplication::instance() || role < 0 || role > 3) {
        return 0;
    }
    const KColorScheme scheme(inactive ? QPalette::Inactive : QPalette::Active, KColorScheme::View);
    static constexpr KColorScheme::ForegroundRole roles[] = {
        KColorScheme::PositiveText, KColorScheme::NeutralText,
        KColorScheme::NegativeText, KColorScheme::LinkText};
    return scheme.foreground(roles[role]).color().rgba();
}

int mirivue_format_byte_size(double size, char *destination, size_t capacity)
{
    if (!destination || !capacity) {
        return 0;
    }
    const QByteArray encoded = KFormat().formatByteSize(size).toUtf8();
    if (static_cast<size_t>(encoded.size()) >= capacity) {
        return 0;
    }
    std::memcpy(destination, encoded.constData(), static_cast<size_t>(encoded.size()) + 1);
    return encoded.size();
}

// Original Mirivue bridge to the same public formatter used by Dolphin.
int mirivue_format_relative_date(qint64 milliseconds, char *destination, size_t capacity)
{
    if (!destination || !capacity) {
        return 0;
    }
    const QByteArray encoded = KFormat().formatRelativeDateTime(
        QDateTime::fromMSecsSinceEpoch(milliseconds), QLocale::ShortFormat).toUtf8();
    if (static_cast<size_t>(encoded.size()) >= capacity) {
        return 0;
    }
    std::memcpy(destination, encoded.constData(), static_cast<size_t>(encoded.size()) + 1);
    return encoded.size();
}

void *mirivue_toolbar_create(void *parent)
{
    if (!QApplication::instance() || !parent) {
        return nullptr;
    }
    return new KToolBar(static_cast<QWidget *>(parent), true, true);
}

const char *mirivue_places_location_identity(void *pointer, const char *location)
{
    static thread_local QByteArray result;
    if (!pointer || !location) return nullptr;
    auto *view = static_cast<KFilePlacesView *>(pointer);
    auto *model = static_cast<KFilePlacesModel *>(view->model());
    const QUrl url = QUrl::fromUserInput(QString::fromUtf8(location));
    QString caption;
    if (url.path().isEmpty() || url.path() == QLatin1String("/"))
        caption = QUrlQuery(url).queryItemValue(QStringLiteral("title"), QUrl::FullyDecoded);
    const QModelIndex index = model->closestItem(url);
    if (caption.isEmpty() && index.isValid() && model->url(index).matches(url, QUrl::StripTrailingSlash))
        caption = model->text(index);
    if (caption.isEmpty()) {
        const QUrl adjusted = url.adjusted(QUrl::StripTrailingSlash);
        caption = adjusted.fileName();
        if (caption.isEmpty()) caption = url.isLocalFile() ? QStringLiteral("/")
            : (!adjusted.path().isEmpty() && adjusted.path() != QLatin1String("/") ? adjusted.path()
               : (!url.host().isEmpty() ? url.host() : adjusted.toDisplayString()));
    }
    QUrl folderUrl = url.adjusted(QUrl::StripTrailingSlash);
    folderUrl.setPath(folderUrl.path() + QLatin1Char('/'));
    result = QJsonDocument(QJsonObject{{"name", caption},
        {"icon", KIO::iconNameForUrl(folderUrl)}}).toJson(QJsonDocument::Compact);
    return result.constData();
}

void *mirivue_places_create(void *parent, PlaceCallback activated, PlaceCallback dropped,
                            PlaceCallback splitRequested, PlaceCallback tabRequested,
                            PlaceCallback activeTabRequested, PlaceCallback windowRequested,
                            PlaceCallback errorReported, PlaceCallback trashEmptied,
                            TrashHasItemsCallback trashHasItems,
                            const char *splitLabel)
{
    if (!QApplication::instance() || !parent) {
        return nullptr;
    }
    auto *view = new MirivuePlacesView(static_cast<QWidget *>(parent));
    auto *model = new KFilePlacesModel(view);
    QObject::connect(model, &KFilePlacesModel::errorMessage, view,
                     [errorReported](const QString &message) {
                         if (errorReported) {
                             const QByteArray value = message.toUtf8();
                             errorReported(value.constData());
                         }
                     });
    view->setDropOnPlaceEnabled(true);
    view->setTeardownFunction([model](const QModelIndex &index) {
        model->requestTeardown(index);
    });
    view->setAutoResizeItemsEnabled(false); // Dolphin PlacesPanel::readSettings()

    // Dolphin reads PlacesPanel/IconSize from dolphinrc before installing the
    // model. Use the same setting and persist changes made in the KDE menu.
    const auto dolphinConfig = KSharedConfig::openConfig(QStringLiteral("dolphinrc"));
    KConfigGroup placesConfig(dolphinConfig, QStringLiteral("PlacesPanel"));
    const int iconSize = qMax(0, placesConfig.readEntry("IconSize", -1));
    view->setIconSize(QSize(iconSize, iconSize));
    view->setModel(model);
    QObject::connect(view, &KFilePlacesView::iconSizeChanged, view,
                     [dolphinConfig](const QSize &newSize) {
                         int size = qMin(newSize.width(), newSize.height());
                         if (size <= 0) {
                             size = -1;
                         }
                         KConfigGroup group(dolphinConfig, QStringLiteral("PlacesPanel"));
                         group.writeEntry("IconSize", size);
                         dolphinConfig->sync();
                     });

    // Dolphin adds this action to KFilePlacesView's own context menu. Keep
    // the native menu and let its selected KDE model index supply the URL.
    auto *split = new QAction(QIcon::fromTheme(QStringLiteral("view-split-left-right")),
                              QString::fromUtf8(splitLabel ? splitLabel : ""), view);
    split->setPriority(QAction::HighPriority);
    view->addAction(split);
    QObject::connect(view, &KFilePlacesView::contextMenuAboutToShow, view,
                     [view, model, split, trashEmptied, trashHasItems, errorReported]
                     (const QModelIndex &index, QMenu *menu) {
                         const QUrl url = model->url(index);
                         split->setVisible(url.isValid());
                         if (url.scheme() != QLatin1String("trash") || !menu || menu->actions().isEmpty()) {
                             return;
                         }
                         // KFilePlacesView reads trashrc/Status/Empty to disable
                         // its action. A completed KIO job can leave Mirivue's
                         // listing older than this status. Keep the native
                         // action's icon and label, and own the job result so
                         // the view reloads only after successful completion.
                         QAction *original = menu->actions().first();
                         auto *empty = new QAction(original->icon(), original->text(), menu);
                         empty->setEnabled(original->isEnabled()
                                           || (trashHasItems && trashHasItems()));
                         menu->insertAction(original, empty);
                         menu->removeAction(original);
                         QObject::connect(empty, &QAction::triggered, view,
                                          [view, trashEmptied, errorReported] {
                             using Ask = KIO::AskUserActionInterface;
                             auto *job = new KIO::DeleteOrTrashJob(QList<QUrl>{},
                                 Ask::EmptyTrash, Ask::DefaultConfirmation, view->window());
                             QObject::connect(job, &KJob::result, view,
                                              [trashEmptied, errorReported](KJob *finished) {
                                 if (finished->error()) {
                                     if (errorReported && finished->error() != KIO::ERR_USER_CANCELED) {
                                         const QByteArray message = finished->errorString().toUtf8();
                                         errorReported(message.constData());
                                     }
                                 } else if (trashEmptied) {
                                     trashEmptied("completed");
                                 }
                             });
                             job->start();
                         });
                     });
    QObject::connect(split, &QAction::triggered, view, [view, model, splitRequested]() {
        if (!splitRequested) {
            return;
        }
        const QUrl url = model->url(view->currentIndex());
        if (url.isValid()) {
            const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
            splitRequested(value.constData());
        }
    });

    QObject::connect(view, &KFilePlacesView::placeActivated, view,
                     [activated](const QUrl &url) {
                         if (activated) {
                             const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
                             activated(value.constData());
                         }
                     });
    QObject::connect(view, &KFilePlacesView::newWindowRequested, view,
                     [windowRequested](const QUrl &url) {
                         if (windowRequested) {
                             const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
                             windowRequested(value.constData());
                         }
                     });
    QObject::connect(view, &KFilePlacesView::tabRequested, view,
                     [tabRequested](const QUrl &url) {
                         if (tabRequested) {
                             const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
                             tabRequested(value.constData());
                         }
                     });
    QObject::connect(view, &KFilePlacesView::activeTabRequested, view,
                     [activeTabRequested](const QUrl &url) {
                         if (activeTabRequested) {
                             const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
                             activeTabRequested(value.constData());
                         }
                     });
    QObject::connect(view, &KFilePlacesView::urlsDropped, view,
                     [view, dropped, errorReported](const QUrl &destination, QDropEvent *event, QWidget *dropWidget) {
                         if (!event || !event->mimeData()->hasUrls() || !destination.isValid()) {
                             return;
                         }
                         // KDE owns the Move/Copy/Link choice, undo recording,
                         // conflicts, and the Plasma progress notification.
                         event->acceptProposedAction();
                         auto *job = KIO::drop(event, destination);
                         KJobWidgets::setWindow(job, dropWidget ? dropWidget : view);
                         QObject::connect(job, &KJob::result, view,
                                          [dropped, errorReported](KJob *finished) {
                                              if (finished->error()) {
                                                  if (errorReported && finished->error() != KIO::ERR_USER_CANCELED) {
                                                      const QByteArray message = finished->errorString().toUtf8();
                                                      errorReported(message.constData());
                                                  }
                                              } else if (dropped) {
                                                  dropped("completed");
                                              }
                                          });
                     });
    return view;
}

void mirivue_places_set_url(void *pointer, const char *url)
{
    if (!pointer || !url) {
        return;
    }
    static_cast<KFilePlacesView *>(pointer)->setUrl(QUrl::fromUserInput(QString::fromUtf8(url)));
}

void *mirivue_navigator_create(void *parent, void *places, const char *initial,
                               PlaceCallback changed, PlaceCallback tabRequested,
                               PlaceCallback activeTabRequested, PlaceCallback windowRequested,
                               PlaceCallback dropCompleted, PlaceCallback errorReported)
{
    if (!parent || !places) {
        return nullptr;
    }
    auto *placesView = static_cast<KFilePlacesView *>(places);
    auto *model = static_cast<KFilePlacesModel *>(placesView->model());
    auto *navigator = createPathNavigator(model, QUrl::fromUserInput(QString::fromUtf8(initial ? initial : "")),
                                          static_cast<QWidget *>(parent));
    const auto relay = [navigator](PlaceCallback callback, const QUrl &url) {
        if (callback) {
            const QByteArray value = url.toString(QUrl::FullyEncoded).toUtf8();
            callback(value.constData());
        }
    };
    QObject::connect(navigator, &KUrlNavigator::urlChanged, navigator,
                     [relay, changed](const QUrl &url) { relay(changed, url); });
    // Accept the entered URL first; then return to the breadcrumb presentation.
    QObject::connect(navigator, &KUrlNavigator::returnPressed, navigator,
                     [navigator] {
                         QTimer::singleShot(0, navigator, [navigator] { navigator->setUrlEditable(false); });
                     });
    QObject::connect(navigator, &KUrlNavigator::tabRequested, navigator,
                     [relay, tabRequested](const QUrl &url) { relay(tabRequested, url); });
    QObject::connect(navigator, &KUrlNavigator::activeTabRequested, navigator,
                     [relay, activeTabRequested](const QUrl &url) { relay(activeTabRequested, url); });
    QObject::connect(navigator, &KUrlNavigator::newWindowRequested, navigator,
                     [relay, windowRequested](const QUrl &url) { relay(windowRequested, url); });
    QObject::connect(navigator, &KUrlNavigator::urlsDropped, navigator,
                     [navigator, dropCompleted, errorReported](const QUrl &destination, QDropEvent *event) {
                         if (!event || !destination.isValid()) {
                             return;
                         }
                         event->acceptProposedAction();
                         auto *job = KIO::drop(event, destination);
                         KJobWidgets::setWindow(job, navigator->dropWidget() ? navigator->dropWidget() : navigator);
                         QObject::connect(job, &KJob::result, navigator,
                                          [dropCompleted, errorReported](KJob *finished) {
                                              if (finished->error()) {
                                                  if (errorReported && finished->error() != KIO::ERR_USER_CANCELED) {
                                                      const QByteArray message = finished->errorString().toUtf8();
                                                      errorReported(message.constData());
                                                  }
                                              } else if (dropCompleted) {
                                                  dropCompleted("completed");
                                              }
                                          });
                     });
    return navigator;
}

void mirivue_navigator_set_url(void *pointer, const char *url)
{
    if (pointer && url) {
        auto *navigator = static_cast<KUrlNavigator *>(pointer);
        const QSignalBlocker block(navigator);
        const QUrl next = QUrl::fromUserInput(QString::fromUtf8(url));
        if (navigator->locationUrl() != next) {
            navigator->setLocationUrl(next);
        }
    }
}

void mirivue_navigator_set_editable(void *pointer, int editable)
{
    if (pointer) {
        auto *navigator = static_cast<KUrlNavigator *>(pointer);
        navigator->setUrlEditable(editable != 0);
        if (editable) {
            navigator->editor()->setFocus();
            if (navigator->editor()->lineEdit()) {
                navigator->editor()->lineEdit()->selectAll();
            }
        }
    }
}

int mirivue_navigator_is_editable(void *pointer)
{
    return pointer && static_cast<KUrlNavigator *>(pointer)->isUrlEditable();
}

void mirivue_navigator_set_active(void *pointer, int active)
{
    if (pointer) {
        static_cast<KUrlNavigator *>(pointer)->setActive(active != 0);
    }
}

void mirivue_navigator_set_split_mode(void *pointer, int split)
{
    Q_UNUSED(split);
    if (pointer) {
        // The active pane is already distinguished by the navigator text.
        // Keep Breeze's ordinary frame colour in both panes, matching the
        // neutral outlines of Dolphin's location bars and pane dividers.
        auto *navigator = static_cast<KUrlNavigator *>(pointer);
        navigator->setHighlightFocusIndicator(false);
    }
}

void mirivue_navigator_set_full_path(void *pointer, int showFull)
{
    if (pointer) {
        static_cast<KUrlNavigator *>(pointer)->setShowFullPath(showFull != 0);
    }
}

void mirivue_navigator_set_places_selector_visible(void *pointer, int visible)
{
    if (pointer) {
        static_cast<KUrlNavigator *>(pointer)->setPlacesSelectorVisible(visible != 0);
    }
}

int mirivue_navigator_is_places_selector_visible(void *pointer)
{
    return pointer && static_cast<KUrlNavigator *>(pointer)->isPlacesSelectorVisible();
}

void mirivue_navigator_set_hidden_folders(void *pointer, int show)
{
    if (pointer) {
        static_cast<KUrlNavigator *>(pointer)->setShowHiddenFolders(show != 0);
    }
}

int mirivue_navigator_shows_hidden_folders(void *pointer)
{
    return pointer && static_cast<KUrlNavigator *>(pointer)->showHiddenFolders();
}

int mirivue_navigator_has_background(void *pointer)
{
    return pointer && static_cast<KUrlNavigator *>(pointer)->isBackgroundEnabled();
}
}

// DolphinMainWindow::activateWindow: Wayland activation is token-based.
extern "C" void mirivue_activate_window(void *pointer, const char *token)
{
    if (!pointer) return;
    auto *widget = static_cast<QWidget *>(pointer);
    widget->setAttribute(Qt::WA_NativeWindow, true);
    if (KWindowSystem::isPlatformWayland()) {
        KWindowSystem::setCurrentXdgActivationToken(QString::fromUtf8(token ? token : ""));
    } else if (KWindowSystem::isPlatformX11()) {
        KStartupInfo::setNewStartupId(widget->windowHandle(), QByteArray(token ? token : ""));
    }
    KWindowSystem::activateWindow(widget->windowHandle());
}

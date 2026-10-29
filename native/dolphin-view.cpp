// SPDX-License-Identifier: GPL-2.0-or-later
// Mirivue model/operation adapter for the bundled Dolphin item engine.
// Upstream provenance and the small integration patches are documented alongside it.
#include "kitemviews/kstandarditemlistview.h"
#include "kitemviews/kstandarditemlistwidget.h"
#include "kitemviews/kitemlistcontainer.h"
#include "kitemviews/kitemlistcontroller.h"
#include "kitemviews/kitemlistselectionmanager.h"
#include "kitemviews/kitemlistheader.h"
#include "kitemviews/private/kitemlistroleeditor.h"
#include "kitemviews/private/kitemlistheaderwidget.h"
#include <QAbstractItemModel>
#include <QApplication>
#include "date-groups.h"
#include <QBrush>
#include <QGraphicsView>
#include <QGraphicsSceneDragDropEvent>
#include <QItemSelectionModel>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QMimeDatabase>
#include <QMimeData>
#include <QTextBoundaryFinder>
#include <QTimer>
#include <QIcon>
#include <QLabel>
#include <QScrollBar>
#include <QStyle>
#include <QPointer>
#include <QEvent>
#include <QCoreApplication>
#include <KIO/Global>
#include <KColorScheme>

namespace {
constexpr int IsDirectoryRole = Qt::UserRole + 42;
constexpr int FileUrlRole = Qt::UserRole + 43;
constexpr int IsHiddenRole = Qt::UserRole + 44;
using Callback = int (*)(const char *);
QByteArray roleFor(int column) { return column == 0 ? QByteArray("text") : QByteArray("column") + QByteArray::number(column); }
int columnFor(const QByteArray &role) { return role == "text" ? 0 : role.mid(6).toInt(); }
int notify(Callback callback, QJsonObject value) {
    const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Compact);
    return callback ? callback(bytes.constData()) : 0;
}

class FileItems final : public KItemModelBase {
public:
    QPointer<QAbstractItemModel> source;
    mutable QVector<QHash<QByteArray, QVariant>> cache;
    QList<int> columns{0};
    mutable bool groupsDirty = true;
    mutable QList<QPair<int, QVariant>> groupCache;
    Callback callback;
    QUrl folder;
    QByteArray dragToken;
    QList<QPersistentModelIndex> beforeLayout;
    explicit FileItems(QAbstractItemModel *source, Callback callback)
        : KItemModelBase("text"), source(source), callback(callback) {
        connect(source, &QAbstractItemModel::modelReset, this, [this] {
            groupsDirty=true; const int old = cache.size(); cache.clear();
            if (old) Q_EMIT itemsRemoved(KItemRangeList() << KItemRange(0, old));
            cache.resize(this->source->rowCount());
            if (!cache.isEmpty()) Q_EMIT itemsInserted(KItemRangeList() << KItemRange(0, cache.size()));
        });
        connect(source, &QAbstractItemModel::rowsInserted, this, [this](const QModelIndex &, int a, int b) {
            groupsDirty=true; for (int n=a; n<=b; ++n) cache.insert(a, QHash<QByteArray,QVariant>{});
            Q_EMIT itemsInserted(KItemRangeList() << KItemRange(a, b-a+1));
        });
        connect(source, &QAbstractItemModel::rowsRemoved, this, [this](const QModelIndex &, int a, int b) {
            groupsDirty=true; cache.remove(a, b-a+1); Q_EMIT itemsRemoved(KItemRangeList() << KItemRange(a, b-a+1));
        });
        connect(source, &QAbstractItemModel::layoutAboutToBeChanged, this, [this] {
            beforeLayout.clear();
            for (int row=0; row<count(); ++row) beforeLayout.append(this->source->index(row, 0));
        });
        connect(source, &QAbstractItemModel::layoutChanged, this, [this] {
            groupsDirty=true;
            QVector<QHash<QByteArray, QVariant>> moved(cache.size()); QList<int> positions;
            if (beforeLayout.size() != cache.size()) return;
            for (int row=0; row<count(); ++row) {
                const int next = beforeLayout[row].row();
                positions.append(next); if (next>=0 && next<moved.size()) moved[next] = std::move(cache[row]);
            }
            cache = std::move(moved); beforeLayout.clear();
            if (count()) Q_EMIT itemsMoved(KItemRange(0, count()), positions);
        });
        connect(source, &QAbstractItemModel::dataChanged, this,
                [this](const QModelIndex &a, const QModelIndex &b, const QList<int> &qtRoles) {
            groupsDirty=true;
            QSet<QByteArray> changed;
            const bool all = qtRoles.isEmpty();
            if (all || qtRoles.contains(Qt::DisplayRole) || qtRoles.contains(Qt::EditRole))
                for (int column=a.column(); column<=b.column(); ++column) changed.insert(roleFor(column));
            if (a.column()==0 && (all || qtRoles.contains(Qt::DisplayRole) || qtRoles.contains(Qt::EditRole)))
                changed.unite({"url","isDir","isHidden","type"});
            if (all || qtRoles.contains(Qt::DecorationRole)) { changed.insert("iconPixmap"); changed.insert("mirivueIcon"); }
            if (all || qtRoles.contains(Qt::ForegroundRole))
                for (int c=a.column();c<=b.column();++c) changed.insert("foreground:"+roleFor(c));
            if (all || qtRoles.contains(Qt::FontRole))
                for (int c=a.column();c<=b.column();++c) changed.insert("font:"+roleFor(c));
            for (int row=a.row(); row<=b.row() && row<cache.size(); ++row) cache[row].clear();
            Q_EMIT itemsChanged(KItemRangeList() << KItemRange(a.row(), b.row()-a.row()+1), changed);
        });
    }
    int count() const override { return cache.size(); }
    QList<QPair<int, QVariant>> groups() const override {
        if (!groupedSorting() || !source) return {};
        if (!groupsDirty) return groupCache;
        const int column = columnFor(sortRole());
        QList<QDateTime> times;
        for (int row=0;row<count();++row) {
            const auto timestamp = source->data(source->index(row,column),Qt::UserRole).toLongLong();
            times.append(timestamp > 0 ? QDateTime::fromMSecsSinceEpoch(timestamp/1000000) : QDateTime());
        }
        groupCache = mirivueDateGroups(times); groupsDirty=false;
        return groupCache;
    }
    QHash<QByteArray,QVariant> data(int row) const override {
        if (!source || row<0 || row>=count()) return {};
        auto &values = cache[row];
        if (values.isEmpty()) {
            const auto index = source->index(row, 0);
            values["url"] = source->data(index, FileUrlRole);
            values["isDir"] = source->data(index, IsDirectoryRole);
            const QString name = source->data(index, Qt::DisplayRole).toString();
            values["text"] = name; values["isHidden"] = source->data(index, IsHiddenRole).toBool();
            values["type"] = values["isDir"].toBool() ? QStringLiteral("Dossier") : QStringLiteral("Fichier");
            for (int column : columns) {
                const auto cell = source->index(row, column);
                values[roleFor(column)] = source->data(cell, Qt::DisplayRole);
                const auto color = source->data(cell, Qt::ForegroundRole);
                if (color.isValid()) values["foreground:"+roleFor(column)] = color;
                const auto font = source->data(cell, Qt::FontRole);
                if (font.isValid()) values["font:"+roleFor(column)] = font;
            }
        }
        return values;
    }
    QIcon icon(int row) const {
        if(!source || row<0 || row>=count()) return {};
        if(!cache[row].contains("mirivueIcon")) {
            const auto value=source->data(source->index(row,0),Qt::DecorationRole);
            cache[row]["mirivueIcon"]=value;
        }
        return cache[row].value("mirivueIcon").value<QIcon>();
    }
    void setColumns(const QList<int> &next) {
        if (columns == next) return;
        columns = next; for (auto &values : cache) values.clear();
        if(count()) Q_EMIT itemsChanged(KItemRangeList() << KItemRange(0,count()), {});
    }
    QString roleDescription(const QByteArray &role) const override {
        return source ? source->headerData(columnFor(role), Qt::Horizontal).toString() : QString();
    }
    QUrl url(int row) const override { return data(row).value("url").toUrl(); }
    QUrl directory() const override { return folder; }
    bool isDir(int row) const override { return data(row).value("isDir").toBool(); }
    // The controller uses -1 for the view background, including empty folders.
    // Rejecting it makes Qt refuse the drag before a drop can reach the app.
    bool supportsDropping(int row) const override { return row < 0 || isDir(row); }
    bool canEnterOnHover(int row) const override { return isDir(row); }
    int indexForKeyboardSearch(const QString &text, int start) const override {
        for (int n=0; n<count(); ++n) {
            const int row=(start+n)%count();
            if (data(row).value("text").toString().startsWith(text, Qt::CaseInsensitive)) return row;
        }
        return -1;
    }
    QMimeData *createMimeData(const KItemSet &indices) const override {
        QJsonArray rows; QList<QUrl> urls;
        for (int row : indices) { rows.append(row); urls.append(url(row)); }
        if (!notify(callback, {{"event","can-drag"},{"rows",rows}})) return nullptr;
        auto *mime = new QMimeData; mime->setUrls(urls);
        mime->setData("application/x-mirivue-files", "1");
        mime->setData("application/x-mirivue-source-pane", dragToken); return mime;
    }
protected:
    void onSortRoleChanged(const QByteArray &, const QByteArray &, bool resort) override {
        if (resort) source->sort(columnFor(sortRole()), sortOrder());
    }
    void onSortOrderChanged(Qt::SortOrder, Qt::SortOrder) override {
        source->sort(columnFor(sortRole()), sortOrder());
    }
};

class FileWidget final : public KStandardItemListWidget {
    qint64 iconKey = -1;
    int pixelSize = 0;
    qreal iconDpr = 0;
    QPixmap preparedIcon;
public:
    FileItems *fileItems=nullptr;
    using KStandardItemListWidget::KStandardItemListWidget;
    static KItemListWidgetInformant *createInformant() { return new KStandardItemListWidgetInformant; }
protected:
    void refreshCache() override {
        auto values = data();
        const auto icon = fileItems ? fileItems->icon(index()) : QIcon();
        values["mirivueIcon"]=icon;
        const qreal dpr = scene() && !scene()->views().isEmpty() ? scene()->views()[0]->devicePixelRatioF() : qApp->devicePixelRatio();
        const int pixels = qMax(1, qRound(styleOption().iconSize*dpr));
        if (icon.cacheKey()!=iconKey || pixels!=pixelSize || dpr!=iconDpr) {
            preparedIcon = icon.pixmap(QSize(pixels,pixels)); preparedIcon.setDevicePixelRatio(dpr);
            iconKey = icon.cacheKey(); pixelSize = pixels; iconDpr = dpr;
        }
        values["iconPixmap"] = preparedIcon;
        setData(values, {"iconPixmap","mirivueIcon"});
    }
    QColor roleTextColor(const QByteArray &role,const QColor &normal) const override {
        if(isSelected()) return normal;
        const auto value=data().value("foreground:"+role);
        if(value.canConvert<QBrush>()) return value.value<QBrush>().color();
        return value.canConvert<QColor>()?value.value<QColor>():normal;
    }
    QFont roleFont(const QByteArray &role,const QFont &normal) const override {
        const auto value=data().value("font:"+role);
        return value.canConvert<QFont>()?value.value<QFont>().resolve(normal):normal;
    }
    bool isHidden() const override { return data().value("isHidden").toBool(); }
    bool isRoleRightAligned(const QByteArray &role) const override {
        return role=="column1" || role=="column2" || role=="column5" || role=="column6" || role=="column9";
    }
    int selectionLength(const QString &text) const override {
        // Dolphin's KFileItemListWidget selection policy, including multi-part suffixes.
        if (data().value("isDir").toBool()) return numberOfUnicodeCharactersIn(text);
        int end=text.size(); const auto extension=QMimeDatabase().suffixForFileName(text);
        if (extension.isEmpty()) {
            end=text.lastIndexOf('.'); if (end<1 || end==text.size()-1) end=text.size();
        } else end-=extension.size()+1;
        return numberOfUnicodeCharactersIn(text.left(end));
    }
};

class FileView final : public KStandardItemListView {
public:
    using KItemListView::setStyleOption;
    using KItemListView::setItemSize;
    using KItemListView::visibleItemListWidgets;
    bool headerContains(const QPointF &scenePoint) const {
        for (auto *child : childItems()) {
            auto *header=qobject_cast<KItemListHeaderWidget *>(child->toGraphicsObject());
            if (header && header->isVisible() && header->contains(header->mapFromScene(scenePoint))) return true;
        }
        return false;
    }
protected:
    void initializeItemListWidget(KItemListWidget *item) override {
        static_cast<FileWidget *>(item)->fileItems=static_cast<FileItems *>(model());
        KStandardItemListView::initializeItemListWidget(item);
    }
    KItemListWidgetCreatorBase *defaultWidgetCreator() const override {
        return new KItemListWidgetCreator<FileWidget>;
    }
};

class Backend final : public QObject {
    bool selectionGuard=false;
    bool activePane=true;
    bool updatingPalette=false;
    QByteArray response;
    QHash<QByteArray,qreal> customWidths;
    bool requestedAutomatic=true,fillWidth=true,details=true,adjustingColumns=false;
public:
    FileItems *items;
    FileView *view;
    KItemListController *controller;
    KItemListContainer *widget;
    QPointer<QItemSelectionModel> selection;
    Callback callback;
    QLabel *empty;
    Backend(QAbstractItemModel *source, QItemSelectionModel *selection, QWidget *parent, Callback callback)
        : selection(selection), callback(callback) {
        items=new FileItems(source,callback); view=new FileView;
        controller=new KItemListController(items,view);
        controller->setSelectionBehavior(KItemListController::MultiSelection);
        widget=new KItemListContainer(controller,parent); setParent(widget);
        view->setAccessibleParentsObject(widget);
        // Keep KItemListContainer's native frame, as DolphinView does. Flat
        // containers are made transparent by Breeze::polishScrollArea().
        empty=new QLabel(widget); empty->setAlignment(Qt::AlignCenter); empty->setWordWrap(true);
        empty->setAttribute(Qt::WA_TransparentForMouseEvents); empty->hide();
        widget->installEventFilter(this);
        updatePalette();
        auto updateEmpty=[this] { empty->setVisible(items->count()==0&&!empty->text().isEmpty()); };
        connect(items,&KItemModelBase::itemsInserted,this,updateEmpty);
        connect(items,&KItemModelBase::itemsRemoved,this,updateEmpty);
        connect(view,&QGraphicsWidget::geometryChanged,this,[this] { fitColumns(); });
        connect(items,&KItemModelBase::itemsInserted,this,[this] { fitColumns(); });
        connect(items,&KItemModelBase::itemsChanged,this,[this] { fitColumns(); });
        connect(controller,&KItemListController::itemActivated,this,[this](int row) { send("activate",row); });
        connect(controller,&KItemListController::itemsActivated,this,[this](const KItemSet &) { send("activate-selection"); });
        connect(controller,&KItemListController::itemMiddleClicked,this,[this](int row) {
            notify(this->callback,{{"event","middle"},{"row",row},
                   {"modifiers",int(QApplication::keyboardModifiers())}});
        });
        connect(controller,&KItemListController::mouseButtonPressed,this,[this](int row,Qt::MouseButtons) { send("press",row); });
        connect(controller,&KItemListController::itemContextMenuRequested,this,[this](int row,const QPointF &p) { context("context",row,p); });
        connect(controller,&KItemListController::viewContextMenuRequested,this,[this](const QPointF &p) { context("context",-1,p); });
        connect(controller,&KItemListController::headerContextMenuRequested,this,[this](const QPointF &p) { context("header-context",-1,p); });
        connect(controller,&KItemListController::itemDropEvent,this,[this](int row,QGraphicsSceneDragDropEvent *event) {
            QJsonArray urls; for (const auto &url:event->mimeData()->urls()) urls.append(url.toString());
            const auto p=graphics()->mapFromScene(event->scenePos());
            const int action=notify(this->callback,{{"event","drop"},{"row",row},{"urls",urls},
                {"x",p.x()},{"y",p.y()},{"actions",int(event->possibleActions())},
                {"proposed",int(event->proposedAction())},{"modifiers",int(event->modifiers())},
                {"internal",event->mimeData()->hasFormat("application/x-mirivue-files")},
                {"sourcePane",QString::fromUtf8(event->mimeData()->data("application/x-mirivue-source-pane"))}});
            if(action) { event->setDropAction(Qt::DropAction(action)); event->accept(); } else event->ignore();
        });
        connect(view,&KItemListView::roleEditingFinished,this,[this](int row,const QByteArray &,const QVariant &result) {
            const bool structured=result.canConvert<EditResult>();
            const QString name=structured ? result.value<EditResult>().newName : result.toString();
            const auto direction=structured ? result.value<EditResult>().direction : EditDone;
            const QPersistentModelIndex index(items->source->index(row,0));
            const QPersistentModelIndex next(direction==EditDone?QModelIndex():items->source->index(row+(direction==EditNext?1:-1),0));
            QTimer::singleShot(0,this,[this,index,next,name] {
                if(!index.isValid() || !items->source) return;
                if(items->source->setData(index,KIO::decodeFileName(name),Qt::EditRole)
                        && next.isValid() && (next.flags()&Qt::ItemIsEditable)) {
                    this->selection->setCurrentIndex(next,QItemSelectionModel::ClearAndSelect|QItemSelectionModel::Rows);
                    view->editRole(next.row(),"text");
                }
            });
        });
        auto *manager=controller->selectionManager();
        connect(manager,&KItemListSelectionManager::selectionChanged,this,[this](const KItemSet &,const KItemSet &) { toQt(); });
        connect(manager,&KItemListSelectionManager::currentChanged,this,[this](int,int) { toQt(); });
        connect(selection,&QItemSelectionModel::selectionChanged,this,[this] { fromQt(); });
        connect(selection,&QItemSelectionModel::currentChanged,this,[this] { fromQt(); });
        connect(source,&QAbstractItemModel::layoutChanged,this,[this] { fromQt(); });
        connect(view->header(),&KItemListHeader::columnWidthChanged,this,[this](const QByteArray &r,qreal w,qreal) {
            requestedAutomatic=false; customWidths[r]=w; fitColumns();
            notify(this->callback,{{"event","column-width"},{"column",columnFor(r)},{"width",w}});
        });
        connect(view,&KItemListView::visibleRolesChanged,this,[this](const QList<QByteArray> &roles,const QList<QByteArray> &) {
            QJsonArray columns; for(const auto &r:roles) columns.append(columnFor(r));
            notify(this->callback,{{"event","columns-moved"},{"columns",columns}});
        });
        connect(view,&KItemListView::sortRoleChanged,this,[this](const QByteArray &r,const QByteArray &) { sorted(columnFor(r)); });
        connect(view,&KItemListView::sortOrderChanged,this,[this](Qt::SortOrder,Qt::SortOrder) { sorted(columnFor(items->sortRole())); });
        items->cache.resize(source->rowCount());
        if(items->count()) Q_EMIT items->itemsInserted(KItemRangeList() << KItemRange(0,items->count()));
        fromQt();
    }
    void fitColumns() {
        if(!details || adjustingColumns || view->header()->automaticColumnResizing()) return;
        QHash<QByteArray,qreal> widths; qreal others=0;
        for(const auto &role:view->visibleRoles()) {
            const qreal width=requestedAutomatic?view->header()->preferredColumnWidth(role):customWidths.value(role,120);
            widths[role]=qMax<qreal>(20,width); if(role!="text") others+=widths[role];
        }
        if(fillWidth) widths["text"]=qMax(widths.value("text"),view->size().width()-others-view->header()->leftPadding()-view->header()->rightPadding());
        bool changed=false;
        for(auto it=widths.cbegin();it!=widths.cend();++it)
            if(!qFuzzyCompare(view->header()->columnWidth(it.key())+1,it.value()+1)) {changed=true;break;}
        if(changed) {
            adjustingColumns=true; view->header()->setColumnWidths(widths); adjustingColumns=false;
        }
    }
    void updatePalette() {
        if (updatingPalette) return;
        updatingPalette = true;
        // DolphinView::updatePalette(): use the KDE View background on the
        // container's QGraphicsView, and blend the inactive pane over its parent.
        QColor color = KColorScheme(widget->isActiveWindow() ? QPalette::Active : QPalette::Inactive,
                                    KColorScheme::View).background().color();
        if (!activePane) color.setAlpha(150);
        QWidget *viewport = widget->viewport();
        QPalette palette;
        palette.setColor(viewport->backgroundRole(), color);
        if (viewport->palette().resolveMask() != palette.resolveMask()
                || viewport->palette().color(viewport->backgroundRole()) != color) {
            viewport->setPalette(palette);
        }
        updatingPalette = false;
        widget->update();
    }
    void setPaneActive(bool active) {
        activePane = active;
        updatePalette();
    }
    bool eventFilter(QObject *object,QEvent *event) override {
        if (object == widget && (event->type() == QEvent::PaletteChange
                || event->type() == QEvent::StyleChange || event->type() == QEvent::WindowActivate
                || event->type() == QEvent::WindowDeactivate)) updatePalette();
        if(object==widget && event->type()==QEvent::Resize)
            empty->setGeometry(widget->rect().adjusted(24,24,-24,-24));
        return QObject::eventFilter(object,event);
    }
    QGraphicsView *graphics() const { return qobject_cast<QGraphicsView *>(widget->viewport()); }
    QWidget *canvas() const { return graphics()->viewport(); }
    void send(const char *event,int row=-1) { notify(callback,{{"event",event},{"row",row}}); }
    void context(const char *event,int row,const QPointF &point) {
        const auto p=canvas()->mapFromGlobal(point.toPoint());
        notify(callback,{{"event",event},{"row",row},{"x",p.x()},{"y",p.y()}});
    }
    void sorted(int column) { notify(callback,{{"event","sort"},{"column",column},{"order",int(items->sortOrder())}}); }
    void fromQt() {
        if(selectionGuard || !selection || !items->source) return; selectionGuard=true;
        KItemSet chosen; for(const auto &index:selection->selectedRows()) chosen.insert(index.row());
        controller->selectionManager()->setSelectedItems(chosen);
        controller->selectionManager()->setCurrentItem(selection->currentIndex().row());
        selectionGuard=false;
    }
    void toQt() {
        if(selectionGuard || !selection || !items->source) return; selectionGuard=true;
        QItemSelection chosen;
        for(int row:controller->selectionManager()->selectedItems())
            chosen.select(items->source->index(row,0),items->source->index(row,items->source->columnCount()-1));
        selection->select(chosen,QItemSelectionModel::ClearAndSelect|QItemSelectionModel::Rows);
        const int current=controller->selectionManager()->currentItem();
        selection->setCurrentIndex(current>=0?items->source->index(current,0):QModelIndex(),QItemSelectionModel::NoUpdate);
        selectionGuard=false;
    }
    void configure(const QJsonObject &config) {
        view->beginTransaction();
        const int mode=config.value("mode").toInt();
        view->setItemLayout(mode==0?KStandardItemListView::DetailsLayout:mode==1?KStandardItemListView::IconsLayout:KStandardItemListView::CompactLayout);
        const int sortColumn = config.value("sortColumn").toInt();
        if (items->sortRole()!=roleFor(sortColumn)) items->groupsDirty=true;
        items->setSortRole(roleFor(sortColumn),false);
        items->setGroupedSorting(config.value("grouped").toBool() && (sortColumn==14 || sortColumn==38 || sortColumn==39));
        items->setSortOrder(Qt::SortOrder(config.value("sortOrder").toInt()));
        view->setHeaderVisible(mode==0); view->setSupportsItemExpanding(false);
        view->setHighlightEntireRow(mode==0); view->setAlternateBackgrounds(config.value("alternate").toBool(true));
        QList<int> columns; QList<QByteArray> roles;
        for(const auto &v:config.value("columns").toArray()) { columns.append(v.toInt()); roles.append(roleFor(v.toInt())); }
        if(columns.isEmpty()) {columns={0};roles={"text"};}
        auto option=view->styleOption(); option.font=widget->font(); option.fontMetrics=QFontMetrics(option.font);
        option.palette=widget->palette(); option.iconSize=config.value("iconSize").toInt(22);
        // DolphinItemListView::updateGridSize(): same padding and row metrics.
        option.padding=2; option.horizontalMargin=mode==2?8:mode==1?widget->style()->pixelMetric(QStyle::PM_SizeGripSize):0;
        option.verticalMargin=mode==1?option.horizontalMargin:0;
        option.maxTextLines=mode==1?2:0; option.maxTextWidth=0;
        view->setStyleOption(option);
        if(mode==0) view->setItemSize(QSizeF(-1,4+qMax(option.iconSize,option.fontMetrics.lineSpacing())));
        else if(mode==2) view->setItemSize(QSizeF(8+option.iconSize+option.fontMetrics.height()*5,4+qMax(option.iconSize,int(roles.size())*option.fontMetrics.lineSpacing())));
        else view->setItemSize(QSizeF(qMax(96,option.iconSize+20),option.iconSize+option.fontMetrics.height()*(1+roles.size())+12));
        items->setColumns(columns); if(view->visibleRoles()!=roles) view->setVisibleRoles(roles);
        details=mode==0; requestedAutomatic=config.value("automatic").toBool(true); fillWidth=config.value("fill").toBool(true);
        if(details) {
            const auto widths=config.value("widths").toArray();customWidths.clear();
            for(int column:columns) if(column<widths.size()) customWidths[roleFor(column)]=widths[column].toDouble();
            view->header()->setAutomaticColumnResizing(requestedAutomatic&&fillWidth);
            fitColumns();
        }
        items->folder=QUrl(config.value("directory").toString());
        items->dragToken=config.value("dragToken").toString().toUtf8();
        const QString message=config.value("empty").toString();
        empty->setText(message); empty->setVisible(items->count()==0&&!message.isEmpty());
        empty->setGeometry(widget->rect().adjusted(24,24,-24,-24));
        view->endTransaction();
    }
    const char *query(const QJsonObject &q) {
        QJsonObject answer; const auto operation=q.value("op").toString();
        if(operation=="index") {
            const auto scene=graphics()->mapToScene(QPoint(q.value("x").toInt(),q.value("y").toInt()));
            answer["row"]=view->itemAt(view->mapFromScene(scene)).value_or(-1);
        } else if(operation=="background") {
            const auto scene=graphics()->mapToScene(QPoint(q.value("x").toInt(),q.value("y").toInt()));
            const auto point=view->mapFromScene(scene);
            // The native header shares the graphics viewport with file items.
            // An invalid item index alone therefore does not identify empty space.
            answer["background"]=!view->headerContains(scene) && !view->itemAt(point).has_value();
        } else if(operation=="rect") {
            const auto r=graphics()->mapFromScene(view->mapRectToScene(view->itemRect(q.value("row").toInt()))).boundingRect();
            answer={{"x",r.x()},{"y",r.y()},{"width",r.width()},{"height",r.height()}};
        } else if(operation=="groups") {
            QJsonArray result;
            for (const auto &group:items->groups())
                result.append(QJsonObject{{"row", group.first},{"label", group.second.toString()}});
            answer["groups"]=result;
        } else if(operation=="widths") {
            QJsonArray widths;for(int c=0;c<items->source->columnCount();++c) widths.append(view->header()->columnWidth(roleFor(c)));answer["widths"]=widths;
        } else if(operation=="item") {
            const int row=q.value("row").toInt();
            auto values=items->data(row);
            for(auto *object:view->visibleItemListWidgets()) if(object->index()==row) values=object->data();
            QJsonArray cells;for(int c:items->columns) cells.append(values.value(roleFor(c)).toString());
            answer={{"text",values.value("text").toString()},{"url",values.value("url").toUrl().toString()},
                    {"cells",cells},{"iconKey",QString::number(values.value("mirivueIcon").value<QIcon>().cacheKey())},
                    {"color",values.value("foreground:text").value<QColor>().name()},
                    {"hidden",values.value("isHidden").toBool()},
                    {"sortColumn",columnFor(items->sortRole())},{"sortOrder",int(items->sortOrder())}};
        } else if(operation=="selected") {
            QJsonArray rows;for(int row:controller->selectionManager()->selectedItems()) rows.append(row);answer["rows"]=rows;
        } else {
            answer={{"engine","KStandardItemListView"},{"container","KItemListContainer"},
                    {"visibleObjects",view->visibleItemListWidgets().size()},{"count",items->count()},
                    {"layout",int(view->itemLayout())},{"itemWidth",view->itemSize().width()},
                    {"itemHeight",view->itemSize().height()},{"headerVisible",view->isHeaderVisible()}};
        }
        response=QJsonDocument(answer).toJson(QJsonDocument::Compact);return response.constData();
    }
};
}

namespace {
using EventCallback=int (*)(void *,void *,int);
class EventGate final : public QObject {
    EventCallback callback;
    QSet<int> types;
public:
    EventGate(QObject *target,QObject *owner,EventCallback callback,const QByteArray &json)
        : QObject(owner),callback(callback) {
        for(const auto &type:QJsonDocument::fromJson(json).array()) types.insert(type.toInt());
        target->installEventFilter(this);
    }
    bool eventFilter(QObject *watched,QEvent *event) override {
        // Graphics-scene painting/layout belongs entirely to Dolphin's C++
        // engine. Forward only interactions needed by the Python controller.
        if(QCoreApplication::closingDown() || !types.contains(int(event->type()))
                || !qobject_cast<QWidget *>(watched)) return false;
        return callback(watched,event,int(event->type()))!=0;
    }
};
}

extern "C" {
Q_DECL_EXPORT void *mirivue_event_gate_create(void *target,void *owner,EventCallback callback,const char *json) {
    return new EventGate(static_cast<QObject *>(target),static_cast<QObject *>(owner),callback,json);
}
Q_DECL_EXPORT void *mirivue_dolphin_create(void *model,void *selection,void *parent,Callback callback) {
    return new Backend(static_cast<QAbstractItemModel *>(model),static_cast<QItemSelectionModel *>(selection),static_cast<QWidget *>(parent),callback);
}
Q_DECL_EXPORT void mirivue_dolphin_set_active(void *p, int active) { static_cast<Backend *>(p)->setPaneActive(active != 0); }
Q_DECL_EXPORT void *mirivue_dolphin_widget(void *p) { return static_cast<Backend *>(p)->widget; }
Q_DECL_EXPORT void *mirivue_dolphin_canvas(void *p) { return static_cast<Backend *>(p)->canvas(); }
Q_DECL_EXPORT void mirivue_dolphin_configure(void *p,const char *json) {static_cast<Backend *>(p)->configure(QJsonDocument::fromJson(json).object());}
Q_DECL_EXPORT const char *mirivue_dolphin_query(void *p,const char *json) {return static_cast<Backend *>(p)->query(QJsonDocument::fromJson(json).object());}
Q_DECL_EXPORT void mirivue_dolphin_scroll(void *p,int row) {static_cast<Backend *>(p)->view->scrollToItem(row);}
Q_DECL_EXPORT void mirivue_dolphin_edit(void *p,int row) {
    auto *b=static_cast<Backend *>(p);const auto index=b->items->source->index(row,0);
    if(index.flags()&Qt::ItemIsEditable) b->view->editRole(row,"text");
}
}

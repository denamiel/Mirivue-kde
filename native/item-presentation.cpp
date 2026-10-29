// SPDX-License-Identifier: MIT
// A bounded, in-process presentation cache. File operations and metadata stay
// in the source model; resizing a view only reads native Qt values.
#include <QAbstractProxyModel>
#include <QDateTime>
#include <QHeaderView>
#include <QTableView>
#include <QTimer>
#include <QResizeEvent>
#include <list>
#include <unordered_map>

namespace {
class ItemPresentation final : public QAbstractProxyModel
{
    struct Cell {
        QHash<int, QVariant> values;
        Qt::ItemFlags flags;
        bool hasFlags = false;
        std::list<quint64>::iterator age;
    };
    static constexpr size_t Capacity = 4096;
    mutable std::unordered_map<quint64, Cell> cells;
    mutable std::list<quint64> ages;
    mutable QHash<quint64, QVariant> headers;
    int rows = 0, columns = 0;
    QModelIndexList oldPersistent;
    QList<QPersistentModelIndex> sourcePersistent;

    static quint64 key(int row, int column) {
        return (quint64(quint32(row)) << 32) | quint32(column);
    }
    void clear() const { cells.clear(); ages.clear(); headers.clear(); }
    void shiftRows(int first, int removed, int inserted) {
        // Retain unchanged file presentations during incremental KIO updates.
        // Re-key the bounded cache, preserving its LRU order and cell values.
        std::unordered_map<quint64, Cell> shifted;
        for (auto &entry : cells) {
            int row = int(entry.first >> 32);
            const int column = int(quint32(entry.first));
            if (row >= first && row < first + removed) {
                ages.erase(entry.second.age);
                continue;
            }
            if (row >= first) row += inserted - removed;
            const auto id = key(row, column);
            *entry.second.age = id;
            shifted.emplace(id, std::move(entry.second));
        }
        cells.swap(shifted);
    }
    Cell &cell(int row, int column) const {
        const auto id = key(row, column);
        auto found = cells.find(id);
        if (found != cells.end()) {
            ages.splice(ages.begin(), ages, found->second.age);
            return found->second;
        }
        if (cells.size() >= Capacity) {
            cells.erase(ages.back());
            ages.pop_back();
        }
        ages.push_front(id);
        Cell value;
        value.age = ages.begin();
        return cells.emplace(id, std::move(value)).first->second;
    }
    void invalidate(const QModelIndex &first, const QModelIndex &last) const {
        for (auto it = cells.begin(); it != cells.end();) {
            const int row = int(it->first >> 32);
            const int column = int(quint32(it->first));
            if (row >= first.row() && row <= last.row()
                && column >= first.column() && column <= last.column()) {
                ages.erase(it->second.age);
                it = cells.erase(it);
            } else ++it;
        }
    }

public:
    ItemPresentation(QAbstractItemModel *source, QObject *parent)
        : QAbstractProxyModel(parent) {
        QAbstractProxyModel::setSourceModel(source);
        rows = source->rowCount();
        columns = source->columnCount();
        connect(source, &QAbstractItemModel::dataChanged, this,
                [this](const QModelIndex &a, const QModelIndex &b, const QList<int> &roles) {
            // Clear BEFORE emitting: a sorting proxy may immediately reread it.
            invalidate(a, b);
            Q_EMIT dataChanged(mapFromSource(a), mapFromSource(b), roles);
        });
        connect(source, &QAbstractItemModel::headerDataChanged, this,
                [this](Qt::Orientation orientation, int a, int b) {
            headers.clear(); Q_EMIT headerDataChanged(orientation, a, b);
        });
        connect(source, &QAbstractItemModel::modelAboutToBeReset, this, [this] {
            beginResetModel(); clear();
        });
        connect(source, &QAbstractItemModel::modelReset, this, [this] {
            rows = sourceModel()->rowCount(); columns = sourceModel()->columnCount();
            endResetModel();
        });
        connect(source, &QAbstractItemModel::rowsAboutToBeInserted, this,
                [this](const QModelIndex &parent, int a, int b) {
            Q_ASSERT(!parent.isValid()); beginInsertRows({}, a, b);
        });
        connect(source, &QAbstractItemModel::rowsInserted, this,
                [this](const QModelIndex &, int a, int b) {
            shiftRows(a, 0, b-a+1); rows += b-a+1; endInsertRows();
        });
        connect(source, &QAbstractItemModel::rowsAboutToBeRemoved, this,
                [this](const QModelIndex &parent, int a, int b) {
            Q_ASSERT(!parent.isValid()); beginRemoveRows({}, a, b);
        });
        connect(source, &QAbstractItemModel::rowsRemoved, this,
                [this](const QModelIndex &, int a, int b) {
            shiftRows(a, b-a+1, 0); rows -= b-a+1; endRemoveRows();
        });
        connect(source, &QAbstractItemModel::columnsAboutToBeInserted, this,
                [this](const QModelIndex &parent, int a, int b) {
            Q_ASSERT(!parent.isValid()); clear(); beginInsertColumns({}, a, b);
        });
        connect(source, &QAbstractItemModel::columnsInserted, this,
                [this](const QModelIndex &, int a, int b) { columns += b-a+1; endInsertColumns(); });
        connect(source, &QAbstractItemModel::columnsAboutToBeRemoved, this,
                [this](const QModelIndex &parent, int a, int b) {
            Q_ASSERT(!parent.isValid()); clear(); beginRemoveColumns({}, a, b);
        });
        connect(source, &QAbstractItemModel::columnsRemoved, this,
                [this](const QModelIndex &, int a, int b) { columns -= b-a+1; endRemoveColumns(); });
        connect(source, &QAbstractItemModel::layoutAboutToBeChanged, this, [this] {
            Q_EMIT layoutAboutToBeChanged();
            oldPersistent = persistentIndexList(); sourcePersistent.clear();
            for (const auto &index : oldPersistent) sourcePersistent.append(mapToSource(index));
            clear();
        });
        connect(source, &QAbstractItemModel::layoutChanged, this, [this] {
            QModelIndexList updated;
            for (const auto &index : sourcePersistent) updated.append(mapFromSource(index));
            changePersistentIndexList(oldPersistent, updated);
            oldPersistent.clear(); sourcePersistent.clear(); clear();
            Q_EMIT layoutChanged();
        });
        // Relative dates are rendered data too. Refresh them at midnight
        // without needing a directory reload or a user interaction.
        auto *midnight = new QTimer(this);
        auto arm = [midnight] {
            const auto now = QDateTime::currentDateTime();
            const QDateTime next(now.date().addDays(1), QTime(0, 0));
            midnight->start(int(qMax<qint64>(1, now.msecsTo(next))));
        };
        midnight->setSingleShot(true);
        connect(midnight, &QTimer::timeout, this, [this, arm] {
            clear();
            if (rows && columns) Q_EMIT dataChanged(index(0, 0), index(rows-1, columns-1), {Qt::DisplayRole});
            arm();
        });
        arm();
    }

    QModelIndex index(int row, int column, const QModelIndex &parent = {}) const override {
        return !parent.isValid() && row >= 0 && row < rows && column >= 0 && column < columns
            ? createIndex(row, column) : QModelIndex();
    }
    QModelIndex parent(const QModelIndex &) const override { return {}; }
    int rowCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : rows; }
    int columnCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : columns; }
    bool hasChildren(const QModelIndex &parent = {}) const override { return !parent.isValid() && rows > 0 && columns > 0; }
    QModelIndex mapToSource(const QModelIndex &i) const override {
        return i.isValid() && i.model() == this && sourceModel()
            ? sourceModel()->index(i.row(), i.column()) : QModelIndex();
    }
    QModelIndex mapFromSource(const QModelIndex &i) const override {
        return i.isValid() && i.model() == sourceModel() ? index(i.row(), i.column()) : QModelIndex();
    }
    QVariant data(const QModelIndex &i, int role = Qt::DisplayRole) const override {
        if (!i.isValid() || i.model() != this || !sourceModel()) return {};
        // Tooltips and sorting are queried on demand. Only drawing values
        // (including empty roles) belong in the bounded presentation cache.
        if (role >= Qt::UserRole || role == Qt::ToolTipRole)
            return sourceModel()->data(mapToSource(i), role);
        auto &entry = cell(i.row(), i.column());
        auto found = entry.values.constFind(role);
        if (found != entry.values.cend()) return *found;
        auto result = sourceModel()->data(mapToSource(i), role);
        // The source callback can emit dataChanged, so reacquire the cell.
        cell(i.row(), i.column()).values.insert(role, result);
        return result;
    }
    Qt::ItemFlags flags(const QModelIndex &i) const override {
        if (!i.isValid() || i.model() != this || !sourceModel()) return Qt::NoItemFlags;
        // Name editability depends on active operations. It must stay live.
        if (i.column() == 0) return sourceModel()->flags(mapToSource(i));
        auto &entry = cell(i.row(), i.column());
        if (entry.hasFlags) return entry.flags;
        const auto result = sourceModel()->flags(mapToSource(i));
        auto &current = cell(i.row(), i.column()); current.flags = result; current.hasFlags = true;
        return result;
    }
    QVariant headerData(int section, Qt::Orientation orientation, int role) const override {
        const auto id = (quint64(orientation) << 60) | (quint64(quint32(section)) << 24) | quint32(role);
        auto found = headers.constFind(id);
        if (found != headers.cend()) return *found;
        const auto result = sourceModel()->headerData(section, orientation, role);
        headers.insert(id, result); return result;
    }
};

// Dolphin resizes Name using stored content widths; a splitter drag does not
// remeasure every cell and does not stretch the last metadata column.
class DetailsHeader final : public QHeaderView {
    bool automatic = true, fill = true, adjusting = false, configured = false;
    int preferredName = 0;
public:
    explicit DetailsHeader(QTableView *table) : QHeaderView(Qt::Horizontal, table) {
        setStretchLastSection(false);
        connect(this, &QHeaderView::sectionResized, this, [this](int logical, int, int) {
            if (configured && !adjusting) {
                if (logical == 0) preferredName = sectionSize(0);
                adjustName();
            }
        });
    }
    void configure(bool autoWidth, bool fillWidth, bool capture) {
        configured = true; automatic = autoWidth; fill = fillWidth;
        if (capture || preferredName == 0) preferredName = sectionSize(0);
        adjustName();
    }
    void suspend() { configured = false; }
    bool isAdjusting() const { return adjusting || !configured; }
    void adjustName() {
        if (!configured || adjusting || !count() || isSectionHidden(0)) return;
        auto *table = qobject_cast<QTableView *>(parentWidget());
        if (!table) return;
        const int remaining = viewport()->width() - (length() - sectionSize(0));
        int width = preferredName;
        if (automatic) {
            // This is Dolphin's lower bound, clamped to the measured name.
            const int minimumName = qMin(preferredName, table->iconSize().width() * 2 + 200);
            width = qMax(minimumName, qMin(preferredName, remaining));
        }
        if (fill) width = qMax(width, remaining);
        width = qMax(minimumSectionSize(), width);
        if (width != sectionSize(0)) {
            adjusting = true; resizeSection(0, width); adjusting = false;
        }
    }
protected:
    void resizeEvent(QResizeEvent *event) override {
        QHeaderView::resizeEvent(event); adjustName();
    }
};
}

extern "C" {
void *mirivue_item_presentation_create(void *source, void *parent) {
    if (!source) return nullptr;
    return static_cast<QAbstractProxyModel *>(new ItemPresentation(
        static_cast<QAbstractItemModel *>(source), static_cast<QObject *>(parent)));
}
void *mirivue_details_header_create(void *table) {
    if (!table) return nullptr;
    return static_cast<QHeaderView *>(new DetailsHeader(static_cast<QTableView *>(table)));
}
void mirivue_details_header_configure(void *header, int automatic, int fill, int capture) {
    if (!header) return;
    auto *value = static_cast<DetailsHeader *>(header);
    if (automatic < 0) value->suspend();
    else value->configure(automatic, fill, capture);
}
int mirivue_details_header_is_adjusting(void *header) {
    return header && static_cast<DetailsHeader *>(header)->isAdjusting();
}
}

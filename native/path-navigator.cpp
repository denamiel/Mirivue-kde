// SPDX-License-Identifier: MIT
#include "path-navigator.h"

#include <KUrlComboBox>
#include <KUrlNavigator>
#include <QEvent>
#include <QLineEdit>
#include <QStyle>
#include <QStyleOptionFrame>
#include <QTimer>
#include <algorithm>

namespace {
class PathNavigator final : public KUrlNavigator {
public:
    PathNavigator(KFilePlacesModel *places, const QUrl &url, QWidget *parent)
        : KUrlNavigator(places, url, parent)
    {
        // KUrlNavigator owns all painting and inherits the toolbar's palette,
        // as Dolphin's navigator does. Do not resolve any palette brushes here.
        setBackgroundEnabled(true);
        editor()->installEventFilter(this);
        editor()->lineEdit()->installEventFilter(this);
        synchronizeHeight();
    }

protected:
    bool event(QEvent *event) override
    {
        const auto type = event->type();
        const bool result = KUrlNavigator::event(event);
        if (changesMetrics(type)) {
            scheduleHeightUpdate();
        }
        return result;
    }

    bool eventFilter(QObject *watched, QEvent *event) override
    {
        if ((watched == editor() || watched == editor()->lineEdit())
            && changesMetrics(event->type())) {
            scheduleHeightUpdate();
        }
        return KUrlNavigator::eventFilter(watched, event);
    }

private:
    static bool changesMetrics(QEvent::Type type)
    {
        return type == QEvent::FontChange || type == QEvent::ApplicationFontChange
            || type == QEvent::StyleChange || type == QEvent::Polish
            || type == QEvent::Show;
    }

    void scheduleHeightUpdate()
    {
        if (m_heightUpdatePending) {
            return;
        }
        m_heightUpdatePending = true;
        QTimer::singleShot(0, this, [this] {
            m_heightUpdatePending = false;
            synchronizeHeight();
        });
    }

    void synchronizeHeight()
    {
        auto *lineEdit = editor()->lineEdit();
        lineEdit->ensurePolished();
        QStyleOptionFrame option;
        option.initFrom(this);
        option.lineWidth = style()->pixelMetric(QStyle::PM_DefaultFrameWidth, &option, lineEdit);
        // The breadcrumb's font can differ from the editor's class font.
        // Ask the style for a frame tall enough for the breadcrumb as well.
        const int frameHeight = style()->sizeFromContents(
            QStyle::CT_LineEdit, &option, QSize(0, fontMetrics().height()), lineEdit).height();
        int height = std::max({frameHeight, editor()->sizeHint().height(), lineEdit->sizeHint().height()});
        if (auto *badge = badgeWidget()) {
            height = std::max(height, badge->sizeHint().height());
        }
        // KF6 fixes this height at construction. Refresh it only when metrics
        // change, never from painting or the pane splitter's resize events.
        if (minimumHeight() != height || maximumHeight() != height) {
            setFixedHeight(height);
            updateGeometry();
        }
    }

    bool m_heightUpdatePending = false;
};
}

KUrlNavigator *createPathNavigator(KFilePlacesModel *places, const QUrl &url, QWidget *parent)
{
    return new PathNavigator(places, url, parent);
}

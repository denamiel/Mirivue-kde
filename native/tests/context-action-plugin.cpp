// SPDX-License-Identifier: GPL-3.0-or-later
// Validation-only provider: actions never execute filesystem operations.
#include <KAbstractFileItemActionPlugin>
#include <KFileItemListProperties>
#include <KFileItem>
#include <KPluginFactory>
#include <QAction>
#include <QMenu>
class TestContextAction final : public KAbstractFileItemActionPlugin {
    Q_OBJECT
public:
    TestContextAction(QObject *parent, const QVariantList &) : KAbstractFileItemActionPlugin(parent) {}
    QList<QAction *> actions(const KFileItemListProperties &items, QWidget *parent) override {
        if (items.items().isEmpty()) return {};
        auto *menu = new QMenu(parent);
        menu->addAction(QStringLiteral("Validation only"));
        menu->menuAction()->setText(QStringLiteral("Localized provider action"));
        return {menu->menuAction()};
    }
};
K_PLUGIN_CLASS_WITH_JSON(TestContextAction, "context-action-plugin.json")
#include "context-action-plugin.moc"

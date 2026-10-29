// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
// Original public-API adapters. No Dolphin implementation copied here.
#include <KActionCollection>
#include <KHamburgerMenu>
#include <KShortcutsDialog>
#include <KShortcutsEditor>
#include <QAction>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMenu>
#include <QMenuBar>
#include <QWidgetAction>
#include <KXMLGUIClient>
#include <KXMLGUIBuilder>
#include <KXMLGUIFactory>
#include <QMainWindow>
#include <QTemporaryDir>
#include <QFile>
#include <QDomDocument>

using JsonNotify = void (*)(const char *);
using MenuNotify = void (*)();

static QList<QKeySequence> sequences(const QJsonArray &values) {
    QList<QKeySequence> result;
    for (const auto &value : values) {
        const QKeySequence key(value.toString(), QKeySequence::PortableText);
        if (!key.isEmpty() && !result.contains(key)) result.append(key);
    }
    return result;
}
static QByteArray shortcutValues(KShortcutsDialog *dialog) {
    QJsonObject result;
    for (auto *collection : dialog->actionCollections()) {
        for (auto *action : collection->actions()) {
            QJsonArray keys;
            for (const auto &key : action->shortcuts()) keys.append(key.toString(QKeySequence::PortableText));
            result.insert(action->objectName(), keys);
        }
    }
    return QJsonDocument(result).toJson(QJsonDocument::Compact);
}
class ShortcutsClient final : public KXMLGUIClient {
public:
    void configure(const QString &base, const QString &local) {
        setComponentName(QStringLiteral("org.pdenams.Mirivue.Qt"), QStringLiteral("Mirivue"));
        setLocalXMLFile(local);
        setXMLFile(base, false);
    }
};
class ShortcutsState final : public QObject {
public:
    QTemporaryDir files;
    QMainWindow host;
    KXMLGUIBuilder builder{&host};
    KXMLGUIFactory factory{&builder};
    ShortcutsClient client;
    bool attached = false;
    ~ShortcutsState() override {if (attached) factory.removeClient(&client);}
};
extern "C" void *mirivue_shortcuts_create(void *parent, const char *payload, JsonNotify changed) {
    if (!parent || !payload) return nullptr;
    QJsonParseError error;
    const auto input = QJsonDocument::fromJson(payload, &error);
    if (error.error != QJsonParseError::NoError || !input.isArray()) return nullptr;
    auto *state = new ShortcutsState;
    QDomDocument document;
    auto root = document.createElement(QStringLiteral("gui"));
    root.setAttribute(QStringLiteral("name"), QStringLiteral("org.pdenams.Mirivue.Qt"));
    root.setAttribute(QStringLiteral("version"), QStringLiteral("1"));
    document.appendChild(root);
    auto properties = document.createElement(QStringLiteral("ActionProperties"));
    root.appendChild(properties);
    auto *collection = state->client.actionCollection();
    collection->setConfigGlobal(false);
    for (const auto &value : input.array()) {
        const auto entry = value.toObject();
        const QString id = entry.value(QStringLiteral("id")).toString();
        if (id.isEmpty()) continue;
        auto *action = collection->addAction(id);
        action->setText(entry.value(QStringLiteral("title")).toString());
        action->setShortcutContext(Qt::WindowShortcut);
        const auto defaults = sequences(entry.value(QStringLiteral("defaults")).toArray());
        collection->setDefaultShortcuts(action, defaults);
        auto property = document.createElement(QStringLiteral("Action"));
        property.setAttribute(QStringLiteral("name"), id);
        property.setAttribute(QStringLiteral("shortcut"), QKeySequence::listToString(defaults));
        properties.appendChild(property);
    }
    QFile base(state->files.filePath(QStringLiteral("shortcuts.rc")));
    const auto bytes = document.toByteArray();
    if (!state->files.isValid() || !base.open(QIODevice::WriteOnly)
        || base.write(bytes) != bytes.size() || !base.flush()) {delete state; return nullptr;}
    base.close();
    state->client.configure(base.fileName(), state->files.filePath(QStringLiteral("local.rc")));
    state->factory.addClient(&state->client);
    state->attached = true;
    for (const auto &value : input.array()) {
        const auto entry = value.toObject();
        if (auto *action = collection->action(entry.value(QStringLiteral("id")).toString()))
            action->setShortcuts(sequences(entry.value(QStringLiteral("sequences")).toArray()));
    }
    auto *dialog = new KShortcutsDialog(KShortcutsEditor::WindowAction,
                                       KShortcutsEditor::LetterShortcutsAllowed, static_cast<QWidget *>(parent));
    dialog->setModal(false);
    dialog->setObjectName(QStringLiteral("mirivueNativeShortcutsDialog"));
    state->setParent(dialog);
    dialog->addCollection(collection, QStringLiteral("Mirivue"));
    QObject::connect(dialog, &QDialog::accepted, dialog, [dialog, changed] {
        if (changed) {const auto values = shortcutValues(dialog); changed(values.constData());}
    });
    return dialog;
}
extern "C" void mirivue_shortcuts_show(void *pointer) {
    if (pointer) static_cast<KShortcutsDialog *>(pointer)->configure(false);
}
extern "C" void mirivue_shortcuts_defaults(void *pointer) {
    if (pointer) if (auto *editor = static_cast<KShortcutsDialog *>(pointer)->findChild<KShortcutsEditor *>()) editor->allDefault();
}
extern "C" const char *mirivue_shortcuts_values(void *pointer) {
    static thread_local QByteArray values;
    values = pointer ? shortcutValues(static_cast<KShortcutsDialog *>(pointer)) : QByteArray("{}");
    return values.constData();
}
extern "C" void *mirivue_hamburger_create(void *parent, void *bar, void *showBar, void *content, MenuNotify prepare) {
    if (!parent || !bar || !showBar || !content) return nullptr;
    auto *action = new KHamburgerMenu(static_cast<QWidget *>(parent));
    action->setObjectName(QStringLiteral("mirivueNativeHamburger"));
    action->setMenu(static_cast<QMenu *>(content));
    action->setMenuBar(static_cast<QMenuBar *>(bar));
    action->setShowMenuBarAction(static_cast<QAction *>(showBar));
    QObject::connect(action, &KHamburgerMenu::aboutToShowMenu, action, [prepare] {if (prepare) prepare();});
    return action;
}
extern "C" void *mirivue_hamburger_widget(void *pointer, void *parent) {
    return pointer && parent ? static_cast<KHamburgerMenu *>(pointer)->requestWidget(static_cast<QWidget *>(parent)) : nullptr;
}
extern "C" void mirivue_hamburger_watch(void *pointer, void *widget) {
    if (pointer && widget) static_cast<KHamburgerMenu *>(pointer)->hideActionsOf(static_cast<QWidget *>(widget));
}
extern "C" void mirivue_hamburger_add_to_menu(void *pointer, void *menu) {
    if (pointer && menu) {
        auto *target = static_cast<QMenu *>(menu);
        static_cast<KHamburgerMenu *>(pointer)->insertIntoMenuBefore(target, target->actions().value(0));
    }
}

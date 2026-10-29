// SPDX-FileCopyrightText: 2026 Mirivue contributors
// SPDX-License-Identifier: MIT
// Original Mirivue adapter using public KDE XMLGUI APIs; no Dolphin code copied.
#include <KActionCollection>
#include <KEditToolBar>
#include <KXMLGUIBuilder>
#include <KXMLGUIClient>
#include <KXMLGUIFactory>
#include <QAbstractButton>
#include <QDomDocument>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMainWindow>
#include <QTemporaryDir>

using ToolbarCallback = void (*)(const char *);

class ToolbarClient final : public KXMLGUIClient {
public:
    void configure(const QString &defaults, const QString &local) {
        setComponentName(QStringLiteral("mirivue-toolbar-editor"), QStringLiteral("Mirivue"));
        setLocalXMLFile(local);
        setXMLFile(defaults, false);
    }
};

class ToolbarEditorState final : public QObject {
public:
    QTemporaryDir files;
    QMainWindow host;
    KXMLGUIBuilder builder{&host};
    KXMLGUIFactory factory{&builder};
    ToolbarClient client;
    bool attached = false;
    explicit ToolbarEditorState() = default;
    ~ToolbarEditorState() override {
        if (attached) factory.removeClient(&client);
    }
    bool write(const QString &name, const QByteArray &bytes) {
        QFile file(files.filePath(name));
        return file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() && file.flush();
    }
};

extern "C" void *mirivue_toolbar_editor_create(void *parent, const char *payload, ToolbarCallback notify) {
    if (!parent || !payload) return nullptr;
    QJsonParseError error;
    const QJsonDocument input = QJsonDocument::fromJson(QByteArray(payload), &error);
    if (error.error != QJsonParseError::NoError || !input.isObject()) return nullptr;
    const auto object = input.object();
    const QByteArray defaults = object.value(QStringLiteral("defaults")).toString().toUtf8();
    const QByteArray current = object.value(QStringLiteral("current")).toString().toUtf8();
    QDomDocument check;
    if (!check.setContent(defaults) || !check.setContent(current)) return nullptr;
    auto *state = new ToolbarEditorState;
    if (!state->files.isValid() || !state->write(QStringLiteral("defaults.rc"), defaults)
        || !state->write(QStringLiteral("current.rc"), current)) {
        delete state;
        return nullptr;
    }
    for (const auto &value : object.value(QStringLiteral("actions")).toArray()) {
        const auto entry = value.toObject();
        const QString name = entry.value(QStringLiteral("id")).toString();
        if (name.isEmpty()) continue;
        auto *action = state->client.actionCollection()->addAction(name);
        action->setText(entry.value(QStringLiteral("text")).toString());
        auto *widget = reinterpret_cast<QWidget *>(quintptr(entry.value(QStringLiteral("widget")).toDouble()));
        if (const QString icon = entry.value(QStringLiteral("icon")).toString(); !icon.isEmpty()) action->setIcon(QIcon::fromTheme(icon));
        else if (auto *button = qobject_cast<QAbstractButton *>(widget)) action->setIcon(button->icon());
    }
    state->client.configure(state->files.filePath(QStringLiteral("defaults.rc")), state->files.filePath(QStringLiteral("current.rc")));
    state->factory.addClient(&state->client);
    state->attached = true;
    auto *dialog = new KEditToolBar(&state->factory, static_cast<QWidget *>(parent));
    dialog->setObjectName(QStringLiteral("mirivueNativeToolbarEditor"));
    dialog->setModal(true);
    state->setParent(dialog);
    QObject::connect(dialog, &KEditToolBar::newToolBarConfig, dialog, [state, notify] {
        if (notify) {
            const QByteArray document = state->client.domDocument().toByteArray();
            notify(document.constData());
        }
    });
    return dialog;
}

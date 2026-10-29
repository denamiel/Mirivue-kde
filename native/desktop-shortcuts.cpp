// SPDX-License-Identifier: MIT
#include <KStandardShortcut>
#include <KStandardShortcutWatcher>
#include <QByteArray>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QKeySequence>
#include <QObject>

extern "C" Q_DECL_EXPORT const char *mirivue_desktop_shortcuts()
{
    using namespace KStandardShortcut;
    QJsonObject result;
    const auto add = [&result](const char *name, StandardShortcut id) {
        QJsonArray keys;
        for (const auto &key : shortcut(id)) {
            keys.append(key.toString(QKeySequence::PortableText));
        }
        result.insert(QString::fromLatin1(name), keys);
    };
    add("new-window", New);
    add("new-folder", CreateFolder);
    add("rename", RenameFile);
    add("delete", MoveToTrash);
    add("delete-permanent", DeleteFile);
    add("undo", Undo);
    add("redo", Redo);
    add("copy", Copy);
    add("cut", Cut);
    add("paste", Paste);
    add("refresh", Reload);
    add("search", Find);
    add("select-all", SelectAll);
    add("hidden", ShowHideHiddenFiles);
    add("menus", OpenMainMenu);
    add("menubar", ShowMenubar);
    add("quit", Quit);
    add("back", Back);
    add("forward", Forward);
    add("parent", Up);
    add("home", Home);
    add("zoom-in", ZoomIn);
    add("zoom-out", ZoomOut);
    add("close-tab", Close);
    add("tab-next", TabNext);
    add("tab-previous", TabPrev);
    add("help", Help);
    add("preferences", Preferences);
    static QByteArray output;
    output = QJsonDocument(result).toJson(QJsonDocument::Compact);
    return output.constData();
}

using ShortcutCallback = void (*)();
extern "C" Q_DECL_EXPORT void mirivue_watch_desktop_shortcuts(QObject *owner, ShortcutCallback changed)
{
    if (owner && changed) {
        QObject::connect(KStandardShortcut::shortcutWatcher(),
                         &KStandardShortcut::StandardShortcutWatcher::shortcutChanged,
                         owner, [changed](KStandardShortcut::StandardShortcut, const QList<QKeySequence> &) { changed(); });
    }
}

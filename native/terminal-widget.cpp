// SPDX-License-Identifier: MIT
#include <QDir>
#include <QLabel>
#include <QPointer>
#include <QVBoxLayout>
#include <QWidget>

#include <KPluginFactory>
#include <KPluginMetaData>
#include <KParts/ReadOnlyPart>
#include <KShell>
#include <kde_terminal_interface.h>

using DirectoryCallback = void (*)(const char *);

class MirivueTerminalWidget final : public QWidget {
    Q_OBJECT
public:
    explicit MirivueTerminalWidget(QWidget *parent, DirectoryCallback changed)
        : QWidget(parent), m_changed(changed)
    {
        auto *layout = new QVBoxLayout(this);
        layout->setContentsMargins(0, 0, 0, 0);
        KPluginFactory *factory = KPluginFactory::loadFactory(
            KPluginMetaData(QStringLiteral("kf6/parts/konsolepart"))).plugin;
        m_part = factory ? factory->create<KParts::ReadOnlyPart>(this) : nullptr;
        m_terminal = m_part ? qobject_cast<TerminalInterface *>(m_part) : nullptr;
        if (!m_terminal) {
            delete m_part;
            m_part = nullptr;
            auto *message = new QLabel(tr("Le panneau Terminal nécessite Konsole (KonsolePart)."), this);
            message->setWordWrap(true);
            layout->addWidget(message);
            return;
        }
        layout->addWidget(m_part->widget());
        setFocusProxy(m_part->widget());
        connect(m_part, &QObject::destroyed, this, [this] {
            m_part = nullptr;
            m_terminal = nullptr;
            m_started = false;
        });
        connect(m_part, SIGNAL(currentDirectoryChanged(QString)),
                this, SLOT(directoryChanged(QString)));
    }

    ~MirivueTerminalWidget() override
    {
        delete m_part;
    }

    void setDirectory(const QString &path)
    {
        if (!m_terminal || path.isEmpty() || !QDir(path).exists()) {
            return;
        }
        const QString clean = QDir::cleanPath(path);
        m_expectedDirectory = QDir(clean).canonicalPath();
        if (!m_started) {
            m_terminal->showShellInDir(clean);
            m_started = true;
            return;
        }
        if (!isVisible() || m_terminal->foregroundProcessId() != -1
            || QDir(m_terminal->currentWorkingDirectory()).canonicalPath() == m_expectedDirectory) {
            return;
        }
        // Clear a partly typed command before changing folders, as Dolphin does.
        m_terminal->sendInput(QStringLiteral("\x05\x15"));
        m_terminal->sendInput(QStringLiteral(" cd ") + KShell::quoteArg(clean) + QLatin1Char('\r'));
    }

    void focusTerminal()
    {
        if (m_part && m_part->widget()) {
            m_part->widget()->setFocus();
        }
    }

private Q_SLOTS:
    void directoryChanged(const QString &path)
    {
        if (!m_changed || !isVisible()) {
            return;
        }
        const QString canonical = QDir(path).canonicalPath();
        if (!canonical.isEmpty() && canonical != m_expectedDirectory) {
            m_expectedDirectory = canonical;
            const QByteArray utf8 = path.toUtf8();
            m_changed(utf8.constData());
        }
    }

private:
    DirectoryCallback m_changed = nullptr;
    QPointer<KParts::ReadOnlyPart> m_part;
    TerminalInterface *m_terminal = nullptr;
    QString m_expectedDirectory;
    bool m_started = false;
};

extern "C" void *mirivue_terminal_create(void *parent, DirectoryCallback changed)
{
    if (!parent) {
        return nullptr;
    }
    return new MirivueTerminalWidget(static_cast<QWidget *>(parent), changed);
}

extern "C" void mirivue_terminal_set_directory(void *widget, const char *path)
{
    if (widget && path) {
        static_cast<MirivueTerminalWidget *>(widget)->setDirectory(QString::fromUtf8(path));
    }
}

extern "C" void mirivue_terminal_focus(void *widget)
{
    if (widget) {
        static_cast<MirivueTerminalWidget *>(widget)->focusTerminal();
    }
}

#include "terminal-widget.moc"

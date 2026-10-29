import sys

from . import __version__
from .diagnostics import configure_logging, diagnostic_report


if '--version' in sys.argv[1:]:
    print(__version__)
elif '--diagnostic' in sys.argv[1:]:
    print(diagnostic_report(__version__))
elif '--smoke-test' in sys.argv[1:]:
    # Installer-only graphical check.  It constructs the real main window but
    # does not browse a user folder or enter the event loop.
    configure_logging(__version__)
    from PySide6.QtWidgets import QApplication
    from .app import Window, prepare_audio_stream_identity
    from .platform_services import services

    prepare_audio_stream_identity()
    services.initialize_icon_theme()
    application = QApplication.instance() or QApplication(['Mirivue', '--smoke-test'])
    window = Window()
    if not window.main_menus or window.centralWidget() is None:
        raise RuntimeError('La fenêtre principale est incomplète.')
    compact = window.compact_button
    if (window.left_toolbar_layout.indexOf(compact) < 0
            and window.right_toolbar_layout.indexOf(compact) < 0):
        raise RuntimeError('Le bouton de vue compacte est absent de la barre d’outils.')
    if compact.icon().isNull():
        raise RuntimeError('Le bouton de vue compacte n’a pas d’icône.')
    window.quit_requested = True
    window.closing = True
    window.close()
    application.processEvents()
    print(f'Mirivue {__version__}: interface initialisée')
elif '--native-places-contract' in sys.argv[1:]:
    configure_logging(__version__)
    from PySide6.QtWidgets import QApplication
    from .app import Window, prepare_audio_stream_identity, prepare_system_style
    from .ui_contract import check_native_places
    from .platform_services import services

    prepare_audio_stream_identity()
    services.initialize_icon_theme()
    application = QApplication.instance() or QApplication(['Mirivue', '--native-places-contract'])
    prepare_system_style(application)
    check_native_places(Window(), application)
    print(f'Mirivue {__version__}: panneau Emplacements natif vérifié')
elif '--ui-contract' in sys.argv[1:]:
    import faulthandler
    import os
    import traceback
    # A Qt/KF6 call can wait inside native code without raising a Python
    # exception. Leave a traceback for the graphical validation timeout.
    faulthandler.dump_traceback_later(20, repeat=False)
    configure_logging(__version__)
    from PySide6.QtWidgets import QApplication
    from .app import Window, prepare_audio_stream_identity, prepare_system_style
    from .ui_contract import check_window
    from .platform_services import services

    prepare_audio_stream_identity()
    services.initialize_icon_theme()
    application = QApplication.instance() or QApplication(['Mirivue', '--ui-contract'])
    prepare_system_style(application)
    try:
        check_window(Window(), application)
    except BaseException:
        traceback.print_exc()
        sys.stderr.flush()
        # Keep exceptions visible to the parent test without entering the
        # same native fixture teardown that made the child time out.
        os._exit(1)
else:
    configure_logging(__version__)
    from .app import main
    main()

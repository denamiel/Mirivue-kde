# Dolphin's generic item engine, pinned in UPSTREAM.json. Application-specific
# KFileItemModel and file operations are supplied by Mirivue's adapter.
file(GLOB engine_sources CONFIGURE_DEPENDS
    kitemviews/kitem*.cpp kitemviews/kstandard*.cpp
    kitemviews/private/kitem*.cpp kitemviews/private/kpixmap*.cpp
    kitemviews/private/kfileitemclipboard.cpp
    kitemviews/accessibility/*.cpp)
kconfig_add_kcfg_files(engine_sources settings/dolphin_contentdisplaysettings.kcfgc)
add_library(mirivue-dolphin-view SHARED ../date-groups.cpp
    ${engine_sources} dolphindebug.cpp views/draganddrophelper.cpp ../dolphin-view.cpp ../desktop-shortcuts.cpp)
set_target_properties(mirivue-dolphin-view PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
target_include_directories(mirivue-dolphin-view PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(mirivue-dolphin-view PRIVATE TRANSLATION_DOMAIN="dolphin")
target_link_libraries(mirivue-dolphin-view PRIVATE
    Qt6::Widgets KF6::ColorScheme KF6::ConfigCore KF6::ConfigGui KF6::CoreAddons
    KF6::GuiAddons KF6::IconThemes KF6::WidgetsAddons KF6::TextWidgets KF6::I18n KF6::KIOCore)
set_target_properties(mirivue-dolphin-view PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)

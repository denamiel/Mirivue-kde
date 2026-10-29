// SPDX-License-Identifier: GPL-2.0-or-later
// Adapted from Dolphin v26.08.2 KFileItemModel::timeRoleGroups.
// SPDX-FileCopyrightText: 2011 Peter Penz <peter.penz19@gmail.com>
// SPDX-FileCopyrightText: 2013 Frank Reininghaus <frank78ac@googlemail.com>
#include "date-groups.h"
#include <QLocale>
#include <QDebug>
#include <KLocalizedString>
QList<QPair<int, QVariant>> mirivueDateGroups(const QList<QDateTime> &times)
{
    if (times.isEmpty()) return {};

    const int maxIndex = times.size() - 1;
    QList<QPair<int, QVariant>> groups;

    const QDate currentDate = QDate::currentDate();

    QDate previousFileDate;
    QString groupValue;
    for (int i = 0; i <= maxIndex; ++i) {
        const QLocale locale;
        const QDateTime fileTime = times.at(i);
        const QDate fileDate = fileTime.date();
        if (fileDate == previousFileDate) {
            // The current item is in the same group as the previous item
            continue;
        }
        previousFileDate = fileDate;

        const int daysDistance = fileDate.daysTo(currentDate);

        QString newGroupValue;
        if (currentDate.year() == fileDate.year() && currentDate.month() == fileDate.month()) {
            switch (daysDistance / 7) {
            case 0:
                switch (daysDistance) {
                case 0:
                    newGroupValue = i18nc("@title:group Date", "Today");
                    break;
                case 1:
                    newGroupValue = i18nc("@title:group Date", "Yesterday");
                    break;
                default:
                    newGroupValue = locale.toString(fileTime, i18nc("@title:group Date: The week day name: dddd", "dddd"));
                    newGroupValue = i18nc(
                        "Can be used to script translation of \"dddd\""
                        "with context @title:group Date",
                        "%1",
                        newGroupValue);
                }
                break;
            case 1:
                newGroupValue = i18nc("@title:group Date", "One Week Ago");
                break;
            case 2:
                newGroupValue = i18nc("@title:group Date", "Two Weeks Ago");
                break;
            case 3:
                newGroupValue = i18nc("@title:group Date", "Three Weeks Ago");
                break;
            case 4:
            case 5:
                newGroupValue = i18nc("@title:group Date", "Earlier this Month");
                break;
            default:
                Q_ASSERT(false);
            }
        } else {
            const QDate lastMonthDate = currentDate.addMonths(-1);
            if (lastMonthDate.year() == fileDate.year() && lastMonthDate.month() == fileDate.month()) {
                if (daysDistance == 1) {
                    const KLocalizedString format = ki18nc(
                        "@title:group Date: "
                        "MMMM is full month name in current locale, and yyyy is "
                        "full year number. You must keep the ' don't use any fancy \" or « or similar. The ' is not shown to the user, it's there to mark a "
                        "part of the text that should not be formatted as a date",
                        "'Yesterday' (MMMM, yyyy)");
                    const QString translatedFormat = format.toString();
                    if (const int count = translatedFormat.count(QLatin1Char('\'')); count >= 2 && count % 2 == 0) {
                        newGroupValue = locale.toString(fileTime, translatedFormat);
                        newGroupValue = i18nc(
                            "Can be used to script translation of "
                            "\"'Yesterday' (MMMM, yyyy)\" with context @title:group Date",
                            "%1",
                            newGroupValue);
                    } else {
                        qWarning().nospace()
                            << "A wrong translation was found: " << translatedFormat << ". Please file a bug report at bugs.kde.org";
                        const QString untranslatedFormat = format.toString({QLatin1String("en_US")});
                        newGroupValue = locale.toString(fileTime, untranslatedFormat);
                    }
                } else if (daysDistance <= 7) {
                    newGroupValue = locale.toString(fileTime,
                                                    i18nc("@title:group Date: "
                                                          "The week day name: dddd, MMMM is full month name "
                                                          "in current locale, and yyyy is full year number.",
                                                          "dddd (MMMM, yyyy)"));
                    newGroupValue = i18nc(
                        "Can be used to script translation of "
                        "\"dddd (MMMM, yyyy)\" with context @title:group Date",
                        "%1",
                        newGroupValue);
                } else if (daysDistance <= 7 * 2) {
                    const KLocalizedString format = ki18nc(
                        "@title:group Date: "
                        "MMMM is full month name in current locale, and yyyy is "
                        "full year number. You must keep the ' don't use any fancy \" or « or similar. The ' is not shown to the user, it's there to mark a "
                        "part of the text that should not be formatted as a date",
                        "'One Week Ago' (MMMM, yyyy)");
                    const QString translatedFormat = format.toString();
                    if (const int count = translatedFormat.count(QLatin1Char('\'')); count >= 2 && count % 2 == 0) {
                        newGroupValue = locale.toString(fileTime, translatedFormat);
                        newGroupValue = i18nc(
                            "Can be used to script translation of "
                            "\"'One Week Ago' (MMMM, yyyy)\" with context @title:group Date",
                            "%1",
                            newGroupValue);
                    } else {
                        qWarning().nospace()
                            << "A wrong translation was found: " << translatedFormat << ". Please file a bug report at bugs.kde.org";
                        const QString untranslatedFormat = format.toString({QLatin1String("en_US")});
                        newGroupValue = locale.toString(fileTime, untranslatedFormat);
                    }
                } else if (daysDistance <= 7 * 3) {
                    const KLocalizedString format = ki18nc(
                        "@title:group Date: "
                        "MMMM is full month name in current locale, and yyyy is "
                        "full year number. You must keep the ' don't use any fancy \" or « or similar. The ' is not shown to the user, it's there to mark a "
                        "part of the text that should not be formatted as a date",
                        "'Two Weeks Ago' (MMMM, yyyy)");
                    const QString translatedFormat = format.toString();
                    if (const int count = translatedFormat.count(QLatin1Char('\'')); count >= 2 && count % 2 == 0) {
                        newGroupValue = locale.toString(fileTime, translatedFormat);
                        newGroupValue = i18nc(
                            "Can be used to script translation of "
                            "\"'Two Weeks Ago' (MMMM, yyyy)\" with context @title:group Date",
                            "%1",
                            newGroupValue);
                    } else {
                        qWarning().nospace()
                            << "A wrong translation was found: " << translatedFormat << ". Please file a bug report at bugs.kde.org";
                        const QString untranslatedFormat = format.toString({QLatin1String("en_US")});
                        newGroupValue = locale.toString(fileTime, untranslatedFormat);
                    }
                } else if (daysDistance <= 7 * 4) {
                    const KLocalizedString format = ki18nc(
                        "@title:group Date: "
                        "MMMM is full month name in current locale, and yyyy is "
                        "full year number. You must keep the ' don't use any fancy \" or « or similar. The ' is not shown to the user, it's there to mark a "
                        "part of the text that should not be formatted as a date",
                        "'Three Weeks Ago' (MMMM, yyyy)");
                    const QString translatedFormat = format.toString();
                    if (const int count = translatedFormat.count(QLatin1Char('\'')); count >= 2 && count % 2 == 0) {
                        newGroupValue = locale.toString(fileTime, translatedFormat);
                        newGroupValue = i18nc(
                            "Can be used to script translation of "
                            "\"'Three Weeks Ago' (MMMM, yyyy)\" with context @title:group Date",
                            "%1",
                            newGroupValue);
                    } else {
                        qWarning().nospace()
                            << "A wrong translation was found: " << translatedFormat << ". Please file a bug report at bugs.kde.org";
                        const QString untranslatedFormat = format.toString({QLatin1String("en_US")});
                        newGroupValue = locale.toString(fileTime, untranslatedFormat);
                    }
                } else {
                    const KLocalizedString format = ki18nc(
                        "@title:group Date: "
                        "MMMM is full month name in current locale, and yyyy is "
                        "full year number. You must keep the ' don't use any fancy \" or « or similar. The ' is not shown to the user, it's there to mark a "
                        "part of the text that should not be formatted as a date",
                        "'Earlier on' MMMM, yyyy");
                    const QString translatedFormat = format.toString();
                    if (const int count = translatedFormat.count(QLatin1Char('\'')); count >= 2 && count % 2 == 0) {
                        newGroupValue = locale.toString(fileTime, translatedFormat);
                        newGroupValue = i18nc(
                            "Can be used to script translation of "
                            "\"'Earlier on' MMMM, yyyy\" with context @title:group Date",
                            "%1",
                            newGroupValue);
                    } else {
                        qWarning().nospace()
                            << "A wrong translation was found: " << translatedFormat << ". Please file a bug report at bugs.kde.org";
                        const QString untranslatedFormat = format.toString({QLatin1String("en_US")});
                        newGroupValue = locale.toString(fileTime, untranslatedFormat);
                    }
                }
            } else {
                newGroupValue = locale.toString(fileTime,
                                                i18nc("@title:group "
                                                      "The month and year: MMMM is full month name in current locale, "
                                                      "and yyyy is full year number",
                                                      "MMMM, yyyy"));
                newGroupValue = i18nc(
                    "Can be used to script translation of "
                    "\"MMMM, yyyy\" with context @title:group Date",
                    "%1",
                    newGroupValue);
            }
        }

        if (newGroupValue != groupValue) {
            groupValue = newGroupValue;
            groups.append(QPair<int, QVariant>(i, newGroupValue));
        }
    }

    return groups;
}

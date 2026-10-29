/*
 * SPDX-FileCopyrightText: 2011 Peter Penz <peter.penz19@gmail.com>
 * SPDX-FileCopyrightText: 2013 Frank Reininghaus <frank78ac@googlemail.com>
 * SPDX-FileCopyrightText: 2013 Emmanuel Pescosta <emmanuelpescosta099@gmail.com>
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

// Natural name comparison extracted unchanged from KFileItemModel,
// Dolphin v26.08.2. The C ABI below supplies names from Mirivue's model.
#include <QCollator>
#include <QLocale>
#include <QString>
#include <QtCore/qcompare.h>
#include <algorithm>

namespace
{
bool isAsciiDigit(QChar c)
{
    return c >= QLatin1Char('0') && c <= QLatin1Char('9');
}

Qt::strong_ordering orderingFromInt(int result)
{
    if (result < 0) {
        return Qt::strong_ordering::less;
    }

    if (result > 0) {
        return Qt::strong_ordering::greater;
    }

    return Qt::strong_ordering::equivalent;
}

int orderingToInt(Qt::strong_ordering ordering)
{
    if (is_lt(ordering)) {
        return -1;
    }

    if (is_gt(ordering)) {
        return 1;
    }

    return 0;
}

Qt::strong_ordering compareDigitStrings(const QString &a, const QString &b)
{
    int firstSignificantA = 0;
    while (firstSignificantA < a.length() && a.at(firstSignificantA) == QLatin1Char('0')) {
        ++firstSignificantA;
    }

    int firstSignificantB = 0;
    while (firstSignificantB < b.length() && b.at(firstSignificantB) == QLatin1Char('0')) {
        ++firstSignificantB;
    }

    const int significantLengthA = a.length() - firstSignificantA;
    const int significantLengthB = b.length() - firstSignificantB;
    if (significantLengthA != significantLengthB) {
        return significantLengthA < significantLengthB ? Qt::strong_ordering::less : Qt::strong_ordering::greater;
    }

    for (int i = 0; i < significantLengthA; ++i) {
        const QChar digitA = a.at(firstSignificantA + i);
        const QChar digitB = b.at(firstSignificantB + i);
        if (digitA != digitB) {
            return digitA < digitB ? Qt::strong_ordering::less : Qt::strong_ordering::greater;
        }
    }

    return Qt::strong_ordering::equivalent;
}

Qt::strong_ordering compareFractionalDigitStrings(const QString &a, const QString &b)
{
    const int length = std::max(a.length(), b.length());
    for (int i = 0; i < length; ++i) {
        const QChar digitA = i < a.length() ? a.at(i) : QLatin1Char('0');
        const QChar digitB = i < b.length() ? b.at(i) : QLatin1Char('0');
        if (digitA != digitB) {
            return digitA < digitB ? Qt::strong_ordering::less : Qt::strong_ordering::greater;
        }
    }

    return Qt::strong_ordering::equivalent;
}

int findDigitRunEnd(const QString &text, int start)
{
    int end = start;
    while (end < text.length() && isAsciiDigit(text.at(end))) {
        ++end;
    }

    return end;
}

int countNumericChainSegments(const QString &text, int start, int *chainEnd)
{
    int end = findDigitRunEnd(text, start);
    int segmentCount = 1;

    while (end + 1 < text.length() && text.at(end) == QLatin1Char('.') && isAsciiDigit(text.at(end + 1))) {
        end = findDigitRunEnd(text, end + 1);
        ++segmentCount;
    }

    if (chainEnd) {
        *chainEnd = end;
    }

    return segmentCount;
}

Qt::strong_ordering compareNumericChains(const QString &a, int startA, int endA, int segmentCountA, const QString &b, int startB, int endB, int segmentCountB)
{
    if (segmentCountA == 2 && segmentCountB == 2) {
        const int dotA = findDigitRunEnd(a, startA);
        const int dotB = findDigitRunEnd(b, startB);

        const Qt::strong_ordering integerResult = compareDigitStrings(a.mid(startA, dotA - startA), b.mid(startB, dotB - startB));
        if (is_neq(integerResult)) {
            return integerResult;
        }

        return compareFractionalDigitStrings(a.mid(dotA + 1, endA - dotA - 1), b.mid(dotB + 1, endB - dotB - 1));
    }

    int segmentStartA = startA;
    int segmentStartB = startB;

    while (true) {
        const int segmentEndA = findDigitRunEnd(a, segmentStartA);
        const int segmentEndB = findDigitRunEnd(b, segmentStartB);

        const Qt::strong_ordering segmentResult =
            compareDigitStrings(a.mid(segmentStartA, segmentEndA - segmentStartA), b.mid(segmentStartB, segmentEndB - segmentStartB));
        if (is_neq(segmentResult)) {
            return segmentResult;
        }

        const bool hasNextSegmentA = segmentEndA < endA;
        const bool hasNextSegmentB = segmentEndB < endB;
        if (!hasNextSegmentA || !hasNextSegmentB) {
            if (hasNextSegmentA != hasNextSegmentB) {
                return hasNextSegmentA ? Qt::strong_ordering::greater : Qt::strong_ordering::less;
            }

            return Qt::strong_ordering::equivalent;
        }

        segmentStartA = segmentEndA + 1;
        segmentStartB = segmentEndB + 1;
    }
}

int findExtensionSeparator(const QString &text)
{
    for (int i = text.length() - 1; i > 0; --i) {
        if (text.at(i) != QLatin1Char('.')) {
            continue;
        }

        if (isAsciiDigit(text.at(i - 1)) && i + 1 < text.length() && isAsciiDigit(text.at(i + 1))) {
            continue;
        }

        return i;
    }

    return -1;
}

Qt::strong_ordering decimalAwareNaturalCompare(const QString &a, const QString &b, const QCollator &collator)
{
    bool comparedNumericTokens = false;
    int indexA = 0;
    int indexB = 0;

    while (indexA < a.length() && indexB < b.length()) {
        if (isAsciiDigit(a.at(indexA)) && isAsciiDigit(b.at(indexB))) {
            comparedNumericTokens = true;
            int chainEndA = indexA;
            const int segmentCountA = countNumericChainSegments(a, indexA, &chainEndA);
            int chainEndB = indexB;
            const int segmentCountB = countNumericChainSegments(b, indexB, &chainEndB);

            const Qt::strong_ordering numericResult = compareNumericChains(a, indexA, chainEndA, segmentCountA, b, indexB, chainEndB, segmentCountB);
            indexA = chainEndA;
            indexB = chainEndB;
            if (is_neq(numericResult)) {
                return numericResult;
            }

            continue;
        }

        int textEndA = indexA;
        while (textEndA < a.length() && !isAsciiDigit(a.at(textEndA))) {
            ++textEndA;
        }

        int textEndB = indexB;
        while (textEndB < b.length() && !isAsciiDigit(b.at(textEndB))) {
            ++textEndB;
        }

        const Qt::strong_ordering textResult = orderingFromInt(collator.compare(a.mid(indexA, textEndA - indexA), b.mid(indexB, textEndB - indexB)));
        if (is_neq(textResult)) {
            return orderingFromInt(collator.compare(a.mid(indexA), b.mid(indexB)));
        }

        indexA = textEndA;
        indexB = textEndB;
    }

    const Qt::strong_ordering remainderResult = orderingFromInt(collator.compare(a.mid(indexA), b.mid(indexB)));
    if (is_neq(remainderResult)) {
        return remainderResult;
    }

    if (!comparedNumericTokens) {
        return Qt::strong_ordering::equivalent;
    }

    const Qt::strong_ordering result = orderingFromInt(QString::compare(a, b, collator.caseSensitivity()));
    if (is_neq(result) || collator.caseSensitivity() == Qt::CaseSensitive) {
        return result;
    }

    return orderingFromInt(QString::compare(a, b, Qt::CaseSensitive));
}
}

extern "C" int mirivue_natural_compare(const char *left, const char *right)
{
    // Listing runs in worker threads; a collator must never be shared between
    // those threads and Qt's GUI-thread sorting proxy.
    thread_local QCollator collator;
    const QLocale locale;
    if (collator.locale() != locale) collator.setLocale(locale);
    collator.setNumericMode(true);
    collator.setCaseSensitivity(Qt::CaseInsensitive);
    const QString a = QString::fromUtf8(left);
    const QString b = QString::fromUtf8(right);
    const int aSeparator = findExtensionSeparator(a);
    const int bSeparator = findExtensionSeparator(b);
    const int aLength = aSeparator < 0 ? a.length() : aSeparator;
    const int bLength = bSeparator < 0 ? b.length() : bSeparator;
    int result = orderingToInt(decimalAwareNaturalCompare(a.left(aLength), b.left(bLength), collator));
    if (result == 0 && (aSeparator >= 0 || bSeparator >= 0)) {
        result = orderingToInt(decimalAwareNaturalCompare(a.mid(aLength), b.mid(bLength), collator));
    }
    return result;
}

extern "C" int mirivue_string_compare(const char *left, const char *right, int mode)
{
    if (mode == 0) return mirivue_natural_compare(left, right);
    const auto a=QString::fromUtf8(left), b=QString::fromUtf8(right);
    const auto sensitivity=mode==1 ? Qt::CaseSensitive : Qt::CaseInsensitive;
    const int result=QString::compare(a,b,sensitivity);
    return result || sensitivity==Qt::CaseSensitive ? result : QString::compare(a,b,Qt::CaseSensitive);
}

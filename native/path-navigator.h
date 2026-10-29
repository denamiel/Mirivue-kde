// SPDX-License-Identifier: MIT
#pragma once

class KFilePlacesModel;
class KUrlNavigator;
class QUrl;
class QWidget;

KUrlNavigator *createPathNavigator(KFilePlacesModel *places, const QUrl &url, QWidget *parent);

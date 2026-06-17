QT += widgets network

CONFIG += c++14
CONFIG -= app_bundle

TEMPLATE = app
TARGET = fruit_quality_qt

SOURCES += \
    src/main.cpp \
    src/mainwindow.cpp \
    src/sensordatareader.cpp

HEADERS += \
    src/mainwindow.h \
    src/sensordatareader.h

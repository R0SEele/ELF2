/****************************************************************************
** Meta object code from reading C++ file 'mainwindow.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.3)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "src/mainwindow.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'mainwindow.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.3. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_MainWindow_t {
    QByteArrayData data[49];
    char stringdata0[935];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_MainWindow_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_MainWindow_t qt_meta_stringdata_MainWindow = {
    {
QT_MOC_LITERAL(0, 0, 10), // "MainWindow"
QT_MOC_LITERAL(1, 11, 16), // "shutdownHardware"
QT_MOC_LITERAL(2, 28, 0), // ""
QT_MOC_LITERAL(3, 29, 12), // "showWorkPage"
QT_MOC_LITERAL(4, 42, 13), // "showStartPage"
QT_MOC_LITERAL(5, 56, 20), // "showFunctionHomePage"
QT_MOC_LITERAL(6, 77, 23), // "showConveyorControlPage"
QT_MOC_LITERAL(7, 101, 18), // "showLedControlPage"
QT_MOC_LITERAL(8, 120, 20), // "showMangoQualityPage"
QT_MOC_LITERAL(9, 141, 20), // "showServoControlPage"
QT_MOC_LITERAL(10, 162, 18), // "showBatchStatsPage"
QT_MOC_LITERAL(11, 181, 20), // "showMangoHistoryPage"
QT_MOC_LITERAL(12, 202, 19), // "showVoicePromptPage"
QT_MOC_LITERAL(13, 222, 17), // "refreshSensorData"
QT_MOC_LITERAL(14, 240, 23), // "refreshMangoQualityData"
QT_MOC_LITERAL(15, 264, 21), // "refreshBatchStatsData"
QT_MOC_LITERAL(16, 286, 23), // "refreshMangoHistoryData"
QT_MOC_LITERAL(17, 310, 18), // "readSensorMessages"
QT_MOC_LITERAL(18, 329, 20), // "handleSensorFinished"
QT_MOC_LITERAL(19, 350, 8), // "exitCode"
QT_MOC_LITERAL(20, 359, 20), // "QProcess::ExitStatus"
QT_MOC_LITERAL(21, 380, 10), // "exitStatus"
QT_MOC_LITERAL(22, 391, 24), // "readMangoQualityMessages"
QT_MOC_LITERAL(23, 416, 26), // "handleMangoQualityFinished"
QT_MOC_LITERAL(24, 443, 21), // "announcePreviousMango"
QT_MOC_LITERAL(25, 465, 18), // "announceBatchMango"
QT_MOC_LITERAL(26, 484, 23), // "readVoicePromptMessages"
QT_MOC_LITERAL(27, 508, 25), // "handleVoicePromptFinished"
QT_MOC_LITERAL(28, 534, 16), // "readCameraFrames"
QT_MOC_LITERAL(29, 551, 18), // "readCameraMessages"
QT_MOC_LITERAL(30, 570, 20), // "handleCameraFinished"
QT_MOC_LITERAL(31, 591, 15), // "updateIotStatus"
QT_MOC_LITERAL(32, 607, 19), // "readTuyaIotMessages"
QT_MOC_LITERAL(33, 627, 21), // "handleTuyaIotFinished"
QT_MOC_LITERAL(34, 649, 24), // "updateConveyorSpeedLabel"
QT_MOC_LITERAL(35, 674, 5), // "value"
QT_MOC_LITERAL(36, 680, 18), // "applyConveyorSpeed"
QT_MOC_LITERAL(37, 699, 20), // "startConveyorForward"
QT_MOC_LITERAL(38, 720, 20), // "startConveyorReverse"
QT_MOC_LITERAL(39, 741, 12), // "stopConveyor"
QT_MOC_LITERAL(40, 754, 24), // "updateLedBrightnessLabel"
QT_MOC_LITERAL(41, 779, 23), // "updateLedThresholdLabel"
QT_MOC_LITERAL(42, 803, 18), // "applyLedBrightness"
QT_MOC_LITERAL(43, 822, 10), // "turnLedOff"
QT_MOC_LITERAL(44, 833, 17), // "toggleLedAutoMode"
QT_MOC_LITERAL(45, 851, 20), // "updateLedAutoControl"
QT_MOC_LITERAL(46, 872, 20), // "moveServoToPosition1"
QT_MOC_LITERAL(47, 893, 20), // "moveServoToPosition2"
QT_MOC_LITERAL(48, 914, 20) // "moveServoToPosition3"

    },
    "MainWindow\0shutdownHardware\0\0showWorkPage\0"
    "showStartPage\0showFunctionHomePage\0"
    "showConveyorControlPage\0showLedControlPage\0"
    "showMangoQualityPage\0showServoControlPage\0"
    "showBatchStatsPage\0showMangoHistoryPage\0"
    "showVoicePromptPage\0refreshSensorData\0"
    "refreshMangoQualityData\0refreshBatchStatsData\0"
    "refreshMangoHistoryData\0readSensorMessages\0"
    "handleSensorFinished\0exitCode\0"
    "QProcess::ExitStatus\0exitStatus\0"
    "readMangoQualityMessages\0"
    "handleMangoQualityFinished\0"
    "announcePreviousMango\0announceBatchMango\0"
    "readVoicePromptMessages\0"
    "handleVoicePromptFinished\0readCameraFrames\0"
    "readCameraMessages\0handleCameraFinished\0"
    "updateIotStatus\0readTuyaIotMessages\0"
    "handleTuyaIotFinished\0updateConveyorSpeedLabel\0"
    "value\0applyConveyorSpeed\0startConveyorForward\0"
    "startConveyorReverse\0stopConveyor\0"
    "updateLedBrightnessLabel\0"
    "updateLedThresholdLabel\0applyLedBrightness\0"
    "turnLedOff\0toggleLedAutoMode\0"
    "updateLedAutoControl\0moveServoToPosition1\0"
    "moveServoToPosition2\0moveServoToPosition3"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_MainWindow[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
      43,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,  229,    2, 0x0a /* Public */,
       3,    0,  230,    2, 0x08 /* Private */,
       4,    0,  231,    2, 0x08 /* Private */,
       5,    0,  232,    2, 0x08 /* Private */,
       6,    0,  233,    2, 0x08 /* Private */,
       7,    0,  234,    2, 0x08 /* Private */,
       8,    0,  235,    2, 0x08 /* Private */,
       9,    0,  236,    2, 0x08 /* Private */,
      10,    0,  237,    2, 0x08 /* Private */,
      11,    0,  238,    2, 0x08 /* Private */,
      12,    0,  239,    2, 0x08 /* Private */,
      13,    0,  240,    2, 0x08 /* Private */,
      14,    0,  241,    2, 0x08 /* Private */,
      15,    0,  242,    2, 0x08 /* Private */,
      16,    0,  243,    2, 0x08 /* Private */,
      17,    0,  244,    2, 0x08 /* Private */,
      18,    2,  245,    2, 0x08 /* Private */,
      22,    0,  250,    2, 0x08 /* Private */,
      23,    2,  251,    2, 0x08 /* Private */,
      24,    0,  256,    2, 0x08 /* Private */,
      25,    0,  257,    2, 0x08 /* Private */,
      26,    0,  258,    2, 0x08 /* Private */,
      27,    2,  259,    2, 0x08 /* Private */,
      28,    0,  264,    2, 0x08 /* Private */,
      29,    0,  265,    2, 0x08 /* Private */,
      30,    2,  266,    2, 0x08 /* Private */,
      31,    0,  271,    2, 0x08 /* Private */,
      32,    0,  272,    2, 0x08 /* Private */,
      33,    2,  273,    2, 0x08 /* Private */,
      34,    1,  278,    2, 0x08 /* Private */,
      36,    0,  281,    2, 0x08 /* Private */,
      37,    0,  282,    2, 0x08 /* Private */,
      38,    0,  283,    2, 0x08 /* Private */,
      39,    0,  284,    2, 0x08 /* Private */,
      40,    1,  285,    2, 0x08 /* Private */,
      41,    1,  288,    2, 0x08 /* Private */,
      42,    0,  291,    2, 0x08 /* Private */,
      43,    0,  292,    2, 0x08 /* Private */,
      44,    0,  293,    2, 0x08 /* Private */,
      45,    0,  294,    2, 0x08 /* Private */,
      46,    0,  295,    2, 0x08 /* Private */,
      47,    0,  296,    2, 0x08 /* Private */,
      48,    0,  297,    2, 0x08 /* Private */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 20,   19,   21,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 20,   19,   21,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 20,   19,   21,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 20,   19,   21,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 20,   19,   21,
    QMetaType::Void, QMetaType::Int,   35,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   35,
    QMetaType::Void, QMetaType::Int,   35,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

void MainWindow::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<MainWindow *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->shutdownHardware(); break;
        case 1: _t->showWorkPage(); break;
        case 2: _t->showStartPage(); break;
        case 3: _t->showFunctionHomePage(); break;
        case 4: _t->showConveyorControlPage(); break;
        case 5: _t->showLedControlPage(); break;
        case 6: _t->showMangoQualityPage(); break;
        case 7: _t->showServoControlPage(); break;
        case 8: _t->showBatchStatsPage(); break;
        case 9: _t->showMangoHistoryPage(); break;
        case 10: _t->showVoicePromptPage(); break;
        case 11: _t->refreshSensorData(); break;
        case 12: _t->refreshMangoQualityData(); break;
        case 13: _t->refreshBatchStatsData(); break;
        case 14: _t->refreshMangoHistoryData(); break;
        case 15: _t->readSensorMessages(); break;
        case 16: _t->handleSensorFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 17: _t->readMangoQualityMessages(); break;
        case 18: _t->handleMangoQualityFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 19: _t->announcePreviousMango(); break;
        case 20: _t->announceBatchMango(); break;
        case 21: _t->readVoicePromptMessages(); break;
        case 22: _t->handleVoicePromptFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 23: _t->readCameraFrames(); break;
        case 24: _t->readCameraMessages(); break;
        case 25: _t->handleCameraFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 26: _t->updateIotStatus(); break;
        case 27: _t->readTuyaIotMessages(); break;
        case 28: _t->handleTuyaIotFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 29: _t->updateConveyorSpeedLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 30: _t->applyConveyorSpeed(); break;
        case 31: _t->startConveyorForward(); break;
        case 32: _t->startConveyorReverse(); break;
        case 33: _t->stopConveyor(); break;
        case 34: _t->updateLedBrightnessLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 35: _t->updateLedThresholdLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 36: _t->applyLedBrightness(); break;
        case 37: _t->turnLedOff(); break;
        case 38: _t->toggleLedAutoMode(); break;
        case 39: _t->updateLedAutoControl(); break;
        case 40: _t->moveServoToPosition1(); break;
        case 41: _t->moveServoToPosition2(); break;
        case 42: _t->moveServoToPosition3(); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject MainWindow::staticMetaObject = { {
    QMetaObject::SuperData::link<QMainWindow::staticMetaObject>(),
    qt_meta_stringdata_MainWindow.data,
    qt_meta_data_MainWindow,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *MainWindow::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *MainWindow::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_MainWindow.stringdata0))
        return static_cast<void*>(this);
    return QMainWindow::qt_metacast(_clname);
}

int MainWindow::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QMainWindow::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 43)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 43;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 43)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 43;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE

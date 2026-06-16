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
    QByteArrayData data[41];
    char stringdata0[766];
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
QT_MOC_LITERAL(12, 202, 17), // "refreshSensorData"
QT_MOC_LITERAL(13, 220, 23), // "refreshMangoQualityData"
QT_MOC_LITERAL(14, 244, 21), // "refreshBatchStatsData"
QT_MOC_LITERAL(15, 266, 23), // "refreshMangoHistoryData"
QT_MOC_LITERAL(16, 290, 18), // "readSensorMessages"
QT_MOC_LITERAL(17, 309, 20), // "handleSensorFinished"
QT_MOC_LITERAL(18, 330, 8), // "exitCode"
QT_MOC_LITERAL(19, 339, 20), // "QProcess::ExitStatus"
QT_MOC_LITERAL(20, 360, 10), // "exitStatus"
QT_MOC_LITERAL(21, 371, 24), // "readMangoQualityMessages"
QT_MOC_LITERAL(22, 396, 26), // "handleMangoQualityFinished"
QT_MOC_LITERAL(23, 423, 16), // "readCameraFrames"
QT_MOC_LITERAL(24, 440, 18), // "readCameraMessages"
QT_MOC_LITERAL(25, 459, 20), // "handleCameraFinished"
QT_MOC_LITERAL(26, 480, 24), // "updateConveyorSpeedLabel"
QT_MOC_LITERAL(27, 505, 5), // "value"
QT_MOC_LITERAL(28, 511, 18), // "applyConveyorSpeed"
QT_MOC_LITERAL(29, 530, 20), // "startConveyorForward"
QT_MOC_LITERAL(30, 551, 20), // "startConveyorReverse"
QT_MOC_LITERAL(31, 572, 12), // "stopConveyor"
QT_MOC_LITERAL(32, 585, 24), // "updateLedBrightnessLabel"
QT_MOC_LITERAL(33, 610, 23), // "updateLedThresholdLabel"
QT_MOC_LITERAL(34, 634, 18), // "applyLedBrightness"
QT_MOC_LITERAL(35, 653, 10), // "turnLedOff"
QT_MOC_LITERAL(36, 664, 17), // "toggleLedAutoMode"
QT_MOC_LITERAL(37, 682, 20), // "updateLedAutoControl"
QT_MOC_LITERAL(38, 703, 20), // "moveServoToPosition1"
QT_MOC_LITERAL(39, 724, 20), // "moveServoToPosition2"
QT_MOC_LITERAL(40, 745, 20) // "moveServoToPosition3"

    },
    "MainWindow\0shutdownHardware\0\0showWorkPage\0"
    "showStartPage\0showFunctionHomePage\0"
    "showConveyorControlPage\0showLedControlPage\0"
    "showMangoQualityPage\0showServoControlPage\0"
    "showBatchStatsPage\0showMangoHistoryPage\0"
    "refreshSensorData\0refreshMangoQualityData\0"
    "refreshBatchStatsData\0refreshMangoHistoryData\0"
    "readSensorMessages\0handleSensorFinished\0"
    "exitCode\0QProcess::ExitStatus\0exitStatus\0"
    "readMangoQualityMessages\0"
    "handleMangoQualityFinished\0readCameraFrames\0"
    "readCameraMessages\0handleCameraFinished\0"
    "updateConveyorSpeedLabel\0value\0"
    "applyConveyorSpeed\0startConveyorForward\0"
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
      35,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,  189,    2, 0x0a /* Public */,
       3,    0,  190,    2, 0x08 /* Private */,
       4,    0,  191,    2, 0x08 /* Private */,
       5,    0,  192,    2, 0x08 /* Private */,
       6,    0,  193,    2, 0x08 /* Private */,
       7,    0,  194,    2, 0x08 /* Private */,
       8,    0,  195,    2, 0x08 /* Private */,
       9,    0,  196,    2, 0x08 /* Private */,
      10,    0,  197,    2, 0x08 /* Private */,
      11,    0,  198,    2, 0x08 /* Private */,
      12,    0,  199,    2, 0x08 /* Private */,
      13,    0,  200,    2, 0x08 /* Private */,
      14,    0,  201,    2, 0x08 /* Private */,
      15,    0,  202,    2, 0x08 /* Private */,
      16,    0,  203,    2, 0x08 /* Private */,
      17,    2,  204,    2, 0x08 /* Private */,
      21,    0,  209,    2, 0x08 /* Private */,
      22,    2,  210,    2, 0x08 /* Private */,
      23,    0,  215,    2, 0x08 /* Private */,
      24,    0,  216,    2, 0x08 /* Private */,
      25,    2,  217,    2, 0x08 /* Private */,
      26,    1,  222,    2, 0x08 /* Private */,
      28,    0,  225,    2, 0x08 /* Private */,
      29,    0,  226,    2, 0x08 /* Private */,
      30,    0,  227,    2, 0x08 /* Private */,
      31,    0,  228,    2, 0x08 /* Private */,
      32,    1,  229,    2, 0x08 /* Private */,
      33,    1,  232,    2, 0x08 /* Private */,
      34,    0,  235,    2, 0x08 /* Private */,
      35,    0,  236,    2, 0x08 /* Private */,
      36,    0,  237,    2, 0x08 /* Private */,
      37,    0,  238,    2, 0x08 /* Private */,
      38,    0,  239,    2, 0x08 /* Private */,
      39,    0,  240,    2, 0x08 /* Private */,
      40,    0,  241,    2, 0x08 /* Private */,

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
    QMetaType::Void, QMetaType::Int, 0x80000000 | 19,   18,   20,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 19,   18,   20,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 19,   18,   20,
    QMetaType::Void, QMetaType::Int,   27,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   27,
    QMetaType::Void, QMetaType::Int,   27,
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
        case 10: _t->refreshSensorData(); break;
        case 11: _t->refreshMangoQualityData(); break;
        case 12: _t->refreshBatchStatsData(); break;
        case 13: _t->refreshMangoHistoryData(); break;
        case 14: _t->readSensorMessages(); break;
        case 15: _t->handleSensorFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 16: _t->readMangoQualityMessages(); break;
        case 17: _t->handleMangoQualityFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 18: _t->readCameraFrames(); break;
        case 19: _t->readCameraMessages(); break;
        case 20: _t->handleCameraFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 21: _t->updateConveyorSpeedLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 22: _t->applyConveyorSpeed(); break;
        case 23: _t->startConveyorForward(); break;
        case 24: _t->startConveyorReverse(); break;
        case 25: _t->stopConveyor(); break;
        case 26: _t->updateLedBrightnessLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 27: _t->updateLedThresholdLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 28: _t->applyLedBrightness(); break;
        case 29: _t->turnLedOff(); break;
        case 30: _t->toggleLedAutoMode(); break;
        case 31: _t->updateLedAutoControl(); break;
        case 32: _t->moveServoToPosition1(); break;
        case 33: _t->moveServoToPosition2(); break;
        case 34: _t->moveServoToPosition3(); break;
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
        if (_id < 35)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 35;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 35)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 35;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE

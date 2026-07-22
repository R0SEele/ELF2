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
    QByteArrayData data[57];
    char stringdata0[1109];
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
QT_MOC_LITERAL(8, 120, 18), // "showFanControlPage"
QT_MOC_LITERAL(9, 139, 20), // "showMangoQualityPage"
QT_MOC_LITERAL(10, 160, 18), // "showBatchStatsPage"
QT_MOC_LITERAL(11, 179, 24), // "showEnvironmentTrendPage"
QT_MOC_LITERAL(12, 204, 20), // "showMangoHistoryPage"
QT_MOC_LITERAL(13, 225, 19), // "showVoicePromptPage"
QT_MOC_LITERAL(14, 245, 17), // "refreshSensorData"
QT_MOC_LITERAL(15, 263, 23), // "refreshMangoQualityData"
QT_MOC_LITERAL(16, 287, 21), // "refreshBatchStatsData"
QT_MOC_LITERAL(17, 309, 27), // "refreshEnvironmentTrendData"
QT_MOC_LITERAL(18, 337, 23), // "refreshMangoHistoryData"
QT_MOC_LITERAL(19, 361, 18), // "readSensorMessages"
QT_MOC_LITERAL(20, 380, 20), // "handleSensorFinished"
QT_MOC_LITERAL(21, 401, 8), // "exitCode"
QT_MOC_LITERAL(22, 410, 20), // "QProcess::ExitStatus"
QT_MOC_LITERAL(23, 431, 10), // "exitStatus"
QT_MOC_LITERAL(24, 442, 24), // "readMangoQualityMessages"
QT_MOC_LITERAL(25, 467, 26), // "handleMangoQualityFinished"
QT_MOC_LITERAL(26, 494, 21), // "announcePreviousMango"
QT_MOC_LITERAL(27, 516, 18), // "announceBatchMango"
QT_MOC_LITERAL(28, 535, 23), // "readVoicePromptMessages"
QT_MOC_LITERAL(29, 559, 25), // "handleVoicePromptFinished"
QT_MOC_LITERAL(30, 585, 16), // "readCameraFrames"
QT_MOC_LITERAL(31, 602, 18), // "readCameraMessages"
QT_MOC_LITERAL(32, 621, 20), // "handleCameraFinished"
QT_MOC_LITERAL(33, 642, 15), // "updateIotStatus"
QT_MOC_LITERAL(34, 658, 19), // "readTuyaIotMessages"
QT_MOC_LITERAL(35, 678, 21), // "handleTuyaIotFinished"
QT_MOC_LITERAL(36, 700, 24), // "syncExternalControlState"
QT_MOC_LITERAL(37, 725, 24), // "updateConveyorSpeedLabel"
QT_MOC_LITERAL(38, 750, 5), // "value"
QT_MOC_LITERAL(39, 756, 18), // "applyConveyorSpeed"
QT_MOC_LITERAL(40, 775, 20), // "startConveyorForward"
QT_MOC_LITERAL(41, 796, 20), // "startConveyorReverse"
QT_MOC_LITERAL(42, 817, 12), // "stopConveyor"
QT_MOC_LITERAL(43, 830, 24), // "updateLedBrightnessLabel"
QT_MOC_LITERAL(44, 855, 23), // "updateLedThresholdLabel"
QT_MOC_LITERAL(45, 879, 18), // "applyLedBrightness"
QT_MOC_LITERAL(46, 898, 10), // "turnLedOff"
QT_MOC_LITERAL(47, 909, 17), // "toggleLedAutoMode"
QT_MOC_LITERAL(48, 927, 20), // "updateLedAutoControl"
QT_MOC_LITERAL(49, 948, 34), // "updateFanTemperatureThreshold..."
QT_MOC_LITERAL(50, 983, 31), // "updateFanHumidityThresholdLabel"
QT_MOC_LITERAL(51, 1015, 18), // "applyFanThresholds"
QT_MOC_LITERAL(52, 1034, 9), // "turnFanOn"
QT_MOC_LITERAL(53, 1044, 10), // "turnFanOff"
QT_MOC_LITERAL(54, 1055, 17), // "toggleFanAutoMode"
QT_MOC_LITERAL(55, 1073, 20), // "updateFanAutoControl"
QT_MOC_LITERAL(56, 1094, 14) // "toggleAutoSort"

    },
    "MainWindow\0shutdownHardware\0\0showWorkPage\0"
    "showStartPage\0showFunctionHomePage\0"
    "showConveyorControlPage\0showLedControlPage\0"
    "showFanControlPage\0showMangoQualityPage\0"
    "showBatchStatsPage\0showEnvironmentTrendPage\0"
    "showMangoHistoryPage\0showVoicePromptPage\0"
    "refreshSensorData\0refreshMangoQualityData\0"
    "refreshBatchStatsData\0refreshEnvironmentTrendData\0"
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
    "handleTuyaIotFinished\0syncExternalControlState\0"
    "updateConveyorSpeedLabel\0value\0"
    "applyConveyorSpeed\0startConveyorForward\0"
    "startConveyorReverse\0stopConveyor\0"
    "updateLedBrightnessLabel\0"
    "updateLedThresholdLabel\0applyLedBrightness\0"
    "turnLedOff\0toggleLedAutoMode\0"
    "updateLedAutoControl\0"
    "updateFanTemperatureThresholdLabel\0"
    "updateFanHumidityThresholdLabel\0"
    "applyFanThresholds\0turnFanOn\0turnFanOff\0"
    "toggleFanAutoMode\0updateFanAutoControl\0"
    "toggleAutoSort"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_MainWindow[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
      51,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,  269,    2, 0x0a /* Public */,
       3,    0,  270,    2, 0x08 /* Private */,
       4,    0,  271,    2, 0x08 /* Private */,
       5,    0,  272,    2, 0x08 /* Private */,
       6,    0,  273,    2, 0x08 /* Private */,
       7,    0,  274,    2, 0x08 /* Private */,
       8,    0,  275,    2, 0x08 /* Private */,
       9,    0,  276,    2, 0x08 /* Private */,
      10,    0,  277,    2, 0x08 /* Private */,
      11,    0,  278,    2, 0x08 /* Private */,
      12,    0,  279,    2, 0x08 /* Private */,
      13,    0,  280,    2, 0x08 /* Private */,
      14,    0,  281,    2, 0x08 /* Private */,
      15,    0,  282,    2, 0x08 /* Private */,
      16,    0,  283,    2, 0x08 /* Private */,
      17,    0,  284,    2, 0x08 /* Private */,
      18,    0,  285,    2, 0x08 /* Private */,
      19,    0,  286,    2, 0x08 /* Private */,
      20,    2,  287,    2, 0x08 /* Private */,
      24,    0,  292,    2, 0x08 /* Private */,
      25,    2,  293,    2, 0x08 /* Private */,
      26,    0,  298,    2, 0x08 /* Private */,
      27,    0,  299,    2, 0x08 /* Private */,
      28,    0,  300,    2, 0x08 /* Private */,
      29,    2,  301,    2, 0x08 /* Private */,
      30,    0,  306,    2, 0x08 /* Private */,
      31,    0,  307,    2, 0x08 /* Private */,
      32,    2,  308,    2, 0x08 /* Private */,
      33,    0,  313,    2, 0x08 /* Private */,
      34,    0,  314,    2, 0x08 /* Private */,
      35,    2,  315,    2, 0x08 /* Private */,
      36,    0,  320,    2, 0x08 /* Private */,
      37,    1,  321,    2, 0x08 /* Private */,
      39,    0,  324,    2, 0x08 /* Private */,
      40,    0,  325,    2, 0x08 /* Private */,
      41,    0,  326,    2, 0x08 /* Private */,
      42,    0,  327,    2, 0x08 /* Private */,
      43,    1,  328,    2, 0x08 /* Private */,
      44,    1,  331,    2, 0x08 /* Private */,
      45,    0,  334,    2, 0x08 /* Private */,
      46,    0,  335,    2, 0x08 /* Private */,
      47,    0,  336,    2, 0x08 /* Private */,
      48,    0,  337,    2, 0x08 /* Private */,
      49,    1,  338,    2, 0x08 /* Private */,
      50,    1,  341,    2, 0x08 /* Private */,
      51,    0,  344,    2, 0x08 /* Private */,
      52,    0,  345,    2, 0x08 /* Private */,
      53,    0,  346,    2, 0x08 /* Private */,
      54,    0,  347,    2, 0x08 /* Private */,
      55,    0,  348,    2, 0x08 /* Private */,
      56,    0,  349,    2, 0x08 /* Private */,

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
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 22,   21,   23,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 22,   21,   23,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 22,   21,   23,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 22,   21,   23,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, 0x80000000 | 22,   21,   23,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   38,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   38,
    QMetaType::Void, QMetaType::Int,   38,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   38,
    QMetaType::Void, QMetaType::Int,   38,
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
        case 6: _t->showFanControlPage(); break;
        case 7: _t->showMangoQualityPage(); break;
        case 8: _t->showBatchStatsPage(); break;
        case 9: _t->showEnvironmentTrendPage(); break;
        case 10: _t->showMangoHistoryPage(); break;
        case 11: _t->showVoicePromptPage(); break;
        case 12: _t->refreshSensorData(); break;
        case 13: _t->refreshMangoQualityData(); break;
        case 14: _t->refreshBatchStatsData(); break;
        case 15: _t->refreshEnvironmentTrendData(); break;
        case 16: _t->refreshMangoHistoryData(); break;
        case 17: _t->readSensorMessages(); break;
        case 18: _t->handleSensorFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 19: _t->readMangoQualityMessages(); break;
        case 20: _t->handleMangoQualityFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 21: _t->announcePreviousMango(); break;
        case 22: _t->announceBatchMango(); break;
        case 23: _t->readVoicePromptMessages(); break;
        case 24: _t->handleVoicePromptFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 25: _t->readCameraFrames(); break;
        case 26: _t->readCameraMessages(); break;
        case 27: _t->handleCameraFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 28: _t->updateIotStatus(); break;
        case 29: _t->readTuyaIotMessages(); break;
        case 30: _t->handleTuyaIotFinished((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< QProcess::ExitStatus(*)>(_a[2]))); break;
        case 31: _t->syncExternalControlState(); break;
        case 32: _t->updateConveyorSpeedLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 33: _t->applyConveyorSpeed(); break;
        case 34: _t->startConveyorForward(); break;
        case 35: _t->startConveyorReverse(); break;
        case 36: _t->stopConveyor(); break;
        case 37: _t->updateLedBrightnessLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 38: _t->updateLedThresholdLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 39: _t->applyLedBrightness(); break;
        case 40: _t->turnLedOff(); break;
        case 41: _t->toggleLedAutoMode(); break;
        case 42: _t->updateLedAutoControl(); break;
        case 43: _t->updateFanTemperatureThresholdLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 44: _t->updateFanHumidityThresholdLabel((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 45: _t->applyFanThresholds(); break;
        case 46: _t->turnFanOn(); break;
        case 47: _t->turnFanOff(); break;
        case 48: _t->toggleFanAutoMode(); break;
        case 49: _t->updateFanAutoControl(); break;
        case 50: _t->toggleAutoSort(); break;
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
        if (_id < 51)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 51;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 51)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 51;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE

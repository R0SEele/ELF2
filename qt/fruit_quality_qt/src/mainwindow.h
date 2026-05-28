#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include "sensordatareader.h"

#include <QFrame>
#include <QGridLayout>
#include <QLabel>
#include <QMainWindow>
#include <QPixmap>
#include <QProcess>
#include <QPushButton>
#include <QSlider>
#include <QStackedWidget>
#include <QTimer>
#include <QVector>

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

public slots:
    void shutdownHardware();

private slots:
    void showWorkPage();
    void showStartPage();
    void showFunctionHomePage();
    void showConveyorControlPage();
    void showLedControlPage();
    void refreshSensorData();
    void readSensorMessages();
    void handleSensorFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void readCameraFrames();
    void readCameraMessages();
    void handleCameraFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void updateConveyorSpeedLabel(int value);
    void applyConveyorSpeed();
    void startConveyorForward();
    void startConveyorReverse();
    void stopConveyor();
    void updateLedBrightnessLabel(int value);
    void updateLedThresholdLabel(int value);
    void applyLedBrightness();
    void turnLedOff();
    void toggleLedAutoMode();
    void updateLedAutoControl();

private:
    bool eventFilter(QObject *watched, QEvent *event) override;
    QWidget *createStartPage();
    QWidget *createWorkPage();
    QFrame *createVideoPanel();
    QFrame *createSensorPanel();
    QFrame *createFunctionPlaceholder();
    QWidget *createFunctionHomePage();
    QWidget *createConveyorControlPage();
    QWidget *createLedControlPage();
    QLabel *makeSensorNameLabel(const QString &text);
    QLabel *makeSensorValueLabel();
    void applyGlobalStyle();
    void updateSensorCards(const SensorSnapshot &snapshot);
    void startSensorProcess();
    void stopSensorProcess();
    void startCameraProcess();
    void stopCameraProcess();
    void processCameraBuffer();
    void showCameraFrame(const QByteArray &jpegData);
    void rescaleCameraFrame();
    void setVideoMessage(const QString &message);
    double currentConveyorSpeed() const;
    void runMotorCommand(const QString &command);
    QStringList parseCsvLine(const QString &line) const;
    int readLatestLightLux() const;
    void runLedCommand(int brightnessPct);

    QStackedWidget *m_pages;
    QStackedWidget *m_functionPages;
    QLabel *m_videoStateLabel;
    QLabel *m_sensorStatusLabel;
    QGridLayout *m_sensorGrid;
    QVector<QLabel *> m_sensorNameLabels;
    QVector<QLabel *> m_sensorValueLabels;
    QTimer *m_sensorTimer;
    QProcess *m_sensorProcess;
    QProcess *m_cameraProcess;
    QByteArray m_cameraBuffer;
    QPixmap m_latestFrame;
    SensorDataReader m_sensorReader;
    QSlider *m_conveyorSpeedSlider;
    QLabel *m_conveyorSpeedValueLabel;
    QLabel *m_motorStatusLabel;
    QSlider *m_ledBrightnessSlider;
    QSlider *m_ledThresholdSlider;
    QLabel *m_ledBrightnessValueLabel;
    QLabel *m_ledThresholdValueLabel;
    QLabel *m_ledStatusLabel;
    QPushButton *m_ledAutoButton;
    QTimer *m_ledAutoTimer;
    int m_conveyorDirection;
    int m_ledCurrentBrightness;
    bool m_ledAutoEnabled;
    bool m_ledWasStarted;
    bool m_conveyorWasStarted;
    bool m_shutdownDone;
};

#endif // MAINWINDOW_H

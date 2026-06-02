#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include "sensordatareader.h"

#include <QFrame>
#include <QGridLayout>
#include <QLabel>
#include <QMainWindow>
#include <QPaintEvent>
#include <QPixmap>
#include <QProcess>
#include <QPushButton>
#include <QResizeEvent>
#include <QSlider>
#include <QStackedWidget>
#include <QTimer>
#include <QVector>
#include <QWidget>

class VideoDisplayWidget : public QWidget
{
public:
    explicit VideoDisplayWidget(QWidget *parent = nullptr);

    void setFrame(const QPixmap &frame);
    void setMessage(const QString &message);
    void clearFrame();

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QPixmap m_frame;
    QString m_message;
};

class AspectRatioVideoFrame : public QFrame
{
public:
    explicit AspectRatioVideoFrame(QWidget *parent = nullptr);

    void setContentWidget(QWidget *content);
    void setAspectRatioFromSize(const QSize &size);

protected:
    void resizeEvent(QResizeEvent *event) override;

private:
    void updateContentGeometry();

    QWidget *m_content;
    double m_aspectRatio;
};

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
    void showMangoQualityPage();
    void showServoControlPage();
    void refreshSensorData();
    void refreshMangoQualityData();
    void readSensorMessages();
    void handleSensorFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void readMangoQualityMessages();
    void handleMangoQualityFinished(int exitCode, QProcess::ExitStatus exitStatus);
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
    void moveServoToPosition1();
    void moveServoToPosition2();
    void moveServoToPosition3();

private:
    QWidget *createStartPage();
    QWidget *createWorkPage();
    QFrame *createVideoPanel();
    QFrame *createSensorPanel();
    QFrame *createFunctionPlaceholder();
    QWidget *createFunctionHomePage();
    QWidget *createConveyorControlPage();
    QWidget *createLedControlPage();
    QWidget *createMangoQualityPage();
    QWidget *createServoControlPage();
    QLabel *makeSensorNameLabel(const QString &text);
    QLabel *makeSensorValueLabel();
    void applyGlobalStyle();
    void updateSensorCards(const SensorSnapshot &snapshot);
    void startSensorProcess();
    void stopSensorProcess();
    void startMangoQualityProcess();
    void stopMangoQualityProcess();
    void startCameraProcess();
    void stopCameraProcess();
    void processCameraBuffer();
    void showCameraFrame(const QByteArray &jpegData);
    void rescaleCameraFrame();
    void setVideoMessage(const QString &message);
    double currentConveyorSpeed() const;
    void runMotorCommand(const QString &command);
    void loadConveyorSpeedRange();
    QStringList parseCsvLine(const QString &line) const;
    int readLatestLightLux() const;
    void runLedCommand(int brightnessPct);
    void runServoCommand(const QString &position, const QString &label);

    QStackedWidget *m_pages;
    QStackedWidget *m_functionPages;
    QFrame *m_videoPanel;
    AspectRatioVideoFrame *m_videoSurface;
    VideoDisplayWidget *m_videoDisplay;
    QLabel *m_sensorStatusLabel;
    QGridLayout *m_sensorGrid;
    QVector<QLabel *> m_sensorNameLabels;
    QVector<QLabel *> m_sensorValueLabels;
    QTimer *m_sensorTimer;
    QProcess *m_sensorProcess;
    QTimer *m_mangoQualityTimer;
    QProcess *m_mangoQualityProcess;
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
    QLabel *m_mangoMaturityValueLabel;
    QLabel *m_mangoSugarValueLabel;
    QLabel *m_mangoRotValueLabel;
    QLabel *m_mangoFinalValueLabel;
    QLabel *m_mangoYoloValueLabel;
    QLabel *m_mangoDataValueLabel;
    QLabel *m_mangoQualityStatusLabel;
    QLabel *m_mangoReasonLabel;
    QLabel *m_servoStatusLabel;
    int m_conveyorDirection;
    int m_conveyorMinSpeedX10;
    int m_conveyorMaxSpeedX10;
    int m_conveyorDefaultSpeedX10;
    int m_ledCurrentBrightness;
    bool m_ledAutoEnabled;
    bool m_ledWasStarted;
    bool m_conveyorWasStarted;
    bool m_shutdownDone;
};

#endif // MAINWINDOW_H

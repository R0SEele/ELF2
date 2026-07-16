#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include "environmenttrendchart.h"
#include "sensordatareader.h"

#include <QColor>
#include <QFrame>
#include <QGridLayout>
#include <QLabel>
#include <QList>
#include <QMainWindow>
#include <QPaintEvent>
#include <QPixmap>
#include <QProcess>
#include <QPushButton>
#include <QJsonObject>
#include <QResizeEvent>
#include <QSlider>
#include <QStackedWidget>
#include <QTableWidget>
#include <QTimer>
#include <QVector>
#include <QWidget>

class QNetworkAccessManager;
class QNetworkReply;

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

class DonutChartWidget : public QWidget
{
public:
    explicit DonutChartWidget(QWidget *parent = nullptr);

    void setData(const QVector<double> &values, const QStringList &labels, const QVector<QColor> &colors);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QVector<double> m_values;
    QStringList m_labels;
    QVector<QColor> m_colors;
};

class BarChartWidget : public QWidget
{
public:
    explicit BarChartWidget(QWidget *parent = nullptr);

    void setData(const QVector<double> &values, const QStringList &labels, const QVector<QColor> &colors);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QVector<double> m_values;
    QStringList m_labels;
    QVector<QColor> m_colors;
};

class QualityScoreWidget : public QWidget
{
public:
    explicit QualityScoreWidget(QWidget *parent = nullptr);

    void setScore(double score, const QString &status, const QColor &color);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    double m_score;
    QString m_status;
    QColor m_color;
};

class QualityFactorWidget : public QWidget
{
public:
    explicit QualityFactorWidget(QWidget *parent = nullptr);

    void setData(const QStringList &labels, const QVector<double> &values, const QStringList &details, const QVector<QColor> &colors);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QStringList m_labels;
    QVector<double> m_values;
    QStringList m_details;
    QVector<QColor> m_colors;
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
    void showBatchStatsPage();
    void showEnvironmentTrendPage();
    void showMangoHistoryPage();
    void showVoicePromptPage();
    void refreshSensorData();
    void refreshMangoQualityData();
    void refreshBatchStatsData();
    void refreshEnvironmentTrendData();
    void refreshMangoHistoryData();
    void readSensorMessages();
    void handleSensorFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void readMangoQualityMessages();
    void handleMangoQualityFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void announcePreviousMango();
    void announceBatchMango();
    void readVoicePromptMessages();
    void handleVoicePromptFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void readCameraFrames();
    void readCameraMessages();
    void handleCameraFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void updateIotStatus();
    void readTuyaIotMessages();
    void handleTuyaIotFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void syncExternalControlState();
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
    QWidget *createMangoHistoryPage();
    QFrame *createVideoPanel();
    QFrame *createSensorPanel();
    QFrame *createFunctionPlaceholder();
    QWidget *createFunctionHomePage();
    QWidget *createConveyorControlPage();
    QWidget *createLedControlPage();
    QWidget *createMangoQualityPage();
    QWidget *createServoControlPage();
    QWidget *createBatchStatsPage();
    QWidget *createEnvironmentTrendPage();
    QWidget *createVoicePromptPage();
    QLabel *makeSensorNameLabel(const QString &text);
    QLabel *makeSensorValueLabel();
    QFrame *makeMetricCard(const QString &name, QLabel **valueLabel, const QString &accentName = QString());
    QFrame *makeFunctionSection(const QString &title, const QList<QPushButton *> &buttons);
    QFrame *makeFunctionGridSection(const QString &title, const QList<QPushButton *> &buttons, int columns);
    void applyGlobalStyle();
    void updateSensorCards(const SensorSnapshot &snapshot);
    void selectEnvironmentMetric(int index);
    void selectEnvironmentRange(int minutes);
    void startSensorProcess();
    void stopSensorProcess();
    void startMangoQualityProcess();
    void stopMangoQualityProcess();
    void startCameraProcess();
    void stopCameraProcess();
    void startTuyaIotProcess();
    void stopTuyaIotProcess();
    bool isTuyaIotProcessRunning() const;
    void setIotStatusText(const QString &text, const QString &state);
    void initializeExternalControlState();
    QJsonObject readExternalControlState() const;
    void processCameraBuffer();
    void showCameraFrame(const QByteArray &jpegData);
    void rescaleCameraFrame();
    void setVideoMessage(const QString &message);
    double currentConveyorSpeed() const;
    QString currentConveyorGearName() const;
    void selectConveyorSpeedGear(int gear);
    void updateConveyorGearButtons();
    void updateConveyorRunButtons();
    void runMotorCommand(const QString &command);
    void loadConveyorSpeedRange();
    QStringList parseCsvLine(const QString &line) const;
    int readLatestLightLux() const;
    void runLedCommand(int brightnessPct);
    void runServoCommand(const QString &position, const QString &label);
    void runVoicePromptCommand(const QString &target, const QString &label);

    QStackedWidget *m_pages;
    QStackedWidget *m_functionPages;
    QWidget *m_environmentTrendPage;
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
    QProcess *m_voicePromptProcess;
    QProcess *m_cameraProcess;
    QProcess *m_motorCommandProcess;
    QProcess *m_servoCommandProcess;
    QTimer *m_servoCommandTimer;
    QProcess *m_tuyaIotProcess;
    QTimer *m_iotStatusTimer;
    QTimer *m_controlStateTimer;
    QNetworkAccessManager *m_iotNetworkManager;
    QNetworkReply *m_iotNetworkReply;
    QLabel *m_networkStatusLabel;
    QByteArray m_cameraBuffer;
    QPixmap m_latestFrame;
    QString m_lastDetectRequestId;
    QString m_lastDetectCommand;
    qint64 m_lastDetectCommandAtMs;
    SensorDataReader m_sensorReader;
    QSlider *m_conveyorSpeedSlider;
    QLabel *m_conveyorSpeedValueLabel;
    QLabel *m_motorStatusLabel;
    QPushButton *m_conveyorForwardButton;
    QPushButton *m_conveyorReverseButton;
    QPushButton *m_conveyorStopButton;
    QPushButton *m_conveyorSlowButton;
    QPushButton *m_conveyorMediumButton;
    QPushButton *m_conveyorFastButton;
    QSlider *m_ledBrightnessSlider;
    QSlider *m_ledThresholdSlider;
    QLabel *m_ledBrightnessValueLabel;
    QLabel *m_ledThresholdValueLabel;
    QLabel *m_ledStatusLabel;
    QPushButton *m_ledAutoButton;
    QTimer *m_ledAutoTimer;
    double m_ledFilteredLux;
    bool m_ledHasFilteredLux;
    qint64 m_ledLastAutoAdjustMs;
    QLabel *m_mangoMaturityValueLabel;
    QLabel *m_mangoSugarValueLabel;
    QLabel *m_mangoRotValueLabel;
    QLabel *m_mangoFinalValueLabel;
    QLabel *m_mangoIdValueLabel;
    QLabel *m_mangoGradeValueLabel;
    QLabel *m_mangoChannelValueLabel;
    QLabel *m_mangoStabilityValueLabel;
    QLabel *m_mangoYoloValueLabel;
    QLabel *m_mangoDataValueLabel;
    QLabel *m_mangoQualityStatusLabel;
    QLabel *m_mangoReasonLabel;
    QualityScoreWidget *m_mangoScoreChart;
    QualityFactorWidget *m_mangoFactorChart;
    QLabel *m_batchTotalValueLabel;
    QLabel *m_batchSaleableValueLabel;
    QLabel *m_batchRejectValueLabel;
    QLabel *m_batchLatestValueLabel;
    QLabel *m_batchStatusLabel;
    QLabel *m_batchSummaryLabel;
    DonutChartWidget *m_batchMaturityChart;
    BarChartWidget *m_batchGradeChart;
    BarChartWidget *m_batchChannelChart;
    EnvironmentTrendChartWidget *m_environmentTrendChart;
    QLabel *m_environmentCurrentValueLabel;
    QLabel *m_environmentMinValueLabel;
    QLabel *m_environmentMaxValueLabel;
    QLabel *m_environmentTrendStatusLabel;
    QVector<QPushButton *> m_environmentMetricButtons;
    QVector<QPushButton *> m_environmentRangeButtons;
    int m_environmentMetricIndex;
    int m_environmentRangeMinutes;
    QTableWidget *m_historyTable;
    QLabel *m_historySummaryLabel;
    QLabel *m_voicePromptStatusLabel;
    QPushButton *m_voicePreviousButton;
    QPushButton *m_voiceBatchButton;
    QLabel *m_servoStatusLabel;
    QPushButton *m_servoPosition1Button;
    QPushButton *m_servoPosition2Button;
    QPushButton *m_servoPosition3Button;
    QString m_servoCommandLabel;
    bool m_servoCommandTimedOut;
    int m_conveyorDirection;
    int m_conveyorMinSpeedX10;
    int m_conveyorMaxSpeedX10;
    int m_conveyorDefaultSpeedX10;
    int m_conveyorSpeedGear;
    double m_conveyorSlowSpeedMs;
    double m_conveyorMediumSpeedMs;
    double m_conveyorFastSpeedMs;
    int m_ledCurrentBrightness;
    bool m_ledAutoEnabled;
    bool m_ledWasStarted;
    bool m_conveyorWasStarted;
    bool m_tuyaIotStartedByQt;
    bool m_shutdownDone;
};

#endif // MAINWINDOW_H

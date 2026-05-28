#include "mainwindow.h"

#include <QApplication>
#include <QCoreApplication>
#include <QDateTime>
#include <QFile>
#include <QEvent>
#include <QHBoxLayout>
#include <QPixmap>
#include <QSizePolicy>
#include <QSpacerItem>
#include <QTextStream>
#include <QVBoxLayout>

namespace {
const char *kSensorCsvDirectory = "/home/elf/projects/datas/csv";
const char *kSensorCsvScript = "/home/elf/projects/src/hardware/sensors/csv_logger.py";
const char *kCameraScript = "/home/elf/projects/deeplearning/yolo11_demo/camera_detect.py";
const char *kMotorCommandScript = "/home/elf/projects/src/hardware/motor/conveyor_cli.py";
const char *kLedCommandScript = "/home/elf/projects/src/hardware/led/ws2812b.py";
const char *kSensorCsvFile = "/home/elf/projects/datas/csv/sensor_realtime.csv";
const int kSensorCardCount = 6;
const int kFrameHeaderSize = 4;
const int kMaxFrameBytes = 20 * 1024 * 1024;
const int kConveyorMinSpeedX10 = 1;
const int kConveyorMaxSpeedX10 = 5;

QString defaultSensorName(int index)
{
    static const QStringList names = {
        "温度",
        "湿度",
        "二氧化碳",
        "光照",
        "空气质量",
        "环境状态"
    };

    if (index >= 0 && index < names.size()) {
        return names.at(index);
    }

    return QString("数据 %1").arg(index + 1);
}
}

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent),
      m_pages(new QStackedWidget(this)),
      m_functionPages(nullptr),
      m_videoStateLabel(nullptr),
      m_sensorStatusLabel(nullptr),
      m_sensorGrid(nullptr),
      m_sensorTimer(new QTimer(this)),
      m_sensorProcess(new QProcess(this)),
      m_cameraProcess(new QProcess(this)),
      m_sensorReader(kSensorCsvFile),
      m_conveyorSpeedSlider(nullptr),
      m_conveyorSpeedValueLabel(nullptr),
      m_motorStatusLabel(nullptr),
      m_ledBrightnessSlider(nullptr),
      m_ledThresholdSlider(nullptr),
      m_ledBrightnessValueLabel(nullptr),
      m_ledThresholdValueLabel(nullptr),
      m_ledStatusLabel(nullptr),
      m_ledAutoButton(nullptr),
      m_ledAutoTimer(new QTimer(this)),
      m_conveyorDirection(0),
      m_ledCurrentBrightness(40),
      m_ledAutoEnabled(false),
      m_ledWasStarted(false),
      m_conveyorWasStarted(false),
      m_shutdownDone(false)
{
    setWindowTitle("水果端侧AI视觉质检系统");
    setCentralWidget(m_pages);
    applyGlobalStyle();

    m_pages->addWidget(createStartPage());
    m_pages->addWidget(createWorkPage());
    m_pages->setCurrentIndex(0);

    connect(m_sensorTimer, &QTimer::timeout, this, &MainWindow::refreshSensorData);
    m_sensorTimer->setInterval(1000);

    connect(m_sensorProcess, &QProcess::readyReadStandardError, this, &MainWindow::readSensorMessages);
    connect(m_sensorProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleSensorFinished);

    connect(m_cameraProcess, &QProcess::readyReadStandardOutput, this, &MainWindow::readCameraFrames);
    connect(m_cameraProcess, &QProcess::readyReadStandardError, this, &MainWindow::readCameraMessages);
    connect(m_cameraProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleCameraFinished);

    connect(m_ledAutoTimer, &QTimer::timeout, this, &MainWindow::updateLedAutoControl);
    m_ledAutoTimer->setInterval(1000);
}

MainWindow::~MainWindow()
{
    shutdownHardware();
}

void MainWindow::shutdownHardware()
{
    if (m_shutdownDone) {
        return;
    }

    m_shutdownDone = true;
    m_ledAutoTimer->stop();
    if (m_ledWasStarted) {
        turnLedOff();
    }
    stopConveyor();
    stopSensorProcess();
    stopCameraProcess();
}

void MainWindow::showWorkPage()
{
    m_pages->setCurrentIndex(1);
    startSensorProcess();
    refreshSensorData();
    if (!m_sensorTimer->isActive()) {
        m_sensorTimer->start();
    }
    startCameraProcess();
}

void MainWindow::showStartPage()
{
    shutdownHardware();
    m_sensorTimer->stop();
    m_pages->setCurrentIndex(0);
    m_shutdownDone = false;
}

void MainWindow::showFunctionHomePage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(0);
    }
}

void MainWindow::showConveyorControlPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(1);
    }
}

void MainWindow::showLedControlPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(2);
    }
}

void MainWindow::refreshSensorData()
{
    updateSensorCards(m_sensorReader.readLatest());
}

void MainWindow::readSensorMessages()
{
    m_sensorProcess->readAllStandardError();
    if (m_sensorStatusLabel) {
        m_sensorStatusLabel->setText("仅环境数据");
    }
}

void MainWindow::handleSensorFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    if (m_pages->currentIndex() != 1 || !m_sensorStatusLabel) {
        return;
    }

    if (exitStatus == QProcess::CrashExit) {
        m_sensorStatusLabel->setText("环境数据");
    } else if (exitCode != 0) {
        m_sensorStatusLabel->setText("环境数据");
    }
}

void MainWindow::readCameraFrames()
{
    m_cameraBuffer.append(m_cameraProcess->readAllStandardOutput());
    processCameraBuffer();
}

void MainWindow::readCameraMessages()
{
    const QString message = QString::fromLocal8Bit(m_cameraProcess->readAllStandardError()).trimmed();
    if (!message.isEmpty() && m_latestFrame.isNull()) {
        setVideoMessage("检测程序启动中\n" + message.left(80));
    }
}

void MainWindow::handleCameraFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    if (m_pages->currentIndex() != 1) {
        return;
    }

    if (exitStatus == QProcess::CrashExit) {
        setVideoMessage("检测程序异常退出");
    } else if (exitCode != 0) {
        setVideoMessage(QString("检测程序已退出\n退出码：%1").arg(exitCode));
    } else {
        setVideoMessage("检测程序已停止");
    }
}

bool MainWindow::eventFilter(QObject *watched, QEvent *event)
{
    if (watched == m_videoStateLabel && event->type() == QEvent::Resize) {
        rescaleCameraFrame();
    }

    return QMainWindow::eventFilter(watched, event);
}

QWidget *MainWindow::createStartPage()
{
    QWidget *page = new QWidget;
    page->setObjectName("startPage");

    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(70, 54, 70, 54);
    layout->setSpacing(34);

    QLabel *title = new QLabel("水果端侧AI视觉质检系统");
    title->setObjectName("startTitle");
    title->setAlignment(Qt::AlignCenter);
    title->setWordWrap(true);

    QPushButton *startButton = new QPushButton("开始检测");
    startButton->setObjectName("startButton");
    startButton->setMinimumHeight(92);
    startButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(startButton, &QPushButton::clicked, this, &MainWindow::showWorkPage);

    layout->addStretch(2);
    layout->addWidget(title);
    layout->addSpacing(34);
    layout->addWidget(startButton);
    layout->addStretch(3);

    return page;
}

QWidget *MainWindow::createWorkPage()
{
    QWidget *page = new QWidget;
    page->setObjectName("workPage");

    QHBoxLayout *rootLayout = new QHBoxLayout(page);
    rootLayout->setContentsMargins(12, 10, 12, 10);
    rootLayout->setSpacing(12);

    QVBoxLayout *leftLayout = new QVBoxLayout;
    leftLayout->setSpacing(12);
    leftLayout->addWidget(createVideoPanel(), 5);
    leftLayout->addWidget(createSensorPanel(), 2);

    rootLayout->addLayout(leftLayout, 6);
    rootLayout->addWidget(createFunctionPlaceholder(), 3);

    return page;
}

QFrame *MainWindow::createVideoPanel()
{
    QFrame *panel = new QFrame;
    panel->setObjectName("videoPanel");
    panel->setFrameShape(QFrame::NoFrame);

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(16, 12, 16, 16);
    layout->setSpacing(10);

    QLabel *title = new QLabel("检测视频实时画面");
    title->setObjectName("panelTitle");

    QFrame *videoSurface = new QFrame;
    videoSurface->setObjectName("videoSurface");
    videoSurface->setMinimumSize(460, 300);
    videoSurface->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    QVBoxLayout *surfaceLayout = new QVBoxLayout(videoSurface);
    surfaceLayout->setContentsMargins(10, 10, 10, 10);

    m_videoStateLabel = new QLabel("视频画面\n等待接入检测程序");
    m_videoStateLabel->setObjectName("videoState");
    m_videoStateLabel->setAlignment(Qt::AlignCenter);
    m_videoStateLabel->setWordWrap(true);
    m_videoStateLabel->setScaledContents(false);
    m_videoStateLabel->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    m_videoStateLabel->installEventFilter(this);
    surfaceLayout->addWidget(m_videoStateLabel);

    layout->addWidget(title);
    layout->addWidget(videoSurface, 1);

    return panel;
}

QFrame *MainWindow::createSensorPanel()
{
    QFrame *panel = new QFrame;
    panel->setObjectName("sensorPanel");

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(16, 10, 16, 12);
    layout->setSpacing(8);

    QHBoxLayout *header = new QHBoxLayout;
    QLabel *title = new QLabel("环境实时数据");
    title->setObjectName("panelTitle");
    m_sensorStatusLabel = new QLabel("仅环境数据");
    m_sensorStatusLabel->setObjectName("sensorStatus");
    m_sensorStatusLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    header->addWidget(title);
    header->addWidget(m_sensorStatusLabel, 1);

    m_sensorGrid = new QGridLayout;
    m_sensorGrid->setContentsMargins(0, 0, 0, 0);
    m_sensorGrid->setHorizontalSpacing(10);
    m_sensorGrid->setVerticalSpacing(8);

    for (int i = 0; i < kSensorCardCount; ++i) {
        QFrame *card = new QFrame;
        card->setObjectName("sensorCard");
        card->setMinimumHeight(64);

        QVBoxLayout *cardLayout = new QVBoxLayout(card);
        cardLayout->setContentsMargins(12, 6, 12, 6);
        cardLayout->setSpacing(2);

        QLabel *name = makeSensorNameLabel(defaultSensorName(i));
        QLabel *value = makeSensorValueLabel();
        cardLayout->addWidget(name);
        cardLayout->addWidget(value);

        m_sensorNameLabels.append(name);
        m_sensorValueLabels.append(value);
        m_sensorGrid->addWidget(card, i / 3, i % 3);
    }

    layout->addLayout(header);
    layout->addLayout(m_sensorGrid, 1);

    return panel;
}

QFrame *MainWindow::createFunctionPlaceholder()
{
    QFrame *panel = new QFrame;
    panel->setObjectName("functionPanel");

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(16, 14, 16, 14);
    layout->setSpacing(12);

    QLabel *title = new QLabel("功能控制");
    title->setObjectName("panelTitle");

    QPushButton *exitButton = new QPushButton("退出检测");
    exitButton->setObjectName("exitButton");
    exitButton->setMinimumHeight(76);
    connect(exitButton, &QPushButton::clicked, this, &MainWindow::showStartPage);

    m_functionPages = new QStackedWidget(panel);
    m_functionPages->addWidget(createFunctionHomePage());
    m_functionPages->addWidget(createConveyorControlPage());
    m_functionPages->addWidget(createLedControlPage());

    layout->addWidget(title);
    layout->addWidget(m_functionPages, 1);
    layout->addWidget(exitButton);

    return panel;
}

QWidget *MainWindow::createFunctionHomePage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(12);

    QPushButton *conveyorButton = new QPushButton("传送带调速控制");
    conveyorButton->setObjectName("featureButton");
    conveyorButton->setMinimumHeight(92);
    conveyorButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(conveyorButton, &QPushButton::clicked, this, &MainWindow::showConveyorControlPage);

    QPushButton *ledButton = new QPushButton("LED亮度控制");
    ledButton->setObjectName("featureButton");
    ledButton->setMinimumHeight(92);
    ledButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(ledButton, &QPushButton::clicked, this, &MainWindow::showLedControlPage);

    QLabel *placeholder = new QLabel("功能区");
    placeholder->setObjectName("functionPlaceholder");
    placeholder->setAlignment(Qt::AlignCenter);

    layout->addWidget(conveyorButton);
    layout->addWidget(ledButton);
    layout->addWidget(placeholder, 1);
    return page;
}

QWidget *MainWindow::createConveyorControlPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(12);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(46);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QLabel *title = new QLabel("传送带控制");
    title->setObjectName("controlTitle");
    title->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);

    QFrame *speedPanel = new QFrame;
    speedPanel->setObjectName("controlCard");
    QVBoxLayout *speedLayout = new QVBoxLayout(speedPanel);
    speedLayout->setContentsMargins(12, 10, 12, 12);
    speedLayout->setSpacing(8);

    QHBoxLayout *speedHeader = new QHBoxLayout;
    QLabel *speedName = new QLabel("速度");
    speedName->setObjectName("controlLabel");
    m_conveyorSpeedValueLabel = new QLabel;
    m_conveyorSpeedValueLabel->setObjectName("speedValue");
    m_conveyorSpeedValueLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    speedHeader->addWidget(speedName);
    speedHeader->addWidget(m_conveyorSpeedValueLabel, 1);

    m_conveyorSpeedSlider = new QSlider(Qt::Horizontal);
    m_conveyorSpeedSlider->setObjectName("speedSlider");
    m_conveyorSpeedSlider->setRange(kConveyorMinSpeedX10, kConveyorMaxSpeedX10);
    m_conveyorSpeedSlider->setSingleStep(1);
    m_conveyorSpeedSlider->setPageStep(1);
    m_conveyorSpeedSlider->setTickPosition(QSlider::TicksBelow);
    m_conveyorSpeedSlider->setTickInterval(1);
    m_conveyorSpeedSlider->setValue(3);
    connect(m_conveyorSpeedSlider, &QSlider::valueChanged, this, &MainWindow::updateConveyorSpeedLabel);
    connect(m_conveyorSpeedSlider, &QSlider::sliderReleased, this, &MainWindow::applyConveyorSpeed);

    speedLayout->addLayout(speedHeader);
    speedLayout->addWidget(m_conveyorSpeedSlider);

    QHBoxLayout *runLayout = new QHBoxLayout;
    runLayout->setSpacing(8);

    QPushButton *forwardButton = new QPushButton("正转");
    forwardButton->setObjectName("runButton");
    forwardButton->setMinimumHeight(74);
    connect(forwardButton, &QPushButton::clicked, this, &MainWindow::startConveyorForward);

    QPushButton *reverseButton = new QPushButton("反转");
    reverseButton->setObjectName("runButton");
    reverseButton->setMinimumHeight(74);
    connect(reverseButton, &QPushButton::clicked, this, &MainWindow::startConveyorReverse);

    QPushButton *stopButton = new QPushButton("停止");
    stopButton->setObjectName("stopButton");
    stopButton->setMinimumHeight(74);
    connect(stopButton, &QPushButton::clicked, this, &MainWindow::stopConveyor);

    runLayout->addWidget(forwardButton);
    runLayout->addWidget(reverseButton);
    runLayout->addWidget(stopButton);

    m_motorStatusLabel = new QLabel("状态：已停止");
    m_motorStatusLabel->setObjectName("motorStatus");
    m_motorStatusLabel->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    m_motorStatusLabel->setWordWrap(true);
    m_motorStatusLabel->setMinimumHeight(56);

    layout->addWidget(backButton);
    layout->addWidget(title);
    layout->addWidget(speedPanel);
    layout->addLayout(runLayout);
    layout->addWidget(m_motorStatusLabel);
    layout->addStretch(1);

    updateConveyorSpeedLabel(m_conveyorSpeedSlider->value());
    return page;
}

QWidget *MainWindow::createLedControlPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(12);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(46);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QLabel *title = new QLabel("LED亮度控制");
    title->setObjectName("controlTitle");

    QFrame *brightnessPanel = new QFrame;
    brightnessPanel->setObjectName("controlCard");
    QVBoxLayout *brightnessLayout = new QVBoxLayout(brightnessPanel);
    brightnessLayout->setContentsMargins(12, 10, 12, 12);
    brightnessLayout->setSpacing(8);

    QHBoxLayout *brightnessHeader = new QHBoxLayout;
    QLabel *brightnessName = new QLabel("亮度");
    brightnessName->setObjectName("controlLabel");
    m_ledBrightnessValueLabel = new QLabel;
    m_ledBrightnessValueLabel->setObjectName("speedValue");
    m_ledBrightnessValueLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    brightnessHeader->addWidget(brightnessName);
    brightnessHeader->addWidget(m_ledBrightnessValueLabel, 1);

    m_ledBrightnessSlider = new QSlider(Qt::Horizontal);
    m_ledBrightnessSlider->setObjectName("speedSlider");
    m_ledBrightnessSlider->setRange(0, 100);
    m_ledBrightnessSlider->setSingleStep(5);
    m_ledBrightnessSlider->setPageStep(10);
    m_ledBrightnessSlider->setTickPosition(QSlider::TicksBelow);
    m_ledBrightnessSlider->setTickInterval(20);
    m_ledBrightnessSlider->setValue(m_ledCurrentBrightness);
    connect(m_ledBrightnessSlider, &QSlider::valueChanged, this, &MainWindow::updateLedBrightnessLabel);
    connect(m_ledBrightnessSlider, &QSlider::sliderReleased, this, &MainWindow::applyLedBrightness);

    brightnessLayout->addLayout(brightnessHeader);
    brightnessLayout->addWidget(m_ledBrightnessSlider);

    QFrame *thresholdPanel = new QFrame;
    thresholdPanel->setObjectName("controlCard");
    QVBoxLayout *thresholdLayout = new QVBoxLayout(thresholdPanel);
    thresholdLayout->setContentsMargins(12, 10, 12, 12);
    thresholdLayout->setSpacing(8);

    QHBoxLayout *thresholdHeader = new QHBoxLayout;
    QLabel *thresholdName = new QLabel("光照阈值");
    thresholdName->setObjectName("controlLabel");
    m_ledThresholdValueLabel = new QLabel;
    m_ledThresholdValueLabel->setObjectName("speedValue");
    m_ledThresholdValueLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    thresholdHeader->addWidget(thresholdName);
    thresholdHeader->addWidget(m_ledThresholdValueLabel, 1);

    m_ledThresholdSlider = new QSlider(Qt::Horizontal);
    m_ledThresholdSlider->setObjectName("speedSlider");
    m_ledThresholdSlider->setRange(0, 2000);
    m_ledThresholdSlider->setSingleStep(50);
    m_ledThresholdSlider->setPageStep(100);
    m_ledThresholdSlider->setTickPosition(QSlider::TicksBelow);
    m_ledThresholdSlider->setTickInterval(500);
    m_ledThresholdSlider->setValue(500);
    connect(m_ledThresholdSlider, &QSlider::valueChanged, this, &MainWindow::updateLedThresholdLabel);

    thresholdLayout->addLayout(thresholdHeader);
    thresholdLayout->addWidget(m_ledThresholdSlider);

    QHBoxLayout *buttonLayout = new QHBoxLayout;
    buttonLayout->setSpacing(8);

    QPushButton *applyButton = new QPushButton("应用");
    applyButton->setObjectName("runButton");
    applyButton->setMinimumHeight(64);
    connect(applyButton, &QPushButton::clicked, this, &MainWindow::applyLedBrightness);

    QPushButton *offButton = new QPushButton("关闭");
    offButton->setObjectName("stopButton");
    offButton->setMinimumHeight(64);
    connect(offButton, &QPushButton::clicked, this, &MainWindow::turnLedOff);

    m_ledAutoButton = new QPushButton("自动调节：关");
    m_ledAutoButton->setObjectName("runButton");
    m_ledAutoButton->setMinimumHeight(64);
    connect(m_ledAutoButton, &QPushButton::clicked, this, &MainWindow::toggleLedAutoMode);

    buttonLayout->addWidget(applyButton);
    buttonLayout->addWidget(offButton);
    buttonLayout->addWidget(m_ledAutoButton);

    m_ledStatusLabel = new QLabel("状态：等待设置");
    m_ledStatusLabel->setObjectName("motorStatus");
    m_ledStatusLabel->setWordWrap(true);
    m_ledStatusLabel->setMinimumHeight(58);

    layout->addWidget(backButton);
    layout->addWidget(title);
    layout->addWidget(brightnessPanel);
    layout->addWidget(thresholdPanel);
    layout->addLayout(buttonLayout);
    layout->addWidget(m_ledStatusLabel);
    layout->addStretch(1);

    updateLedBrightnessLabel(m_ledBrightnessSlider->value());
    updateLedThresholdLabel(m_ledThresholdSlider->value());
    return page;
}

QLabel *MainWindow::makeSensorNameLabel(const QString &text)
{
    QLabel *label = new QLabel(text);
    label->setObjectName("sensorName");
    label->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    return label;
}

QLabel *MainWindow::makeSensorValueLabel()
{
    QLabel *label = new QLabel("--");
    label->setObjectName("sensorValue");
    label->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    label->setMinimumHeight(32);
    return label;
}

void MainWindow::applyGlobalStyle()
{
    qApp->setStyleSheet(
        "QMainWindow, QWidget#startPage, QWidget#workPage {"
        "  background: #eaf8df;"
        "  color: #173d24;"
        "}"
        "QLabel {"
        "  color: #173d24;"
        "}"
        "QLabel#startTitle {"
        "  font-size: 44px;"
        "  font-weight: 700;"
        "}"
        "QPushButton#startButton {"
        "  background: #5fb66a;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 32px;"
        "  font-weight: 700;"
        "  padding: 18px;"
        "}"
        "QPushButton#startButton:pressed {"
        "  background: #4a9b55;"
        "}"
        "QPushButton#exitButton {"
        "  background: #ffffff;"
        "  color: #1f5a31;"
        "  border: 2px solid #72bd78;"
        "  border-radius: 8px;"
        "  font-size: 26px;"
        "  font-weight: 700;"
        "  padding: 14px;"
        "}"
        "QPushButton#exitButton:pressed {"
        "  background: #d7f0cc;"
        "}"
        "QPushButton#featureButton {"
        "  background: #5fb66a;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "  padding: 14px;"
        "}"
        "QPushButton#featureButton:pressed {"
        "  background: #4a9b55;"
        "}"
        "QPushButton#secondaryButton {"
        "  background: #edf8e8;"
        "  color: #1f5a31;"
        "  border: 1px solid #9ed49b;"
        "  border-radius: 7px;"
        "  font-size: 18px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#runButton {"
        "  background: #ffffff;"
        "  color: #1f5a31;"
        "  border: 2px solid #68b870;"
        "  border-radius: 8px;"
        "  font-size: 22px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#runButton:pressed {"
        "  background: #d7f0cc;"
        "}"
        "QPushButton#stopButton {"
        "  background: #d9534f;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 22px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#stopButton:pressed {"
        "  background: #b8403c;"
        "}"
        "QFrame#videoPanel, QFrame#sensorPanel, QFrame#functionPanel {"
        "  background: #f7fff2;"
        "  border: 2px solid #9ed49b;"
        "  border-radius: 8px;"
        "}"
        "QLabel#panelTitle {"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "  color: #1f5a31;"
        "}"
        "QFrame#videoSurface {"
        "  background: #142418;"
        "  border: 3px solid #72bd78;"
        "  border-radius: 6px;"
        "}"
        "QLabel#videoState {"
        "  color: #d7f5cf;"
        "  font-size: 28px;"
        "  font-weight: 700;"
        "}"
        "QLabel#sensorStatus {"
        "  color: #4b7654;"
        "  font-size: 16px;"
        "}"
        "QFrame#sensorCard {"
        "  background: #e2f4d5;"
        "  border: 1px solid #95cb90;"
        "  border-radius: 7px;"
        "}"
        "QLabel#sensorName {"
        "  font-size: 18px;"
        "  color: #46734d;"
        "}"
        "QLabel#sensorValue {"
        "  font-size: 26px;"
        "  font-weight: 700;"
        "  color: #123f20;"
        "}"
        "QLabel#functionPlaceholder {"
        "  background: #e2f4d5;"
        "  border: 1px dashed #8bc084;"
        "  border-radius: 7px;"
        "  color: #4a7653;"
        "  font-size: 24px;"
        "  line-height: 150%;"
        "}"
        "QLabel#controlTitle {"
        "  color: #1f5a31;"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "}"
        "QFrame#controlCard {"
        "  background: #e2f4d5;"
        "  border: 1px solid #95cb90;"
        "  border-radius: 7px;"
        "}"
        "QLabel#controlLabel {"
        "  color: #46734d;"
        "  font-size: 18px;"
        "}"
        "QLabel#speedValue {"
        "  color: #123f20;"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "}"
        "QLabel#motorStatus {"
        "  color: #4b7654;"
        "  font-size: 18px;"
        "}"
        "QSlider#speedSlider::groove:horizontal {"
        "  height: 10px;"
        "  background: #c4e7b9;"
        "  border-radius: 5px;"
        "}"
        "QSlider#speedSlider::handle:horizontal {"
        "  width: 28px;"
        "  margin: -9px 0;"
        "  border-radius: 14px;"
        "  background: #4a9b55;"
        "}"
    );
}

void MainWindow::updateSensorCards(const SensorSnapshot &snapshot)
{
    for (int i = 0; i < m_sensorValueLabels.size(); ++i) {
        if (i < snapshot.values.size()) {
            const SensorValue item = snapshot.values.at(i);
            QString valueText = item.value;
            if (!item.unit.isEmpty() && !valueText.endsWith(item.unit)) {
                valueText += " " + item.unit;
            }

            m_sensorNameLabels.at(i)->setText(item.name);
            m_sensorValueLabels.at(i)->setText(valueText);
        } else {
            m_sensorNameLabels.at(i)->setText(defaultSensorName(i));
            m_sensorValueLabels.at(i)->setText("--");
        }
    }

    m_sensorStatusLabel->setText("仅环境数据");
}

void MainWindow::startSensorProcess()
{
    if (m_sensorProcess->state() != QProcess::NotRunning) {
        return;
    }

    QStringList args;
    args << kSensorCsvScript
         << "--output-dir" << kSensorCsvDirectory
         << "--parent-pid" << QString::number(QCoreApplication::applicationPid());

    m_sensorProcess->setWorkingDirectory("/home/elf/projects");
    m_sensorProcess->start("python3", args);

    if (!m_sensorProcess->waitForStarted(1000) && m_sensorStatusLabel) {
        m_sensorStatusLabel->setText("传感器采集程序启动失败");
    }
}

void MainWindow::stopSensorProcess()
{
    if (m_sensorProcess->state() == QProcess::NotRunning) {
        return;
    }

    m_sensorProcess->terminate();
    if (!m_sensorProcess->waitForFinished(1500)) {
        m_sensorProcess->kill();
        m_sensorProcess->waitForFinished(1000);
    }
}

void MainWindow::startCameraProcess()
{
    if (m_cameraProcess->state() != QProcess::NotRunning) {
        return;
    }

    m_cameraBuffer.clear();
    m_latestFrame = QPixmap();
    setVideoMessage("检测程序启动中...");

    QStringList args;
    args << kCameraScript
         << "--qt-stream"
         << "--parent-pid" << QString::number(QCoreApplication::applicationPid());

    m_cameraProcess->setWorkingDirectory("/home/elf/projects/deeplearning/yolo11_demo");
    m_cameraProcess->start("python3", args);

    if (!m_cameraProcess->waitForStarted(1000)) {
        setVideoMessage("检测程序启动失败\n请检查 python3 与摄像头配置");
    }
}

void MainWindow::stopCameraProcess()
{
    if (m_cameraProcess->state() == QProcess::NotRunning) {
        return;
    }

    m_cameraProcess->terminate();
    if (!m_cameraProcess->waitForFinished(1500)) {
        m_cameraProcess->kill();
        m_cameraProcess->waitForFinished(1000);
    }

    m_cameraBuffer.clear();
    m_latestFrame = QPixmap();
    setVideoMessage("视频画面\n等待接入检测程序");
}

void MainWindow::processCameraBuffer()
{
    while (m_cameraBuffer.size() >= kFrameHeaderSize) {
        const uchar b0 = static_cast<uchar>(m_cameraBuffer.at(0));
        const uchar b1 = static_cast<uchar>(m_cameraBuffer.at(1));
        const uchar b2 = static_cast<uchar>(m_cameraBuffer.at(2));
        const uchar b3 = static_cast<uchar>(m_cameraBuffer.at(3));
        const int frameSize = (static_cast<int>(b0) << 24)
                            | (static_cast<int>(b1) << 16)
                            | (static_cast<int>(b2) << 8)
                            | static_cast<int>(b3);

        if (frameSize <= 0 || frameSize > kMaxFrameBytes) {
            m_cameraBuffer.clear();
            setVideoMessage("视频数据格式错误");
            return;
        }

        if (m_cameraBuffer.size() < kFrameHeaderSize + frameSize) {
            return;
        }

        const QByteArray jpegData = m_cameraBuffer.mid(kFrameHeaderSize, frameSize);
        m_cameraBuffer.remove(0, kFrameHeaderSize + frameSize);
        showCameraFrame(jpegData);
    }
}

void MainWindow::showCameraFrame(const QByteArray &jpegData)
{
    QPixmap frame;
    if (!frame.loadFromData(jpegData, "JPG")) {
        return;
    }

    m_latestFrame = frame;
    rescaleCameraFrame();
}

void MainWindow::rescaleCameraFrame()
{
    if (!m_videoStateLabel || m_latestFrame.isNull()) {
        return;
    }

    const QSize targetSize = m_videoStateLabel->contentsRect().size();
    if (targetSize.isEmpty()) {
        return;
    }

    m_videoStateLabel->setText(QString());
    m_videoStateLabel->setPixmap(
        m_latestFrame.scaled(targetSize, Qt::KeepAspectRatio, Qt::SmoothTransformation)
    );
}

void MainWindow::setVideoMessage(const QString &message)
{
    if (!m_videoStateLabel) {
        return;
    }

    m_videoStateLabel->setPixmap(QPixmap());
    m_videoStateLabel->setText(message);
}

double MainWindow::currentConveyorSpeed() const
{
    if (!m_conveyorSpeedSlider) {
        return 0.3;
    }
    return static_cast<double>(m_conveyorSpeedSlider->value()) / 10.0;
}

void MainWindow::updateConveyorSpeedLabel(int value)
{
    if (m_conveyorSpeedValueLabel) {
        m_conveyorSpeedValueLabel->setText(QString("%1 m/s").arg(value / 10.0, 0, 'f', 1));
    }
}

void MainWindow::applyConveyorSpeed()
{
    if (m_conveyorDirection > 0) {
        startConveyorForward();
    } else if (m_conveyorDirection < 0) {
        startConveyorReverse();
    }
}

void MainWindow::startConveyorForward()
{
    m_conveyorDirection = 1;
    m_conveyorWasStarted = true;
    runMotorCommand("forward");
}

void MainWindow::startConveyorReverse()
{
    m_conveyorDirection = -1;
    m_conveyorWasStarted = true;
    runMotorCommand("reverse");
}

void MainWindow::stopConveyor()
{
    const bool shouldSendStop = m_conveyorWasStarted || m_conveyorDirection != 0;
    m_conveyorDirection = 0;
    m_conveyorWasStarted = false;
    if (shouldSendStop) {
        runMotorCommand("stop");
    } else if (m_motorStatusLabel) {
        m_motorStatusLabel->setText("状态：已停止");
    }
}

void MainWindow::runMotorCommand(const QString &command)
{
    QStringList args;
    args << kMotorCommandScript << command;
    if (command != "stop") {
        args << "--speed-ms" << QString::number(currentConveyorSpeed(), 'f', 1);
    }

    QProcess process;
    process.setWorkingDirectory("/home/elf/projects");
    process.start("python3", args);
    if (!process.waitForStarted(1000)) {
        if (m_motorStatusLabel) {
            m_motorStatusLabel->setText("状态：电机命令启动失败");
        }
        return;
    }

    process.waitForFinished(2000);
    const QString output = QString::fromLocal8Bit(process.readAllStandardOutput()).trimmed();
    const QString error = QString::fromLocal8Bit(process.readAllStandardError()).trimmed();

    if (process.state() != QProcess::NotRunning) {
        process.kill();
        process.waitForFinished(500);
    }

    if (!m_motorStatusLabel) {
        return;
    }

    if (process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0) {
        if (command == "forward") {
            m_motorStatusLabel->setText(QString("状态：正转 %1 m/s").arg(currentConveyorSpeed(), 0, 'f', 1));
        } else if (command == "reverse") {
            m_motorStatusLabel->setText(QString("状态：反转 %1 m/s").arg(currentConveyorSpeed(), 0, 'f', 1));
        } else {
            m_motorStatusLabel->setText("状态：已停止");
        }
    } else {
        const QString message = !error.isEmpty() ? error : output;
        m_motorStatusLabel->setText("状态：命令失败 " + message.left(80));
    }
}

QStringList MainWindow::parseCsvLine(const QString &line) const
{
    QStringList fields;
    QString field;
    bool inQuotes = false;

    for (int i = 0; i < line.size(); ++i) {
        const QChar ch = line.at(i);
        if (ch == '"') {
            if (inQuotes && i + 1 < line.size() && line.at(i + 1) == '"') {
                field.append('"');
                ++i;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (ch == ',' && !inQuotes) {
            fields.append(field);
            field.clear();
        } else {
            field.append(ch);
        }
    }

    fields.append(field);
    return fields;
}

void MainWindow::updateLedBrightnessLabel(int value)
{
    if (m_ledBrightnessValueLabel) {
        m_ledBrightnessValueLabel->setText(QString("%1%").arg(value));
    }
}

void MainWindow::updateLedThresholdLabel(int value)
{
    if (m_ledThresholdValueLabel) {
        m_ledThresholdValueLabel->setText(QString("%1 lx").arg(value));
    }
}

void MainWindow::applyLedBrightness()
{
    if (!m_ledBrightnessSlider) {
        return;
    }

    m_ledAutoEnabled = false;
    if (m_ledAutoTimer->isActive()) {
        m_ledAutoTimer->stop();
    }
    if (m_ledAutoButton) {
        m_ledAutoButton->setText("自动调节：关");
    }

    m_ledCurrentBrightness = m_ledBrightnessSlider->value();
    runLedCommand(m_ledCurrentBrightness);
}

void MainWindow::turnLedOff()
{
    m_ledAutoEnabled = false;
    if (m_ledAutoTimer->isActive()) {
        m_ledAutoTimer->stop();
    }
    if (m_ledAutoButton) {
        m_ledAutoButton->setText("自动调节：关");
    }
    m_ledCurrentBrightness = 0;
    m_ledWasStarted = false;
    if (m_ledBrightnessSlider) {
        m_ledBrightnessSlider->setValue(0);
    }
    runLedCommand(0);
}

void MainWindow::toggleLedAutoMode()
{
    m_ledAutoEnabled = !m_ledAutoEnabled;
    if (m_ledAutoButton) {
        m_ledAutoButton->setText(m_ledAutoEnabled ? "自动调节：开" : "自动调节：关");
    }

    if (m_ledAutoEnabled) {
        updateLedAutoControl();
        m_ledAutoTimer->start();
    } else {
        m_ledAutoTimer->stop();
    }
}

void MainWindow::updateLedAutoControl()
{
    if (!m_ledAutoEnabled || !m_ledThresholdSlider) {
        return;
    }

    const int lightLux = readLatestLightLux();
    if (lightLux < 0) {
        if (m_ledStatusLabel) {
            m_ledStatusLabel->setText("状态：未读取到光照数据");
        }
        return;
    }

    const int threshold = m_ledThresholdSlider->value();
    int nextBrightness = m_ledCurrentBrightness;
    const int error = threshold - lightLux;
    if (error > 80) {
        nextBrightness = qMin(100, nextBrightness + 5);
    } else if (error < -80) {
        nextBrightness = qMax(0, nextBrightness - 5);
    }

    if (nextBrightness != m_ledCurrentBrightness) {
        m_ledCurrentBrightness = nextBrightness;
        if (m_ledBrightnessSlider) {
            m_ledBrightnessSlider->setValue(nextBrightness);
        }
        runLedCommand(nextBrightness);
    } else if (m_ledStatusLabel) {
        m_ledStatusLabel->setText(QString("状态：自动调节中 光照 %1 lx 阈值 %2 lx 亮度 %3%")
                                  .arg(lightLux)
                                  .arg(threshold)
                                  .arg(m_ledCurrentBrightness));
    }
}

int MainWindow::readLatestLightLux() const
{
    QFile file(kSensorCsvFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return -1;
    }

    QTextStream stream(&file);
    stream.setCodec("UTF-8");
    QString headerLine;
    QString lastLine;
    while (!stream.atEnd()) {
        const QString line = stream.readLine().trimmed();
        if (line.isEmpty()) {
            continue;
        }
        if (headerLine.isEmpty()) {
            headerLine = line;
        } else {
            lastLine = line;
        }
    }

    if (headerLine.isEmpty() || lastLine.isEmpty()) {
        return -1;
    }

    const QStringList headers = parseCsvLine(headerLine);
    const QStringList fields = parseCsvLine(lastLine);
    const int index = headers.indexOf("light_lux");
    if (index < 0 || index >= fields.size()) {
        return -1;
    }

    bool ok = false;
    const double lux = fields.at(index).trimmed().toDouble(&ok);
    if (!ok) {
        return -1;
    }
    return static_cast<int>(lux);
}

void MainWindow::runLedCommand(int brightnessPct)
{
    if (brightnessPct > 0) {
        m_ledWasStarted = true;
    }

    QStringList args;
    if (brightnessPct <= 0) {
        args << kLedCommandScript << "off";
    } else {
        args << kLedCommandScript << "set" << "--brightness" << QString::number(brightnessPct);
    }

    QProcess process;
    process.setWorkingDirectory("/home/elf/projects");
    process.start("python3", args);
    if (!process.waitForStarted(1000)) {
        if (m_ledStatusLabel) {
            m_ledStatusLabel->setText("状态：LED命令启动失败");
        }
        return;
    }

    process.waitForFinished(3000);
    const QString output = QString::fromLocal8Bit(process.readAllStandardOutput()).trimmed();
    const QString error = QString::fromLocal8Bit(process.readAllStandardError()).trimmed();
    if (process.state() != QProcess::NotRunning) {
        process.kill();
        process.waitForFinished(500);
    }

    if (!m_ledStatusLabel) {
        return;
    }

    if (process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0) {
        m_ledStatusLabel->setText(QString("状态：白光亮度 %1%").arg(brightnessPct));
    } else {
        const QString message = !error.isEmpty() ? error : output;
        m_ledStatusLabel->setText("状态：LED命令失败 " + message.left(100));
    }
}

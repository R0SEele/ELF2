#include "mainwindow.h"

#include <QAbstractItemView>
#include <QApplication>
#include <QCoreApplication>
#include <QDateTime>
#include <QFile>
#include <QEvent>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLayout>
#include <QFileInfo>
#include <QImage>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPainter>
#include <QPixmap>
#include <QResizeEvent>
#include <QScrollArea>
#include <QSizePolicy>
#include <QSpacerItem>
#include <QStyle>
#include <QTextStream>
#include <QUrl>
#include <QVBoxLayout>
#include <QtGlobal>

#include <numeric>

namespace {
const char *kSensorCsvDirectory = "/home/elf/projects/datas/csv";
const char *kSensorCsvScript = "/home/elf/projects/src/hardware/sensors/csv_logger.py";
const char *kCameraScript = "/home/elf/projects/deeplearning/yolo11_demo/camera_detect.py";
const char *kMangoQualityScript = "/home/elf/projects/src/software/mango_quality/mango_quality_cli.py";
const char *kVoiceAssistantScript = "/home/elf/projects/src/software/voice_assistant/voice_assistant.py";
const char *kDefaultVoiceBackend = "edge-tts";
const char *kDefaultVoiceEdgeVoice = "zh-CN-XiaoxiaoNeural";
const char *kDefaultVoiceAlsaDevice = "plughw:2,0";
const char *kMotorCommandScript = "/home/elf/projects/src/hardware/motor/conveyor_cli.py";
const char *kLedCommandScript = "/home/elf/projects/src/hardware/led/ws2812b.py";
const char *kServoCommandScript = "/home/elf/projects/src/hardware/servo/sorter.py";
const char *kProjectTitle = "芒果端侧AI视觉质检与智能分拣系统";
const char *kLogoPath = "/home/elf/projects/logo.jpeg";
const char *kTuyaIotElf = "/home/elf/projects/iot/TuyaOpen/apps/tuya_cloud/fruit_quality_cloud/dist/fruit_quality_cloud_0.1.0/fruit_quality_cloud_0.1.0.elf";
const char *kTuyaIotWorkDir = "/home/elf/projects/iot/TuyaOpen/apps/tuya_cloud/fruit_quality_cloud/dist/fruit_quality_cloud_0.1.0";
const char *kTuyaIotProcessPattern = "[f]ruit_quality_cloud_0.1.0.elf";
const char *kNetworkProbeUrl = "https://openapi.tuyacn.com";
const char *kMotorConfigFile = "/home/elf/projects/config/motor.yaml";
const char *kSensorCsvFile = "/home/elf/projects/datas/csv/sensor_realtime.csv";
const char *kMangoQualityCsvFile = "/home/elf/projects/datas/csv/mango_quality_realtime.csv";
const char *kMangoBatchCsvFile = "/home/elf/projects/datas/csv/mango_batch_summary.csv";
const char *kMangoHistoryCsvFile = "/home/elf/projects/datas/csv/mango_quality_history.csv";
const int kEnvironmentSampleIntervalS = 5;
const int kSensorRefreshIntervalMs = 5000;
const int kLedAutoIntervalMs = 5000;
const int kLedAutoMinAdjustGapMs = 4500;
const int kIotStatusIntervalMs = 5000;
const int kIotNetworkTimeoutMs = 4000;
const int kLedAutoDeadbandLux = 100;
const int kLedAutoMediumErrorLux = 300;
const int kLedAutoLargeErrorLux = 600;
const double kLedAutoFilterAlpha = 0.35;
const int kSensorStopWaitMs = 8000;
const int kSensorCardCount = 6;
const int kFrameHeaderSize = 4;
const int kMaxFrameBytes = 20 * 1024 * 1024;

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

class CompactStackedWidget : public QStackedWidget
{
public:
    explicit CompactStackedWidget(QWidget *parent = nullptr)
        : QStackedWidget(parent)
    {
    }

    QSize sizeHint() const override
    {
        return QSize(120, 120);
    }

    QSize minimumSizeHint() const override
    {
        return QSize(0, 0);
    }
};

QPixmap loadStartLogo()
{
    QImage image(kLogoPath);
    if (image.isNull()) {
        return QPixmap();
    }

    image = image.convertToFormat(QImage::Format_ARGB32);
    for (int y = 0; y < image.height(); ++y) {
        QRgb *line = reinterpret_cast<QRgb *>(image.scanLine(y));
        for (int x = 0; x < image.width(); ++x) {
            const QRgb pixel = line[x];
            if (qRed(pixel) < 24 && qGreen(pixel) < 24 && qBlue(pixel) < 24) {
                line[x] = qRgba(qRed(pixel), qGreen(pixel), qBlue(pixel), 0);
            }
        }
    }

    return QPixmap::fromImage(image);
}
}

VideoDisplayWidget::VideoDisplayWidget(QWidget *parent)
    : QWidget(parent),
      m_message("视频画面\n等待接入检测程序")
{
    setObjectName("videoState");
    setMinimumSize(180, 120);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void VideoDisplayWidget::setFrame(const QPixmap &frame)
{
    m_frame = frame;
    m_message.clear();
    update();
}

void VideoDisplayWidget::setMessage(const QString &message)
{
    m_frame = QPixmap();
    m_message = message;
    update();
}

void VideoDisplayWidget::clearFrame()
{
    m_frame = QPixmap();
    update();
}

void VideoDisplayWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
    painter.fillRect(rect(), QColor("#0B0F14"));

    if (!m_frame.isNull()) {
        const QSize targetSize = rect().size();
        const QSize scaledSize = m_frame.size().scaled(targetSize, Qt::KeepAspectRatio);
        const QRect target(
            (width() - scaledSize.width()) / 2,
            (height() - scaledSize.height()) / 2,
            scaledSize.width(),
            scaledSize.height()
        );
        painter.drawPixmap(target, m_frame);
        return;
    }

    painter.setPen(QColor("#F2F2F7"));
    QFont font = painter.font();
    font.setPointSize(24);
    font.setBold(true);
    painter.setFont(font);
    painter.drawText(rect().adjusted(16, 16, -16, -16), Qt::AlignCenter | Qt::TextWordWrap, m_message);
}

AspectRatioVideoFrame::AspectRatioVideoFrame(QWidget *parent)
    : QFrame(parent),
      m_content(nullptr),
      m_aspectRatio(4.0 / 3.0)
{
    setObjectName("videoSurface");
    setFrameShape(QFrame::NoFrame);
    setMinimumSize(180, 120);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void AspectRatioVideoFrame::setContentWidget(QWidget *content)
{
    m_content = content;
    if (m_content) {
        m_content->setParent(this);
        m_content->show();
    }
    updateContentGeometry();
}

void AspectRatioVideoFrame::setAspectRatioFromSize(const QSize &size)
{
    if (size.width() <= 0 || size.height() <= 0) {
        return;
    }

    const double nextRatio = static_cast<double>(size.width()) / static_cast<double>(size.height());
    if (qAbs(nextRatio - m_aspectRatio) < 0.001) {
        return;
    }

    m_aspectRatio = nextRatio;
    updateContentGeometry();
}

void AspectRatioVideoFrame::resizeEvent(QResizeEvent *event)
{
    QFrame::resizeEvent(event);
    updateContentGeometry();
}

void AspectRatioVideoFrame::updateContentGeometry()
{
    if (!m_content || width() <= 0 || height() <= 0) {
        return;
    }

    const int availableW = width();
    const int availableH = height();
    int contentW = availableW;
    int contentH = static_cast<int>(contentW / m_aspectRatio);

    if (contentH > availableH) {
        contentH = availableH;
        contentW = static_cast<int>(contentH * m_aspectRatio);
    }

    const int x = (availableW - contentW) / 2;
    const int y = (availableH - contentH) / 2;
    m_content->setGeometry(x, y, contentW, contentH);
}

DonutChartWidget::DonutChartWidget(QWidget *parent)
    : QWidget(parent)
{
    setObjectName("chartCanvas");
    setMinimumHeight(142);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void DonutChartWidget::setData(const QVector<double> &values, const QStringList &labels, const QVector<QColor> &colors)
{
    m_values = values;
    m_labels = labels;
    m_colors = colors;
    update();
}

void DonutChartWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(QPen(QColor("#DDE6F2"), 1));
    painter.setBrush(QColor("#ffffff"));
    painter.drawRoundedRect(rect().adjusted(0, 0, -1, -1), 7, 7);

    const int side = qMax(64, qMin(static_cast<int>(width() * 0.45), height() - 14));
    const QRectF pieRect(10, (height() - side) / 2.0, side, side);
    const double total = std::accumulate(m_values.begin(), m_values.end(), 0.0);

    painter.setPen(Qt::NoPen);
    if (total <= 0.0) {
        painter.setBrush(QColor("#E8EEF7"));
        painter.drawEllipse(pieRect);
    } else {
        int startAngle = 90 * 16;
        for (int i = 0; i < m_values.size(); ++i) {
            const int spanAngle = -qRound(m_values.at(i) * 360.0 * 16.0 / total);
            painter.setBrush(i < m_colors.size() ? m_colors.at(i) : QColor("#9CA3AF"));
            painter.drawPie(pieRect, startAngle, spanAngle);
            startAngle += spanAngle;
        }
    }

    painter.setBrush(QColor("#ffffff"));
    painter.drawEllipse(pieRect.adjusted(side * 0.26, side * 0.26, -side * 0.26, -side * 0.26));

    painter.setPen(QColor("#111827"));
    QFont centerFont = painter.font();
    centerFont.setPointSize(17);
    centerFont.setBold(true);
    painter.setFont(centerFont);
    painter.drawText(pieRect, Qt::AlignCenter, QString::number(static_cast<int>(total)));

    QFont labelFont = painter.font();
    labelFont.setPointSize(10);
    labelFont.setBold(false);
    painter.setFont(labelFont);
    const int legendX = pieRect.right() + 18;
    int legendY = qMax(16, (height() - m_labels.size() * 24) / 2);
    for (int i = 0; i < m_labels.size(); ++i) {
        const QColor color = i < m_colors.size() ? m_colors.at(i) : QColor("#9CA3AF");
        painter.setPen(Qt::NoPen);
        painter.setBrush(color);
        painter.drawRoundedRect(QRectF(legendX, legendY + 4, 12, 12), 3, 3);
        painter.setPen(QColor("#374151"));
        const int value = i < m_values.size() ? qRound(m_values.at(i)) : 0;
        painter.drawText(QRect(legendX + 18, legendY, width() - legendX - 20, 20),
                         Qt::AlignLeft | Qt::AlignVCenter,
                         QString("%1  %2").arg(m_labels.at(i)).arg(value));
        legendY += 24;
    }
}

BarChartWidget::BarChartWidget(QWidget *parent)
    : QWidget(parent)
{
    setObjectName("chartCanvas");
    setMinimumHeight(128);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void BarChartWidget::setData(const QVector<double> &values, const QStringList &labels, const QVector<QColor> &colors)
{
    m_values = values;
    m_labels = labels;
    m_colors = colors;
    update();
}

void BarChartWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(QPen(QColor("#DDE6F2"), 1));
    painter.setBrush(QColor("#ffffff"));
    painter.drawRoundedRect(rect().adjusted(0, 0, -1, -1), 7, 7);

    const int count = qMin(m_values.size(), m_labels.size());
    if (count <= 0) {
        return;
    }

    double maxValue = 1.0;
    for (double value : m_values) {
        maxValue = qMax(maxValue, value);
    }

    const int left = 12;
    const int right = width() - 12;
    const int top = 10;
    const int bottom = height() - 26;
    const int availableW = qMax(1, right - left);
    const int gap = 8;
    const int barW = qMax(10, (availableW - gap * (count - 1)) / count);

    QFont valueFont = painter.font();
    valueFont.setPointSize(10);
    valueFont.setBold(true);
    painter.setFont(valueFont);

    for (int i = 0; i < count; ++i) {
        const int x = left + i * (barW + gap);
        const int barH = qRound((bottom - top) * (m_values.at(i) / maxValue));
        const QRectF barRect(x, bottom - barH, barW, barH);
        const QColor color = i < m_colors.size() ? m_colors.at(i) : QColor("#6B7280");

        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor("#EEF4FB"));
        painter.drawRoundedRect(QRectF(x, top, barW, bottom - top), 5, 5);
        painter.setBrush(color);
        painter.drawRoundedRect(barRect, 5, 5);

        painter.setPen(QColor("#111827"));
        painter.drawText(QRect(x, qMax(0, static_cast<int>(barRect.top()) - 20), barW, 18),
                         Qt::AlignCenter,
                         QString::number(qRound(m_values.at(i))));

        painter.setPen(QColor("#4B5563"));
        painter.drawText(QRect(x - 4, bottom + 4, barW + 8, 20),
                         Qt::AlignCenter,
                         m_labels.at(i));
    }
}

QualityScoreWidget::QualityScoreWidget(QWidget *parent)
    : QWidget(parent),
      m_score(0.0),
      m_status("等待数据"),
      m_color("#2F6B4F")
{
    setObjectName("qualityScoreCanvas");
    setMinimumSize(128, 128);
    setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Preferred);
}

void QualityScoreWidget::setScore(double score, const QString &status, const QColor &color)
{
    m_score = qBound(0.0, score, 100.0);
    m_status = status;
    m_color = color;
    update();
}

void QualityScoreWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);

    const int side = qMin(width(), height()) - 14;
    const QRectF ringRect((width() - side) / 2.0, 8, side, side);
    const int penWidth = qMax(12, side / 12);

    painter.setPen(QPen(QColor("#E1E6DD"), penWidth, Qt::SolidLine, Qt::RoundCap));
    painter.drawArc(ringRect.adjusted(penWidth / 2.0, penWidth / 2.0, -penWidth / 2.0, -penWidth / 2.0), 90 * 16, -360 * 16);

    painter.setPen(QPen(m_color, penWidth, Qt::SolidLine, Qt::RoundCap));
    painter.drawArc(ringRect.adjusted(penWidth / 2.0, penWidth / 2.0, -penWidth / 2.0, -penWidth / 2.0),
                    90 * 16,
                    -qRound(360.0 * 16.0 * m_score / 100.0));

    painter.setPen(QColor("#26352A"));
    QFont scoreFont = painter.font();
    scoreFont.setPointSize(qMax(18, side / 6));
    scoreFont.setBold(true);
    painter.setFont(scoreFont);
    painter.drawText(ringRect.adjusted(0, side * 0.16, 0, -side * 0.18),
                     Qt::AlignCenter,
                     QString::number(qRound(m_score)));

    QFont statusFont = painter.font();
    statusFont.setPointSize(qMax(9, side / 15));
    statusFont.setBold(true);
    painter.setFont(statusFont);
    painter.setPen(QColor("#697468"));
    painter.drawText(ringRect.adjusted(8, side * 0.58, -8, -side * 0.08),
                     Qt::AlignCenter | Qt::TextWordWrap,
                     m_status);
}

QualityFactorWidget::QualityFactorWidget(QWidget *parent)
    : QWidget(parent)
{
    setObjectName("qualityFactorCanvas");
    setMinimumHeight(188);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
}

void QualityFactorWidget::setData(const QStringList &labels, const QVector<double> &values, const QStringList &details, const QVector<QColor> &colors)
{
    m_labels = labels;
    m_values = values;
    m_details = details;
    m_colors = colors;
    update();
}

void QualityFactorWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.fillRect(rect(), Qt::transparent);

    const int count = qMin(m_labels.size(), m_values.size());
    if (count <= 0) {
        return;
    }

    const int left = 8;
    const int right = width() - 8;
    const int rowH = qMax(30, (height() - 6) / count);
    const int barLeft = left + 72;
    const int barRight = right - 42;
    const int barW = qMax(1, barRight - barLeft);

    QFont labelFont = painter.font();
    labelFont.setPointSize(10);
    labelFont.setBold(true);
    QFont detailFont = painter.font();
    detailFont.setPointSize(8);

    for (int i = 0; i < count; ++i) {
        const int y = 4 + i * rowH;
        const double value = qBound(0.0, m_values.at(i), 100.0);
        const QColor color = i < m_colors.size() ? m_colors.at(i) : QColor("#2F6B4F");
        const QString detail = i < m_details.size() ? m_details.at(i) : QString();

        painter.setFont(labelFont);
        painter.setPen(QColor("#26352A"));
        painter.drawText(QRect(left, y, 66, 20), Qt::AlignLeft | Qt::AlignVCenter, m_labels.at(i));

        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor("#E9EEE6"));
        const QRectF track(barLeft, y + 7, barW, 12);
        painter.drawRoundedRect(track, 6, 6);
        painter.setBrush(color);
        painter.drawRoundedRect(QRectF(barLeft, y + 7, barW * value / 100.0, 12), 6, 6);

        painter.setFont(labelFont);
        painter.setPen(QColor("#26352A"));
        painter.drawText(QRect(barRight + 8, y, 34, 20), Qt::AlignRight | Qt::AlignVCenter, QString::number(qRound(value)));

        painter.setFont(detailFont);
        painter.setPen(QColor("#697468"));
        const QString clippedDetail = painter.fontMetrics().elidedText(detail, Qt::ElideRight, qMax(1, right - barLeft));
        painter.drawText(QRect(barLeft, y + 21, qMax(1, right - barLeft), rowH - 21),
                         Qt::AlignLeft | Qt::AlignTop,
                         clippedDetail);
    }
}

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent),
      m_pages(new QStackedWidget(this)),
      m_functionPages(nullptr),
      m_videoPanel(nullptr),
      m_videoSurface(nullptr),
      m_videoDisplay(nullptr),
      m_sensorStatusLabel(nullptr),
      m_sensorGrid(nullptr),
      m_sensorTimer(new QTimer(this)),
      m_sensorProcess(new QProcess(this)),
      m_mangoQualityTimer(new QTimer(this)),
      m_mangoQualityProcess(new QProcess(this)),
      m_voicePromptProcess(new QProcess(this)),
      m_cameraProcess(new QProcess(this)),
      m_motorCommandProcess(new QProcess(this)),
      m_tuyaIotProcess(new QProcess(this)),
      m_iotStatusTimer(new QTimer(this)),
      m_iotNetworkManager(new QNetworkAccessManager(this)),
      m_iotNetworkReply(nullptr),
      m_networkStatusLabel(nullptr),
      m_sensorReader(kSensorCsvFile),
      m_conveyorSpeedSlider(nullptr),
      m_conveyorSpeedValueLabel(nullptr),
      m_motorStatusLabel(nullptr),
      m_conveyorForwardButton(nullptr),
      m_conveyorReverseButton(nullptr),
      m_conveyorStopButton(nullptr),
      m_conveyorSlowButton(nullptr),
      m_conveyorMediumButton(nullptr),
      m_conveyorFastButton(nullptr),
      m_ledBrightnessSlider(nullptr),
      m_ledThresholdSlider(nullptr),
      m_ledBrightnessValueLabel(nullptr),
      m_ledThresholdValueLabel(nullptr),
      m_ledStatusLabel(nullptr),
      m_ledAutoButton(nullptr),
      m_ledAutoTimer(new QTimer(this)),
      m_ledFilteredLux(0.0),
      m_ledHasFilteredLux(false),
      m_ledLastAutoAdjustMs(0),
      m_mangoMaturityValueLabel(nullptr),
      m_mangoSugarValueLabel(nullptr),
      m_mangoRotValueLabel(nullptr),
      m_mangoFinalValueLabel(nullptr),
      m_mangoIdValueLabel(nullptr),
      m_mangoGradeValueLabel(nullptr),
      m_mangoChannelValueLabel(nullptr),
      m_mangoStabilityValueLabel(nullptr),
      m_mangoYoloValueLabel(nullptr),
      m_mangoDataValueLabel(nullptr),
      m_mangoQualityStatusLabel(nullptr),
      m_mangoReasonLabel(nullptr),
      m_mangoScoreChart(nullptr),
      m_mangoFactorChart(nullptr),
      m_batchTotalValueLabel(nullptr),
      m_batchSaleableValueLabel(nullptr),
      m_batchRejectValueLabel(nullptr),
      m_batchLatestValueLabel(nullptr),
      m_batchStatusLabel(nullptr),
      m_batchSummaryLabel(nullptr),
      m_batchMaturityChart(nullptr),
      m_batchGradeChart(nullptr),
      m_batchChannelChart(nullptr),
      m_historyTable(nullptr),
      m_historySummaryLabel(nullptr),
      m_voicePromptStatusLabel(nullptr),
      m_voicePreviousButton(nullptr),
      m_voiceBatchButton(nullptr),
      m_servoStatusLabel(nullptr),
      m_servoPosition1Button(nullptr),
      m_servoPosition2Button(nullptr),
      m_servoPosition3Button(nullptr),
      m_conveyorDirection(0),
      m_conveyorMinSpeedX10(1),
      m_conveyorMaxSpeedX10(10),
      m_conveyorDefaultSpeedX10(5),
      m_conveyorSpeedGear(0),
      m_conveyorSlowSpeedMs(0.10),
      m_conveyorMediumSpeedMs(0.13),
      m_conveyorFastSpeedMs(0.16),
      m_ledCurrentBrightness(40),
      m_ledAutoEnabled(false),
      m_ledWasStarted(false),
      m_conveyorWasStarted(false),
      m_tuyaIotStartedByQt(false),
      m_shutdownDone(false)
{
    setWindowTitle(kProjectTitle);
    setMinimumSize(0, 0);
    setCentralWidget(m_pages);
    m_pages->setContentsMargins(0, 0, 0, 0);
    m_pages->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    loadConveyorSpeedRange();
    applyGlobalStyle();

    m_pages->addWidget(createStartPage());
    m_pages->addWidget(createWorkPage());
    m_pages->addWidget(createMangoHistoryPage());
    m_pages->setCurrentIndex(0);

    connect(m_sensorTimer, &QTimer::timeout, this, &MainWindow::refreshSensorData);
    m_sensorTimer->setInterval(kSensorRefreshIntervalMs);
    connect(m_mangoQualityTimer, &QTimer::timeout, this, &MainWindow::refreshMangoQualityData);
    m_mangoQualityTimer->setInterval(1000);

    connect(m_sensorProcess, &QProcess::readyReadStandardError, this, &MainWindow::readSensorMessages);
    connect(m_sensorProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleSensorFinished);
    connect(m_mangoQualityProcess, &QProcess::readyReadStandardError, this, &MainWindow::readMangoQualityMessages);
    connect(m_mangoQualityProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleMangoQualityFinished);

    m_voicePromptProcess->setProcessChannelMode(QProcess::MergedChannels);
    connect(m_voicePromptProcess, &QProcess::readyReadStandardOutput, this, &MainWindow::readVoicePromptMessages);
    connect(m_voicePromptProcess, &QProcess::readyReadStandardError, this, &MainWindow::readVoicePromptMessages);
    connect(m_voicePromptProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleVoicePromptFinished);

    connect(m_cameraProcess, &QProcess::readyReadStandardOutput, this, &MainWindow::readCameraFrames);
    connect(m_cameraProcess, &QProcess::readyReadStandardError, this, &MainWindow::readCameraMessages);
    connect(m_cameraProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleCameraFinished);

    m_tuyaIotProcess->setProcessChannelMode(QProcess::MergedChannels);
    connect(m_tuyaIotProcess, &QProcess::readyReadStandardOutput, this, &MainWindow::readTuyaIotMessages);
    connect(m_tuyaIotProcess, &QProcess::readyReadStandardError, this, &MainWindow::readTuyaIotMessages);
    connect(m_tuyaIotProcess,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            &MainWindow::handleTuyaIotFinished);
    connect(m_iotStatusTimer, &QTimer::timeout, this, &MainWindow::updateIotStatus);
    m_iotStatusTimer->setInterval(kIotStatusIntervalMs);
    startTuyaIotProcess();
    updateIotStatus();
    m_iotStatusTimer->start();

    connect(m_ledAutoTimer, &QTimer::timeout, this, &MainWindow::updateLedAutoControl);
    m_ledAutoTimer->setInterval(kLedAutoIntervalMs);
}

MainWindow::~MainWindow()
{
    shutdownHardware();
    stopTuyaIotProcess();
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
    m_mangoQualityTimer->stop();
    stopMangoQualityProcess();
    if (m_voicePromptProcess->state() != QProcess::NotRunning) {
        m_voicePromptProcess->terminate();
        if (!m_voicePromptProcess->waitForFinished(1500)) {
            m_voicePromptProcess->kill();
            m_voicePromptProcess->waitForFinished(500);
        }
    }
    stopSensorProcess();
    stopCameraProcess();
    if (m_motorCommandProcess->state() != QProcess::NotRunning) {
        m_motorCommandProcess->kill();
        m_motorCommandProcess->waitForFinished(500);
    }
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
    startMangoQualityProcess();
    refreshMangoQualityData();
    if (!m_mangoQualityTimer->isActive()) {
        m_mangoQualityTimer->start();
    }
}

void MainWindow::showStartPage()
{
    shutdownHardware();
    m_sensorTimer->stop();
    m_pages->setCurrentIndex(0);
    m_shutdownDone = false;
}

void MainWindow::showMangoHistoryPage()
{
    refreshMangoHistoryData();
    m_pages->setCurrentIndex(2);
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

void MainWindow::showMangoQualityPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(3);
    }
    startMangoQualityProcess();
    refreshMangoQualityData();
}

void MainWindow::showServoControlPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(5);
    }
}

void MainWindow::showBatchStatsPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(4);
    }
    refreshBatchStatsData();
}

void MainWindow::showVoicePromptPage()
{
    if (m_functionPages) {
        m_functionPages->setCurrentIndex(6);
    }
}

void MainWindow::refreshSensorData()
{
    updateSensorCards(m_sensorReader.readLatest());
}

void MainWindow::refreshMangoQualityData()
{
    if (!m_mangoScoreChart) {
        refreshBatchStatsData();
        return;
    }

    QFile file(kMangoQualityCsvFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        m_mangoMaturityValueLabel->setText("--");
        m_mangoSugarValueLabel->setText("--");
        m_mangoRotValueLabel->setText("--");
        m_mangoFinalValueLabel->setText("--");
        m_mangoIdValueLabel->setText("--");
        m_mangoGradeValueLabel->setText("--");
        m_mangoChannelValueLabel->setText("--");
        m_mangoStabilityValueLabel->setText("--");
        m_mangoYoloValueLabel->setText("--");
        m_mangoDataValueLabel->setText("等待融合结果");
        m_mangoScoreChart->setScore(0, "等待数据", QColor("#697468"));
        m_mangoFactorChart->setData(
            {"成熟度", "参考糖度", "新鲜度", "稳定性", "YOLO"},
            {0, 0, 0, 0, 0},
            {"等待融合结果", "等待融合结果", "等待融合结果", "等待融合结果", "等待融合结果"},
            {QColor("#C8D8D0"), QColor("#C8D8D0"), QColor("#C8D8D0"), QColor("#C8D8D0"), QColor("#C8D8D0")}
        );
        if (m_mangoQualityStatusLabel) {
            m_mangoQualityStatusLabel->setText("状态：未读取到三模态融合结果");
        }
        if (m_mangoReasonLabel) {
            m_mangoReasonLabel->setText("请确认YOLO检测、HSV/RGB特征与光谱采集已启动。");
        }
        return;
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
        m_mangoDataValueLabel->setText("等待融合结果");
        m_mangoScoreChart->setScore(0, "等待数据", QColor("#697468"));
        if (m_mangoQualityStatusLabel) {
            m_mangoQualityStatusLabel->setText("状态：融合结果为空");
        }
        return;
    }

    const QStringList headers = parseCsvLine(headerLine);
    const QStringList fields = parseCsvLine(lastLine);
    auto valueFor = [&](const QString &key, const QString &fallback = QString("--")) {
        const int index = headers.indexOf(key);
        if (index < 0 || index >= fields.size()) {
            return fallback;
        }
        const QString value = fields.at(index).trimmed();
        return value.isEmpty() ? fallback : value;
    };

    const QString maturity = valueFor("maturity_label");
    const QString maturityScore = valueFor("maturity_score", QString());
    const QString sugar = valueFor("sugar_label");
    const QString brixRange = valueFor("reference_brix_range", QString());
    const QString rot = valueFor("rot_status");
    const QString rotScore = valueFor("rot_score", QString());
    const QString finalStatus = valueFor("final_status");
    const QString mangoId = valueFor("mango_id", "--");
    const QString qualityGrade = valueFor("quality_grade", "--");
    const QString suggestedChannel = valueFor("suggested_channel", "--");
    const QString stableFrames = valueFor("stable_frames", QString());
    const QString consistency = valueFor("consistency_label", QString());
    const QString consistencyScore = valueFor("consistency_score", QString());
    const QString yoloLabel = valueFor("yolo_label", "未检测到");
    const QString yoloConfidence = valueFor("yolo_confidence", QString());
    const QString dataStatus = valueFor("data_status", "等待数据");
    const QString reason = valueFor("reason", "暂无说明");
    const QString timestamp = valueFor("timestamp", QString());
    auto scoreFor = [](const QString &text, double fallback = 0.0) {
        bool ok = false;
        const double value = text.toDouble(&ok);
        return ok ? qBound(0.0, value, 100.0) : fallback;
    };
    auto ratioFor = [](const QString &text, double fallback = 0.0) {
        bool ok = false;
        const double value = text.toDouble(&ok);
        if (!ok) {
            return fallback;
        }
        return qBound(0.0, value <= 1.0 ? value * 100.0 : value, 100.0);
    };

    const double maturityValue = scoreFor(maturityScore);
    const double sugarValue = scoreFor(valueFor("sugar_score", QString()));
    const double rotRiskValue = scoreFor(rotScore);
    const double freshnessValue = 100.0 - rotRiskValue;
    const double stabilityValue = ratioFor(consistencyScore);
    const double yoloValue = ratioFor(yoloConfidence);
    const bool hasValidDetection = finalStatus != "无有效检测" && qualityGrade != "--";
    const double overallScore = hasValidDetection
        ? qBound(0.0,
                 maturityValue * 0.30
               + sugarValue * 0.20
               + freshnessValue * 0.30
               + stabilityValue * 0.10
               + yoloValue * 0.10,
                 100.0)
        : 0.0;

    QColor scoreColor("#697468");
    if (finalStatus == "可接受") {
        scoreColor = QColor("#2F6B4F");
    } else if (finalStatus == "需要复检") {
        scoreColor = QColor("#C77B2B");
    } else if (finalStatus == "建议剔除") {
        scoreColor = QColor("#A53A32");
    }

    m_mangoMaturityValueLabel->setText(maturityScore.isEmpty() ? maturity : QString("%1  %2分").arg(maturity, maturityScore));
    m_mangoSugarValueLabel->setText(brixRange.isEmpty() ? sugar : QString("%1  %2").arg(sugar, brixRange));
    m_mangoRotValueLabel->setText(rotScore.isEmpty() ? rot : QString("%1  %2分").arg(rot, rotScore));
    m_mangoFinalValueLabel->setText(finalStatus);
    m_mangoIdValueLabel->setText(mangoId == "--" ? "--" : QString("#%1").arg(mangoId));
    m_mangoGradeValueLabel->setText(qualityGrade);
    m_mangoChannelValueLabel->setText(suggestedChannel);
    if (stableFrames.isEmpty() && consistency.isEmpty()) {
        m_mangoStabilityValueLabel->setText("--");
    } else {
        m_mangoStabilityValueLabel->setText(QString("%1  连续%2帧")
                                            .arg(consistency.isEmpty() ? "稳定性--" : "稳定性" + consistency)
                                            .arg(stableFrames.isEmpty() ? "--" : stableFrames));
    }
    m_mangoYoloValueLabel->setText(yoloConfidence.isEmpty() ? yoloLabel : QString("%1  置信度%2").arg(yoloLabel, yoloConfidence));
    QString dataStatusText = dataStatus;
    if (dataStatus.contains("vision_ok") && dataStatus.contains("spectrum_ok")) {
        dataStatusText = "视觉+光谱";
    } else if (dataStatus.contains("vision_ok")) {
        dataStatusText = "仅视觉";
    } else if (dataStatus.contains("spectrum_ok")) {
        dataStatusText = "仅光谱";
    } else if (dataStatus.contains("missing")) {
        dataStatusText = "等待数据";
    }
    m_mangoDataValueLabel->setText(dataStatusText);
    m_mangoScoreChart->setScore(overallScore, finalStatus, scoreColor);
    m_mangoFactorChart->setData(
        {"成熟度", "参考糖度", "新鲜度", "稳定性", "YOLO"},
        {maturityValue, sugarValue, freshnessValue, stabilityValue, yoloValue},
        {
            maturityScore.isEmpty() ? maturity : QString("%1 / %2分").arg(maturity, maturityScore),
            brixRange.isEmpty() ? sugar : QString("%1 / %2").arg(sugar, brixRange),
            QString("%1 / 风险%2分").arg(rot, rotScore.isEmpty() ? "--" : rotScore),
            stableFrames.isEmpty() ? consistency : QString("%1 / 连续%2帧").arg(consistency.isEmpty() ? "--" : consistency, stableFrames),
            yoloConfidence.isEmpty() ? yoloLabel : QString("%1 / %2").arg(yoloLabel, yoloConfidence)
        },
        {QColor("#2F6B4F"), QColor("#C77B2B"), QColor("#4F7F5F"), QColor("#60705C"), QColor("#7A6A45")}
    );

    if (m_mangoQualityStatusLabel) {
        m_mangoQualityStatusLabel->setText(timestamp.isEmpty() ? "状态：三模态融合结果" : "状态：更新于 " + timestamp);
    }
    if (m_mangoReasonLabel) {
        m_mangoReasonLabel->setText(reason);
    }

    refreshBatchStatsData();
}

void MainWindow::refreshBatchStatsData()
{
    if (!m_batchTotalValueLabel) {
        return;
    }

    auto resetBatchUi = [&]() {
        m_batchTotalValueLabel->setText("0");
        m_batchSaleableValueLabel->setText("--");
        m_batchRejectValueLabel->setText("0");
        m_batchLatestValueLabel->setText("--");
        if (m_batchStatusLabel) {
            m_batchStatusLabel->setText("状态：等待批次统计");
        }
        if (m_batchSummaryLabel) {
            m_batchSummaryLabel->setText("当前批次尚未完成芒果计数。");
        }
        if (m_batchMaturityChart) {
            m_batchMaturityChart->setData({0, 0, 0}, {"未熟", "成熟", "过熟"}, {QColor("#34C759"), QColor("#FFCC00"), QColor("#FF9500")});
        }
        if (m_batchGradeChart) {
            m_batchGradeChart->setData({0, 0, 0, 0}, {"A", "B", "C", "剔除"}, {QColor("#007AFF"), QColor("#34C759"), QColor("#FF9500"), QColor("#FF3B30")});
        }
        if (m_batchChannelChart) {
            m_batchChannelChart->setData({0, 0, 0, 0, 0}, {"销售", "催熟", "加工", "复检", "剔除"}, {QColor("#34C759"), QColor("#FFCC00"), QColor("#FF9500"), QColor("#5E5CE6"), QColor("#FF3B30")});
        }
    };

    QFile file(kMangoBatchCsvFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        resetBatchUi();
        return;
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
        resetBatchUi();
        return;
    }

    const QStringList headers = parseCsvLine(headerLine);
    const QStringList fields = parseCsvLine(lastLine);
    auto valueFor = [&](const QString &key, const QString &fallback = QString("0")) {
        const int index = headers.indexOf(key);
        if (index < 0 || index >= fields.size()) {
            return fallback;
        }
        const QString value = fields.at(index).trimmed();
        return value.isEmpty() ? fallback : value;
    };
    auto intFor = [&](const QString &key) {
        bool ok = false;
        const int value = valueFor(key).toInt(&ok);
        return ok ? value : 0;
    };
    auto doubleFor = [&](const QString &key) {
        bool ok = false;
        const double value = valueFor(key).toDouble(&ok);
        return ok ? value : 0.0;
    };

    const int total = intFor("total_count");
    const int reject = intFor("reject_count");
    const double saleable = doubleFor("saleable_ratio");
    const double rotRisk = doubleFor("rot_risk_ratio");
    const QString latestId = valueFor("last_mango_id", "--");
    const QString latestGrade = valueFor("last_quality_grade", "--");
    const QString latestChannel = valueFor("last_suggested_channel", "--");
    const QString latestMaturity = valueFor("last_maturity_label", "--");
    const QString timestamp = valueFor("timestamp", "");

    m_batchTotalValueLabel->setText(QString::number(total));
    m_batchSaleableValueLabel->setText(total > 0 ? QString("%1%").arg(saleable, 0, 'f', 1) : "--");
    m_batchRejectValueLabel->setText(QString::number(reject));
    if (latestId == "--" || latestId.isEmpty()) {
        m_batchLatestValueLabel->setText("--");
    } else {
        m_batchLatestValueLabel->setText(QString("#%1  %2").arg(latestId, latestGrade));
    }

    if (m_batchMaturityChart) {
        m_batchMaturityChart->setData(
            {static_cast<double>(intFor("unripe_count")), static_cast<double>(intFor("ripe_count")), static_cast<double>(intFor("overripe_count"))},
            {"未熟", "成熟", "过熟"},
            {QColor("#34C759"), QColor("#FFCC00"), QColor("#FF9500")}
        );
    }
    if (m_batchGradeChart) {
        m_batchGradeChart->setData(
            {static_cast<double>(intFor("grade_a_count")), static_cast<double>(intFor("grade_b_count")), static_cast<double>(intFor("grade_c_count")), static_cast<double>(intFor("reject_count"))},
            {"A", "B", "C", "剔除"},
            {QColor("#007AFF"), QColor("#34C759"), QColor("#FF9500"), QColor("#FF3B30")}
        );
    }
    if (m_batchChannelChart) {
        m_batchChannelChart->setData(
            {static_cast<double>(intFor("channel_sales_count")), static_cast<double>(intFor("channel_ripen_count")), static_cast<double>(intFor("channel_process_count")), static_cast<double>(intFor("channel_recheck_count")), static_cast<double>(intFor("channel_reject_count"))},
            {"销售", "催熟", "加工", "复检", "剔除"},
            {QColor("#34C759"), QColor("#FFCC00"), QColor("#FF9500"), QColor("#5E5CE6"), QColor("#FF3B30")}
        );
    }

    if (m_batchStatusLabel) {
        m_batchStatusLabel->setText(timestamp.isEmpty() ? "状态：批次统计已更新" : "状态：更新于 " + timestamp);
    }
    if (m_batchSummaryLabel) {
        if (total > 0) {
            m_batchSummaryLabel->setText(QString("本批次已统计%1个芒果，可销售%2%，异常风险%3%。最近结果：%4，%5。")
                                         .arg(total)
                                         .arg(saleable, 0, 'f', 1)
                                         .arg(rotRisk, 0, 'f', 1)
                                         .arg(latestMaturity)
                                         .arg(latestChannel));
        } else {
            m_batchSummaryLabel->setText("当前批次尚未完成芒果计数。");
        }
    }
}

void MainWindow::refreshMangoHistoryData()
{
    if (!m_historyTable) {
        return;
    }

    QFile file(kMangoHistoryCsvFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        m_historyTable->setRowCount(0);
        if (m_historySummaryLabel) {
            m_historySummaryLabel->setText("已检测 0 个芒果");
        }
        return;
    }

    QTextStream stream(&file);
    stream.setCodec("UTF-8");
    QString headerLine;
    QVector<QStringList> rows;
    while (!stream.atEnd()) {
        const QString line = stream.readLine().trimmed();
        if (line.isEmpty()) {
            continue;
        }
        if (headerLine.isEmpty()) {
            headerLine = line;
        } else {
            rows.append(parseCsvLine(line));
        }
    }

    const QStringList headers = parseCsvLine(headerLine);
    auto columnValue = [&](const QStringList &fields, const QString &key, const QString &fallback = QString("--")) {
        const int index = headers.indexOf(key);
        if (index < 0 || index >= fields.size()) {
            return fallback;
        }
        const QString value = fields.at(index).trimmed();
        return value.isEmpty() ? fallback : value;
    };

    m_historyTable->setRowCount(rows.size());
    const QStringList keys = {
        "mango_id",
        "timestamp",
        "quality_grade",
        "maturity_label",
        "reference_brix_range",
        "rot_status",
        "suggested_channel",
        "final_status"
    };

    int displayRow = 0;
    for (int i = rows.size() - 1; i >= 0; --i) {
        const QStringList fields = rows.at(i);
        for (int col = 0; col < keys.size(); ++col) {
            QString text = columnValue(fields, keys.at(col));
            if (keys.at(col) == "mango_id" && text != "--") {
                text = "#" + text;
            }
            QTableWidgetItem *item = new QTableWidgetItem(text);
            item->setTextAlignment(Qt::AlignCenter);
            m_historyTable->setItem(displayRow, col, item);
        }
        ++displayRow;
    }

    if (m_historySummaryLabel) {
        m_historySummaryLabel->setText(QString("已检测 %1 个芒果").arg(rows.size()));
    }
}

void MainWindow::readSensorMessages()
{
    m_sensorProcess->readAllStandardError();
    if (m_sensorStatusLabel) {
        m_sensorStatusLabel->clear();
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

void MainWindow::readMangoQualityMessages()
{
    m_mangoQualityProcess->readAllStandardError();
}

void MainWindow::handleMangoQualityFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    if (!m_mangoQualityStatusLabel) {
        return;
    }

    if (exitStatus == QProcess::CrashExit) {
        m_mangoQualityStatusLabel->setText("状态：三模态融合程序异常退出");
    } else if (exitCode != 0) {
        m_mangoQualityStatusLabel->setText(QString("状态：三模态融合程序退出：%1").arg(exitCode));
    }
}

void MainWindow::announcePreviousMango()
{
    runVoicePromptCommand("previous", "上一个芒果");
}

void MainWindow::announceBatchMango()
{
    runVoicePromptCommand("batch", "整批芒果");
}

void MainWindow::readVoicePromptMessages()
{
    const QByteArray output = m_voicePromptProcess->readAllStandardOutput()
                            + m_voicePromptProcess->readAllStandardError();
    const QString message = QString::fromLocal8Bit(output).trimmed();
    if (!message.isEmpty() && m_voicePromptStatusLabel) {
        m_voicePromptStatusLabel->setText("状态：" + message.left(160));
    }
}

void MainWindow::handleVoicePromptFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    const QByteArray output = m_voicePromptProcess->readAllStandardOutput()
                            + m_voicePromptProcess->readAllStandardError();
    const QString message = QString::fromLocal8Bit(output).trimmed();

    if (m_voicePreviousButton) {
        m_voicePreviousButton->setEnabled(true);
    }
    if (m_voiceBatchButton) {
        m_voiceBatchButton->setEnabled(true);
    }

    if (!m_voicePromptStatusLabel) {
        return;
    }

    if (exitStatus == QProcess::NormalExit && exitCode == 0) {
        m_voicePromptStatusLabel->setText("状态：语音评价已完成");
    } else {
        m_voicePromptStatusLabel->setText("状态：语音评价失败 " + message.left(140));
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

void MainWindow::updateIotStatus()
{
    if (m_iotNetworkReply) {
        return;
    }

    const bool processRunning = isTuyaIotProcessRunning();
    if (!processRunning) {
        setIotStatusText("物联网未运行", "offline");
        startTuyaIotProcess();
        return;
    }

    setIotStatusText("物联网运行中", "checking");

    QNetworkRequest request{QUrl(kNetworkProbeUrl)};
    m_iotNetworkReply = m_iotNetworkManager->get(request);

    QTimer::singleShot(kIotNetworkTimeoutMs, this, [this]() {
        if (m_iotNetworkReply && m_iotNetworkReply->isRunning()) {
            m_iotNetworkReply->abort();
        }
    });

    connect(m_iotNetworkReply, &QNetworkReply::finished, this, [this]() {
        QNetworkReply *reply = m_iotNetworkReply;
        if (!reply) {
            return;
        }

        const bool networkOk = reply->error() == QNetworkReply::NoError
                               || reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).isValid();
        reply->deleteLater();
        m_iotNetworkReply = nullptr;

        if (!isTuyaIotProcessRunning()) {
            setIotStatusText("物联网未运行", "offline");
        } else if (networkOk) {
            setIotStatusText("网络正常", "online");
        } else {
            setIotStatusText("网络待确认", "warning");
        }
    });
}

void MainWindow::readTuyaIotMessages()
{
    m_tuyaIotProcess->readAllStandardOutput();
    m_tuyaIotProcess->readAllStandardError();
}

void MainWindow::handleTuyaIotFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    Q_UNUSED(exitCode);
    Q_UNUSED(exitStatus);
    m_tuyaIotStartedByQt = false;
    setIotStatusText("物联网未运行", "offline");
}

QWidget *MainWindow::createStartPage()
{
    QWidget *page = new QWidget;
    page->setObjectName("startPage");
    page->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(54, 46, 54, 54);
    layout->setSpacing(0);

    QLabel *logo = new QLabel;
    logo->setObjectName("startLogo");
    logo->setAlignment(Qt::AlignCenter);
    logo->setFixedSize(860, 210);
    const QPixmap logoPixmap = loadStartLogo();
    if (!logoPixmap.isNull()) {
        logo->setPixmap(logoPixmap.scaled(820, 190, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }

    QLabel *title = new QLabel(kProjectTitle);
    title->setObjectName("startTitle");
    title->setAlignment(Qt::AlignCenter);
    title->setWordWrap(true);

    QPushButton *startButton = new QPushButton("开始检测");
    startButton->setObjectName("startButton");
    startButton->setFixedSize(320, 78);
    connect(startButton, &QPushButton::clicked, this, &MainWindow::showWorkPage);

    layout->addStretch(1);
    layout->addWidget(logo, 0, Qt::AlignHCenter);
    layout->addSpacing(28);
    layout->addWidget(title);
    layout->addSpacing(42);
    layout->addWidget(startButton, 0, Qt::AlignHCenter);
    layout->addStretch(1);

    return page;
}

QWidget *MainWindow::createMangoHistoryPage()
{
    QWidget *page = new QWidget;
    page->setObjectName("historyPage");
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(28, 24, 28, 24);
    layout->setSpacing(14);

    QHBoxLayout *header = new QHBoxLayout;
    QLabel *title = new QLabel("已检测芒果记录");
    title->setObjectName("historyTitle");
    QPushButton *backButton = new QPushButton("返回检测");
    backButton->setObjectName("secondaryButton");
    backButton->setFixedHeight(48);
    backButton->setMinimumWidth(142);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showWorkPage);
    header->addWidget(title);
    header->addWidget(backButton, 0, Qt::AlignRight);

    m_historySummaryLabel = new QLabel("已检测 0 个芒果");
    m_historySummaryLabel->setObjectName("historySummary");

    m_historyTable = new QTableWidget;
    m_historyTable->setObjectName("historyTable");
    m_historyTable->setColumnCount(8);
    m_historyTable->setHorizontalHeaderLabels({"编号", "时间", "等级", "成熟度", "参考糖度", "腐烂", "流向", "结论"});
    m_historyTable->verticalHeader()->setVisible(false);
    m_historyTable->horizontalHeader()->setStretchLastSection(true);
    m_historyTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_historyTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_historyTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_historyTable->setSelectionMode(QAbstractItemView::SingleSelection);
    m_historyTable->setAlternatingRowColors(true);
    m_historyTable->setShowGrid(false);

    layout->addLayout(header);
    layout->addWidget(m_historySummaryLabel);
    layout->addWidget(m_historyTable, 1);

    refreshMangoHistoryData();
    return page;
}

QWidget *MainWindow::createWorkPage()
{
    QWidget *page = new QWidget;
    page->setObjectName("workPage");
    page->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    QHBoxLayout *rootLayout = new QHBoxLayout(page);
    rootLayout->setContentsMargins(8, 8, 8, 8);
    rootLayout->setSpacing(8);
    rootLayout->setSizeConstraint(QLayout::SetNoConstraint);

    QVBoxLayout *leftLayout = new QVBoxLayout;
    leftLayout->setContentsMargins(0, 0, 0, 0);
    leftLayout->setSpacing(8);
    leftLayout->addWidget(createVideoPanel(), 5);
    leftLayout->addWidget(createSensorPanel(), 2);

    rootLayout->addLayout(leftLayout, 6);
    QFrame *functionPanel = createFunctionPlaceholder();
    functionPanel->setMinimumWidth(0);
    functionPanel->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Expanding);
    rootLayout->addWidget(functionPanel, 3);
    rootLayout->setStretch(0, 6);
    rootLayout->setStretch(1, 3);

    return page;
}

QFrame *MainWindow::createVideoPanel()
{
    QFrame *panel = new QFrame;
    m_videoPanel = panel;
    panel->setObjectName("videoPanel");
    panel->setFrameShape(QFrame::NoFrame);
    panel->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(12, 8, 12, 10);
    layout->setSpacing(6);

    QHBoxLayout *header = new QHBoxLayout;
    header->setContentsMargins(0, 0, 0, 0);
    header->setSpacing(8);

    QLabel *title = new QLabel("检测视频实时画面");
    title->setObjectName("panelTitle");
    m_networkStatusLabel = new QLabel("物联网启动中");
    m_networkStatusLabel->setObjectName("networkStatus");
    m_networkStatusLabel->setProperty("state", "checking");
    m_networkStatusLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    m_networkStatusLabel->setMinimumHeight(30);

    header->addWidget(title);
    header->addWidget(m_networkStatusLabel, 0, Qt::AlignRight);

    AspectRatioVideoFrame *videoSurface = new AspectRatioVideoFrame;
    m_videoSurface = videoSurface;

    m_videoDisplay = new VideoDisplayWidget;
    videoSurface->setContentWidget(m_videoDisplay);

    layout->addLayout(header);
    layout->addWidget(videoSurface, 1);

    return panel;
}

QFrame *MainWindow::createSensorPanel()
{
    QFrame *panel = new QFrame;
    panel->setObjectName("sensorPanel");
    panel->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(12, 6, 12, 8);
    layout->setSpacing(4);

    QHBoxLayout *header = new QHBoxLayout;
    QLabel *title = new QLabel("环境实时数据");
    title->setObjectName("panelTitle");
    m_sensorStatusLabel = new QLabel("");
    m_sensorStatusLabel->setObjectName("sensorStatus");
    m_sensorStatusLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    m_sensorStatusLabel->hide();
    header->addWidget(title);
    header->addWidget(m_sensorStatusLabel, 1);

    m_sensorGrid = new QGridLayout;
    m_sensorGrid->setContentsMargins(0, 0, 0, 0);
    m_sensorGrid->setHorizontalSpacing(8);
    m_sensorGrid->setVerticalSpacing(4);

    for (int i = 0; i < kSensorCardCount; ++i) {
        QFrame *card = new QFrame;
        card->setObjectName(QString("sensorCard_%1").arg(i));
        card->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);

        QVBoxLayout *cardLayout = new QVBoxLayout(card);
        cardLayout->setContentsMargins(10, 3, 10, 3);
        cardLayout->setSpacing(0);

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
    panel->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Expanding);

    QVBoxLayout *layout = new QVBoxLayout(panel);
    layout->setContentsMargins(12, 8, 12, 8);
    layout->setSpacing(6);

    QLabel *title = new QLabel("功能区");
    title->setObjectName("panelTitle");

    QPushButton *exitButton = new QPushButton("退出检测");
    exitButton->setObjectName("exitButton");
    exitButton->setMinimumHeight(0);
    exitButton->setFixedHeight(58);
    connect(exitButton, &QPushButton::clicked, this, &MainWindow::showStartPage);

    m_functionPages = new CompactStackedWidget(panel);
    m_functionPages->setMinimumSize(0, 0);
    m_functionPages->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    m_functionPages->addWidget(createFunctionHomePage());
    m_functionPages->addWidget(createConveyorControlPage());
    m_functionPages->addWidget(createLedControlPage());
    m_functionPages->addWidget(createMangoQualityPage());
    m_functionPages->addWidget(createBatchStatsPage());
    m_functionPages->addWidget(createServoControlPage());
    m_functionPages->addWidget(createVoicePromptPage());

    layout->addWidget(title);
    layout->addWidget(m_functionPages, 1);
    layout->addWidget(exitButton);

    return panel;
}

QWidget *MainWindow::createFunctionHomePage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(10);

    QPushButton *conveyorButton = new QPushButton("传送带");
    conveyorButton->setObjectName("featureButton_orange");
    conveyorButton->setFixedHeight(58);
    conveyorButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(conveyorButton, &QPushButton::clicked, this, &MainWindow::showConveyorControlPage);

    QPushButton *ledButton = new QPushButton("LED亮度");
    ledButton->setObjectName("featureButton_blue");
    ledButton->setFixedHeight(58);
    ledButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(ledButton, &QPushButton::clicked, this, &MainWindow::showLedControlPage);

    QPushButton *servoButton = new QPushButton("舵机分拣");
    servoButton->setObjectName("featureButton_purple");
    servoButton->setFixedHeight(58);
    servoButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(servoButton, &QPushButton::clicked, this, &MainWindow::showServoControlPage);

    QPushButton *mangoButton = new QPushButton("当前芒果");
    mangoButton->setObjectName("featureButton_green");
    mangoButton->setFixedHeight(58);
    mangoButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(mangoButton, &QPushButton::clicked, this, &MainWindow::showMangoQualityPage);

    QPushButton *batchButton = new QPushButton("批次统计");
    batchButton->setObjectName("featureButton_indigo");
    batchButton->setFixedHeight(58);
    batchButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(batchButton, &QPushButton::clicked, this, &MainWindow::showBatchStatsPage);

    QPushButton *voiceButton = new QPushButton("语音评价");
    voiceButton->setObjectName("featureButton_blue");
    voiceButton->setFixedHeight(58);
    voiceButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(voiceButton, &QPushButton::clicked, this, &MainWindow::showVoicePromptPage);

    QPushButton *historyButton = new QPushButton("历史记录");
    historyButton->setObjectName("featureButtonProminent");
    historyButton->setFixedHeight(64);
    historyButton->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    connect(historyButton, &QPushButton::clicked, this, &MainWindow::showMangoHistoryPage);

    layout->addWidget(makeFunctionSection("实时使用", {conveyorButton, ledButton, servoButton}));
    layout->addWidget(makeFunctionSection("数据查看", {mangoButton, batchButton, voiceButton, historyButton}));
    layout->addStretch(1);
    return page;
}

QWidget *MainWindow::createConveyorControlPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
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
    QLabel *speedName = new QLabel("档位");
    speedName->setObjectName("controlLabel");
    m_conveyorSpeedValueLabel = new QLabel;
    m_conveyorSpeedValueLabel->setObjectName("speedValue");
    m_conveyorSpeedValueLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    speedHeader->addWidget(speedName);
    speedHeader->addWidget(m_conveyorSpeedValueLabel, 1);

    QHBoxLayout *gearLayout = new QHBoxLayout;
    gearLayout->setSpacing(1);

    m_conveyorSlowButton = new QPushButton("一档\n慢");
    m_conveyorSlowButton->setObjectName("gearLeft");
    m_conveyorSlowButton->setCheckable(true);
    m_conveyorSlowButton->setMinimumHeight(72);
    connect(m_conveyorSlowButton, &QPushButton::clicked, this, [this]() { selectConveyorSpeedGear(0); });

    m_conveyorMediumButton = new QPushButton("二档\n中");
    m_conveyorMediumButton->setObjectName("gearMiddle");
    m_conveyorMediumButton->setCheckable(true);
    m_conveyorMediumButton->setMinimumHeight(72);
    connect(m_conveyorMediumButton, &QPushButton::clicked, this, [this]() { selectConveyorSpeedGear(1); });

    m_conveyorFastButton = new QPushButton("三档\n快");
    m_conveyorFastButton->setObjectName("gearRight");
    m_conveyorFastButton->setCheckable(true);
    m_conveyorFastButton->setMinimumHeight(72);
    connect(m_conveyorFastButton, &QPushButton::clicked, this, [this]() { selectConveyorSpeedGear(2); });

    gearLayout->addWidget(m_conveyorSlowButton);
    gearLayout->addWidget(m_conveyorMediumButton);
    gearLayout->addWidget(m_conveyorFastButton);

    speedLayout->addLayout(speedHeader);
    speedLayout->addLayout(gearLayout);

    QHBoxLayout *runLayout = new QHBoxLayout;
    runLayout->setSpacing(1);

    m_conveyorReverseButton = new QPushButton("< 反转");
    m_conveyorReverseButton->setObjectName("segmentLeft");
    m_conveyorReverseButton->setCheckable(true);
    m_conveyorReverseButton->setMinimumHeight(72);
    connect(m_conveyorReverseButton, &QPushButton::clicked, this, &MainWindow::startConveyorReverse);

    m_conveyorStopButton = new QPushButton("停止");
    m_conveyorStopButton->setObjectName("segmentMiddle");
    m_conveyorStopButton->setCheckable(true);
    m_conveyorStopButton->setChecked(true);
    m_conveyorStopButton->setMinimumHeight(72);
    connect(m_conveyorStopButton, &QPushButton::clicked, this, &MainWindow::stopConveyor);

    m_conveyorForwardButton = new QPushButton("正转 >");
    m_conveyorForwardButton->setObjectName("segmentRight");
    m_conveyorForwardButton->setCheckable(true);
    m_conveyorForwardButton->setMinimumHeight(72);
    connect(m_conveyorForwardButton, &QPushButton::clicked, this, &MainWindow::startConveyorForward);

    runLayout->addWidget(m_conveyorReverseButton);
    runLayout->addWidget(m_conveyorStopButton);
    runLayout->addWidget(m_conveyorForwardButton);

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

    updateConveyorGearButtons();
    return page;
}

QWidget *MainWindow::createLedControlPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
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
    applyButton->setObjectName("primaryControlButton");
    applyButton->setMinimumHeight(64);
    connect(applyButton, &QPushButton::clicked, this, &MainWindow::applyLedBrightness);

    QPushButton *offButton = new QPushButton("关闭");
    offButton->setObjectName("destructiveControlButton");
    offButton->setMinimumHeight(64);
    connect(offButton, &QPushButton::clicked, this, &MainWindow::turnLedOff);

    m_ledAutoButton = new QPushButton("自动调节  关");
    m_ledAutoButton->setObjectName("switchButton");
    m_ledAutoButton->setCheckable(true);
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

QWidget *MainWindow::createMangoQualityPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(8);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(38);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QLabel *title = new QLabel("当前芒果");
    title->setObjectName("controlTitle");

    auto makeRow = [](const QString &name, QLabel **valueLabel) {
        QFrame *row = new QFrame;
        row->setObjectName("qualityRow");
        row->setMinimumHeight(32);
        row->setMaximumHeight(38);
        QHBoxLayout *rowLayout = new QHBoxLayout(row);
        rowLayout->setContentsMargins(8, 2, 8, 2);
        rowLayout->setSpacing(5);

        QLabel *nameLabel = new QLabel(name);
        nameLabel->setObjectName("qualityName");
        nameLabel->setMinimumWidth(70);

        QLabel *value = new QLabel("--");
        value->setObjectName("qualityValue");
        value->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
        value->setWordWrap(false);
        value->setMinimumWidth(0);

        rowLayout->addWidget(nameLabel);
        rowLayout->addWidget(value, 1);
        *valueLabel = value;
        return row;
    };

    QFrame *summaryCard = new QFrame;
    summaryCard->setObjectName("qualitySummaryCard");
    QVBoxLayout *summaryLayout = new QVBoxLayout(summaryCard);
    summaryLayout->setContentsMargins(10, 8, 10, 8);
    summaryLayout->setSpacing(4);

    QHBoxLayout *summaryTop = new QHBoxLayout;
    summaryTop->setSpacing(8);
    QLabel *idName = new QLabel("编号");
    idName->setObjectName("qualityName");
    m_mangoIdValueLabel = new QLabel("--");
    m_mangoIdValueLabel->setObjectName("qualityBadge");
    m_mangoIdValueLabel->setAlignment(Qt::AlignCenter);
    m_mangoGradeValueLabel = new QLabel("--");
    m_mangoGradeValueLabel->setObjectName("qualityBadgeStrong");
    m_mangoGradeValueLabel->setAlignment(Qt::AlignCenter);
    summaryTop->addWidget(idName);
    summaryTop->addWidget(m_mangoIdValueLabel);
    summaryTop->addStretch(1);
    summaryTop->addWidget(m_mangoGradeValueLabel);

    m_mangoFinalValueLabel = new QLabel("--");
    m_mangoFinalValueLabel->setObjectName("qualityConclusion");
    m_mangoFinalValueLabel->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    m_mangoFinalValueLabel->setWordWrap(true);
    m_mangoFinalValueLabel->setMaximumHeight(54);

    m_mangoChannelValueLabel = new QLabel("--");
    m_mangoChannelValueLabel->setObjectName("qualityChannel");
    m_mangoChannelValueLabel->setWordWrap(true);
    m_mangoChannelValueLabel->setMaximumHeight(44);

    summaryLayout->addLayout(summaryTop);
    summaryLayout->addWidget(m_mangoFinalValueLabel);
    summaryLayout->addWidget(m_mangoChannelValueLabel);

    QFrame *scoreCard = new QFrame;
    scoreCard->setObjectName("qualityChartCard");
    QHBoxLayout *scoreLayout = new QHBoxLayout(scoreCard);
    scoreLayout->setContentsMargins(8, 7, 8, 7);
    scoreLayout->setSpacing(8);
    m_mangoScoreChart = new QualityScoreWidget;
    m_mangoScoreChart->setMaximumWidth(132);
    m_mangoFactorChart = new QualityFactorWidget;
    scoreLayout->addWidget(m_mangoScoreChart, 0, Qt::AlignVCenter);
    scoreLayout->addWidget(m_mangoFactorChart, 1);

    QGridLayout *detailGrid = new QGridLayout;
    detailGrid->setContentsMargins(0, 0, 0, 0);
    detailGrid->setHorizontalSpacing(6);
    detailGrid->setVerticalSpacing(6);
    detailGrid->addWidget(makeRow("成熟度", &m_mangoMaturityValueLabel), 0, 0);
    detailGrid->addWidget(makeRow("糖度", &m_mangoSugarValueLabel), 0, 1);
    detailGrid->addWidget(makeRow("腐烂", &m_mangoRotValueLabel), 1, 0);
    detailGrid->addWidget(makeRow("稳定", &m_mangoStabilityValueLabel), 1, 1);
    detailGrid->addWidget(makeRow("YOLO", &m_mangoYoloValueLabel), 2, 0);
    detailGrid->addWidget(makeRow("数据", &m_mangoDataValueLabel), 2, 1);

    layout->addWidget(backButton);
    layout->addWidget(title);
    layout->addWidget(summaryCard);
    layout->addWidget(scoreCard);
    layout->addLayout(detailGrid);

    m_mangoQualityStatusLabel = new QLabel("状态：等待三模态融合结果");
    m_mangoQualityStatusLabel->setObjectName("motorStatus");
    m_mangoQualityStatusLabel->setWordWrap(true);
    m_mangoQualityStatusLabel->hide();

    m_mangoReasonLabel = new QLabel("");
    m_mangoReasonLabel->setObjectName("qualityReason");
    m_mangoReasonLabel->setWordWrap(true);
    m_mangoReasonLabel->setMinimumHeight(0);
    m_mangoReasonLabel->setMaximumHeight(0);
    m_mangoReasonLabel->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    m_mangoReasonLabel->hide();

    layout->addWidget(m_mangoQualityStatusLabel);
    layout->addWidget(m_mangoReasonLabel);
    layout->addStretch(1);

    return page;
}

QWidget *MainWindow::createServoControlPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(10);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(46);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QLabel *title = new QLabel("自动分拣");
    title->setObjectName("controlTitle");

    QLabel *description = new QLabel("自动根据芒果等级与建议流向触发舵机，手动按钮仅用于调试。");
    description->setObjectName("motorStatus");
    description->setWordWrap(true);

    QHBoxLayout *positionLayout = new QHBoxLayout;
    positionLayout->setSpacing(1);

    m_servoPosition1Button = new QPushButton("1号\n-45度");
    m_servoPosition1Button->setObjectName("segmentLeft");
    m_servoPosition1Button->setCheckable(true);
    m_servoPosition1Button->setMinimumHeight(74);
    connect(m_servoPosition1Button, &QPushButton::clicked, this, &MainWindow::moveServoToPosition1);

    m_servoPosition2Button = new QPushButton("2号\n0度");
    m_servoPosition2Button->setObjectName("segmentMiddle");
    m_servoPosition2Button->setCheckable(true);
    m_servoPosition2Button->setMinimumHeight(74);
    connect(m_servoPosition2Button, &QPushButton::clicked, this, &MainWindow::moveServoToPosition2);

    m_servoPosition3Button = new QPushButton("3号\n45度");
    m_servoPosition3Button->setObjectName("segmentRight");
    m_servoPosition3Button->setCheckable(true);
    m_servoPosition3Button->setMinimumHeight(74);
    connect(m_servoPosition3Button, &QPushButton::clicked, this, &MainWindow::moveServoToPosition3);

    positionLayout->addWidget(m_servoPosition1Button);
    positionLayout->addWidget(m_servoPosition2Button);
    positionLayout->addWidget(m_servoPosition3Button);

    m_servoStatusLabel = new QLabel("状态：自动分拣已接入融合程序");
    m_servoStatusLabel->setObjectName("motorStatus");
    m_servoStatusLabel->setWordWrap(true);
    m_servoStatusLabel->setMinimumHeight(56);

    layout->addWidget(backButton);
    layout->addWidget(title);
    layout->addWidget(description);
    layout->addLayout(positionLayout);
    layout->addWidget(m_servoStatusLabel);
    layout->addStretch(1);

    return page;
}

QWidget *MainWindow::createBatchStatsPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(6);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(42);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QScrollArea *scrollArea = new QScrollArea;
    scrollArea->setObjectName("panelScrollArea");
    scrollArea->setWidgetResizable(true);
    scrollArea->setFrameShape(QFrame::NoFrame);
    scrollArea->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);

    QWidget *content = new QWidget;
    content->setObjectName("panelScrollContent");
    QVBoxLayout *contentLayout = new QVBoxLayout(content);
    contentLayout->setContentsMargins(0, 0, 0, 0);
    contentLayout->setSpacing(6);

    QLabel *title = new QLabel("批次统计");
    title->setObjectName("controlTitle");

    QGridLayout *metricGrid = new QGridLayout;
    metricGrid->setContentsMargins(0, 0, 0, 0);
    metricGrid->setHorizontalSpacing(6);
    metricGrid->setVerticalSpacing(6);
    metricGrid->addWidget(makeMetricCard("本批数量", &m_batchTotalValueLabel, "blue"), 0, 0);
    metricGrid->addWidget(makeMetricCard("可销售", &m_batchSaleableValueLabel, "green"), 0, 1);
    metricGrid->addWidget(makeMetricCard("剔除数", &m_batchRejectValueLabel, "red"), 1, 0);
    metricGrid->addWidget(makeMetricCard("最新结果", &m_batchLatestValueLabel, "purple"), 1, 1);

    QLabel *maturityTitle = new QLabel("成熟分布");
    maturityTitle->setObjectName("chartTitle");
    m_batchMaturityChart = new DonutChartWidget;
    m_batchMaturityChart->setMaximumHeight(162);

    QLabel *gradeTitle = new QLabel("品质等级");
    gradeTitle->setObjectName("chartTitle");
    m_batchGradeChart = new BarChartWidget;
    m_batchGradeChart->setMaximumHeight(124);

    QLabel *channelTitle = new QLabel("分拣流向");
    channelTitle->setObjectName("chartTitle");
    m_batchChannelChart = new BarChartWidget;
    m_batchChannelChart->setMaximumHeight(124);

    m_batchStatusLabel = new QLabel("状态：等待批次统计");
    m_batchStatusLabel->setObjectName("motorStatus");
    m_batchStatusLabel->setWordWrap(true);

    m_batchSummaryLabel = new QLabel("当前批次尚未完成芒果计数。");
    m_batchSummaryLabel->setObjectName("qualityReason");
    m_batchSummaryLabel->setWordWrap(true);
    m_batchSummaryLabel->setMinimumHeight(42);
    m_batchSummaryLabel->setMaximumHeight(64);

    contentLayout->addWidget(title);
    contentLayout->addLayout(metricGrid);
    contentLayout->addWidget(maturityTitle);
    contentLayout->addWidget(m_batchMaturityChart);
    contentLayout->addWidget(gradeTitle);
    contentLayout->addWidget(m_batchGradeChart);
    contentLayout->addWidget(channelTitle);
    contentLayout->addWidget(m_batchChannelChart);
    contentLayout->addWidget(m_batchStatusLabel);
    contentLayout->addWidget(m_batchSummaryLabel);
    contentLayout->addStretch(1);

    scrollArea->setWidget(content);

    layout->addWidget(backButton);
    layout->addWidget(scrollArea, 1);

    refreshBatchStatsData();
    return page;
}

QWidget *MainWindow::createVoicePromptPage()
{
    QWidget *page = new QWidget;
    page->setMinimumSize(0, 0);
    page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(12);

    QPushButton *backButton = new QPushButton("返回功能区");
    backButton->setObjectName("secondaryButton");
    backButton->setMinimumHeight(46);
    connect(backButton, &QPushButton::clicked, this, &MainWindow::showFunctionHomePage);

    QLabel *title = new QLabel("语音评价");
    title->setObjectName("controlTitle");

    m_voicePreviousButton = new QPushButton("评价上一个芒果");
    m_voicePreviousButton->setObjectName("primaryControlButton");
    m_voicePreviousButton->setMinimumHeight(76);
    connect(m_voicePreviousButton, &QPushButton::clicked, this, &MainWindow::announcePreviousMango);

    m_voiceBatchButton = new QPushButton("评价整批芒果");
    m_voiceBatchButton->setObjectName("primaryControlButton");
    m_voiceBatchButton->setMinimumHeight(76);
    connect(m_voiceBatchButton, &QPushButton::clicked, this, &MainWindow::announceBatchMango);

    m_voicePromptStatusLabel = new QLabel("状态：等待语音评价");
    m_voicePromptStatusLabel->setObjectName("motorStatus");
    m_voicePromptStatusLabel->setWordWrap(true);
    m_voicePromptStatusLabel->setMinimumHeight(70);

    layout->addWidget(backButton);
    layout->addWidget(title);
    layout->addWidget(m_voicePreviousButton);
    layout->addWidget(m_voiceBatchButton);
    layout->addWidget(m_voicePromptStatusLabel);
    layout->addStretch(1);

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
    return label;
}

QFrame *MainWindow::makeMetricCard(const QString &name, QLabel **valueLabel, const QString &accentName)
{
    QFrame *card = new QFrame;
    card->setObjectName(accentName.isEmpty() ? "metricCard" : QString("metricCard_") + accentName);
    card->setMinimumHeight(70);
    card->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);

    QVBoxLayout *layout = new QVBoxLayout(card);
    layout->setContentsMargins(10, 6, 10, 8);
    layout->setSpacing(2);

    QLabel *nameLabel = new QLabel(name);
    nameLabel->setObjectName("metricName");

    QLabel *value = new QLabel("--");
    value->setObjectName("metricValue");
    value->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    value->setWordWrap(true);

    layout->addWidget(nameLabel);
    layout->addWidget(value, 1);
    *valueLabel = value;
    return card;
}

QFrame *MainWindow::makeFunctionSection(const QString &title, const QList<QPushButton *> &buttons)
{
    QFrame *section = new QFrame;
    section->setObjectName("functionSection");
    section->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);

    QVBoxLayout *layout = new QVBoxLayout(section);
    layout->setContentsMargins(10, 10, 10, 10);
    layout->setSpacing(8);

    QLabel *titleLabel = new QLabel(title);
    titleLabel->setObjectName("functionSectionTitle");
    layout->addWidget(titleLabel);

    for (QPushButton *button : buttons) {
        layout->addWidget(button);
    }

    return section;
}

void MainWindow::applyGlobalStyle()
{
    qApp->setStyleSheet(
        "QMainWindow, QWidget#startPage, QWidget#workPage, QWidget#historyPage {"
        "  background: #F4F6F1;"
        "  color: #1F2933;"
        "}"
        "QLabel {"
        "  color: #1F2933;"
        "}"
        "QLabel#startLogo {"
        "  background: transparent;"
        "}"
        "QLabel#startTitle {"
        "  color: #26352A;"
        "  font-size: 48px;"
        "  font-weight: 700;"
        "  letter-spacing: 0px;"
        "}"
        "QPushButton#startButton {"
        "  background: #2F6B4F;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 30px;"
        "  font-weight: 700;"
        "  padding: 12px 28px;"
        "}"
        "QPushButton#startButton:pressed {"
        "  background: #244F3B;"
        "}"
        "QPushButton#exitButton {"
        "  background: #ffffff;"
        "  color: #A53A32;"
        "  border: 1px solid #E8C7C2;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#exitButton:pressed {"
        "  background: #FBEDEA;"
        "}"
        "QPushButton#featureButton, QPushButton#featureButton_orange, QPushButton#featureButton_blue, QPushButton#featureButton_purple, QPushButton#featureButton_green, QPushButton#featureButton_indigo {"
        "  color: #26352A;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#featureButton { background: #ffffff; border: 1px solid #D8DED3; }"
        "QPushButton#featureButton_orange { background: #FFF4D8; color: #7A4B12; border: 1px solid #E9C879; }"
        "QPushButton#featureButton_blue { background: #EAF1EE; color: #2D5C4A; border: 1px solid #C8D8D0; }"
        "QPushButton#featureButton_purple { background: #F2EFE6; color: #604E2F; border: 1px solid #D9CFB8; }"
        "QPushButton#featureButton_green { background: #E7F3EA; color: #1F6A43; border: 1px solid #B7D7C0; }"
        "QPushButton#featureButton_indigo { background: #EEF0F3; color: #45505A; border: 1px solid #D0D6DC; }"
        "QPushButton#featureButton:pressed, QPushButton#featureButton_orange:pressed, QPushButton#featureButton_blue:pressed, QPushButton#featureButton_purple:pressed, QPushButton#featureButton_green:pressed, QPushButton#featureButton_indigo:pressed { background: #ffffff; }"
        "QPushButton#featureButtonProminent {"
        "  background: #C77B2B;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 21px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#featureButtonProminent:pressed {"
        "  background: #9C5D1B;"
        "}"
        "QFrame#functionSection {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 8px;"
        "}"
        "QLabel#functionSectionTitle {"
        "  color: #697468;"
        "  font-size: 16px;"
        "  font-weight: 700;"
        "}"
        "QPushButton#secondaryButton {"
        "  background: #EAF1EE;"
        "  color: #2D5C4A;"
        "  border: 1px solid #C8D8D0;"
        "  border-radius: 7px;"
        "  font-size: 18px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#runButton {"
        "  background: #ffffff;"
        "  color: #2F6B4F;"
        "  border: 1px solid #B7D7C0;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#runButton:pressed {"
        "  background: #E7F3EA;"
        "}"
        "QPushButton#stopButton {"
        "  background: #A53A32;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#stopButton:pressed {"
        "  background: #7F2B25;"
        "}"
        "QPushButton#primaryControlButton {"
        "  background: #2F6B4F;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#primaryControlButton:pressed {"
        "  background: #244F3B;"
        "}"
        "QPushButton#destructiveControlButton {"
        "  background: #FBEDEA;"
        "  color: #A53A32;"
        "  border: 1px solid #E8C7C2;"
        "  border-radius: 8px;"
        "  font-size: 20px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#destructiveControlButton:pressed {"
        "  background: #F3D6D1;"
        "}"
        "QPushButton#switchButton {"
        "  background: #EEF0F3;"
        "  color: #45505A;"
        "  border: 1px solid #D0D6DC;"
        "  border-radius: 8px;"
        "  font-size: 19px;"
        "  font-weight: 700;"
        "  padding: 10px;"
        "}"
        "QPushButton#switchButton:checked {"
        "  background: #2F6B4F;"
        "  color: white;"
        "  border: 1px solid #2F6B4F;"
        "}"
        "QPushButton#segmentLeft, QPushButton#segmentMiddle, QPushButton#segmentRight, QPushButton#gearLeft, QPushButton#gearMiddle, QPushButton#gearRight {"
        "  background: #EEF0F3;"
        "  color: #1F2933;"
        "  border: 1px solid #D0D6DC;"
        "  border-radius: 0px;"
        "  font-size: 18px;"
        "  font-weight: 700;"
        "  padding: 8px;"
        "}"
        "QPushButton#segmentLeft, QPushButton#gearLeft {"
        "  border-top-left-radius: 8px;"
        "  border-bottom-left-radius: 8px;"
        "}"
        "QPushButton#segmentMiddle, QPushButton#gearMiddle {"
        "  border-radius: 0px;"
        "}"
        "QPushButton#segmentRight, QPushButton#gearRight {"
        "  border-top-right-radius: 8px;"
        "  border-bottom-right-radius: 8px;"
        "}"
        "QPushButton#segmentLeft:checked, QPushButton#segmentMiddle:checked, QPushButton#segmentRight:checked, QPushButton#gearLeft:checked, QPushButton#gearMiddle:checked, QPushButton#gearRight:checked {"
        "  background: #2F6B4F;"
        "  color: white;"
        "  border-color: #2F6B4F;"
        "}"
        "QPushButton#segmentLeft:pressed, QPushButton#segmentMiddle:pressed, QPushButton#segmentRight:pressed, QPushButton#gearLeft:pressed, QPushButton#gearMiddle:pressed, QPushButton#gearRight:pressed {"
        "  background: #DDE7E1;"
        "}"
        "QFrame#videoPanel, QFrame#sensorPanel, QFrame#functionPanel {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 8px;"
        "}"
        "QLabel#panelTitle {"
        "  font-size: 21px;"
        "  font-weight: 700;"
        "  color: #26352A;"
        "}"
        "QLabel#networkStatus {"
        "  background: #EEF0F3;"
        "  color: #45505A;"
        "  border: 1px solid #D0D6DC;"
        "  border-radius: 14px;"
        "  font-size: 15px;"
        "  font-weight: 700;"
        "  padding: 3px 12px;"
        "}"
        "QLabel#networkStatus[state=\"online\"] {"
        "  background: #E7F3EA;"
        "  color: #1F6A43;"
        "  border: 1px solid #B7D7C0;"
        "}"
        "QLabel#networkStatus[state=\"warning\"] {"
        "  background: #FFF4D8;"
        "  color: #7A4B12;"
        "  border: 1px solid #E9C879;"
        "}"
        "QLabel#networkStatus[state=\"offline\"] {"
        "  background: #FBEDEA;"
        "  color: #A53A32;"
        "  border: 1px solid #E8C7C2;"
        "}"
        "QLabel#networkStatus[state=\"checking\"] {"
        "  background: #EEF0F3;"
        "  color: #45505A;"
        "  border: 1px solid #D0D6DC;"
        "}"
        "QFrame#videoSurface {"
        "  background: #101713;"
        "  border: 1px solid #26352A;"
        "  border-radius: 6px;"
        "}"
        "QWidget#videoState {"
        "  color: #F2F2F7;"
        "  font-size: 28px;"
        "  font-weight: 700;"
        "}"
        "QLabel#sensorStatus {"
        "  color: #697468;"
        "  font-size: 16px;"
        "}"
        "QFrame#sensorCard, QFrame#sensorCard_0, QFrame#sensorCard_1, QFrame#sensorCard_2, QFrame#sensorCard_3, QFrame#sensorCard_4, QFrame#sensorCard_5 {"
        "  border-radius: 7px;"
        "}"
        "QFrame#sensorCard { background: #F7F8F4; border: 1px solid #D8DED3; }"
        "QFrame#sensorCard_0 { background: #FFF4D8; border: 1px solid #E9C879; }"
        "QFrame#sensorCard_1 { background: #E7F3EA; border: 1px solid #B7D7C0; }"
        "QFrame#sensorCard_2 { background: #EEF0F3; border: 1px solid #D0D6DC; }"
        "QFrame#sensorCard_3 { background: #FFF8E6; border: 1px solid #E7D390; }"
        "QFrame#sensorCard_4 { background: #EAF1EE; border: 1px solid #C8D8D0; }"
        "QFrame#sensorCard_5 { background: #F2EFE6; border: 1px solid #D9CFB8; }"
        "QLabel#sensorName {"
        "  font-size: 15px;"
        "  color: #697468;"
        "}"
        "QLabel#sensorValue {"
        "  font-size: 21px;"
        "  font-weight: 700;"
        "  color: #26352A;"
        "}"
        "QLabel#functionPlaceholder {"
        "  background: #F7F8F4;"
        "  border: 1px dashed #C8D8D0;"
        "  border-radius: 7px;"
        "  color: #697468;"
        "  font-size: 19px;"
        "  line-height: 150%;"
        "}"
        "QLabel#controlTitle {"
        "  color: #26352A;"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "}"
        "QLabel#chartTitle {"
        "  color: #3E4A3F;"
        "  font-size: 16px;"
        "  font-weight: 700;"
        "}"
        "QFrame#controlCard {"
        "  background: #F7F8F4;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 7px;"
        "}"
        "QLabel#controlLabel {"
        "  color: #697468;"
        "  font-size: 18px;"
        "}"
        "QLabel#speedValue {"
        "  color: #26352A;"
        "  font-size: 24px;"
        "  font-weight: 700;"
        "}"
        "QLabel#motorStatus {"
        "  color: #697468;"
        "  font-size: 18px;"
        "}"
        "QFrame#qualitySummaryCard, QFrame#qualityChartCard {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 8px;"
        "}"
        "QLabel#qualityBadge {"
        "  background: #F2EFE6;"
        "  color: #604E2F;"
        "  border: 1px solid #D9CFB8;"
        "  border-radius: 8px;"
        "  font-size: 14px;"
        "  font-weight: 700;"
        "  padding: 3px 8px;"
        "}"
        "QLabel#qualityBadgeStrong {"
        "  background: #E7F3EA;"
        "  color: #1F6A43;"
        "  border: 1px solid #B7D7C0;"
        "  border-radius: 8px;"
        "  font-size: 15px;"
        "  font-weight: 700;"
        "  padding: 3px 10px;"
        "}"
        "QLabel#qualityConclusion {"
        "  color: #26352A;"
        "  font-size: 21px;"
        "  font-weight: 700;"
        "}"
        "QLabel#qualityChannel {"
        "  color: #697468;"
        "  font-size: 14px;"
        "  font-weight: 700;"
        "}"
        "QFrame#qualityRow {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 7px;"
        "}"
        "QLabel#qualityName {"
        "  color: #697468;"
        "  font-size: 13px;"
        "  font-weight: 700;"
        "}"
        "QLabel#qualityValue {"
        "  color: #26352A;"
        "  font-size: 13px;"
        "  font-weight: 700;"
        "}"
        "QLabel#qualityReason {"
        "  color: #45505A;"
        "  font-size: 16px;"
        "  line-height: 140%;"
        "}"
        "QFrame#metricCard_blue, QFrame#metricCard_green, QFrame#metricCard_red, QFrame#metricCard_purple, QFrame#metricCard {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 7px;"
        "}"
        "QFrame#metricCard_blue { background: #EAF1EE; border: 1px solid #C8D8D0; }"
        "QFrame#metricCard_green { background: #E7F3EA; border: 1px solid #B7D7C0; }"
        "QFrame#metricCard_red { background: #FBEDEA; border: 1px solid #E8C7C2; }"
        "QFrame#metricCard_purple { background: #F2EFE6; border: 1px solid #D9CFB8; }"
        "QLabel#metricName {"
        "  color: #697468;"
        "  font-size: 14px;"
        "  font-weight: 700;"
        "}"
        "QLabel#metricValue {"
        "  color: #26352A;"
        "  font-size: 22px;"
        "  font-weight: 700;"
        "}"
        "QWidget#chartCanvas {"
        "  background: #FFFFFF;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 7px;"
        "}"
        "QScrollArea#panelScrollArea {"
        "  background: transparent;"
        "  border: none;"
        "}"
        "QWidget#panelScrollContent {"
        "  background: transparent;"
        "}"
        "QScrollBar:vertical {"
        "  background: transparent;"
        "  width: 8px;"
        "  margin: 0;"
        "}"
        "QScrollBar::handle:vertical {"
        "  background: #C8D8D0;"
        "  border-radius: 4px;"
        "}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
        "  height: 0px;"
        "}"
        "QLabel#historyTitle {"
        "  color: #26352A;"
        "  font-size: 34px;"
        "  font-weight: 700;"
        "}"
        "QLabel#historySummary {"
        "  color: #45505A;"
        "  font-size: 18px;"
        "  font-weight: 600;"
        "}"
        "QTableWidget#historyTable {"
        "  background: #FFFFFF;"
        "  alternate-background-color: #F7F8F4;"
        "  border: 1px solid #D8DED3;"
        "  border-radius: 8px;"
        "  color: #1F2933;"
        "  font-size: 17px;"
        "  gridline-color: transparent;"
        "}"
        "QTableWidget#historyTable::item {"
        "  padding: 10px;"
        "}"
        "QHeaderView::section {"
        "  background: #EAF1EE;"
        "  color: #2D5C4A;"
        "  border: none;"
        "  padding: 10px;"
        "  font-size: 16px;"
        "  font-weight: 700;"
        "}"
        "QSlider#speedSlider::groove:horizontal {"
        "  height: 6px;"
        "  background: #D8DED3;"
        "  border-radius: 3px;"
        "}"
        "QSlider#speedSlider::sub-page:horizontal {"
        "  background: #2F6B4F;"
        "  border-radius: 3px;"
        "}"
        "QSlider#speedSlider::handle:horizontal {"
        "  width: 30px;"
        "  height: 30px;"
        "  margin: -12px 0;"
        "  border-radius: 8px;"
        "  background: #ffffff;"
        "  border: 1px solid #C8D8D0;"
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

    m_sensorStatusLabel->clear();
}

void MainWindow::startSensorProcess()
{
    if (m_sensorProcess->state() != QProcess::NotRunning) {
        return;
    }

    QStringList args;
    args << kSensorCsvScript
         << "--output-dir" << kSensorCsvDirectory
         << "--interval" << QString::number(kEnvironmentSampleIntervalS)
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
    if (!m_sensorProcess->waitForFinished(kSensorStopWaitMs)) {
        m_sensorProcess->kill();
        m_sensorProcess->waitForFinished(1000);
    }
}

void MainWindow::startMangoQualityProcess()
{
    if (m_mangoQualityProcess->state() != QProcess::NotRunning) {
        return;
    }

    QStringList args;
    args << kMangoQualityScript
         << "--interval" << "0.5"
         << "--parent-pid" << QString::number(QCoreApplication::applicationPid());

    m_mangoQualityProcess->setWorkingDirectory("/home/elf/projects");
    m_mangoQualityProcess->start("python3", args);

    if (!m_mangoQualityProcess->waitForStarted(1000) && m_mangoQualityStatusLabel) {
        m_mangoQualityStatusLabel->setText("状态：三模态融合程序启动失败");
    }
}

void MainWindow::stopMangoQualityProcess()
{
    if (m_mangoQualityProcess->state() == QProcess::NotRunning) {
        return;
    }

    m_mangoQualityProcess->terminate();
    if (!m_mangoQualityProcess->waitForFinished(1500)) {
        m_mangoQualityProcess->kill();
        m_mangoQualityProcess->waitForFinished(1000);
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

void MainWindow::startTuyaIotProcess()
{
    if (m_tuyaIotProcess->state() != QProcess::NotRunning) {
        return;
    }

    if (isTuyaIotProcessRunning()) {
        m_tuyaIotStartedByQt = false;
        setIotStatusText("物联网运行中", "checking");
        return;
    }

    const QFileInfo elfInfo(kTuyaIotElf);
    if (!elfInfo.exists() || !elfInfo.isExecutable()) {
        setIotStatusText("物联网程序缺失", "offline");
        return;
    }

    m_tuyaIotProcess->setWorkingDirectory(kTuyaIotWorkDir);
    m_tuyaIotProcess->start(kTuyaIotElf, QStringList());
    if (m_tuyaIotProcess->waitForStarted(1200)) {
        m_tuyaIotStartedByQt = true;
        setIotStatusText("物联网启动中", "checking");
    } else {
        m_tuyaIotStartedByQt = false;
        setIotStatusText("物联网启动失败", "offline");
    }
}

void MainWindow::stopTuyaIotProcess()
{
    if (!m_tuyaIotStartedByQt || m_tuyaIotProcess->state() == QProcess::NotRunning) {
        return;
    }

    m_tuyaIotProcess->terminate();
    if (!m_tuyaIotProcess->waitForFinished(2000)) {
        m_tuyaIotProcess->kill();
        m_tuyaIotProcess->waitForFinished(1000);
    }
    m_tuyaIotStartedByQt = false;
}

bool MainWindow::isTuyaIotProcessRunning() const
{
    if (m_tuyaIotProcess->state() != QProcess::NotRunning) {
        return true;
    }

    const int exitCode = QProcess::execute("pgrep", {"-f", kTuyaIotProcessPattern});
    return exitCode == 0;
}

void MainWindow::setIotStatusText(const QString &text, const QString &state)
{
    if (!m_networkStatusLabel) {
        return;
    }

    m_networkStatusLabel->setText(text);
    m_networkStatusLabel->setProperty("state", state);
    m_networkStatusLabel->style()->unpolish(m_networkStatusLabel);
    m_networkStatusLabel->style()->polish(m_networkStatusLabel);
    m_networkStatusLabel->update();
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
    if (m_videoSurface) {
        m_videoSurface->setAspectRatioFromSize(frame.size());
    }
    rescaleCameraFrame();
}

void MainWindow::rescaleCameraFrame()
{
    if (!m_videoDisplay || m_latestFrame.isNull()) {
        return;
    }

    m_videoDisplay->setFrame(m_latestFrame);
}

void MainWindow::setVideoMessage(const QString &message)
{
    if (!m_videoDisplay) {
        return;
    }

    m_videoDisplay->setMessage(message);
}

double MainWindow::currentConveyorSpeed() const
{
    if (m_conveyorSpeedGear == 0) {
        return m_conveyorSlowSpeedMs;
    }
    if (m_conveyorSpeedGear == 2) {
        return m_conveyorFastSpeedMs;
    }
    return m_conveyorMediumSpeedMs;
}

QString MainWindow::currentConveyorGearName() const
{
    if (m_conveyorSpeedGear == 0) {
        return "一档 慢";
    }
    if (m_conveyorSpeedGear == 2) {
        return "三档 快";
    }
    return "二档 中";
}

void MainWindow::selectConveyorSpeedGear(int gear)
{
    m_conveyorSpeedGear = qMax(0, qMin(2, gear));
    updateConveyorGearButtons();
    applyConveyorSpeed();
}

void MainWindow::updateConveyorGearButtons()
{
    if (m_conveyorSlowButton) {
        m_conveyorSlowButton->setChecked(m_conveyorSpeedGear == 0);
        m_conveyorSlowButton->setText(QString("一档\n慢 %1").arg(m_conveyorSlowSpeedMs, 0, 'f', 2));
    }
    if (m_conveyorMediumButton) {
        m_conveyorMediumButton->setChecked(m_conveyorSpeedGear == 1);
        m_conveyorMediumButton->setText(QString("二档\n中 %1").arg(m_conveyorMediumSpeedMs, 0, 'f', 2));
    }
    if (m_conveyorFastButton) {
        m_conveyorFastButton->setChecked(m_conveyorSpeedGear == 2);
        m_conveyorFastButton->setText(QString("三档\n快 %1").arg(m_conveyorFastSpeedMs, 0, 'f', 2));
    }
    if (m_conveyorSpeedValueLabel) {
        m_conveyorSpeedValueLabel->setText(QString("%1  %2 m/s")
                                           .arg(currentConveyorGearName())
                                           .arg(currentConveyorSpeed(), 0, 'f', 2));
    }
}

void MainWindow::updateConveyorRunButtons()
{
    if (m_conveyorForwardButton) {
        m_conveyorForwardButton->setChecked(m_conveyorDirection > 0);
    }
    if (m_conveyorReverseButton) {
        m_conveyorReverseButton->setChecked(m_conveyorDirection < 0);
    }
    if (m_conveyorStopButton) {
        m_conveyorStopButton->setChecked(m_conveyorDirection == 0);
    }
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
    updateConveyorRunButtons();
    runMotorCommand("forward");
}

void MainWindow::startConveyorReverse()
{
    m_conveyorDirection = -1;
    m_conveyorWasStarted = true;
    updateConveyorRunButtons();
    runMotorCommand("reverse");
}

void MainWindow::stopConveyor()
{
    const bool shouldSendStop = m_conveyorWasStarted || m_conveyorDirection != 0;
    m_conveyorDirection = 0;
    m_conveyorWasStarted = false;
    updateConveyorRunButtons();
    if (shouldSendStop) {
        runMotorCommand("stop");
    } else if (m_motorStatusLabel) {
        m_motorStatusLabel->setText("状态：已停止");
    }
}

void MainWindow::runMotorCommand(const QString &command)
{
    if (m_motorCommandProcess->state() != QProcess::NotRunning) {
        m_motorCommandProcess->kill();
        m_motorCommandProcess->waitForFinished(100);
    }

    QStringList args;
    args << kMotorCommandScript << command;
    if (command != "stop") {
        args << "--speed-ms" << QString::number(currentConveyorSpeed(), 'f', 2);
    }

    const QString displayCommand = command;
    const double displaySpeed = currentConveyorSpeed();
    const QString displayGear = currentConveyorGearName();

    if (m_motorStatusLabel) {
        if (command == "forward") {
            m_motorStatusLabel->setText(QString("状态：正在切换 正转 %1 %2 m/s")
                                        .arg(displayGear)
                                        .arg(displaySpeed, 0, 'f', 2));
        } else if (command == "reverse") {
            m_motorStatusLabel->setText(QString("状态：正在切换 反转 %1 %2 m/s")
                                        .arg(displayGear)
                                        .arg(displaySpeed, 0, 'f', 2));
        } else {
            m_motorStatusLabel->setText("状态：正在停止");
        }
    }

    m_motorCommandProcess->setWorkingDirectory("/home/elf/projects");
    m_motorCommandProcess->start("python3", args);

    if (!m_motorCommandProcess->waitForStarted(80)) {
        if (m_motorStatusLabel) {
            m_motorStatusLabel->setText("状态：电机命令启动失败");
        }
    }

    QProcess *process = m_motorCommandProcess;
    disconnect(process,
               static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
               this,
               nullptr);
    connect(process,
            static_cast<void (QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished),
            this,
            [this, process, displayCommand, displaySpeed, displayGear](int exitCode, QProcess::ExitStatus exitStatus) {
                const QString output = QString::fromLocal8Bit(process->readAllStandardOutput()).trimmed();
                const QString error = QString::fromLocal8Bit(process->readAllStandardError()).trimmed();

                if (!m_motorStatusLabel) {
                    return;
                }

                if (exitStatus == QProcess::NormalExit && exitCode == 0) {
                    if (displayCommand == "forward") {
                        m_motorStatusLabel->setText(QString("状态：正转 %1 %2 m/s")
                                                    .arg(displayGear)
                                                    .arg(displaySpeed, 0, 'f', 2));
                    } else if (displayCommand == "reverse") {
                        m_motorStatusLabel->setText(QString("状态：反转 %1 %2 m/s")
                                                    .arg(displayGear)
                                                    .arg(displaySpeed, 0, 'f', 2));
                    } else {
                        m_motorStatusLabel->setText("状态：已停止");
                    }
                } else {
                    const QString message = !error.isEmpty() ? error : output;
                    m_motorStatusLabel->setText("状态：命令失败 " + message.left(80));
                }
            });
}

void MainWindow::loadConveyorSpeedRange()
{
    QFile file(kMotorConfigFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return;
    }

    QTextStream stream(&file);
    stream.setCodec("UTF-8");
    bool inConveyorSection = false;
    double minSpeed = m_conveyorMinSpeedX10 / 10.0;
    double maxSpeed = m_conveyorMaxSpeedX10 / 10.0;
    double defaultSpeed = m_conveyorDefaultSpeedX10 / 10.0;
    double slowSpeed = m_conveyorSlowSpeedMs;
    double mediumSpeed = m_conveyorMediumSpeedMs;
    double fastSpeed = m_conveyorFastSpeedMs;

    while (!stream.atEnd()) {
        const QString rawLine = stream.readLine();
        const QString trimmed = rawLine.trimmed();
        if (trimmed.isEmpty() || trimmed.startsWith("#")) {
            continue;
        }

        const int indent = rawLine.size() - rawLine.trimmed().size();
        if (indent == 2 && trimmed == "conveyor:") {
            inConveyorSection = true;
            continue;
        }
        if (inConveyorSection && indent <= 2 && trimmed.endsWith(":")) {
            break;
        }
        if (!inConveyorSection || indent < 4) {
            continue;
        }

        const int colon = trimmed.indexOf(':');
        if (colon <= 0) {
            continue;
        }

        const QString key = trimmed.left(colon).trimmed();
        QString value = trimmed.mid(colon + 1).trimmed();
        const int comment = value.indexOf('#');
        if (comment >= 0) {
            value = value.left(comment).trimmed();
        }

        bool ok = false;
        const double number = value.toDouble(&ok);
        if (!ok) {
            continue;
        }

        if (key == "min_speed_ms") {
            minSpeed = number;
        } else if (key == "max_speed_ms") {
            maxSpeed = number;
        } else if (key == "default_speed_ms") {
            defaultSpeed = number;
        } else if (key == "slow_speed_ms") {
            slowSpeed = number;
        } else if (key == "medium_speed_ms") {
            mediumSpeed = number;
        } else if (key == "fast_speed_ms") {
            fastSpeed = number;
        }
    }

    if (minSpeed <= 0.0 || maxSpeed <= minSpeed) {
        return;
    }

    m_conveyorMinSpeedX10 = qMax(1, static_cast<int>(qRound(minSpeed * 10.0)));
    m_conveyorMaxSpeedX10 = qMax(m_conveyorMinSpeedX10, static_cast<int>(qRound(maxSpeed * 10.0)));
    m_conveyorDefaultSpeedX10 = static_cast<int>(qRound(defaultSpeed * 10.0));
    m_conveyorDefaultSpeedX10 = qMax(m_conveyorMinSpeedX10, qMin(m_conveyorMaxSpeedX10, m_conveyorDefaultSpeedX10));
    m_conveyorSlowSpeedMs = qMax(minSpeed, qMin(maxSpeed, slowSpeed));
    m_conveyorMediumSpeedMs = qMax(minSpeed, qMin(maxSpeed, mediumSpeed));
    m_conveyorFastSpeedMs = qMax(minSpeed, qMin(maxSpeed, fastSpeed));
    if (m_conveyorSlowSpeedMs > m_conveyorMediumSpeedMs) {
        qSwap(m_conveyorSlowSpeedMs, m_conveyorMediumSpeedMs);
    }
    if (m_conveyorMediumSpeedMs > m_conveyorFastSpeedMs) {
        qSwap(m_conveyorMediumSpeedMs, m_conveyorFastSpeedMs);
    }
    if (defaultSpeed <= (m_conveyorSlowSpeedMs + m_conveyorMediumSpeedMs) * 0.5) {
        m_conveyorSpeedGear = 0;
    } else if (defaultSpeed >= (m_conveyorMediumSpeedMs + m_conveyorFastSpeedMs) * 0.5) {
        m_conveyorSpeedGear = 2;
    } else {
        m_conveyorSpeedGear = 1;
    }
}

void MainWindow::moveServoToPosition1()
{
    if (m_servoPosition1Button) {
        m_servoPosition1Button->setChecked(true);
    }
    if (m_servoPosition2Button) {
        m_servoPosition2Button->setChecked(false);
    }
    if (m_servoPosition3Button) {
        m_servoPosition3Button->setChecked(false);
    }
    runServoCommand("1", "1号 -45度");
}

void MainWindow::moveServoToPosition2()
{
    if (m_servoPosition1Button) {
        m_servoPosition1Button->setChecked(false);
    }
    if (m_servoPosition2Button) {
        m_servoPosition2Button->setChecked(true);
    }
    if (m_servoPosition3Button) {
        m_servoPosition3Button->setChecked(false);
    }
    runServoCommand("2", "2号 0度");
}

void MainWindow::moveServoToPosition3()
{
    if (m_servoPosition1Button) {
        m_servoPosition1Button->setChecked(false);
    }
    if (m_servoPosition2Button) {
        m_servoPosition2Button->setChecked(false);
    }
    if (m_servoPosition3Button) {
        m_servoPosition3Button->setChecked(true);
    }
    runServoCommand("3", "3号 45度");
}

void MainWindow::runVoicePromptCommand(const QString &target, const QString &label)
{
    if (m_voicePromptProcess->state() != QProcess::NotRunning) {
        if (m_voicePromptStatusLabel) {
            m_voicePromptStatusLabel->setText("状态：语音评价正在进行，请稍候");
        }
        return;
    }

    if (m_voicePreviousButton) {
        m_voicePreviousButton->setEnabled(false);
    }
    if (m_voiceBatchButton) {
        m_voiceBatchButton->setEnabled(false);
    }
    if (m_voicePromptStatusLabel) {
        m_voicePromptStatusLabel->setText("状态：正在评价" + label);
    }

    QStringList args;
    const QString voiceBackend = qEnvironmentVariable("VOICE_BACKEND", kDefaultVoiceBackend).trimmed();
    const QString edgeVoice = qEnvironmentVariable("VOICE_EDGE_VOICE", kDefaultVoiceEdgeVoice).trimmed();
    const QString alsaDevice = qEnvironmentVariable("VOICE_ALSA_DEVICE", kDefaultVoiceAlsaDevice).trimmed();
    const QString ttsTimeout = qEnvironmentVariable("VOICE_TTS_TIMEOUT", "12").trimmed();
    args << kVoiceAssistantScript
         << "--once"
         << "--target" << target
         << "--speak-invalid"
         << "--timeout" << "5";
    if (!voiceBackend.isEmpty()) {
        args << "--backend" << voiceBackend;
    }
    if (!edgeVoice.isEmpty()) {
        args << "--edge-voice" << edgeVoice;
    }
    if (!ttsTimeout.isEmpty()) {
        args << "--tts-timeout" << ttsTimeout;
    }
    if (!alsaDevice.isEmpty()) {
        args << "--alsa-device" << alsaDevice;
    }

    m_voicePromptProcess->setWorkingDirectory("/home/elf/projects");
    m_voicePromptProcess->start("python3", args);

    if (!m_voicePromptProcess->waitForStarted(500)) {
        if (m_voicePreviousButton) {
            m_voicePreviousButton->setEnabled(true);
        }
        if (m_voiceBatchButton) {
            m_voiceBatchButton->setEnabled(true);
        }
        if (m_voicePromptStatusLabel) {
            m_voicePromptStatusLabel->setText("状态：语音评价程序启动失败");
        }
    }
}

void MainWindow::runServoCommand(const QString &position, const QString &label)
{
    if (m_servoStatusLabel) {
        m_servoStatusLabel->setText("状态：正在旋转到 " + label);
    }

    QStringList args;
    args << kServoCommandScript << position;

    QProcess process;
    process.setWorkingDirectory("/home/elf/projects");
    process.start("python3", args);
    if (!process.waitForStarted(1000)) {
        if (m_servoStatusLabel) {
            m_servoStatusLabel->setText("状态：舵机命令启动失败");
        }
        return;
    }

    process.waitForFinished(4000);
    const QString output = QString::fromLocal8Bit(process.readAllStandardOutput()).trimmed();
    const QString error = QString::fromLocal8Bit(process.readAllStandardError()).trimmed();

    if (process.state() != QProcess::NotRunning) {
        process.kill();
        process.waitForFinished(500);
        if (m_servoStatusLabel) {
            m_servoStatusLabel->setText("状态：舵机命令超时");
        }
        return;
    }

    if (!m_servoStatusLabel) {
        return;
    }

    if (process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0) {
        m_servoStatusLabel->setText(output.isEmpty() ? "状态：已旋转到 " + label : "状态：" + output);
    } else {
        const QString message = !error.isEmpty() ? error : output;
        m_servoStatusLabel->setText("状态：舵机命令失败 " + message.left(140));
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
        m_ledAutoButton->setChecked(false);
        m_ledAutoButton->setText("自动调节  关");
    }
    m_ledHasFilteredLux = false;
    m_ledLastAutoAdjustMs = 0;

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
        m_ledAutoButton->setChecked(false);
        m_ledAutoButton->setText("自动调节  关");
    }
    m_ledHasFilteredLux = false;
    m_ledLastAutoAdjustMs = 0;
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
        m_ledAutoButton->setChecked(m_ledAutoEnabled);
        m_ledAutoButton->setText(m_ledAutoEnabled ? "自动调节  开" : "自动调节  关");
    }

    if (m_ledAutoEnabled) {
        m_ledHasFilteredLux = false;
        m_ledLastAutoAdjustMs = 0;
        updateLedAutoControl();
        m_ledAutoTimer->start();
    } else {
        m_ledAutoTimer->stop();
        m_ledHasFilteredLux = false;
        m_ledLastAutoAdjustMs = 0;
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
        m_ledHasFilteredLux = false;
        return;
    }

    if (m_ledHasFilteredLux) {
        m_ledFilteredLux = (1.0 - kLedAutoFilterAlpha) * m_ledFilteredLux
                           + kLedAutoFilterAlpha * static_cast<double>(lightLux);
    } else {
        m_ledFilteredLux = static_cast<double>(lightLux);
        m_ledHasFilteredLux = true;
    }

    const int threshold = m_ledThresholdSlider->value();
    int nextBrightness = m_ledCurrentBrightness;
    const int filteredLux = qRound(m_ledFilteredLux);
    const int error = threshold - filteredLux;

    const qint64 nowMs = QDateTime::currentMSecsSinceEpoch();
    const bool canAdjust = m_ledLastAutoAdjustMs == 0
                           || (nowMs - m_ledLastAutoAdjustMs) >= kLedAutoMinAdjustGapMs;

    if (canAdjust && qAbs(error) > kLedAutoDeadbandLux) {
        int step = 1;
        const int absError = qAbs(error);
        if (absError >= kLedAutoLargeErrorLux) {
            step = 5;
        } else if (absError >= kLedAutoMediumErrorLux) {
            step = 3;
        }

        if (error > 0) {
            nextBrightness = qMin(100, nextBrightness + step);
        } else {
            nextBrightness = qMax(0, nextBrightness - step);
        }
    }

    if (nextBrightness != m_ledCurrentBrightness) {
        m_ledCurrentBrightness = nextBrightness;
        m_ledLastAutoAdjustMs = nowMs;
        if (m_ledBrightnessSlider) {
            m_ledBrightnessSlider->setValue(nextBrightness);
        }
        runLedCommand(nextBrightness);
    } else if (m_ledStatusLabel) {
        const QString state = qAbs(error) <= kLedAutoDeadbandLux ? "稳定" : "等待调节";
        m_ledStatusLabel->setText(QString("状态：自动调节%1 光照 %2 lx 滤波 %3 lx 阈值 %4 lx 亮度 %5%")
                                  .arg(state)
                                  .arg(lightLux)
                                  .arg(filteredLux)
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

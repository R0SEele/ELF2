#include "environmenttrendchart.h"

#include <QPainter>
#include <QPainterPath>
#include <QtGlobal>

#include <algorithm>

namespace {
QString formatAxisValue(double value, double span)
{
    const int decimals = span < 10.0 ? 1 : 0;
    return QString::number(value, 'f', decimals);
}

QString formatAxisTime(const QDateTime &timestamp, qint64 spanMs)
{
    if (spanMs >= 48LL * 60LL * 60LL * 1000LL) {
        return timestamp.toString("MM-dd");
    }
    if (spanMs >= 24LL * 60LL * 60LL * 1000LL) {
        return timestamp.toString("MM-dd HH:mm");
    }
    return timestamp.toString("HH:mm");
}
}

EnvironmentTrendChartWidget::EnvironmentTrendChartWidget(QWidget *parent)
    : QWidget(parent),
      m_color("#2F6B4F")
{
    setObjectName("environmentTrendChart");
    setMinimumHeight(160);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void EnvironmentTrendChartWidget::setSeries(const QVector<EnvironmentTrendPoint> &points,
                                             const QString &title,
                                             const QString &unit,
                                             const QColor &color)
{
    m_points = points;
    m_title = title;
    m_unit = unit;
    m_color = color;
    update();
}

void EnvironmentTrendChartWidget::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(QPen(QColor("#D8DED3"), 1));
    painter.setBrush(QColor("#FFFFFF"));
    painter.drawRoundedRect(rect().adjusted(0, 0, -1, -1), 7, 7);

    QFont titleFont = painter.font();
    titleFont.setPointSize(11);
    titleFont.setBold(true);
    painter.setFont(titleFont);
    painter.setPen(QColor("#26352A"));
    painter.drawText(QRect(14, 8, width() - 28, 22), Qt::AlignLeft | Qt::AlignVCenter, m_title);

    if (m_points.isEmpty()) {
        QFont emptyFont = painter.font();
        emptyFont.setPointSize(14);
        emptyFont.setBold(false);
        painter.setFont(emptyFont);
        painter.setPen(QColor("#849087"));
        painter.drawText(rect().adjusted(16, 36, -16, -16), Qt::AlignCenter, "暂无趋势数据");
        return;
    }

    double minValue = m_points.first().value;
    double maxValue = minValue;
    for (const EnvironmentTrendPoint &point : m_points) {
        minValue = qMin(minValue, point.value);
        maxValue = qMax(maxValue, point.value);
    }

    double valueSpan = maxValue - minValue;
    const double padding = valueSpan > 0.0 ? valueSpan * 0.12 : qMax(1.0, qAbs(maxValue) * 0.08);
    minValue -= padding;
    maxValue += padding;
    valueSpan = qMax(0.0001, maxValue - minValue);

    const QRectF plotRect(48.0, 38.0, qMax(1, width() - 62), qMax(1, height() - 72));
    QFont axisFont = painter.font();
    axisFont.setPointSize(8);
    axisFont.setBold(false);
    painter.setFont(axisFont);

    const int gridCount = 4;
    for (int i = 0; i <= gridCount; ++i) {
        const double ratio = static_cast<double>(i) / gridCount;
        const double y = plotRect.bottom() - ratio * plotRect.height();
        const double axisValue = minValue + ratio * valueSpan;
        painter.setPen(QPen(QColor("#E5EAE3"), 1));
        painter.drawLine(QPointF(plotRect.left(), y), QPointF(plotRect.right(), y));
        painter.setPen(QColor("#697468"));
        painter.drawText(QRectF(2, y - 9, 40, 18),
                         Qt::AlignRight | Qt::AlignVCenter,
                         formatAxisValue(axisValue, valueSpan));
    }

    const qint64 startMs = m_points.first().timestamp.toMSecsSinceEpoch();
    const qint64 endMs = m_points.last().timestamp.toMSecsSinceEpoch();
    const qint64 timeSpanMs = qMax<qint64>(1, endMs - startMs);
    const QVector<QDateTime> axisTimes = {
        m_points.first().timestamp,
        QDateTime::fromMSecsSinceEpoch(startMs + timeSpanMs / 2),
        m_points.last().timestamp
    };
    for (int i = 0; i < axisTimes.size(); ++i) {
        const int alignment = i == 0 ? Qt::AlignLeft : (i == axisTimes.size() - 1 ? Qt::AlignRight : Qt::AlignCenter);
        const double centerX = plotRect.left() + plotRect.width() * i / (axisTimes.size() - 1);
        QRectF labelRect(centerX - 52, plotRect.bottom() + 8, 104, 18);
        if (i == 0) {
            labelRect.moveLeft(plotRect.left());
        } else if (i == axisTimes.size() - 1) {
            labelRect.moveRight(plotRect.right());
        }
        painter.setPen(QColor("#697468"));
        painter.drawText(labelRect,
                         alignment | Qt::AlignVCenter,
                         formatAxisTime(axisTimes.at(i), timeSpanMs));
    }

    QVector<qint64> gaps;
    for (int i = 1; i < m_points.size(); ++i) {
        const qint64 gap = m_points.at(i - 1).timestamp.msecsTo(m_points.at(i).timestamp);
        if (gap > 0) {
            gaps.append(gap);
        }
    }
    std::sort(gaps.begin(), gaps.end());
    const qint64 typicalGapMs = gaps.isEmpty() ? 5000 : gaps.at(gaps.size() / 2);
    const qint64 breakGapMs = qMax<qint64>(60000, typicalGapMs * 8);

    auto chartPoint = [&](const EnvironmentTrendPoint &point) {
        const double xRatio = static_cast<double>(point.timestamp.toMSecsSinceEpoch() - startMs) / timeSpanMs;
        const double yRatio = (point.value - minValue) / valueSpan;
        return QPointF(plotRect.left() + xRatio * plotRect.width(),
                       plotRect.bottom() - yRatio * plotRect.height());
    };

    QPainterPath path;
    path.moveTo(chartPoint(m_points.first()));
    for (int i = 1; i < m_points.size(); ++i) {
        const QPointF point = chartPoint(m_points.at(i));
        const qint64 gapMs = m_points.at(i - 1).timestamp.msecsTo(m_points.at(i).timestamp);
        if (gapMs > breakGapMs) {
            path.moveTo(point);
        } else {
            path.lineTo(point);
        }
    }

    painter.setClipRect(plotRect.adjusted(-3, -3, 3, 3));
    painter.setPen(QPen(m_color, 2.5, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);

    const QPointF latestPoint = chartPoint(m_points.last());
    painter.setPen(QPen(QColor("#FFFFFF"), 2));
    painter.setBrush(m_color);
    painter.drawEllipse(latestPoint, 4.5, 4.5);
    painter.setClipping(false);

    painter.setFont(axisFont);
    painter.setPen(QColor("#697468"));
    painter.drawText(QRectF(plotRect.right() - 54, 8, 54, 22),
                     Qt::AlignRight | Qt::AlignVCenter,
                     m_unit);
}

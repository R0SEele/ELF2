#include "environmenttrendchart.h"

#include <QEvent>
#include <QGestureEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPinchGesture>
#include <QtGlobal>

#include <cmath>

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
    if (spanMs <= 5LL * 60LL * 1000LL) {
        return timestamp.toString("HH:mm:ss");
    }
    return timestamp.toString("HH:mm");
}
}

EnvironmentTrendChartWidget::EnvironmentTrendChartWidget(QWidget *parent)
    : QWidget(parent),
      m_color("#2F6B4F"),
      m_dataStartMs(0),
      m_dataEndMs(0),
      m_viewStartMs(0),
      m_viewEndMs(0),
      m_dragViewStartMs(0),
      m_dragViewEndMs(0),
      m_dragStartX(0),
      m_hoverIndex(-1),
      m_hasCustomView(false),
      m_dragging(false)
{
    setObjectName("environmentTrendChart");
    setMinimumHeight(300);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    setMouseTracking(true);
    setCursor(Qt::OpenHandCursor);
    grabGesture(Qt::PinchGesture);
}

void EnvironmentTrendChartWidget::setSeries(const QVector<EnvironmentTrendPoint> &points,
                                             const QString &title,
                                             const QString &unit,
                                             const QColor &color)
{
    const qint64 previousDataEndMs = m_dataEndMs;
    const qint64 previousViewStartMs = m_viewStartMs;
    const qint64 previousViewEndMs = m_viewEndMs;
    const bool wasFollowingLatest = m_hasCustomView
        && previousViewEndMs >= previousDataEndMs - 1000;

    m_points = points;
    m_title = title;
    m_unit = unit;
    m_color = color;
    m_hoverIndex = -1;

    if (m_points.isEmpty()) {
        m_dataStartMs = 0;
        m_dataEndMs = 0;
        m_viewStartMs = 0;
        m_viewEndMs = 0;
        m_hasCustomView = false;
        update();
        return;
    }

    m_dataStartMs = m_points.first().timestamp.toMSecsSinceEpoch();
    m_dataEndMs = m_points.last().timestamp.toMSecsSinceEpoch();
    if (!m_hasCustomView || previousViewEndMs <= previousViewStartMs) {
        resetView();
        return;
    }

    const qint64 previousSpanMs = previousViewEndMs - previousViewStartMs;
    if (wasFollowingLatest) {
        setVisibleRange(m_dataEndMs - previousSpanMs, m_dataEndMs, true);
    } else {
        setVisibleRange(previousViewStartMs, previousViewEndMs, true);
    }
    update();
}

void EnvironmentTrendChartWidget::zoomIn()
{
    zoomAt(0.72, plotRect().center().x());
}

void EnvironmentTrendChartWidget::zoomOut()
{
    zoomAt(1.0 / 0.72, plotRect().center().x());
}

void EnvironmentTrendChartWidget::resetView()
{
    if (m_points.isEmpty()) {
        return;
    }
    m_viewStartMs = m_dataStartMs;
    m_viewEndMs = qMax(m_dataStartMs + 1000, m_dataEndMs);
    m_hasCustomView = false;
    m_hoverIndex = -1;
    update();
}

QRectF EnvironmentTrendChartWidget::plotRect() const
{
    return QRectF(64.0, 50.0, qMax(1, width() - 84), qMax(1, height() - 92));
}

void EnvironmentTrendChartWidget::setVisibleRange(qint64 startMs,
                                                   qint64 endMs,
                                                   bool customView)
{
    if (m_points.isEmpty()) {
        return;
    }

    const qint64 dataEndMs = qMax(m_dataStartMs + 1000, m_dataEndMs);
    const qint64 dataSpanMs = dataEndMs - m_dataStartMs;
    const qint64 requestedSpanMs = qMax<qint64>(1000, endMs - startMs);
    const qint64 spanMs = qMin(dataSpanMs, requestedSpanMs);
    startMs = qBound(m_dataStartMs, startMs, dataEndMs - spanMs);

    m_viewStartMs = startMs;
    m_viewEndMs = startMs + spanMs;
    m_hasCustomView = customView
        && (spanMs < dataSpanMs || startMs > m_dataStartMs);
    m_hoverIndex = -1;
    update();
}

void EnvironmentTrendChartWidget::zoomAt(double factor, double anchorX)
{
    if (m_points.size() < 2 || factor <= 0.0) {
        return;
    }

    const QRectF plot = plotRect();
    const qint64 dataEndMs = qMax(m_dataStartMs + 1000, m_dataEndMs);
    const qint64 dataSpanMs = dataEndMs - m_dataStartMs;
    const qint64 viewSpanMs = qMax<qint64>(1000, m_viewEndMs - m_viewStartMs);
    const qint64 minimumSpanMs = qMin<qint64>(dataSpanMs, 30LL * 1000LL);
    const qint64 newSpanMs = qBound(minimumSpanMs,
                                    static_cast<qint64>(viewSpanMs * factor),
                                    dataSpanMs);
    const double anchorRatio = qBound(0.0,
                                      (anchorX - plot.left()) / qMax(1.0, plot.width()),
                                      1.0);
    const qint64 anchorTimeMs = m_viewStartMs
        + static_cast<qint64>(anchorRatio * viewSpanMs);
    const qint64 newStartMs = anchorTimeMs
        - static_cast<qint64>(anchorRatio * newSpanMs);
    setVisibleRange(newStartMs, newStartMs + newSpanMs, newSpanMs < dataSpanMs);
}

int EnvironmentTrendChartWidget::nearestPointIndex(qint64 timestampMs) const
{
    if (m_points.isEmpty()) {
        return -1;
    }

    int low = 0;
    int high = m_points.size();
    while (low < high) {
        const int middle = low + (high - low) / 2;
        if (m_points.at(middle).timestamp.toMSecsSinceEpoch() < timestampMs) {
            low = middle + 1;
        } else {
            high = middle;
        }
    }

    if (low <= 0) {
        return 0;
    }
    if (low >= m_points.size()) {
        return m_points.size() - 1;
    }
    const qint64 leftDistance = qAbs(
        m_points.at(low - 1).timestamp.toMSecsSinceEpoch() - timestampMs
    );
    const qint64 rightDistance = qAbs(
        m_points.at(low).timestamp.toMSecsSinceEpoch() - timestampMs
    );
    return leftDistance <= rightDistance ? low - 1 : low;
}

bool EnvironmentTrendChartWidget::event(QEvent *event)
{
    if (event->type() == QEvent::Gesture) {
        QGestureEvent *gestureEvent = static_cast<QGestureEvent *>(event);
        if (QPinchGesture *pinch = static_cast<QPinchGesture *>(
                gestureEvent->gesture(Qt::PinchGesture))) {
            if ((pinch->changeFlags() & QPinchGesture::ScaleFactorChanged)
                && pinch->lastScaleFactor() > 0.0
                && pinch->scaleFactor() > 0.0) {
                const double scaleStep = pinch->scaleFactor() / pinch->lastScaleFactor();
                zoomAt(1.0 / scaleStep, plotRect().center().x());
            }
            gestureEvent->accept(pinch);
            return true;
        }
    }
    return QWidget::event(event);
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

    const QRectF plot = plotRect();
    const qint64 viewStartMs = m_viewStartMs;
    const qint64 viewEndMs = qMax(m_viewStartMs + 1, m_viewEndMs);
    const qint64 timeSpanMs = viewEndMs - viewStartMs;

    int firstVisibleIndex = nearestPointIndex(viewStartMs);
    int lastVisibleIndex = nearestPointIndex(viewEndMs);
    while (firstVisibleIndex < m_points.size() - 1
           && m_points.at(firstVisibleIndex).timestamp.toMSecsSinceEpoch() < viewStartMs) {
        ++firstVisibleIndex;
    }
    while (lastVisibleIndex > 0
           && m_points.at(lastVisibleIndex).timestamp.toMSecsSinceEpoch() > viewEndMs) {
        --lastVisibleIndex;
    }
    if (firstVisibleIndex > lastVisibleIndex) {
        firstVisibleIndex = qMax(0, nearestPointIndex((viewStartMs + viewEndMs) / 2));
        lastVisibleIndex = firstVisibleIndex;
    }

    double minValue = m_points.at(firstVisibleIndex).value;
    double maxValue = minValue;
    for (int i = firstVisibleIndex; i <= lastVisibleIndex; ++i) {
        minValue = qMin(minValue, m_points.at(i).value);
        maxValue = qMax(maxValue, m_points.at(i).value);
    }
    double valueSpan = maxValue - minValue;
    const double visiblePadding = valueSpan > 0.0
        ? valueSpan * 0.12
        : qMax(1.0, qAbs(maxValue) * 0.08);
    minValue -= visiblePadding;
    maxValue += visiblePadding;
    valueSpan = qMax(0.0001, maxValue - minValue);

    QFont axisFont = painter.font();
    axisFont.setPointSize(8);
    axisFont.setBold(false);
    painter.setFont(axisFont);

    const int gridCount = 4;
    for (int i = 0; i <= gridCount; ++i) {
        const double ratio = static_cast<double>(i) / gridCount;
        const double y = plot.bottom() - ratio * plot.height();
        const double axisValue = minValue + ratio * valueSpan;
        painter.setPen(QPen(QColor("#E5EAE3"), 1));
        painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y));
        painter.setPen(QColor("#697468"));
        painter.drawText(QRectF(4, y - 9, 52, 18),
                         Qt::AlignRight | Qt::AlignVCenter,
                         formatAxisValue(axisValue, valueSpan));
    }

    const int timeTickCount = width() >= 900 ? 5 : 3;
    for (int i = 0; i < timeTickCount; ++i) {
        const int alignment = i == 0 ? Qt::AlignLeft : (i == timeTickCount - 1 ? Qt::AlignRight : Qt::AlignCenter);
        const double ratio = static_cast<double>(i) / (timeTickCount - 1);
        const double centerX = plot.left() + plot.width() * ratio;
        QRectF labelRect(centerX - 52, plot.bottom() + 8, 104, 18);
        if (i == 0) {
            labelRect.moveLeft(plot.left());
        } else if (i == timeTickCount - 1) {
            labelRect.moveRight(plot.right());
        }
        painter.setPen(QColor("#697468"));
        painter.drawText(labelRect,
                         alignment | Qt::AlignVCenter,
                         formatAxisTime(QDateTime::fromMSecsSinceEpoch(
                                            viewStartMs + static_cast<qint64>(ratio * timeSpanMs)
                                        ),
                                        timeSpanMs));
    }

    const qint64 breakGapMs = 60LL * 1000LL;

    auto chartPoint = [&](const EnvironmentTrendPoint &point) {
        const double xRatio = static_cast<double>(
            point.timestamp.toMSecsSinceEpoch() - viewStartMs
        ) / timeSpanMs;
        const double yRatio = (point.value - minValue) / valueSpan;
        return QPointF(plot.left() + xRatio * plot.width(),
                       plot.bottom() - yRatio * plot.height());
    };

    const int pathStartIndex = qMax(0, firstVisibleIndex - 1);
    const int pathEndIndex = qMin(m_points.size() - 1, lastVisibleIndex + 1);
    QPainterPath path;
    path.moveTo(chartPoint(m_points.at(pathStartIndex)));
    for (int i = pathStartIndex + 1; i <= pathEndIndex; ++i) {
        const QPointF point = chartPoint(m_points.at(i));
        const qint64 gapMs = m_points.at(i - 1).timestamp.msecsTo(m_points.at(i).timestamp);
        if (gapMs > breakGapMs) {
            path.moveTo(point);
        } else {
            path.lineTo(point);
        }
    }

    painter.setClipRect(plot.adjusted(-3, -3, 3, 3));
    painter.setPen(QPen(m_color, 2.5, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);

    if (lastVisibleIndex - firstVisibleIndex <= 120) {
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5));
        painter.setBrush(m_color);
        for (int i = firstVisibleIndex; i <= lastVisibleIndex; ++i) {
            painter.drawEllipse(chartPoint(m_points.at(i)), 3.0, 3.0);
        }
    }
    painter.setClipping(false);

    if (m_hoverIndex >= firstVisibleIndex && m_hoverIndex <= lastVisibleIndex) {
        const EnvironmentTrendPoint &hoverPoint = m_points.at(m_hoverIndex);
        const QPointF point = chartPoint(hoverPoint);
        painter.setPen(QPen(QColor("#AAB5AC"), 1, Qt::DashLine));
        painter.drawLine(QPointF(point.x(), plot.top()), QPointF(point.x(), plot.bottom()));
        painter.setPen(QPen(QColor("#FFFFFF"), 2));
        painter.setBrush(m_color);
        painter.drawEllipse(point, 5.0, 5.0);

        QFont tooltipFont = axisFont;
        tooltipFont.setPointSize(9);
        tooltipFont.setBold(true);
        painter.setFont(tooltipFont);
        const QString hoverText = QString("%1 %2   %3")
            .arg(QString::number(hoverPoint.value, 'f', valueSpan < 10.0 ? 1 : 0))
            .arg(m_unit)
            .arg(hoverPoint.timestamp.toString("MM-dd HH:mm:ss"));
        const int tooltipWidth = painter.fontMetrics().horizontalAdvance(hoverText) + 20;
        QRectF tooltipRect(0, plot.top() + 8, tooltipWidth, 30);
        tooltipRect.moveLeft(point.x() + 10);
        if (tooltipRect.right() > plot.right()) {
            tooltipRect.moveRight(point.x() - 10);
        }
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor("#26352A"));
        painter.drawRoundedRect(tooltipRect, 5, 5);
        painter.setPen(QColor("#FFFFFF"));
        painter.drawText(tooltipRect, Qt::AlignCenter, hoverText);
    }

    painter.setFont(axisFont);
    painter.setPen(QColor("#697468"));
    painter.drawText(QRectF(plot.right() - 180, 8, 180, 22),
                     Qt::AlignRight | Qt::AlignVCenter,
                     m_unit);
}

void EnvironmentTrendChartWidget::wheelEvent(QWheelEvent *event)
{
    const QPoint delta = event->pixelDelta().isNull() ? event->angleDelta() : event->pixelDelta();
    if (delta.y() == 0 || !plotRect().contains(event->position())) {
        event->ignore();
        return;
    }

    const double sensitivity = event->pixelDelta().isNull() ? 0.0018 : 0.012;
    zoomAt(std::exp(-delta.y() * sensitivity), event->position().x());
    event->accept();
}

void EnvironmentTrendChartWidget::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton && plotRect().contains(event->pos())) {
        m_dragging = true;
        m_dragStartX = event->pos().x();
        m_dragViewStartMs = m_viewStartMs;
        m_dragViewEndMs = m_viewEndMs;
        setCursor(Qt::ClosedHandCursor);
        event->accept();
        return;
    }
    QWidget::mousePressEvent(event);
}

void EnvironmentTrendChartWidget::mouseMoveEvent(QMouseEvent *event)
{
    const QRectF plot = plotRect();
    if (m_dragging) {
        const qint64 spanMs = m_dragViewEndMs - m_dragViewStartMs;
        const qint64 offsetMs = static_cast<qint64>(
            -(event->pos().x() - m_dragStartX) * spanMs / qMax(1.0, plot.width())
        );
        setVisibleRange(m_dragViewStartMs + offsetMs,
                        m_dragViewEndMs + offsetMs,
                        true);
        event->accept();
        return;
    }

    const int previousHoverIndex = m_hoverIndex;
    if (plot.contains(event->pos()) && !m_points.isEmpty()) {
        const double ratio = qBound(0.0,
                                    (event->pos().x() - plot.left()) / qMax(1.0, plot.width()),
                                    1.0);
        const qint64 timestampMs = m_viewStartMs
            + static_cast<qint64>(ratio * (m_viewEndMs - m_viewStartMs));
        m_hoverIndex = nearestPointIndex(timestampMs);
        const qint64 pointTimeMs = m_points.at(m_hoverIndex).timestamp.toMSecsSinceEpoch();
        if (pointTimeMs < m_viewStartMs || pointTimeMs > m_viewEndMs) {
            m_hoverIndex = -1;
        }
    } else {
        m_hoverIndex = -1;
    }
    if (previousHoverIndex != m_hoverIndex) {
        update();
    }
    QWidget::mouseMoveEvent(event);
}

void EnvironmentTrendChartWidget::mouseReleaseEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton && m_dragging) {
        m_dragging = false;
        setCursor(Qt::OpenHandCursor);
        event->accept();
        return;
    }
    QWidget::mouseReleaseEvent(event);
}

void EnvironmentTrendChartWidget::mouseDoubleClickEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton && plotRect().contains(event->pos())) {
        resetView();
        event->accept();
        return;
    }
    QWidget::mouseDoubleClickEvent(event);
}

void EnvironmentTrendChartWidget::leaveEvent(QEvent *event)
{
    if (!m_dragging && m_hoverIndex >= 0) {
        m_hoverIndex = -1;
        update();
    }
    QWidget::leaveEvent(event);
}

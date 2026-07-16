#ifndef ENVIRONMENTTRENDCHART_H
#define ENVIRONMENTTRENDCHART_H

#include <QColor>
#include <QDateTime>
#include <QMouseEvent>
#include <QPaintEvent>
#include <QRectF>
#include <QVector>
#include <QWheelEvent>
#include <QWidget>

struct EnvironmentTrendPoint
{
    QDateTime timestamp;
    double value = 0.0;
};

class EnvironmentTrendChartWidget : public QWidget
{
public:
    explicit EnvironmentTrendChartWidget(QWidget *parent = nullptr);

    void setSeries(const QVector<EnvironmentTrendPoint> &points,
                   const QString &title,
                   const QString &unit,
                   const QColor &color);
    void zoomIn();
    void zoomOut();
    void resetView();

protected:
    bool event(QEvent *event) override;
    void paintEvent(QPaintEvent *event) override;
    void wheelEvent(QWheelEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void mouseDoubleClickEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    QRectF plotRect() const;
    void zoomAt(double factor, double anchorX);
    void setVisibleRange(qint64 startMs, qint64 endMs, bool customView);
    int nearestPointIndex(qint64 timestampMs) const;

    QVector<EnvironmentTrendPoint> m_points;
    QString m_title;
    QString m_unit;
    QColor m_color;
    qint64 m_dataStartMs;
    qint64 m_dataEndMs;
    qint64 m_viewStartMs;
    qint64 m_viewEndMs;
    qint64 m_dragViewStartMs;
    qint64 m_dragViewEndMs;
    int m_dragStartX;
    int m_hoverIndex;
    bool m_hasCustomView;
    bool m_dragging;
};

#endif // ENVIRONMENTTRENDCHART_H

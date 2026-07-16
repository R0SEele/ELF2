#ifndef ENVIRONMENTTRENDCHART_H
#define ENVIRONMENTTRENDCHART_H

#include <QColor>
#include <QDateTime>
#include <QPaintEvent>
#include <QVector>
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

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QVector<EnvironmentTrendPoint> m_points;
    QString m_title;
    QString m_unit;
    QColor m_color;
};

#endif // ENVIRONMENTTRENDCHART_H

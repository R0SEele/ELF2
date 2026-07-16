#include "sensordatareader.h"

#include <QDateTime>
#include <QFile>
#include <QFileInfo>
#include <QSet>
#include <QTextStream>
#include <QtGlobal>

namespace {
bool looksLikeHeader(const QStringList &fields)
{
    int namedFields = 0;
    for (const QString &field : fields) {
        const QString text = field.trimmed();
        if (text.isEmpty()) {
            continue;
        }

        bool numeric = false;
        text.toDouble(&numeric);
        if (!numeric) {
            ++namedFields;
        }
    }

    return namedFields > 0;
}

bool isLikelyKeyValueName(const QString &name)
{
    bool numeric = false;
    name.trimmed().toDouble(&numeric);
    return !name.trimmed().isEmpty() && !numeric;
}

const QStringList &sensorCsvFields()
{
    static const QStringList fields = {
        "temperature_c",
        "humidity_rh",
        "co2_ppm",
        "light_lux",
        "air_quality_ppm",
        "env_status",
        "timestamp",
        "sensor_errors"
    };

    return fields;
}

bool isStandardCsvHeader(const QStringList &fields)
{
    const QStringList standardFields = sensorCsvFields();
    if (fields.size() < standardFields.size()) {
        return false;
    }

    for (int i = 0; i < standardFields.size(); ++i) {
        if (fields.at(i).trimmed().toLower() != standardFields.at(i)) {
            return false;
        }
    }

    return true;
}
}

SensorDataReader::SensorDataReader(const QString &csvFilePath)
    : m_csvFilePath(csvFilePath)
{
}

SensorSnapshot SensorDataReader::readLatest() const
{
    if (m_csvFilePath.isEmpty() || !QFileInfo::exists(m_csvFilePath)) {
        SensorSnapshot snapshot;
        snapshot.sourceFile = QFileInfo(m_csvFilePath).fileName();
        snapshot.updatedAt = "未检测到环境 CSV 文件";
        return snapshot;
    }

    return readCsv(m_csvFilePath);
}

SensorSnapshot SensorDataReader::readCsv(const QString &filePath) const
{
    SensorSnapshot snapshot;
    snapshot.sourceFile = QFileInfo(filePath).fileName();
    snapshot.updatedAt = QFileInfo(filePath).lastModified().toString("yyyy-MM-dd HH:mm:ss");

    QFile file(filePath);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        snapshot.updatedAt = "CSV 文件读取失败";
        return snapshot;
    }

    QTextStream stream(&file);
    stream.setCodec("UTF-8");

    QStringList rows;
    while (!stream.atEnd()) {
        const QString line = stream.readLine().trimmed();
        if (!line.isEmpty()) {
            rows.append(line);
        }
    }

    if (rows.isEmpty()) {
        return snapshot;
    }

    const QStringList first = parseCsvLine(rows.first());
    const QStringList last = parseCsvLine(rows.last());

    if (rows.size() >= 2 && first.size() == last.size() && looksLikeHeader(first)) {
        const int valueCountBefore = snapshot.values.size();
        for (int i = 0; i < first.size(); ++i) {
            const QString key = first.at(i).trimmed();
            const QString value = last.at(i).trimmed();
            if (key.isEmpty() || value.isEmpty() || !shouldDisplayField(key)) {
                continue;
            }

            snapshot.values.append({displayNameFor(key), displayValueFor(key, value), unitFor(key)});
        }

        if (snapshot.values.size() > valueCountBefore) {
            return snapshot;
        }
    }

    const QStringList standardFields = sensorCsvFields();
    if (!isStandardCsvHeader(last) && last.size() >= 6) {
        for (int i = 0; i < qMin(last.size(), standardFields.size()); ++i) {
            const QString key = standardFields.at(i);
            const QString value = last.at(i).trimmed();
            if (value.isEmpty() || !shouldDisplayField(key)) {
                continue;
            }

            snapshot.values.append({displayNameFor(key), displayValueFor(key, value), unitFor(key)});
        }

        if (!snapshot.values.isEmpty()) {
            return snapshot;
        }
    }

    if (rows.size() >= 2) {
        QSet<QString> seen;
        for (const QString &row : rows) {
            const QStringList fields = parseCsvLine(row);
            if (fields.size() < 2) {
                continue;
            }

            const QString key = fields.at(0).trimmed();
            const QString value = fields.at(1).trimmed();
            if (!isLikelyKeyValueName(key) || value.isEmpty() || seen.contains(key) || !shouldDisplayField(key)) {
                continue;
            }

            seen.insert(key);
            QString unit;
            if (fields.size() >= 3) {
                unit = fields.at(2).trimmed();
            }
            if (unit.isEmpty()) {
                unit = unitFor(key);
            }

            const QString displayValue = displayValueFor(key, value);
            if (displayValue != value.trimmed()) {
                unit.clear();
            }

            snapshot.values.append({displayNameFor(key), displayValue, unit});
        }

        if (!snapshot.values.isEmpty()) {
            return snapshot;
        }
    }

    return snapshot;
}

QStringList SensorDataReader::parseCsvLine(const QString &line) const
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

bool SensorDataReader::shouldDisplayField(const QString &key) const
{
    const QString lowered = key.trimmed().toLower();

    static const QStringList allowedFields = {
        sensorCsvFields().at(0),
        sensorCsvFields().at(1),
        sensorCsvFields().at(2),
        sensorCsvFields().at(3),
        sensorCsvFields().at(4),
        sensorCsvFields().at(5)
    };

    return allowedFields.contains(lowered);
}

QString SensorDataReader::displayNameFor(const QString &key) const
{
    const QString lowered = key.trimmed().toLower();

    if (lowered.contains("time") || lowered.contains("时间")) {
        return "采集时间";
    }
    if (lowered.contains("temp") || lowered.contains("温度")) {
        return "温度";
    }
    if (lowered.contains("humid") || lowered.contains("湿度")) {
        return "湿度";
    }
    if (lowered.contains("co2") || lowered.contains("二氧化碳")) {
        return "二氧化碳";
    }
    if (lowered.contains("light") || lowered.contains("lux") || lowered.contains("光照")) {
        return "光照";
    }
    if (lowered.contains("mq") || lowered.contains("air") || lowered.contains("空气")) {
        return "空气质量";
    }
    if (lowered.contains("env") || lowered.contains("status") || lowered.contains("状态")) {
        return "环境状态";
    }
    if (lowered.contains("ethylene") || lowered.contains("乙烯")) {
        return "乙烯";
    }
    if (lowered.contains("em") || lowered.contains("电磁")) {
        return "电磁状态";
    }

    return key.trimmed();
}

QString SensorDataReader::displayValueFor(const QString &key, const QString &value) const
{
    const QString trimmed = value.trimmed();
    if (trimmed.isEmpty()) {
        return trimmed;
    }

    const QString lowered = key.trimmed().toLower();
    if (lowered.contains("env") || lowered.contains("status") || lowered.contains("状态")) {
        return trimmed;
    }

    bool ok = false;
    const double numeric = trimmed.toDouble(&ok);
    if (!ok) {
        return trimmed;
    }

    const QString rating = ratingFor(key, numeric);
    if (rating.isEmpty()) {
        return trimmed;
    }

    if (lowered.contains("temp") || lowered.contains("温度")) {
        return QString("%1℃  %2").arg(QString::number(numeric, 'f', 1), rating);
    }
    if (lowered.contains("humid") || lowered.contains("湿度")) {
        return QString("%1%  %2").arg(QString::number(numeric, 'f', 1), rating);
    }
    if (lowered == "air_quality_ppm") {
        return QString("%1%  %2").arg(QString::number(numeric, 'f', 1), rating);
    }
    if (lowered.contains("co2") || lowered.contains("二氧化碳")) {
        return QString("%1  %2").arg(QString::number(qRound(numeric)), rating);
    }
    if (lowered.contains("light") || lowered.contains("lux") || lowered.contains("光照")) {
        return QString("%1  %2").arg(QString::number(qRound(numeric)), rating);
    }

    return QString("%1  %2").arg(trimmed, rating);
}

QString SensorDataReader::ratingFor(const QString &key, double value) const
{
    const QString lowered = key.trimmed().toLower();

    if (lowered.contains("temp") || lowered.contains("温度")) {
        if (value < 15.0) {
            return "偏低";
        }
        if (value <= 28.0) {
            return "适宜";
        }
        if (value <= 35.0) {
            return "偏高";
        }
        return "过热";
    }

    if (lowered.contains("humid") || lowered.contains("湿度")) {
        if (value < 40.0) {
            return "偏干";
        }
        if (value <= 70.0) {
            return "舒适";
        }
        return "偏湿";
    }

    if (lowered.contains("co2") || lowered.contains("二氧化碳")) {
        if (value < 800.0) {
            return "空气清新";
        }
        if (value < 1200.0) {
            return "略高";
        }
        if (value < 2000.0) {
            return "偏闷";
        }
        return "通风不足";
    }

    if (lowered.contains("light") || lowered.contains("lux") || lowered.contains("光照")) {
        if (value < 50.0) {
            return "偏暗";
        }
        if (value < 200.0) {
            return "柔和";
        }
        if (value < 500.0) {
            return "明亮";
        }
        if (value < 1000.0) {
            return "较亮";
        }
        return "强光";
    }

    if (lowered == "air_quality_ppm") {
        if (value < 25.0) {
            return "良好";
        }
        if (value < 50.0) {
            return "一般";
        }
        if (value < 75.0) {
            return "偏差";
        }
        return "较差";
    }

    return QString();
}

QString SensorDataReader::unitFor(const QString &key) const
{
    const QString lowered = key.trimmed().toLower();

    if (lowered.contains("temp") || lowered.contains("温度")) {
        return QString();
    }
    if (lowered.contains("humid") || lowered.contains("湿度")) {
        return QString();
    }
    if (lowered.contains("co2") || lowered.contains("二氧化碳")) {
        return QString();
    }
    if (lowered.contains("light") || lowered.contains("lux") || lowered.contains("光照")) {
        return QString();
    }
    if (lowered.contains("ethylene") || lowered.contains("乙烯")) {
        return "ppm";
    }
    if (lowered == "air_quality_ppm") {
        return QString();
    }
    if (lowered.contains("ppm")) {
        return "ppm";
    }

    return QString();
}

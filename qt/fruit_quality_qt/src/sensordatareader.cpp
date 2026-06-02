#include "sensordatareader.h"

#include <QDateTime>
#include <QFile>
#include <QFileInfo>
#include <QSet>
#include <QTextStream>

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
        for (int i = 0; i < first.size(); ++i) {
            const QString key = first.at(i).trimmed();
            const QString value = last.at(i).trimmed();
            if (key.isEmpty() || value.isEmpty() || !shouldDisplayField(key)) {
                continue;
            }

            snapshot.values.append({displayNameFor(key), value, unitFor(key)});
        }
        return snapshot;
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

            snapshot.values.append({displayNameFor(key), value, unit});
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
        "temperature_c",
        "humidity_rh",
        "co2_ppm",
        "light_lux",
        "air_quality_ppm",
        "env_status"
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

QString SensorDataReader::unitFor(const QString &key) const
{
    const QString lowered = key.trimmed().toLower();

    if (lowered.contains("temp") || lowered.contains("温度")) {
        return "℃";
    }
    if (lowered.contains("humid") || lowered.contains("湿度")) {
        return "%";
    }
    if (lowered.contains("co2") || lowered.contains("二氧化碳")) {
        return "ppm";
    }
    if (lowered.contains("light") || lowered.contains("lux") || lowered.contains("光照")) {
        return "lx";
    }
    if (lowered.contains("ethylene") || lowered.contains("乙烯")) {
        return "ppm";
    }
    if (lowered == "air_quality_ppm") {
        return "%";
    }
    if (lowered.contains("ppm")) {
        return "ppm";
    }

    return QString();
}

#ifndef SENSORDATAREADER_H
#define SENSORDATAREADER_H

#include <QString>
#include <QStringList>
#include <QVector>

struct SensorValue
{
    QString name;
    QString value;
    QString unit;
};

struct SensorSnapshot
{
    QVector<SensorValue> values;
    QString sourceFile;
    QString updatedAt;
};

class SensorDataReader
{
public:
    explicit SensorDataReader(const QString &csvFilePath);

    SensorSnapshot readLatest() const;

private:
    SensorSnapshot readCsv(const QString &filePath) const;
    QStringList parseCsvLine(const QString &line) const;
    bool shouldDisplayField(const QString &key) const;
    QString displayNameFor(const QString &key) const;
    QString displayValueFor(const QString &key, const QString &value) const;
    QString ratingFor(const QString &key, double value) const;
    QString unitFor(const QString &key) const;

    QString m_csvFilePath;
};

#endif // SENSORDATAREADER_H

#include "mainwindow.h"

#include <QApplication>
#include <QFont>
#include <QSocketNotifier>

#include <csignal>
#include <fcntl.h>
#include <unistd.h>

namespace {
int g_signalPipe[2] = {-1, -1};

void signalHandler(int signalNumber)
{
    const char value = static_cast<char>(signalNumber);
    if (g_signalPipe[1] != -1) {
        const ssize_t ignored = write(g_signalPipe[1], &value, sizeof(value));
        Q_UNUSED(ignored);
    }
}

void installSignalHandler(int signalNumber)
{
    struct sigaction action;
    action.sa_handler = signalHandler;
    sigemptyset(&action.sa_mask);
    action.sa_flags = 0;
    sigaction(signalNumber, &action, nullptr);
}
}

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);

    QFont appFont("Noto Sans CJK SC");
    appFont.setPointSize(18);
    app.setFont(appFont);

    MainWindow window;
    window.showFullScreen();

    QSocketNotifier *signalNotifier = nullptr;
    if (pipe(g_signalPipe) == 0) {
        fcntl(g_signalPipe[0], F_SETFL, fcntl(g_signalPipe[0], F_GETFL, 0) | O_NONBLOCK);
        fcntl(g_signalPipe[1], F_SETFL, fcntl(g_signalPipe[1], F_GETFL, 0) | O_NONBLOCK);

        installSignalHandler(SIGINT);
        installSignalHandler(SIGTERM);
        installSignalHandler(SIGHUP);

        signalNotifier = new QSocketNotifier(g_signalPipe[0], QSocketNotifier::Read, &app);
        QObject::connect(signalNotifier, &QSocketNotifier::activated, [&app, &window, signalNotifier]() {
            signalNotifier->setEnabled(false);

            char buffer[16];
            while (read(g_signalPipe[0], buffer, sizeof(buffer)) > 0) {
            }

            window.shutdownHardware();
            app.quit();
        });
    }

    QObject::connect(&app, &QCoreApplication::aboutToQuit, &window, &MainWindow::shutdownHardware);

    return app.exec();
}

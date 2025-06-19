// Hubert XXXXX, nr indeksu 155943
#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <ctime>
#include <atomic>
#include <mutex>
#include <sstream>
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
using namespace std;

// 7-segmentowe cyfry (3 linie)
string digits[10][3] = {
    {" _ ", "| |", "|_|"}, // 0
    {"   ", "  |", "  |"}, // 1
    {" _ ", " _|", "|_ "}, // 2
    {" _ ", " _|", " _|"}, // 3
    {"   ", "|_|", "  |"}, // 4
    {" _ ", "|_ ", " _|"}, // 5
    {" _ ", "|_ ", "|_|"}, // 6
    {" _ ", "  |", "  |"}, // 7
    {" _ ", "|_|", "|_|"}, // 8
    {" _ ", "|_|", " _|"}  // 9
};
string colonSym[3] = {"   ", " . ", " . "};
string justColons[3] = {"   ", " : ", " : "};

struct Alarm {
    atomic<bool> set{false};
    int hour = 0;
    int min = 0;
    atomic<bool> triggered{false};
};

struct Timer {
    atomic<bool> set{false};
    int seconds = 0;
    atomic<bool> running{false};
};

mutex globalMutex;
atomic<bool> needsUpdate{true};
string lastStatus = "";
string lastResponse = "";
string currentInput = "";  // Aktualnie wpisywany tekst

atomic<bool> blinkOn{true};
atomic<bool> displayAlarm{false};
atomic<bool> displayTimerUp{false};
atomic<bool> blinkClock{false};
atomic<bool> blinkShowColons{false};
atomic<bool> blinkActive{false};
atomic<bool> czekajNaPotwierdzenie{false};

// Konfiguracja terminala dla nieblokującego wejścia
void setupTerminal() {
    termios term;
    tcgetattr(STDIN_FILENO, &term);
    term.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &term);
    fcntl(STDIN_FILENO, F_SETFL, O_NONBLOCK);
}

// Przywracanie ustawień terminala
void restoreTerminal() {
    termios term;
    tcgetattr(STDIN_FILENO, &term);
    term.c_lflag |= (ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &term);
    fcntl(STDIN_FILENO, F_SETFL, 0);
}

// Czyszczenie ekranu + kursor na początek
void clearScreen() {
    cout << "\033[2J\033[H";
}

// Wyświetlanie 7-segmentowego zegara lub samych dwukropków
void displayTimeAscii(const string &timeStr, bool onlyColons = false) {
    if (onlyColons) {
        for(int row = 0; row < 3; ++row) {
            for(char ch : timeStr) {
                if(ch == ':') cout << justColons[row];
                else cout << "   ";
            }
            cout << endl;
        }
    } else {
        for(int row = 0; row < 3; ++row) {
            for(char ch : timeStr) {
                if(ch >= '0' && ch <= '9') cout << digits[ch - '0'][row];
                else if(ch == ':') cout << colonSym[row];
                else cout << "   ";
            }
            cout << endl;
        }
    }
}

// Wątek od zegara/timera
void clockThread(Alarm &alarm, Timer &timer) {
    string lastTimeStr = "";
    string displayMsg = "";

    while (true) {
        bool shouldUpdate = needsUpdate.load();

        time_t now = time(nullptr);
        tm *local = localtime(&now);

        bool showTimer = false;
        string timeStr;
        string statusMsg = "";

        {
            lock_guard<mutex> lock(globalMutex);
            if (timer.set && timer.running && timer.seconds > 0) showTimer = true;
        }

        if (showTimer) {
            int min, sec;
            {
                lock_guard<mutex> lock(globalMutex);
                min = timer.seconds / 60;
                sec = timer.seconds % 60;
            }
            char buf[6];
            snprintf(buf, sizeof(buf), "%02d:%02d", min, sec);
            timeStr = buf;

            // Timer upłynął - sprawdzamy PRZED zmniejszeniem licznika
            lock_guard<mutex> lock(globalMutex);
            if (timer.seconds == 1 && timer.running && !displayTimerUp) {
                displayTimerUp = true;
                blinkClock = true;
                czekajNaPotwierdzenie = true;
                shouldUpdate = true;
                cout << '\a';
                displayMsg = "Timer upłynął! Wciśnij Enter, aby kontynuować...";
            }
        } else {
            char buf[6];
            snprintf(buf, sizeof(buf), "%02d:%02d", local->tm_hour, local->tm_min);
            timeStr = buf;

            lock_guard<mutex> lock(globalMutex);
            if (alarm.set && !alarm.triggered && local->tm_hour == alarm.hour && local->tm_min == alarm.min) {
                alarm.triggered = true;
                displayAlarm = true;
                blinkClock = true;
                czekajNaPotwierdzenie = true;
                shouldUpdate = true;
                cout << '\a';
                std::ostringstream oss;
                oss << "ALARM! " << (alarm.hour < 10 ? "0" : "") << alarm.hour
                    << ":" << (alarm.min < 10 ? "0" : "") << alarm.min
                    << " osiągnięty! Wciśnij Enter, aby kontynuować...";
                displayMsg = oss.str();
            }
        }

        if (timeStr != lastTimeStr || shouldUpdate || blinkActive) {
            clearScreen();
            cout << endl;
            
            if (blinkClock && blinkShowColons) {
                displayTimeAscii(timeStr, true);
            } else {
                displayTimeAscii(timeStr, false);
            }
            cout << endl;

            if ((displayAlarm || displayTimerUp) && blinkClock) {
                cout << "\033[5m\033[1;31m" << displayMsg << "\033[0m" << endl;
            } else {
                cout << endl;
            }

            if (!lastResponse.empty()) {
                cout << lastResponse << endl;
                lastResponse = "";  // Czyść komunikat po wyświetleniu
            } else {
                cout << endl;
            }

            // Wyświetlanie promptu i aktualnego wejścia
            if (czekajNaPotwierdzenie) {
                cout << "[Aby zakończyć alarm/timer, wciśnij Enter] ";
            } else {
                cout << "[Komenda] Ustaw alarm (a HH:MM), timer (t MM:SS), reset (r), wyjść (q): ";
            }
            
            // Wyświetl aktualnie wpisywany tekst
            cout << currentInput;
            cout.flush();

            lastTimeStr = timeStr;
            lastStatus = displayMsg;  // Przywracam zapisywanie statusu
            needsUpdate = false;
        }

        this_thread::sleep_for(chrono::milliseconds(250));

        static auto lastBlink = chrono::steady_clock::now();
        static auto lastTimerUpdate = chrono::steady_clock::now();
        auto currentTime = chrono::steady_clock::now();
        
        // Miganie co 0.5 sekundy
        if (chrono::duration_cast<chrono::milliseconds>(currentTime - lastBlink).count() > 500) {
            blinkShowColons = !blinkShowColons;
            blinkActive = blinkClock.load();
            needsUpdate = true;
            lastBlink = currentTime;
        }

        // Zmniejsz licznik timera co 1 sekundę
        if (showTimer && chrono::duration_cast<chrono::milliseconds>(currentTime - lastTimerUpdate).count() >= 1000) {
            lock_guard<mutex> lock(globalMutex);
            if (timer.seconds > 0) {
                timer.seconds--;
                needsUpdate = true;
            }
            if (timer.seconds == 0) timer.running = false;
            lastTimerUpdate = currentTime;
        }
    }
}

// Wątek obsługi komend z nieblokującym wejściem
void commandThread(Alarm &alarm, Timer &timer) {
    char ch;
    
    while (true) {
        if (read(STDIN_FILENO, &ch, 1) > 0) {
            if (czekajNaPotwierdzenie) {
                if (ch == '\n') {
                    displayAlarm = false;
                    displayTimerUp = false;
                    blinkClock = false;
                    czekajNaPotwierdzenie = false;
                    lastStatus = "";
                    currentInput = "";
                    needsUpdate = true;
                }
                continue;
            }
            
            if (ch == '\n') {
                // Przetwórz komendę
                if (!currentInput.empty()) {
                    string response = "";
                    string line = currentInput;
                    
                    if (line[0] == 'a') {
                        int hh, mm;
                        if (sscanf(line.c_str(), "a %d:%d", &hh, &mm) == 2 && hh >= 0 && hh < 24 && mm >= 0 && mm < 60) {
                            lock_guard<mutex> lock(globalMutex);
                            alarm.hour = hh;
                            alarm.min = mm;
                            alarm.set = true;
                            alarm.triggered = false;
                            timer.set = false;
                            timer.running = false;
                            std::ostringstream oss;
                            oss << "✓ Alarm ustawiony na " << (hh < 10 ? "0" : "") << hh << ":" << (mm < 10 ? "0" : "") << mm;
                            response = oss.str();
                        } else {
                            response = "✗ Błędny format (a HH:MM)";
                        }
                    } else if (line[0] == 't') {
                        int mm, ss;
                        if (sscanf(line.c_str(), "t %d:%d", &mm, &ss) == 2 && mm >= 0 && ss >= 0 && ss < 60) {
                            lock_guard<mutex> lock(globalMutex);
                            timer.seconds = mm * 60 + ss;
                            timer.set = true;
                            timer.running = true;
                            alarm.set = false;
                            alarm.triggered = false;
                            std::ostringstream oss;
                            oss << "✓ Timer ustawiony na " << mm << " minut " << ss << " sekund.";
                            response = oss.str();
                        } else {
                            response = "✗ Błędny format (t MM:SS)";
                        }
                    } else if (line[0] == 'r') {
                        lock_guard<mutex> lock(globalMutex);
                        alarm.set = false;
                        alarm.triggered = false;
                        timer.set = false;
                        timer.running = false;
                        timer.seconds = 0;
                        response = "✓ Reset alarmu i timera.";
                    } else if (line[0] == 'q') {
                        restoreTerminal();
                        clearScreen();
                        cout << "Wyjście z programu." << endl;
                        exit(0);
                    } else {
                        response = "✗ Nieznana komenda.";
                    }
                    
                    lastResponse = response;
                    currentInput = "";
                    needsUpdate = true;
                }
            } else if (ch == 127 || ch == 8) {  // Backspace
                if (!currentInput.empty()) {
                    currentInput.pop_back();
                    needsUpdate = true;
                }
            } else if (ch >= 32 && ch < 127) {  // Drukowalne znaki
                currentInput += ch;
                needsUpdate = true;
            }
        }
        
        this_thread::sleep_for(chrono::milliseconds(10));
    }
}

int main() {
    cout << "=== ZEGAR CYFROWY 7-SEGMENTOWY ===" << endl;
    cout << "Uruchamianie..." << endl;
    this_thread::sleep_for(chrono::seconds(1));

    setupTerminal();  // Konfiguruj terminal dla nieblokującego wejścia

    Alarm alarm;
    Timer timer;

    thread tClock(clockThread, ref(alarm), ref(timer));
    thread tCmd(commandThread, ref(alarm), ref(timer));

    tClock.join();
    tCmd.join();

    restoreTerminal();  // Przywróć ustawienia terminala

    return 0;
}

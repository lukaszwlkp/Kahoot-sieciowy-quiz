# Kahoot — sieciowy quiz

# Twórcy projektu:
* Łukasz Przykłota (159440, L5)
* Stanisław Marszałek (160167, L5)

# Opis:

```markdown
Użytkownik łączy się do serwera i wybiera rolę: twórcy quizu lub gracza.
Zarówno twórca, jak i gracze podają unikalny nick (jeśli nick jest zajęty, serwer prosi o inny).
Tworzenie quizu:
Twórca przechodzi do kreatora quizu, w którym definiuje:
– listę pytań,
– możliwe odpowiedzi,
– poprawne odpowiedzi,
– liczbę punktów za pytanie,
– limit czasu na odpowiedź.
Po zapisaniu quizu serwer:
– generuje jednorazowy kod dostępu do quizu,
– tworzy dla niego osobne lobby,
– umieszcza w nim twórcę.
Twórca widzi listę graczy oczekujących w lobby.
Jeśli twórca rozłączy się przed startem quizu, lobby i quiz zostają usunięte.
Dołączanie graczy:
Gracz podaje kod quizu.
Jeśli kod nie istnieje lub quiz został zakończony, połączenie zostaje odrzucone.
Gracz po poprawnym podaniu nicku i kodu trafia do lobby przypisanego do danego quizu i widzi listę oczekujących graczy.
Próba dołączenia do quizu, który już wystartował, kończy się komunikatem, że do rozpoczętego quizu nie można dołączyć.
Rozpoczęcie quizu:
Quiz może rozpocząć tylko twórca.
Twórca może wystartować quiz w dowolnym momencie, pod warunkiem że w lobby jest co najmniej jeden gracz.
Jeśli twórca rozłączy się po rozpoczęciu quizu, serwer kończy quiz i informuje o tym uczestników.
Przebieg quizu:
Uczestnicy widzą aktualne pytanie i możliwe odpowiedzi.
Twórca widzi odpowiedzi uczestników oraz tabelę punktową.
Uczestnicy widzą tabelę punktową.
Każde pytanie posiada limit czasu. Czas na odpowiedź kończy się:
– po udzieleniu odpowiedzi przez co najmniej 2/3 uczestników,
albo
– po upływie limitu czasu.
Po zakończeniu pytania serwer ujawnia poprawną odpowiedź, nalicza punkty i aktualizuje tabelę punktową.
Rozłączenia uczestników:
Jeśli uczestnik rozłączy się w trakcie quizu, jego dotychczasowe punkty pozostają w tabeli.
Zakończenie quizu:
Po zakończeniu ostatniego pytania serwer wyświetla końcową tabelę punktową i zamyka quiz.
Kod dostępu wygasa, lobby zostaje usunięte, a użytkownicy po zaznajomieniu się z tabelą punktową mają opcję powrotu do ekranu startowego aplikacji.
```

---

## Struktura projektu

Projekt został przygotowany w jednym pliku `server.cpp` zawierającym logikę serwera.  
Klient jest dostarczony jako osobny skrypt `client.py`.  

Dzięki temu:
- łatwo przenosić projekt między systemami,
- utrzymanie kodu jest prostsze.

Kod został poprawiony zgodnie z sugestiami `make lint` oraz przetestowany przy użyciu `make valgrind`.

---

## Instalacja i uruchomienie

1. Klonowanie repozytorium:
```bash
git clone https://github.com/lukaszwlkp/Kahoot-sieciowy-quiz
cd Kahoot-sieciowy-quiz
```

2. Korzystanie z Makefile:

* Kompilacja serwera:
```bash
make server
```

* Kompilacja serwera w trybie debug:
```bash
make debug
```

* Uruchomienie serwera:
```bash
make run-server
```

* Uruchomienie klienta:
```bash
make run-client
```

* Sprawdzenie kodu pod kątem błędów i ostrzeżeń:
```bash
make lint
```

* Testy pamięci i analiza wycieków przy użyciu Valgrind:
```bash
make valgrind
```

* Czyszczenie plików wykonywalnych:
```bash
make clean
```

---

## Użycie

* Serwer:

Uruchom serwer przy użyciu make run-server.

Serwer nasłuchuje na domyślnym porcie 12345.

* Klient:

Uruchom klienta przy użyciu make run-client.

Wprowadź adres serwera, port.

Wybierz rolę: twórca quizu lub gracz oraz wprowadź swój nick.

Postępuj zgodnie z instrukcjami w aplikacji.

* Twórca quizu:

Utwórz quiz w kreatorze.

Udostępnij kod dostępu graczom.

Rozpocznij quiz, gdy wszyscy gracze dołączą.

Obserwuj tabelę punktową oraz odpowiedzi graczy.

* Gracze:

Wpisz kod dostępu do quizu.

Odpowiadaj na pytania i obserwuj tabelę punktową.

---

## Wymagania

* Kompilator C++17 (np. g++)

* Python 3 (dla klienta)

* Make

* System obsługujący gniazda sieciowe (Linux, macOS, Windows z WSL)

---

### Ustawienie roli i nicku

```
ROLE CREATOR <nick>   – twórca quizu
ROLE PLAYER <nick>    – gracz
```

### Komendy dla twórcy (CREATOR)

```
ADD_QUESTION|<pytanie>|<opt1>;<opt2>;...|<poprawna_idx>|<punkty>|<czas_s>
    – dodaje pytanie do quizu

SAVE_QUIZ
    – zapisuje quiz, generuje kod, twórca dołącza do lobby

START
    – startuje quiz, wysyła pierwsze pytanie do graczy
```

### Komendy dla gracza (PLAYER)

```
JOIN|<kod_quizu>
    – dołącza do quizu przed startem

ANSWER|<numer_opcji>
    – odpowiada na aktualne pytanie
```

### Komunikaty serwera (informacyjne)

```
LOBBY_PLAYERS|<lista>     – aktualni gracze w lobby
QUESTION|...              – nowe pytanie dla graczy
QUESTION_VIEW|...         – nowe pytanie dla twórcy
REVEAL|<poprawna_idx>     – ujawnienie poprawnej odpowiedzi
SCORES|nick:punkty,...    – bieżące wyniki
FINAL_SCORES|nick:punkty,... – końcowe wyniki
QUIZ_END                  – quiz zakończony
QUIZ_CANCELLED            – quiz anulowany przed startem
QUIZ_ABORTED              – quiz przerwany w trakcie gry
ERR|<opis>                – błąd/niepoprawna akcja klienta
...
```
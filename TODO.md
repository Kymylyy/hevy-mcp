# TODO

## get_routines — zwracać szczegóły setów per ćwiczenie

Aktualnie `get_routines` w `src/hevy_mcp/tools.py` (linie ~668-682) wyciąga z API tylko nazwy ćwiczeń i łączną liczbę setów. API Hevy zwraca pełne dane setów (ciężar, powtórzenia, rest, RIR itd.) w tablicy `exercise["sets"]`, ale kod je ignoruje.

**Do zrobienia:** rozszerzyć output `get_routines` żeby per ćwiczenie zwracał schemat setów (np. 2x5, 1x5+, ciężar, typ setu).

## search_exercise — boostować ćwiczenia z historii usera

Obecny `search_exercise` szuka tylko po katalogu ćwiczeń i nie wie co user faktycznie robi. Przez to np. "squat" matchuje do "Squat Row" zamiast do "Squat (Barbell)" / "Front Squat", które user regularnie trenuje.

**Do zrobienia:** w `search_exercise` przy matchowaniu sprawdzać ostatnie treningi usera i boostować ćwiczenia które faktycznie wykonuje. Ćwiczenia z historii powinny mieć priorytet nad czystym dopasowaniem tekstowym z katalogu.

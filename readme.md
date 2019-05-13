# Pypres

Projekt został stworzony jako alternatywa dla [`oipres`](https://github.com/sio2project/oipres), który, ponieważ wymaga Qt 4.8, jest trudny do skompilowania.

Ten projekt rozwiązuje w nieoptymalny sposób ten problem dla Staszicowego SIO2 tworząc podobne narzędzie w Pythonie (3.7), które pobiera w prosty i naiwny sposób dane z interfejsu webowego.

Ponieważ to było prostsze, zamiast tworzenia prezentacji, `pyprez.py` tworzy długi plik HTML ze wszystkimi kodami i wynikami uczestników. Planowane jest dodanie w JavaScripcie automatycznego przewijania tej strony, ale na razie (na rozsądnych systemach operacyjnych) można kliknąć środkowy przycisk myszki i przesunąć ją lekko w dół żeby strona sama się przewijała. 

Zalety tego podejścia nad dedykowaną aplikacją to: prostota implementacji, łatwość rozszerzania funkcjonalności JavaScriptem, możliwość przesłania komuś pliku HTML, który można otworzyć w każdej nowoczesnej przeglądarce. Wady: ciężko się czyta tekst jeżeli strona się cały czas przewija, trudno na razie przewidzieć ile będzie trwała prezentacja i pewnie trwa ona dłużej niż taka sama w `oipres`.


### *TBD:*

- [ ] Readme: instalacja, konfiguracja (`config.yaml`), używanie (`--login`, `--password`, kiedy nie jest potrzebne logowanie?).
- [ ] Podsumowanie punktów dla każdego uczestnika.
- [ ] Automatyczne przewijanie (JS).  <!-- To można zsynchronizować z themem Papers, please mniej więcej tak, jak to robi tam menu główne XD -->
- [ ] Licencja (MIT?).
- [ ] Może demo?

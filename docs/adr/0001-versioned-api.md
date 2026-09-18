# ADR 0001 – Versionierte öffentliche API

## Entscheidung

Das Browserfrontend verwendet ausschließlich `/api/v1/*`. Interne `GameService`-Methoden und SQLite-Strukturen werden nicht als implizite öffentliche API behandelt.

## Gründe

- Frontend und Core können unabhängig refaktoriert werden.
- API-Contracts sind dokumentier- und testbar.
- spätere Mobile-/Desktop-Clients können dieselben Ressourcen nutzen.
- Providerwechsel verändert den Browsercontract nicht.

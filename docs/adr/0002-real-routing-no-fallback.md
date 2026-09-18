# ADR 0002 – Reales Routing ohne Luftlinien-Fallback

## Entscheidung

Ein Auftrag kann nur geroutet und angenommen werden, wenn Geocoding und Valhalla erfolgreich sind. Es existiert kein stiller Luftlinien- oder Demo-Polyline-Fallback.

## Konsequenz

Providerstörungen sind im MVP sichtbar und werden mit HTTP 502 signalisiert. Das ist gewollt, weil der reale Datenpfad selbst Teil des MVP-Ziels ist.

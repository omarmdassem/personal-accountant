# Personal Accountant (lokal, Python)

## Idee (kurz)
Ein schlankes, lokales Web-Tool, mit dem Nutzer:
- **Budgets** (Einnahmen/Ausgaben) je Kategorie/Subkategorie und Zeitraum definieren,
- **Transaktionen** manuell erfassen oder per **CSV** importieren,
- im **Dashboard** Budget vs. Ist sowie **Kategorie-Breakdowns** sehen.
Ziel: schneller Überblick über Geldflüsse – ohne Cloud, ohne komplizierte Einrichtung.

---

## Tech-Stack (festgelegt)
- **Backend/Web:** FastAPI (Python)
- **Templating & UI:** Jinja + **HTMX** (progressive Enhancement), **Tailwind CSS** (CDN)
- **Charts:** Chart.js (Script-Tag)
- **ORM/DB:** SQLModel + **SQLite** (lokal), Alembic für Migrationen
- **Auth:** **Session-basiert** (Secure Cookie, CSRF-Schutz)
- **Import:** CSV (XLSX später optional)
- **Währungen:** **Multi-Currency**, Umrechnung über **vom Benutzer gepflegte** FX-Sätze in eine Basiswährung (Standard: EUR)
- **Betrieb:** ausschließlich **lokal** (kein Deployment)

---

## Architektur (modularer Monolith)
Schichten & Verantwortlichkeiten:

~~~
[ Browser (HTML + HTMX) ]
          │  hx-get / hx-post (Formulare, Teilupdates)
          ▼
[ Web-Schicht: FastAPI Router + Jinja-Templates ]
          │  (thin: Inputs prüfen, Service aufrufen, View wählen)
          ▼
[ Domain-Schicht: Services ]
   - Auth (Signup/Signin/Signout/Delete)
   - Budgets (CRUD, Validierungen)
   - Transaktionen (CRUD)
   - Importer (CSV → Mapping → Validierung → Fehler-Report)
   - Dashboard (Aggregationen, FX-Umrechnung zur Basis)
          │  (persistiert/liest)
          ▼
[ Daten-Schicht: SQLModel + SQLite ]
   - Alembic Migrationen
~~~

**Datenmodell (MVP):**
- `users(id, email, hashed_password, created_at)`
- `budgets(id, user_id, type, category, subcategory, timeframe, amount, currency)`
- `transactions(id, user_id, type, category, subcategory, date, amount, currency, notes)`
- `fx_rates(id, user_id, code, rate_to_base, valid_from)`

**Ordnerstruktur (vereinfacht):**
~~~
app/
  main.py            # App-Wiring, Middleware, Router-Registrierung
  config.py          # Settings aus .env
  routers/           # HTTP-Endpunkte (thin)
    system.py
    ... (auth, budgets, transactions, importer, dashboard)
  services/          # Geschäftslogik (fat)  <-- (folgt)
  models.py          # SQLModel Tabellen     <-- (folgt)
  templates/         # Jinja-Templates/Partials (HTMX)
  static/            # CSS/JS/Assets
~~~

**Prinzipien:**
- Router → Services → Daten (einzige Richtung; keine Kreuz-Imports).
- Server-seitige Validierung; Fehler werden im Template/Partial angezeigt.
- Sessions: `HttpOnly`, `SameSite=Lax`, CSRF-Token in POST-Forms.
- CSV-Import mit Header-Mapping, Dry-Run, Zeilen-Fehlerdatei (`errors.csv`).

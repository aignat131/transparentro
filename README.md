# TransparentRO — banii publici, pe înțeles

Aplicație web care arată, pentru cetățeanul de rând, **ce cumpără instituțiile publice, de la cine și cu cât**,
istoricul firmelor și **semnale de verificat** (nu acuzații). MVP: județul **Sibiu**; județul este un parametru
peste tot, deci extinderea la alte județe sau la toată țara este o schimbare de configurare.

Datele provin din surse oficiale: SEAP/SICAP (rapoarte publicate pe data.gov.ro), ANAF, ONRC, BNR.
Detalii în [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md); deciziile luate în [docs/DECISIONS.md](docs/DECISIONS.md).

## Instalare și pornire

Cerințe: **Docker** (cu `docker compose` v2) și **GNU make**. Pentru testele Playwright: Node 20+.

```bash
make up          # creează .env din .env.example, pornește db + api + web
make etl         # import REAL (SEAP 2025–2026 pentru TARGET_COUNTIES) + ANAF + bilanțuri + hartă + semnale
make test        # pytest (ETL + API) într-un container, pe baza tro_test
make e2e         # Playwright (cu stack-ul pornit; prima dată: cd frontend && npm ci && npx playwright install chromium)
```

- Site: http://localhost:3000 · API + documentație OpenAPI: http://localhost:8000/docs
- `make etl-sample` — import real rapid, un singur trimestru (2025 T4).
- `make etl-synthetic` — date **SINTETICE** pentru dezvoltare (nume „(SINTETIC)”, CUI-uri `99…`, banner în UI).
- `make etl-onrc` — completează firmele din registrul ONRC (descarcă ~1 GB).
- `make risk` — recalculează semnalele după ce modificați `backend/tro/etl/risk_thresholds.yaml`.
- `make lint` — ruff + mypy. `make down` / `make clean` (șterge și volumele).

Primul `make etl` durează ~30–40 de minute: descarcă ~1 GB de rapoarte SEAP, interoghează ANAF pentru
~20.000 de CUI-uri de autorități (1 cerere/secundă, câte 100 CUI) și ~400 de bilanțuri. Rulările următoare sunt
incrementale (fișierele deja importate sunt sărite; cache-ul ANAF e refolosit).

**Înainte de rulări regulate**, puneți în `.env` un `USER_AGENT` cu un contact real (e-mail sau URL) — serviciile
publice (Nominatim, ANAF) cer ca clienții automați să fie identificabili.

## Arhitectură

```
            data.gov.ro (CKAN)  ANAF v9 + bilanț  BNR XML  ONRC CSV  Nominatim
                     │                │             │          │         │
                     └───────────────►│  ETL (python -m tro.etl)  ◄──────┘
                                      │  descoperire → descărcare → parsare (după antet)
                                      │  → județ via ANAF → upsert idempotent → deduplicare
                                      │  → îmbogățire firme → geocodare → semnale
                                      ▼
                               PostgreSQL 16  (FTS simple+unaccent, proveniență, erori per rând)
                                      │
                               FastAPI (tro.api)  — cache TTL, CORS, OpenAPI, CSV, alerte, /explain
                                      │
                               Next.js 14 (App Router, SSR) — Tailwind + shadcn/ui, Recharts, Leaflet
```

- `backend/tro/models.py` — model inspirat din OCDS: `Authority` (buyer), `Company` (supplier), `Procedure`
  (tender), `Contract` (award/contract), `ContractAmendment`, `RiskSignal`, `SourceRecord` (proveniență), plus
  `ImportRun`/`ImportError_` (jurnal), `ExchangeRate`, `AnafCache`, `LocalityGeo`, `Subscription`.
- `backend/tro/normalize.py` — CUI (fără „RO”, spații, zerouri), denumiri (fără diacritice și forme juridice),
  detecția persoanelor fizice (GDPR).
- `backend/tro/etl/sources/` — câte un modul per sursă; `seap_parse.py` mapează antetele, `seap.py` încarcă.
- `backend/tro/etl/risk.py` + `risk_thresholds.yaml` — cele 6 semnale.
- `frontend/app/` — pagini; `frontend/components/` — UI; `frontend/e2e/` — Playwright.

Toate listele API acceptă `?county=SB|CJ|…|all`; fără parametru se folosește `DEFAULT_COUNTY`.

## Cum adaug un județ nou (sau toată țara)

1. În `.env`: `TARGET_COUNTIES=SB,CJ` (coduri auto, separate prin virgulă) sau `TARGET_COUNTIES=*` pentru toată țara.
   Pentru a schimba județul afișat implicit: `DEFAULT_COUNTY=CJ` (și rebuild la web: `make up`).
2. `make etl` — fișierele SEAP deja descărcate sunt refolosite; filtrarea se face din nou pentru noile județe
   (importul e marcat per set de județe). Cache-ul ANAF acoperă deja toate autoritățile din țară.
3. Toată țara înseamnă ~4 mil. de rânduri/an: recomandat un server cu ≥ 8 GB RAM și Postgres reglat.

## Cum adaug o sursă nouă

1. Creați `backend/tro/etl/sources/<sursa>.py` cu o funcție `import_<sursa>(session, ...)` care:
   - deschide un `RunLog(session, "<sursa>", params)` și înregistrează erorile cu `run.error(ref, mesaj, rând)`;
   - construiește rânduri cu un `source_id` **stabil** (derivat din identificatorii sursei) și scrie cu
     `tro.etl.upsert.upsert(...)` (INSERT … ON CONFLICT) — astfel re-rularea e idempotentă;
   - scrie proveniența în `SourceRecord` (sursă, URL, hash conținut, dată import).
2. Dacă e nevoie de coloane noi: modificați `models.py` și generați o migrare
   (`docker compose run --rm api alembic revision --autogenerate -m "..."`).
3. Adăugați comanda în `backend/tro/etl/cli.py` (și, dacă e cazul, în `all`) și un test cu un fixture mic în
   `backend/tests/`.
4. Documentați sursa în `docs/DATA_SOURCES.md`.

Pentru o eventuală sursă OCDS: mapați `buyer`→`Authority`, `awards[].suppliers`→`Company`,
`tender`→`Procedure`, `contracts`→`Contract`, `contracts[].amendments`→`ContractAmendment`, cu
`source_id = ocid + id`.

## Configurare (Faza 3)

- **Alerte e-mail**: `MAIL_PROVIDER=console` (doar log, implicit) sau `smtp` + `SMTP_*`. Abonare cu double
  opt-in din paginile de instituție/firmă; trimiterea rezumatelor: `docker compose --profile etl run --rm etl alerts`
  (rulată și de workflow-ul ETL zilnic). `API_BASE_URL`/`PUBLIC_BASE_URL` trebuie să fie adresele publice.
- **Explicații AI** (`GET /explain/{id}`, butonul „Explică-mi contractul”): `ANTHROPIC_API_KEY=...`
  (gol = dezactivat), `ANTHROPIC_MODEL` (implicit `claude-opus-5-5`). Explicațiile sunt salvate și refolosite.

## CI

- `.github/workflows/ci.yml` — ruff, mypy, migrări, pytest (Postgres ca serviciu), tsc + lint + build Next,
  apoi Playwright pe stack-ul docker cu date sintetice.
- `.github/workflows/etl.yml` — ETL incremental zilnic (02:15 UTC) + alerte; necesită secretul
  `PROD_DATABASE_URL` și opțional variabilele `TARGET_COUNTIES`, `SEAP_YEARS`, `ETL_USER_AGENT`.

## Licență și date

Datele sunt publicate de instituțiile statului ca date deschise. Semnalele sunt indicii de verificat, nu acuzații.
Persoanele fizice sunt anonimizate. Vezi pagina /disclaimer din aplicație.

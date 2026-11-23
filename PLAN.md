# PLAN — TransparentRO (MVP Sibiu)

Aplicație web de transparență a banilor publici: ce cumpără instituțiile, de la cine, cât,
istoricul firmelor și semnale de verificat. MVP pe județul Sibiu, extensibil la toată țara.

## Structura repo-ului

```
TransparentRO/
├── PLAN.md, README.md, RAPORT_FINAL.md
├── Makefile                  # make up / etl / test / lint / e2e
├── docker-compose.yml        # db, api, web, etl
├── .env.example
├── .github/workflows/        # ci.yml (lint+teste), etl.yml (ETL zilnic programat)
├── docs/
│   ├── DATA_SOURCES.md       # ce am găsit la fiecare sursă (URL, format, câmpuri, frecvență)
│   └── DECISIONS.md          # decizii luate autonom
├── backend/                  # un singur pachet Python `tro`, folosit de api și etl
│   ├── Dockerfile, pyproject.toml, alembic.ini
│   ├── alembic/versions/     # migrări
│   ├── tro/
│   │   ├── config.py, db.py, models.py
│   │   ├── normalize.py      # CUI, denumiri, PFA/persoane fizice (GDPR)
│   │   ├── cpv.py            # CPV → categorii pe înțeles
│   │   ├── api/              # FastAPI: routers, scheme pydantic, cache
│   │   └── etl/
│   │       ├── cli.py        # python -m tro.etl <comanda>
│   │       ├── sources/      # ckan, seap, anaf, onrc, bnr, geocode
│   │       ├── synthetic.py  # generator date SINTETICE (is_synthetic=true)
│   │       ├── risk.py       # semnale de risc
│   │       └── risk_thresholds.yaml
│   └── tests/                # pytest (ETL + API)
└── frontend/                 # Next.js 14 App Router + Tailwind + shadcn/ui + Recharts + Leaflet
    ├── app/ (pagini), components/, lib/
    └── e2e/                  # Playwright
```

## Faze și verificări

### Faza 0 — Cercetare surse (FĂCUT înainte de cod)
- CKAN data.gov.ro: seturile „Achiziții publice YYYY” (ADR) — XLSX/XLS/ODS trimestriale, NU OCDS.
- ANAF v9 (TVA/date generale) + /bilant; BNR (curs.bnr.ro); ONRC (CSV `^`).
- Verificare: documentat în docs/DATA_SOURCES.md.

### Faza 1 — Fundația
1. Schelet + docker-compose + Makefile + .env.example.
   *Verific:* `make up` pornește db/api/web; `/health` răspunde.
2. Modele SQLAlchemy + migrare Alembic (extensii unaccent/pg_trgm, config FTS `ro_unaccent`).
   *Verific:* `alembic upgrade head` pe DB gol; teste pe normalizare și căutare fără diacritice.
3. ETL: BNR → SEAP (descoperire CKAN, detecție tip raport după antet, filtrare pe județ via ANAF)
   → ANAF firme (+ bilanț) → ONRC (opțional, fișier mare) → geocodare localități → sintetic.
   *Verific:* teste pytest pe parsere cu fixture-uri mici; rulare reală pe un trimestru;
   re-rulare = aceleași numere (idempotență); erori per rând logate în `import_errors`.
4. API FastAPI cu toate endpoint-urile, filtre, paginare, sortare, cache, CORS, OpenAPI.
   *Verific:* pytest pe API + curl pe fiecare endpoint pe stack-ul pornit.
5. Frontend Next.js: acasă, instituție, firmă, contract, căutare, listă contracte, hartă,
   pagini statice, glosar cu tooltip, SEO (metadata, sitemap, OG).
   *Verific:* build fără erori; Playwright: căutare → firmă, instituție → contract, filtre contracte.
   → commit „Faza 1”.

### Faza 2 — Semnale de risc
- 6 semnale calculate în ETL (praguri în `risk_thresholds.yaml`), formulate neutru,
  cu explicație și link la sursă; pagina /semnale cu filtre; afișare pe firmă/contract/instituție.
  *Verific:* teste unitare pe fiecare semnal (cazuri pozitive/negative); curl /risk-signals; Playwright.
  → commit „Faza 2”.

### Faza 3 — Extra (în ordine)
1. Alerte e-mail cu double opt-in (provider configurabil: console/SMTP).
2. /explain/{contract_id} cu Anthropic API (dezactivat fără cheie).
3. Export CSV pentru orice listă filtrată.
4. Județul ca parametru peste tot (fără Sibiu hardcodat).
   *Verific:* teste + curl. → commit „Faza 3”.

### Final
- README.md, RAPORT_FINAL.md, CI GitHub Actions. → commit final.

# Raport final — TransparentRO (MVP Sibiu)

Data: 23.11.2026. Toate cele trei faze sunt implementate, testate și commit-uite. Baza de date locală conține
**exclusiv date reale** pentru județul Sibiu (datele sintetice au fost generate, folosite pentru dezvoltare și
teste, apoi șterse din baza principală).

## 1. Ce funcționează (verificat)

| Componentă | Stare | Cum am verificat |
|---|---|---|
| `make up` (db + api + web în Docker) | ✅ | stack pornit, `/health` OK, toate paginile 200 |
| ETL SEAP (data.gov.ro, 7 trimestre: 2025 T1–T4, 2026 T1–T3) | ✅ | ~6,1 mil. rânduri naționale citite, 123.440 rânduri pentru Sibiu |
| Județul autorităților via ANAF v9 (cache 23.897 CUI) | ✅ | 339 de instituții din județul Sibiu |
| Îmbogățire firme ANAF (8.611 / 9.045 găsite) + bilanțuri 2024–2025 (775 cu cifră de afaceri) | ✅ | profil, data înregistrării, CAEN, stare, cifră de afaceri |
| BNR (17.726 cursuri), conversii la data contractului | ✅ | teste unitare (zile nelucrătoare → curs anterior) |
| Idempotență, incrementalitate, erori per rând | ✅ | teste: 3 importuri succesive → aceleași numere; 7.734 rânduri fără CUI logate, importul continuă |
| Deduplicare (asocieri, loturi, acord-cadru vs. subsecvente) | ✅ | 8.469 rânduri excluse din totaluri; teste dedicate |
| GDPR: 464 persoane fizice/PFA anonimizate | ✅ | teste API: fără nume, CUI, nr. registru; `noindex`; payload ANAF redactat |
| API: instituții, firme, contracte (filtre/paginare/sortare), căutare, statistici, hartă, semnale, CSV, corecții, OpenAPI, cache | ✅ | 89 teste pytest + curl pe fiecare endpoint |
| Căutare fără diacritice (ș/ş, ț/ţ) | ✅ | test cu „Școală”, „scoala”, „Şcoala” (sedilă) |
| Frontend (RO, mobile-first, accesibil): acasă, instituție, firmă, contract, semnale, hartă, metodologie, surse, despre, disclaimer + formular corecție, glosar cu tooltip-uri | ✅ | Playwright 8/8 (4 fluxuri × desktop + mobil), capturi de ecran verificate |
| SEO: metadata per entitate, sitemap, robots, imagini OG | ✅ | test e2e pe `/sitemap.xml` și `/opengraph-image` |
| Semnale de risc (6 tipuri) | ✅ 5 active pe date reale | 681 semnale: concentrare 255, venituri publice 138, firmă nouă 133, fragmentare 121, acte adiționale 34; teste pozitive/negative per semnal |
| Alerte e-mail cu double opt-in | ✅ (provider `console`) | test complet: abonare → confirmare → doar contracte noi → dezabonare |
| `/explain/{id}` (Anthropic API) | ✅ cod + teste fără rețea | **neapelat real** — nu există cheie în mediu (răspunde 503 „neactivat”) |
| Export CSV pentru orice listă filtrată | ✅ | teste: numărul de rânduri = totalul listei |
| Județul ca parametru (`?county=`, `TARGET_COUNTIES`, `DEFAULT_COUNTY`) | ✅ | test: `county=CJ` gol, `county=all` plin; niciun „Sibiu” hardcodat în cod |
| CI (lint, mypy, teste, build, e2e) + ETL zilnic | ✅ scris | **nerulat pe GitHub** (repo-ul nu are remote) |

## 2. Date reale vs. sintetice

- **Reale** (în baza locală acum): contracte, achiziții directe, notificări, atribuiri fără anunț, anunțuri de
  inițiere, modificări de contract (SEAP, 2025-01 → 2026-10), date firme ANAF, bilanțuri ANAF 2024–2025 pentru
  ~400 de furnizori importanți, cursuri BNR 2024–2026, coordonate localități (OpenStreetMap/Nominatim).
- **Sintetice**: doar la cerere (`make etl-synthetic`) și în teste. Marcate `is_synthetic=true`, nume „(SINTETIC)”,
  CUI-uri `99xxxxxxxx`, banner pe toate paginile.
- **Neimportat încă**: ONRC (importatorul există și e testat pe fragmente, dar fișierul are ~660 MB; rulați
  `make etl-onrc`). Anii SEAP 2007–2024 (seturile există; `SEAP_YEARS=2024,2025,2026 make etl`).

Ce trebuie rulat ca să reconstruiți datele reale de la zero:
```bash
make up
make etl          # ~30–40 min prima dată
make etl-onrc     # opțional, ~1 GB
```

## 3. Ce a rămas de făcut / limitări

1. **„Un singur ofertant”** — implementat și testat, dar **inactiv pe date reale**: numărul de oferte nu apare în
   niciun raport SEAP de pe data.gov.ro, iar API-ul intern al e-licitatie.ro nu l-a expus în testele mele (D-07).
2. **Pragurile legale** din `risk_thresholds.yaml` (270.120 / 900.400 lei) trebuie **validate juridic**; pragurile
   sectoriale (Legea 99/2016) nu sunt tratate separat, deci la companiile de utilități (Transgaz, Romgaz)
   semnalul de fragmentare poate fi prea sensibil.
3. **Clasificarea tipului de instituție** e euristică (după denumire).
4. Companiile naționale cu sediul în județ (Transgaz, Romgaz — Mediaș) domină totalurile „Sibiu” (D-20).
5. Linkul spre sursă duce la fișierul oficial de pe data.gov.ro + căutarea numărului pe e-licitatie.ro; rapoartele
   nu conțin ID-ul intern SICAP, deci nu există link direct la pagina anunțului.
6. Valorile din SEAP sunt cele declarate (de regulă fără TVA); erorile din datele primare sunt afișate ca atare.
7. Unele contracte vechi (2020–2023) apar pentru că au fost publicate târziu; graficele pe ani le arată la anul semnării.
8. Formularul de corecție salvează cererile în `correction_requests`, dar nu există încă o interfață de administrare.

## 4. Riscuri cunoscute

- **Juridic / reputațional**: chiar formulate neutru, semnalele pot fi percepute ca acuzații. Recomand revizuirea
  textelor și a disclaimer-ului de către un jurist înainte de publicare și un proces de răspuns la corecții.
- **GDPR**: detecția persoanelor fizice e bazată pe reguli (denumire, formă juridică, CNP); pot exista cazuri
  ratate (ex. PFA cu denumire atipică fără date ANAF). Recomand un DPIA înainte de lansare.
- **Stabilitatea surselor**: formatul rapoartelor SEAP se schimbă între trimestre (2026 T3 a venit cu antete
  diferite — rezolvat, cu test de regresie). Importatorul marchează `failed` un fișier fără rânduri valide.
- **Politețe față de servicii**: ANAF și Nominatim au limite; ETL-ul respectă ≥1,1 s între cereri, dar User-Agent-ul
  trebuie completat cu un contact real (D-19).
- **Securitate**: API-ul nu are autentificare (date publice) și nici rate limiting; `/explain` consumă credit
  Anthropic — de pus rate limiting la reverse proxy înainte de publicare. Next.js fixat pe 14.2.35 (patch de securitate).
- **Explicațiile AI** pot conține greșeli; sunt etichetate ca generate automat și nu au fost testate cu o cheie reală.

## 5. Pașii următori (în ordine)

1. **Completați `USER_AGENT`** în `.env` cu un e-mail/URL de contact real.
2. **Validați juridic** pragurile din `backend/tro/etl/risk_thresholds.yaml`, textele semnalelor și pagina
   /disclaimer; decideți dacă excludeți companiile naționale (Transgaz, Romgaz) din totalurile județene.
3. **Rulați `make etl-onrc`** pentru data înmatriculării din registrul comerțului (mai precisă decât ANAF).
4. **Creați repo-ul pe GitHub**, împingeți codul, setați secretul `PROD_DATABASE_URL` și verificați workflow-urile CI și ETL.
5. **Adăugați `ANTHROPIC_API_KEY`** și testați „Explică-mi contractul” pe câteva contracte; puneți rate limiting.
6. **Configurați SMTP** (`MAIL_PROVIDER=smtp`) și testați un flux real de abonare.
7. **Cereți către ADR** (Legea 544/2001) exportul cu numărul de oferte (sau OCDS) pentru semnalul „un singur ofertant”.
8. Extindeți anii (`SEAP_YEARS=2022,...`) și apoi județele (`TARGET_COUNTIES`), urmărind performanța bazei.
9. Construiți o mică interfață de administrare pentru cererile de corecție.

# Surse de date — ce am verificat (23.11.2026)

Toate verificările au fost făcute direct din mediul de dezvoltare, cu cereri HTTP reale.

## 1. SEAP / SICAP — achiziții publice (data.gov.ro, Agenția pentru Digitalizarea României)

**Constatare importantă:** pe data.gov.ro datele SEAP **nu sunt publicate în format OCDS**.
Căutarea CKAN `q=ocds` întoarce 0 rezultate. Se publică rapoarte trimestriale tabelare.

- Descoperire: `https://data.gov.ro/api/3/action/package_show?id=achizitii-publice-{AN}`
  (seturi existente: `achizitii-publice-2016` … `achizitii-publice-2026`; 2007–2015 în
  `achizitii-publice-2007-2016-contracte6`). Organizație: `agentia-pentru-agenda-digitala-a-romaniei`.
- Format: XLSX (majoritar), XLS (2024 T I–III), **ODS** (2026 T II, deși CKAN spune „.xlsx”).
  Mărimi: achiziții directe 60–170 MB/trimestru, contracte 10–70 MB, restul < 25 MB.
- Frecvență: trimestrială, cu întârziere de ~1–2 luni după încheierea trimestrului.
- Calitate: resurse duplicate (2024 are fiecare fișier de două ori), etichete greșite
  (2025 T II „Notificări…” arată de fapt spre fișierul „Anunțuri de atribuire…”), extensii greșite.
  ⇒ importatorul **detectează tipul raportului după antetul coloanelor**, nu după nume.
- **Nu există coloană de județ/localitate a autorității.** ⇒ județul se rezolvă prin ANAF după CUI.
- **Nu există numărul de oferte primite** în niciun raport.

Rapoarte (tip intern → coloane relevante):

| Tip intern | Nume resursă | Coloane (antet normalizat) |
|---|---|---|
| `ad` | Achiziții directe | Autoritate contractanta, CUI autoritate contractanta, Numar achizitie directa (DA…), Data publicare, Denumire achizitie, Cod CPV, Denumire CPV, Tip contract, Finantare prin fonduri comunitare?, Denumire program, Data finalizare, Valoare achizitie (RON), Ofertant castigator, CUI ofertant castigator |
| `dan` | Notificări de atribuire la cumpărarea directă | … Numar notificare (DAN…), Obiectul achizitiei, … Valoare achizitie (RON), Ofertant castigator, CUI ofertant castigator |
| `contracte` | Contracte | Autoritate contractanta, CUI AC, Tip anunt, Tip procedura, Numar anunt initiere, Data publicare, Tip legislatie, Tip incheiere contract, Tip contract, Tip criterii de atribuire, Cod CPV, Denumire CPV, Numar lot, Numar anunt atribuire, Data publicare (atribuire), Data contract, Numar contract, Incheiat prin, Valoare contract (RON), Ofertant castigator, CUI ofertant castigator. Al doilea rând conține coduri tehnice (DENUMIRE_AC, CUI_AC…) și este ignorat. |
| `atribuire_fara` | Anunțuri de atribuire la proceduri fără anunț de inițiere | … Tip procedura (ex. Negociere fara publicare prealabila), Numar anunt atribuire, … Data contract, Numar contract, Denumire contract, Valoare atribuita (RON), Ofertant castigator, CUI ofertant castigator |
| `initiere` | Anunțuri de inițiere publicate | … Tip procedura, Stare procedura, Numar anunt initiere, Data publicare, Tip contract, Denumire procedura, Cod CPV, Valoare estimata procedura (RON), Moneda |
| `modificari` | Date din modificare contract | Autoritate contractanta, CUI AC, Numar anunt atribuire, Data publicare, Numar contract, Data contract, Descrierea modificarilor, Valoarea totala … inainte de modificari, Moneda, Valoarea totala … dupa modificari, Moneda |
| (ignorat) | Invitații SAD | sistem de achiziții dinamic — volum mic, nu e folosit în MVP |

Exemplu URL (2025 T IV, contracte):
`https://data.gov.ro/dataset/e0cf7ffc-1fa0-4ffb-a82f-c83981d81f21/resource/a1936e88-7fc5-4ffc-af65-6f946e98a005/download/contracte-t_iv_2025.xlsx`

Volum național 2025 T IV: 603.525 achiziții directe, 152.321 rânduri contracte, 84.612 notificări,
3.893 modificări, 2.264 atribuiri fără anunț, 5.942 anunțuri de inițiere.

### SICAP (e-licitatie.ro) — API public al interfeței web
- `POST https://www.e-licitatie.ro/api-pub/NoticeCommon/GetCANoticeList/` funcționează (JSON),
  `GET /api-pub/C_PUBLIC_CANotice/get/{caNoticeId}` funcționează doar cu antet `Referer`.
- `robots.txt` nu există (404). API-ul nu este documentat oficial.
- Detaliul anunțului de atribuire conține `lowestOffer`/`highestOffer`, `sysReasonForUniqueOfferer`,
  dar în exemplele testate lista de loturi atribuite (`section5.contractLotList`) era goală, deci
  numărul de oferte nu a putut fi extras fiabil. **Nu este folosit în MVP** (vezi DECISIONS.md, D-07).

## 2. ANAF — date firme după CUI

- **Endpoint actual (verificat):** `POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva`
  Corp: `[{"cui": 4240600, "data": "AAAA-LL-ZZ"}, …]` (max. 100 CUI/cerere, ANAF cere max. 1 cerere/secundă).
  Versiunea veche `…/PlatitorTvaRest/api/v8/ws/tva` întoarce 404.
- Răspuns: `found[]` / `notFound[]`. Câmpuri folosite: `date_generale.{cui, denumire, adresa,
  stare_inregistrare, data_inregistrare, cod_CAEN, forma_juridica, forma_organizare, nrRegCom}`,
  `inregistrare_scop_Tva.scpTVA`, `stare_inactiv.statusInactivi`,
  `adresa_sediu_social.{sdenumire_Judet, scod_JudetAuto, sdenumire_Localitate}`.
- Folosit pentru: (a) județul/localitatea autorităților contractante (SEAP nu le are),
  (b) profilul firmelor (data înregistrării, CAEN, stare, formă juridică ⇒ detectare PFA/II/IF).
- **Bilanț:** `GET https://webservicesp.anaf.ro/bilant?an=2024&cui=160796` — indicatori `I13` (cifra de
  afaceri netă), `I20` (nr. mediu salariați) etc. Disponibil pentru anii închiși (2024 e ultimul complet).
- Frecvență: zilnică (date fiscale), bilanțuri anuale.

## 3. ONRC — firme înregistrate (data.gov.ro, organizația `onrc`)

- Seturi periodice, ex. `firme-06-10-2025` (cel mai recent găsit). Separator `^`, UTF-8 cu BOM.
- `od_firme.csv` (~660 MB): `DENUMIRE^CUI^COD_INMATRICULARE^DATA_INMATRICULARE^EUID^FORMA_JURIDICA^ADR_TARA^ADR_JUDET^ADR_LOCALITATE^…`
  (dată în format `ZZ/LL/AAAA`; CUI = 0 la unele firme vechi).
- `od_stare_firma.csv` (~88 MB): `COD_INMATRICULARE^COD` — codul de stare (nomenclator `n_stare_firma.csv`
  în setul `firme-inregistrate-la-registrul-comertului-pana-la-data-de-05-05-2025`).
- `od_caen_autorizat.csv` (~390 MB): `COD_INMATRICULARE^COD_CAEN_AUTORIZAT^VER_CAEN_AUTORIZAT`.
- Frecvență: aproximativ lunară/trimestrială.
- Importatorul ONRC este opțional (fișier mare): completează data înmatriculării și forma juridică
  doar pentru CUI-urile deja prezente în baza de date.

## 4. BNR — cursuri de schimb

- **Funcționează:** `https://curs.bnr.ro/nbrfxrates.xml` (zilnic) și
  `https://curs.bnr.ro/files/xml/years/nbrfxrates{AN}.xml` (an întreg).
- `https://www.bnr.ro/nbrfxrates.xml` redirecționează (302) spre pagina principală — nu mai merge.
- Format: `<DataSet><Body><Cube date="2025-01-03"><Rate currency="EUR">4.9749</Rate>…`, atributul
  `multiplier` pentru HUF, JPY etc. Frecvență: zilnică (zile lucrătoare). Pentru zile fără curs
  se folosește ultimul curs anterior publicat.

## 5. OpenStreetMap / Nominatim — coordonate localități (pentru hartă)

- `https://nominatim.openstreetmap.org/search?format=json&q=…` — max. 1 cerere/secundă, User-Agent
  identificabil (politica de utilizare Nominatim). Rezultatele se salvează în tabelul `locality_geo`,
  deci fiecare localitate se cere o singură dată.
- Tile-uri hartă: `https://tile.openstreetmap.org/{z}/{x}/{y}.png` cu atribuire © OpenStreetMap.

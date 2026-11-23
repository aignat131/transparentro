# Decizii luate autonom

Fiecare decizie: context → alegere → consecințe. Ordinea e cronologică.

## D-01. Datele SEAP nu sunt OCDS → importăm rapoartele tabelare
Pe data.gov.ro nu există seturi OCDS pentru SEAP (căutarea „ocds” întoarce 0 rezultate). ADR publică rapoarte
trimestriale XLSX/XLS/ODS. Modelul de date rămâne **inspirat din OCDS** (buyer → `authorities`,
supplier → `companies`, tender → `procedures`, award/contract → `contracts`, amendment → `contract_amendments`),
ca o eventuală sursă OCDS să poată fi adăugată ca un importator nou, fără schimbări de schemă.

## D-02. Tipul raportului se detectează după antet, nu după numele resursei
Resursele CKAN au etichete greșite (ex. 2025 T II „Notificări…” → fișierul „Anunțuri de atribuire…”),
extensii greșite (ODS etichetat .xlsx) și duplicate. Antetul e sursa de adevăr; coloanele se identifică prin
prefixe ale antetului simplificat (tolerează variații între ani — ex. 2026 T III are „CUI”, „Ofertant”,
„Data atribuire” în loc de denumirile complete).

## D-03. Județul autorității se află prin ANAF
Rapoartele SEAP nu au județ/localitate. Pentru fiecare CUI de autoritate cerem ANAF v9 (100 CUI/cerere,
≥1,1 s între cereri) și păstrăm răspunsul în `anaf_cache`. Primul import național interoghează ~8–20 mii CUI-uri
(câteva minute); importurile ulterioare folosesc cache-ul (reîmprospătare după 60 de zile).
Consecință: extinderea la alt județ = schimbarea `TARGET_COUNTIES` (sau `*` pentru toată țara).

## D-04. Chei sursă stabile pentru idempotență
- achiziții directe: `ad:<DA…>`, notificări: `dan:<DAN…>`;
- contracte: `c:<nr. anunț atribuire>:<hash(lot, nr. contract, CUI furnizor, nume furnizor)>`;
- atribuiri fără anunț: `af:…` (aceeași logică); proceduri: `p:<nr. anunț inițiere sau atribuire>`;
- modificări: `m:<hash(autoritate, anunț, contract, dată, valori, descriere)>`.
Toate scrierile sunt `INSERT … ON CONFLICT`. Un fișier deja importat cu succes (aceeași resursă CKAN, aceeași
dată de modificare, aceleași județe țintă) este sărit; `--force` îl reimportă.

## D-05. Erori per înregistrare, nu per fișier
Fiecare rând invalid se scrie în `import_errors` (cu referința `fișier:linie`), importul continuă. Loturile
de upsert care eșuează sunt reluate rând cu rând. Un fișier din care **niciun** rând nu e valid este marcat
`failed` (nu `ok`), ca să nu fie sărit la rularea următoare.

## D-06. GDPR — persoane fizice
Detectăm PFA/II/IF/cabinete individuale după denumire, formă juridică ANAF/ONRC și CUI de 13 cifre (CNP).
- numele nu se stochează (se salvează „Persoană fizică autorizată”), alias-urile nu se păstrează;
- în `anaf_cache` răspunsul ANAF pentru persoane fizice e redactat (fără nume, adresă, telefon);
- în API cheia este `pf-<id>` (nu CUI-ul), CUI-ul/data înființării/nr. registru nu se expun;
- paginile lor au `noindex` și nu apar în sitemap.

## D-07. Numărul de oferte nu există în datele deschise
Niciun raport SEAP nu are numărul de oferte. API-ul intern al e-licitatie.ro (nedocumentat) a fost testat:
detaliul anunțului de atribuire nu a returnat loturi cu număr de oferte în exemplele încercate. Nu facem
scraping. Coloana `procedures.number_of_offers` există, semnalul „un singur ofertant” e implementat și testat,
dar **pe date reale rămâne inactiv** până la o sursă (ex. solicitare Legea 544/2001 către ADR, sau OCDS).

## D-08. Valori și monede
Rapoartele SEAP dau valorile deja în RON (fără TVA, cum sunt declarate). Conversia BNR (cursul din ziua
contractului, sau ultimul curs anterior pentru zile nelucrătoare) se aplică acolo unde apare altă monedă
(modificări de contract, valori estimate). Sursa BNR funcțională este `curs.bnr.ro` (www.bnr.ro redirecționează).

## D-09. Pragurile pentru fragmentare
Pragurile achiziției directe (270.120 lei produse/servicii, 900.400 lei lucrări, fără TVA, Legea 98/2016 art. 7
alin. 5, după Legea 208/2022) sunt în `backend/tro/etl/risk_thresholds.yaml`, cu istoric pe date de intrare în
vigoare. **Trebuie verificate juridic înainte de publicare.** Pragurile sectoriale (Legea 99/2016) nu sunt tratate
separat.

## D-10. Semnalul „firmă nouă” și acoperirea datelor
„Primul contract” înseamnă primul din datele importate. Ca să nu raportăm greșit, semnalul se calculează doar
pentru firmele înființate după prima dată de publicare din baza de date.

## D-11. Bilanțuri ANAF doar pentru furnizorii importanți
O cerere per firmă per an (≥1,1 s) ar însemna ore pentru toți furnizorii. Cerem bilanțuri doar pentru firmele cu
încasări publice ≥ `BILANT_MIN_PUBLIC_RON` (implicit 50.000 lei), maxim `BILANT_MAX_COMPANIES` (400).
Indicatorii se citesc după **denumire** („Cifra de afaceri neta”, „Numar mediu de salariati”), nu după cod:
formularele diferă între tipuri de entități (un `I20` de 2,9 miliarde a apărut la o entitate cu alt formular).

## D-12. ONRC opțional
`od_firme.csv` are ~660 MB; ANAF oferă deja data înregistrării, CAEN și starea. Importatorul ONRC există
(streaming, doar CUI-urile din baza noastră) dar rulează separat (`make etl-onrc`); ONRC are prioritate la
data înființării când e importat (`founded_source`).

## D-13. Date sintetice separate de cele reale
Generatorul produce nume clar fictive cu „(SINTETIC)”, CUI-uri de 10 cifre care încep cu `99` (imposibile pentru
firme reale), coordonate aleatoare. Baza de date principală conține **doar date reale** după `make etl`;
sinteticele sunt pentru dezvoltare (`make etl-synthetic`) și teste. Bannerul apare automat dacă există date sintetice.

## D-14. Geocodare la nivel de localitate
Coordonatele vin din Nominatim, per localitate (nu per adresă), cerute o dată și păstrate în `locality_geo`.
Harta grupează instituțiile din aceeași localitate într-o singură bulă (aria ∝ total cheltuieli).

## D-15. shadcn/ui fără CLI
Componentele shadcn (button, card, input, badge, popover) sunt copiate în `frontend/components/ui`, conform
modelului shadcn (codul aparține proiectului). Tooltip-urile de glosar folosesc Popover Radix: funcționează la
atingere pe mobil și cu tastatura, nu doar la hover.

## D-16. Frontend fără JavaScript obligatoriu pentru filtre
Căutarea și filtrele sunt formulare GET simple, deci funcționează și fără JS, sunt partajabile prin URL și
indexabile. Doar graficele, harta și formularele de alertă/corecție necesită JS.

## D-17. Next.js 14.2.35
Am fixat ultimul patch 14.2.x (14.2.18 are o vulnerabilitate publicată).

## D-18. Rânduri repetate și acorduri-cadru (evitarea dublei numărări)
Verificarea totalurilor pe date reale (32,7 mld. lei la prima rulare — nerealist) a arătat trei surse de dublare
în raportul „Contracte”:
1. **asocieri**: fiecare membru apare pe un rând separat, cu valoarea întreagă a contractului;
2. **loturi**: același contract (același număr) repetat pe fiecare lot, cu valoarea totală;
3. **acord-cadru + contracte subsecvente** raportate sub același anunț (397 din 398 de anunțuri cu subsecvente).
Regula: rândurile repetate primesc `duplicate_of_id` și nu intră în totalurile instituțiilor/județului; dacă un
acord-cadru are subsecvente raportate, numărăm subsecventele (cheltuiala efectivă), altfel valoarea acordului
(un maxim). `repeat_same_company` exclude repetițiile și din totalurile aceleiași firme; membrii unei asocieri își
păstrează contractul pe profil. Rândurile rămân vizibile în liste, cu mențiunea „nu se adună în totaluri”.
După corecție: 4,3 mld. lei în 2025 pentru autoritățile cu sediul în județul Sibiu (8.469 rânduri excluse).

## D-19. User-Agent fără date de contact fictive
Nominatim blochează (403) un User-Agent cu adresă `example.org`. UA-ul implicit este
`TransparentRO-ETL/0.1 (civic transparency project, Romania)`; înainte de rulări regulate trebuie adăugat un
contact real în `USER_AGENT` (nu am folosit adresa personală a utilizatorului).

## D-20. Autorități naționale cu sediul în județ
Filtrarea e după sediul autorității (ANAF). Companiile naționale cu sediul în județ (Transgaz, Romgaz — Mediaș)
intră în „Sibiu” și domină totalurile, deși cheltuie la nivel național. Nu le-am exclus (ar fi o alegere editorială);
interfața permite filtrarea pe tip de instituție.

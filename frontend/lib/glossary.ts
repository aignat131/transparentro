// Glosar: termeni tehnici explicați pe înțeles. Folosit de <Term> (tooltip) și de pagina /glosar.
export const GLOSSARY: Record<string, { term: string; text: string }> = {
  cpv: {
    term: "Cod CPV",
    text: "Vocabularul Comun al Achizițiilor: un cod de 8 cifre care spune ce se cumpără (ex. 45233140 = lucrări de drumuri). Primele două cifre arată domeniul mare.",
  },
  achizitie_directa: {
    term: "Achiziție directă",
    text: "Cumpărare simplificată, fără licitație, permisă doar sub un prag legal (în prezent 270.120 lei fără TVA pentru produse și servicii, 900.400 lei pentru lucrări). Instituția alege furnizorul, de regulă din catalogul electronic SEAP.",
  },
  act_aditional: {
    term: "Act adițional",
    text: "Document prin care se modifică un contract deja semnat: preț, durată, cantități. Legea limitează cât de mult poate crește valoarea fără o procedură nouă.",
  },
  licitatie_deschisa: {
    term: "Licitație deschisă",
    text: "Procedura cea mai transparentă: orice firmă interesată poate depune ofertă după publicarea anunțului.",
  },
  procedura_simplificata: {
    term: "Procedură simplificată",
    text: "Procedură competitivă, mai rapidă, folosită pentru valori între pragul de achiziție directă și pragurile europene.",
  },
  negociere_fara_publicare: {
    term: "Negociere fără publicare prealabilă",
    text: "Procedură de excepție, fără anunț public: instituția negociază direct cu una sau mai multe firme. Este permisă doar în situații prevăzute de lege (urgență, furnizor unic etc.).",
  },
  autoritate_contractanta: {
    term: "Autoritate contractantă",
    text: "Instituția publică (primărie, școală, spital, companie de stat) care cumpără produse, servicii sau lucrări cu bani publici.",
  },
  cui: {
    term: "CUI",
    text: "Codul unic de înregistrare fiscală al unei firme sau instituții. Îl folosim ca să legăm datele din surse diferite.",
  },
  seap: {
    term: "SEAP / SICAP",
    text: "Sistemul electronic de achiziții publice (e-licitatie.ro), unde instituțiile publică anunțurile, contractele și achizițiile directe.",
  },
  semnal: {
    term: "Semnal de verificat",
    text: "O situație calculată automat care merită o privire mai atentă. NU este o acuzație și nu dovedește o neregulă: de multe ori există explicații legitime.",
  },
  acord_cadru: {
    term: "Acord-cadru",
    text: "Înțelegere pe mai mulți ani cu unul sau mai mulți furnizori, în baza căreia se încheie apoi contracte mai mici (subsecvente), pe măsură ce apar nevoile.",
  },
  valoare_estimata: {
    term: "Valoare estimată",
    text: "Cât credea instituția, înainte de procedură, că va costa achiziția. Valoarea finală a contractului poate fi diferită.",
  },
  pfa: {
    term: "Persoană fizică autorizată",
    text: "PFA, întreprindere individuală sau familială. Pentru protecția datelor personale (GDPR) nu le afișăm numele, ci doar localitatea.",
  },
  sintetic: {
    term: "Date sintetice",
    text: "Date generate artificial, doar pentru demonstrații și testare. Nu descriu instituții sau firme reale.",
  },
};

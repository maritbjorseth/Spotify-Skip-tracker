# Product

## Register

product

## Users

Primært én eier (utvikler/musikkentusiast, teknisk komfortabel) som deler dashbordet med venner, familie og potensielt offentligheten. Sekundærbrukere er ikke-tekniske: de har ikke satt opp trackeren selv, kjenner ikke CLI-kommandoer, og forventer at et dashbord skal forklare seg selv.

Brukskontekst: besøker dashbordet etter en lytteøkt for å se hva de har skippet, eller viser det frem til noen andre som en kuriositet. Ikke et daglig arbeidsverktøy — mer et speil over lyttevaner.

## Product Purpose

Skip Stats gir deg et ærlig bilde av hva du faktisk hører på kontra hva du tror du hører på. Den sporer automatisk alle Spotify-avspillinger, oppdager skips, og viser mønstre over tid: hvilke sanger du alltid hopper over, hvilke kontekster som trigger skips, og når på dagen du er mest utålmodig.

Suksess ser slik ut: en bruker åpner dashbordet og sier «Å, jeg skiper *den* sangen nesten alltid — kanskje jeg bør fjerne den fra spillelisten.»

## Brand Personality

Personlig, morsom, innsiktsfull.

Tonen er vennskapelig og direkte — som en god venn som har sett på musikk-dataene dine og forteller deg hva de egentlig betyr. Ikke klinisk analytisk, ikke spillifisert. Ærlig og litt morsom om hvem du er som lytter.

## Anti-references

- **Ikke generisk SaaS-dashbord** (Mixpanel, Amplitude, Grafana): ikke klinisk hvitt, ikke enterprise-grid av widgets, ikke fargerik BI-estetikk. Data skal vises klart uten å føles som et analyseverktøy for et selskap.
- **Ikke Spotify-klon**: ikke forsøk på å ligne den offisielle Spotify-appen. Bruker Spotify-grønn (#1db954) som en anerkjennelse av kontekst, men det er *ikke* Spotify — det er noe mer personlig og rått.

## Design Principles

1. **Data taler for seg selv** — tallene er interessante nok. Ikke pakk dem inn i markedsføringsspråk eller overdrevent positive formuleringer. Vis hva som faktisk skjer.
2. **Forståelig uten manual** — en ny besøkende (ikke teknisk, aldri hørt om skip-tracking) skal forstå hva de ser innen 10 sekunder uten å lese dokumentasjon.
3. **Personlig, ikke generisk** — dashbordet reflekterer én persons lyttevaner. Det skal føles laget for deg, ikke for «en bruker».
4. **Tomme tilstander underviser** — når det ikke er data ennå, forklar hva som skjer og hva brukeren kan forvente. Ingen blanke skjermen.
5. **Respekter konteksten** — dette er et mørkt verktøy for musikkdata. Mørkt tema er ikke et valg for stil, det er riktig for konteksten.

## Accessibility & Inclusion

Mål: WCAG AA. Produktet er potensielt offentlig og bør fungere for alle. Særlig viktig:
- Tilstrekkelig kontrast for tekst på mørke bakgrunner
- Ikke rely på farge alene for semantisk informasjon (skip-rate grønn/amber/rød)
- Fungere på mobil (deles som en link, åpnes på telefon)
- Keyboard-navigasjon for interaktive elementer

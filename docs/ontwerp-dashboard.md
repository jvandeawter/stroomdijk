# Ontwerp dashboard

Het Stroomdijk-dashboard volgt de stijl van het eigen dashboard op de Pi. Dat is op 2026-11-16 alleen lezend bekeken. Er is geen code overgenomen: alleen de stijl staat hieronder, zonder adres of andere huisgegevens. De goedgekeurde mockup (`mockup/index.html`) laat zien hoe het eruit moet zien.

## Gevoel

Rustig, warm en overzichtelijk. Een lichte, gebroken witte achtergrond met witte kaarten. Elke energiestroom heeft een vaste kleur. Grote getallen en kleine, grijze toelichting. Geen opsmuk, wel een kleine illustratie in de kop.

## Kleuren

Licht:

| Token | Waarde | Voor |
|---|---|---|
| `--bg` | `#f4f2ee` | achtergrond |
| `--card` | `#ffffff` | kaarten |
| `--ink` | `#1d1d1b` | tekst |
| `--muted` | `#75716a` | toelichting |
| `--line` | `#e4e0d8` | randen |
| `--sun` | `#d98a00` | zon |
| `--batt` | `#1f8a5b` | batterij, "verbonden" |
| `--home` | `#3a5bd9` | huis |
| `--grid` | `#8a5a9e` | stroomnet |
| `--warn` | `#c0392b` | fout, "niet verbonden" |

Donker, automatisch via `prefers-color-scheme`: `--bg #151514`, `--card #1f1f1d`, `--ink #f1efe9`, `--muted #9b968c`, `--line #33322f`, `--sun #f0a830`, `--batt #3cc184`, `--home #7a93ff`, `--grid #c08ad6`, `--warn #ff6b5b`.

## Letters en getallen

- **Lettertype:** het systeemlettertype (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`), 15px met regelhoogte 1,45.
- **Koppen:** h1 22px (19px op een smal scherm), h2 15px, allebei vet.
- **Grote getallen:** 26px en gewicht 650 in de tegels, 20px in de kleinere kaarten. Altijd met `font-variant-numeric: tabular-nums`, zodat de cijfers niet verspringen.
- **Eenheden:** de eenheid staat klein en grijs achter het getal (`<small>`). Onder de 1000 W toon je hele watts ("745 W"). Daarboven kW met twee decimalen en een komma ("1,96 kW").
- **kWh:** met de Nederlandse notatie en maximaal één decimaal ("5,6 kWh").

## Onderdelen

- **Kop (banner):**
  - Kaart met ronde hoeken (18px) en een heel lichte zonnige tint (`--sun` voor 5 procent gemengd met `--card`).
  - Daarachter een lijnillustratie: zon, heuvel, huisje en palen.
  - Links het logo, de naam van het huis, een korte regel met wat er gekoppeld is, en "Bijgewerkt hh:mm:ss" met een stip ervoor. De stip is groen als hij verbonden is en rood als hij dat niet is.
- **Tabs:** knoppen met ronde hoeken (10px). De actieve is gevuld met `--ink`.
- **Stroomtegels (flows):**
  - Witte kaart met ronde hoeken (16px) en een gekleurde bovenrand van 4px in de kleur van de stroom.
  - Bovenaan een grijs label, daaronder het grote getal en daaronder een kleine regel uitleg ("afname van net", "Solarbank 180 W · overig 229 W").
  - Het raster gaat van 4 naar 2 kolommen onder 720px.
- **Panelen:**
  - Witte kaart met h2-kop, bijvoorbeeld "Zonnepanelen per omvormer" of "Stroomnet per fase".
  - Daarin kleine kaartjes (12px hoeken, alleen een rand) met label, getal en uitleg.
  - Fasen staan in drie kolommen, op een telefoon onder elkaar.
- **Tellers:** een raster van kleine kaartjes (hoeken 14px) met label en waarde, bijvoorbeeld "Afname (teller meter)".
- **Foutmelding:** een balkje in `--warn` met 12 procent tint als achtergrond.

## Teksten

Nederlands, kort en zonder vaktaal. Vaste labels: "Zonne-opwek", "Huisverbruik", "Stroomnet (slimme meter)", "afname van net", "teruglevering aan net", "Zonnepanelen per omvormer" en "Stroomnet per fase".

## Wat anders is dan het eigen dashboard

- **Geen huisgegevens:** in de kop staat "Mijn huis" in plaats van een adres. Merknamen staan alleen bij een bron als die gekoppeld is.
- **Tegels zijn er alleen als de rol gevuld is.** Is er geen net gekoppeld, dan is er geen nettegel en geen huisverbruik. Wat nog niet gekoppeld is, staat onderaan met een knop.
- **Nog niet in prototype 1:** batterijring, prijzen en geschiedenis. Die komen er pas als er een officiële koppeling voor is.
- **Eigen logo:** een zon met twee golven (de "dijk"), in plaats van het huisje met de batterij.

# Plan prototype 1: van kastje aansluiten tot gevuld dashboard

Status: plan, nog niet gebouwd. Datum: 2026-11-16 (versie 3: Stroomdijk staat volledig los van het eigen dashboard).

## Uitgangspunt

Er zijn twee dingen die je niet door elkaar moet halen.

**Het eigen dashboard op de Pi** blijft precies zoals het is. Het is voor dit ene huis en Stroomdijk raakt het niet aan. Stroomdijk gebruikt ook niets van wat dat dashboard verzamelt, dus niet de MQTT-sensoren, niet de bestanden en niet de koppelingen.

**Stroomdijk** is het product voor klanten. Het leest zelf de apparaten van een huishouden uit, via een eigen Home Assistant op het kastje, en geeft de klant een dashboard dat net zo mooi is als het eigen dashboard. Dat dashboard is per huis instelbaar en vult zich vanzelf met wat er gekoppeld is.

Op de Pi doet Stroomdijk alsof het een nieuw klantkastje is. Het krijgt een eigen, lege Home Assistant, zoekt zelf het netwerk af en koppelt de apparaten die het vindt. Dat is dezelfde route die een klant straks doorloopt.

## Doel

De hele klantroute in het klein laten werken:

1. **Wifi instellen.** Heeft het kastje geen netwerk, dan start het een eigen hotspot met een instelpagina. Daar kiest de klant zijn wifi.
2. **Zichzelf inrichten.** Stroomdijk zet zijn eigen Home Assistant klaar, zonder dat de klant iets met Home Assistant hoeft te doen.
3. **Zoeken en koppelen.** Home Assistant zoekt het netwerk af. Stroomdijk laat alleen de energieapparaten zien en loopt met de klant door het koppelen. Wat niet vanzelf gevonden wordt (SolarEdge via de cloud) kan de klant met de hand toevoegen.
4. **Dashboard.** Stroomdijk herkent zelf welke sensor bij welke rol hoort (net, fasen, zon per bron) en toont die live. Het ontwerp volgt het eigen dashboard.

Klaar als: op de Pi de hele route werkt, van hotspot tot gevuld dashboard. Het eigen dashboard, de eigen Home Assistant en de Anker-meter merken daar niets van.

## Wat er nu op de Pi staat (bekeken op 2026-11-16, alleen gelezen)

De Pi draait Debian 13 en hangt via de kabel aan het netwerk (eth0). Wifi (wlan0) staat uit. NetworkManager en avahi draaien. Er is ruim geheugen vrij (zo'n 6,5 GB) en meer dan 100 GB schijf. In `~/docker/compose.yaml` draaien vier containers op het host-netwerk: `home` (nginx, 80), `energie-dashboard` (8080), `mosquitto` (1883) en `homeassistant` (8123, met Bluetooth). Die blijven allemaal ongemoeid. De poorten 8090, 8091 en 8124 zijn vrij.

In het netwerk staan een Enphase Envoy, SolarEdge, een P1-dongle (Zonneplan Connect) en de Anker Solarbank met meter. Het eigen dashboard leest de Envoy lokaal, SolarEdge via de cloud (elke 10 minuten, dus zo'n 144 verzoeken per dag) en de Anker via Modbus.

## Architectuur

```
  telefoon klant
     | (1) wifi "Stroomdijk-xxxx" -> instelpagina :8091
     | (2) daarna thuisnetwerk    -> Stroomdijk-app :8090
     v
  +--------------------+   +------------------------+   +-----------------------+
  | stroomdijk-setup   |   | stroomdijk (app)       |   | stroomdijk-ha         |
  | hotspot + wifi     |   | inrichten, koppelen,   |-->| eigen Home Assistant  |
  | via NetworkManager |   | rollen, dashboard      |   | poort 8124            |
  +--------------------+   +------------------------+   | zoekt het netwerk af  |
                                                        +-----------------------+
                                                                   |
                                     Envoy, P1-dongle, SolarEdge-cloud (geen Anker)

  Apart en onaangeroerd: eigen dashboard (8080), eigen Home Assistant (8123), mosquitto, nginx
```

Alles van Stroomdijk zit in één eigen compose-project `stroomdijk` in een eigen map `~/stroomdijk/` op de Pi. Er zijn drie containers. Op een echt klantkastje is de opzet hetzelfde, alleen zonder het eigen dashboard ernaast.

**`stroomdijk-ha`** is een eigen Home Assistant (`ghcr.io/home-assistant/home-assistant:stable`) met een eigen configmap `~/stroomdijk/ha-config/`. Hij draait op het host-netwerk, want anders kan Home Assistant het netwerk niet afzoeken (mDNS, SSDP en DHCP werken niet goed achter een bridge). Omdat 8123 al bezet is door de eigen Home Assistant, luistert hij op poort 8124 (`http: server_port: 8124` in zijn eigen `configuration.yaml`). Hij krijgt geen `/run/dbus` en geen extra rechten. Daardoor blijft Bluetooth van de eigen Home Assistant en zit hij er niet aan. Hij krijgt een geheugenlimiet van 1 GB. Met de eigen mosquitto praat hij niet: MQTT staat niet op de lijst met toegestane integraties.

**`stroomdijk`** is de app (poort 8090), op een eigen bridge-netwerk met een limiet op geheugen (256 MB) en CPU (0,5). Hij praat alleen met `stroomdijk-ha`, via `host.docker.internal:8124` en de officiële WebSocket-API:

- **Inrichten:** bij een lege Home Assistant doorloopt Stroomdijk zelf de eerste stappen. Hij maakt een eigenaar-gebruiker aan met een willekeurig wachtwoord, stelt land, tijdzone en eenheden in en maakt een long-lived token voor zichzelf. Wachtwoord en token komen in `~/stroomdijk/geheim/`. Daar staan ze alleen op het kastje, nooit in git, in chat of in een log. Niemand hoeft dus zelf een token te maken of over te typen. Dit gaat via de onboarding-API, dezelfde stappen die de Home Assistant-website ook gebruikt. Of dat helemaal zonder browser kan, controleren we in M1. Lukt het niet, dan doe je het eenmalig zelf in de browser en zetten we het token daarna in het bestand.
- **Gevonden apparaten:** `config_entries/flow/progress` geeft wat Home Assistant ontdekt heeft. Stroomdijk filtert op een lijst met toegestane energie-integraties. Sonos, Cast, Roborock en de rest negeert hij.
- **Koppelen:** Stroomdijk doorloopt de config flow van Home Assistant (`config/config_entries/flow`). Home Assistant zegt per stap welke velden nodig zijn, bijvoorbeeld het Enlighten-account voor de Envoy. Stroomdijk maakt daar een eigen eenvoudig scherm van. De gegevens gaan rechtstreeks naar Home Assistant en blijven op het kastje.
- **Rollen:** na het koppelen leest Stroomdijk de device- en entity-registry. Met regels per integratie bepaalt hij welke sensor bij welke rol hoort. Lukt dat niet, dan valt hij terug op `device_class` en `state_class`. Per rol is er één bron, zodat niets dubbel telt.
- **Live waarden:** Stroomdijk abonneert zich op wijzigingen van alleen de gekozen entiteiten. Dat is push, er wordt niet steeds opnieuw gevraagd. De browser krijgt de waarden via Server-Sent Events.

**`stroomdijk-setup`** (poort 8091) draait op het host-netwerk en praat via D-Bus met NetworkManager. Zonder netwerk, of in testmodus, start hij op wlan0 een hotspot "Stroomdijk-xxxx" met een instelpagina op `http://10.42.0.1:8091`. Daar kiest de klant zijn wifi en typt het wachtwoord, en dat gaat alleen naar NetworkManager. Daarna stopt de hotspot en is de app bereikbaar op `http://stroomdijk.local:8090`. In het echte product komt de instelpagina op poort 80, zodat telefoons hem vanzelf openen. Op deze Pi bezet nginx poort 80, dus hier gebruiken we 8091 en zet de QR-code de link er direct in.

Taal: Python 3.13 met `aiohttp`, en voor de setup `dbus-fast`. De pagina's zijn gewone HTML, CSS en JavaScript, zonder build-stap. Images worden op de Pi gebouwd (arm64).

## Het dashboard: het eigen ontwerp, opnieuw gebouwd

Het Stroomdijk-dashboard krijgt de look en indeling van het eigen dashboard: dezelfde tegels, kleuren, lettertypes en de manier waarop net, zon en verbruik getoond worden. Het wordt wel opnieuw gebouwd in deze repo. Twee redenen:

- Het eigen dashboard zit vol huis-specifieke dingen (adres, Anker-Modbus, Zonneplan, eigen tokens) die niet in een product horen.
- Het Stroomdijk-dashboard moet werken met elke combinatie van apparaten. Een tegel verschijnt alleen als de rol gevuld is. Geen zonnepanelen? Dan geen zontegel.

Werkwijze: in M3 bekijken we het eigen dashboard alleen lezend. Wat de stijl is (kleuren, indeling, tegels, teksten) leggen we vast in `docs/ontwerp-dashboard.md`, zonder adres of persoonsgegevens. Daarna bouwen we het na. Er wordt geen code gekopieerd en het eigen dashboard verandert niet.

Prototype 1 laat de live waarden zien: net (afname en teruglevering, per fase, spanning) en zon (totaal en per bron, opwek vandaag). Grafieken, historie, batterij, warmtepomp en kosten komen in latere prototypes.

## Apparaten in prototype 1

| Apparaat | Hoe gevonden | Koppeling in Home Assistant | Aandachtspunt |
|---|---|---|---|
| Enphase Envoy | zeroconf | officieel `enphase_envoy`, lokaal | Als eerste koppelen. Vraagt een Enlighten-account. Het eigen dashboard leest de Envoy ook. Na het koppelen controleren we dat het eigen dashboard gewoon doorloopt. |
| P1-dongle (Zonneplan Connect) | niet | geen | Er is geen officiële lokale koppeling gevonden, alleen een onofficiële via de Zonneplan-cloud. Die gebruiken we niet. In dit huis doet prototype 1 daarom eerst alleen zon. Net en huisverbruik komen later. |
| SolarEdge | met de hand toevoegen | officieel `solaredge`, cloud | Daglimiet op verzoeken, het eigen dashboard gebruikt er al zo'n 144 per dag van. Eerst uitzoeken hoeveel Home Assistant erbij vraagt. Als laatste koppelen, of overslaan als het niet past. |
| Anker Solarbank en meter | niet | geen | Stroomdijk koppelt deze niet. Er mag maar één Modbus-verbinding zijn en die is van het eigen dashboard, en een officiële integratie is er niet. In de app staat hij als "niet ondersteund" met uitleg. |

## Mapstructuur van de repo

```
software/
  CLAUDE.md, README.md, .gitignore
  docs/
    beslissingen.md
    plan-prototype-1.md
    ontwerp-dashboard.md      (M3)
    testen-op-de-pi.md        (M7)
  app/                        (container stroomdijk)
    pyproject.toml
    stroomdijk/
      __main__.py
      config.py
      inrichten.py            (lege Home Assistant klaarzetten, token maken)
      ha_client.py            (WebSocket: inloggen, registries, states, abonneren, opnieuw verbinden)
      ontdekken.py            (gevonden apparaten, filter op toegestane integraties)
      koppelen.py             (config flow doorlopen, stappen naar schermen)
      rollen.py               (regels per integratie, bronkeuze per rol)
      integraties.toml        (toegestane integraties en rolregels)
      web.py
      static/                 (dashboard en koppelschermen)
    tests/
      nep_ha.py               (nep-Home Assistant: onboarding, flows, registries, states)
      test_*.py
  setup/                      (container stroomdijk-setup)
    stroomdijk_setup/
      __main__.py
      netwerk.py              (NetworkManager via D-Bus)
      web.py
      static/
    tests/
  ha/
    configuration.yaml        (basisconfig voor stroomdijk-ha, poort 8124)
  deploy/
    Dockerfile.app
    Dockerfile.setup
    compose.yaml              (project stroomdijk: ha, app, setup)
    naar-pi.sh                (rsync naar ~/stroomdijk, build, up)
```

Op de Pi, buiten git: `~/stroomdijk/ha-config/` (data van de eigen Home Assistant), `~/stroomdijk/geheim/` (wachtwoord en token) en `~/stroomdijk/data/` (gekozen bronnen per rol).

## Mijlpalen

Elke mijlpaal is klein, werkt op zichzelf en wordt apart gecommit.

**M0. Voorbereiding.** Er is niets nodig: Home Assistant en het token regelt Stroomdijk zelf. De P1-dongle blijkt een Zonneplan Connect te zijn, zie de tabel hierboven.

**M1. Eigen Home Assistant naast de bestaande.** Container `stroomdijk-ha` op poort 8124 starten. Stroomdijk richt hem in via de onboarding-API (of jij doet dat eenmalig in de browser). Daarna een script dat via WebSocket laat zien wat hij in het netwerk gevonden heeft. Klaar als: we zien of de Envoy gevonden wordt, en de eigen Home Assistant, Bluetooth en het eigen dashboard ongestoord doordraaien.

*Uitkomst M1 (2026-11-16): gedaan.* `stroomdijk-ha` draait op 8124 en is zonder browser ingericht via de onboarding-API (`scripts/inrichten.py`). Wachtwoord en token staan alleen in `~/stroomdijk/geheim/`. Via zeroconf vond hij vanzelf de Enphase Envoy, plus niet-energieapparaten zoals een printer, Hue, Sonos, Nest, Roborock en UniFi. Die moet Stroomdijk wegfilteren. Drie lessen:

- **Direct inrichten:** zolang Home Assistant niet is ingericht, koppelt hij sommige gevonden apparaten automatisch (hier Sonos en de Bluetooth-chip). Stroomdijk moet hem dus meteen na de eerste start inrichten. De twee koppelingen zijn weggehaald met `scripts/opruimen.py`.
- **Extra koppelingen:** het inrichten voegt zelf Shopping list, Radio Browser en Google Translate toe. Die kunnen er later uit.
- **Geen geheugenlimiet:** die werkt op deze Pi niet, omdat de kernel met `cgroup_disable=memory` draait. `stroomdijk-ha` gebruikt zo'n 500 tot 600 MB.

Het eigen dashboard (reactietijd ongeveer 1 ms, meter en omvormers verbonden) en de eigen Home Assistant (geen fouten) merkten er niets van.

**M2. App-kern met tests op de Mac.** HA-client, inrichten, rollen en regels, getest tegen een nep-Home Assistant. Klaar als: `pytest` groen is zonder Pi.

*Uitkomst M2 (2026-11-16): gedaan.* De kern staat in `app/stroomdijk/`:

- `ha_client.py`: WebSocket en REST, opnieuw verbinden met oplopende wachttijd, abonnementen herstellen.
- `inrichten.py`: Home Assistant inrichten zonder browser.
- `ontdekken.py` en `koppelen.py`: gevonden apparaten filteren, config flows doorlopen, alleen eigen koppelingen verwijderen.
- `rollen.py` en `huis.py`: sensoren naar rollen, live overzicht met omrekening van eenheden.
- `integraties.json`: de toegestane integraties en hun regels.

Er zijn 24 tests tegen een nep-Home Assistant (`app/tests/nep_ha.py`) en ze zijn allemaal groen. Draaien op de Mac: `cd app && ../.venv/bin/python -m pytest`. Let op: de sleutels in `integraties.json` (translation_key en unique_id) zijn nog niet met echte apparaten gecontroleerd (`geverifieerd: false`). Dat doen we in M5 met de echte Envoy.

**M3. Ontwerp vastleggen en dashboard-skelet.** Het eigen dashboard alleen lezend bekijken en de stijl vastleggen in `docs/ontwerp-dashboard.md`. Daarna de app-container op 8090 met een dashboard in die stijl, gevuld met nepwaarden. Klaar als: je zegt dat het eruitziet zoals jouw dashboard.

*Uitkomst M3 (2026-11-16): gedaan, wacht op je oordeel.*

- **Ontwerp:** staat in `docs/ontwerp-dashboard.md`.
- **App:** container `stroomdijk` op poort 8090, met het dashboard in jouw stijl. Het vult zich via Server-Sent Events. Tegels verschijnen alleen als de rol gevuld is, en een leeg huis krijgt een uitnodiging om te koppelen. Er zijn 30 tests en ze zijn allemaal groen.
- **Demomodus:** `STROOMDIJK_DEMO=1` in compose toont nepwaarden. Met `STROOMDIJK_DEMO=0` toont hij de echte gegevens uit `stroomdijk-ha`. Die verbinding is getest.

Belangrijke les: Home Assistant 2026.11 zet de poort uit `configuration.yaml` eenmalig op proef over naar zijn opslag (`.storage/http`). Wordt die proef niet binnen 5 minuten bevestigd (`http/config/promote`), dan valt hij terug op 8123, de poort van de andere Home Assistant. Dat gebeurde om 14:07. De Stroomdijk-HA kon 8123 niet krijgen en had daarna geen werkende webserver meer. De andere Home Assistant merkte er niets van.

- **Hersteld:** de poort is in de opslag vastgezet op 8124.
- **Voorkomen:** de app bevestigt een proefconfig voortaan zelf bij het verbinden (`bevestig_http_config`).

**M4. Gevonden apparaten.** De pagina "Apparaten" toont de energieapparaten die `stroomdijk-ha` gevonden heeft, plus een knop om SolarEdge met de hand toe te voegen. De Anker staat erbij als "niet ondersteund". Klaar als: de lijst klopt met wat er in het netwerk staat.

*Uitkomst M4 (2026-11-16): gedaan.* De pagina `/apparaten` en `/api/apparaten` laten zien:

- **Gevonden:** alleen toegestane energie-integraties. In dit huis is dat de Enphase Envoy via zeroconf, op hetzelfde adres dat het eigen dashboard gebruikt. Printer, Hue, Sonos, Nest, Roborock en UniFi worden weggefilterd.
- **Gekoppeld:** nog niets.
- **Met de hand toevoegen:** SolarEdge.
- **Nog niet mogelijk:** Anker Solarbank en Zonneplan Connect, met uitleg. Let op: dat is een vaste lijst in `integraties.json` (`_niet_ondersteund`). Home Assistant vindt apparaten zonder integratie niet, dus Stroomdijk kan ze ook niet echt "zien".

De knoppen Koppelen en Toevoegen doen nog niets, dat komt in M5. De app draait nu standaard in de echte modus (`STROOMDIJK_DEMO=0`). Er zijn 36 tests en ze zijn allemaal groen.

**M5. Koppelen en dashboard vullen.** Een koppel-wizard per apparaat: eerst de Envoy en daarna eventueel SolarEdge. Het net komt in dit huis pas als er een officieel uit te lezen P1-meter is. Na elke koppeling vallen de sensoren vanzelf in de rollen en verschijnen de tegels. Klaar als: het dashboard live de echte waarden toont, zonder handwerk en zonder dubbel tellen, en het eigen dashboard na elke koppeling gewoon doorloopt.

**M6. Wifi instellen.** Container `stroomdijk-setup` met hotspot en instelpagina, getest op wlan0 terwijl de kabel de hoofdverbinding blijft. Daarvoor zet jij eenmalig wifi aan op de Pi (wifi-land en blokkade opheffen, met sudo). Klaar als: je met je telefoon via "Stroomdijk-xxxx" een wifi kunt kiezen, de Pi verbindt, en kabel, Tailscale, Bluetooth en het eigen dashboard ongestoord blijven. Daarna gaat de hotspot weer uit.

**M7. Generale repetitie.** `stroomdijk-ha` leeggooien en de hele route opnieuw doorlopen zoals een klant: hotspot, wifi, inrichten, zoeken, koppelen, dashboard. Vastleggen in `docs/testen-op-de-pi.md` en een nacht laten draaien.

## Testen zonder het eigen systeem te raken

- **Eigen map en project:** alles van Stroomdijk staat in `~/stroomdijk/` met compose-project `stroomdijk`. In `~/docker/` draaien we nooit compose en veranderen we niets.
- **Eigen Home Assistant blijft dicht:** Stroomdijk praat nooit met de eigen Home Assistant (8123), het eigen dashboard, mosquitto of de Anker-meter.
- **Geen Bluetooth:** `stroomdijk-ha` krijgt geen D-Bus en geen extra rechten, dus Bluetooth blijft bij de eigen Home Assistant.
- **Gedeelde apparaten:** alleen de Envoy en eventueel SolarEdge worden door allebei gelezen. Na het koppelen controleren we het eigen dashboard. SolarEdge koppelen we alleen als de daglimiet het toelaat.
- **Meten bij elke stap:** de reactietijd van `http://127.0.0.1:8080/api/now`, de logs van het eigen dashboard (meter en MQTT verbonden) en `docker stats`.
- **Limieten:** alle Stroomdijk-containers hebben een limiet op geheugen en CPU.
- **Op de Mac:** tests tegen een nep-Home Assistant en een nep-NetworkManager.
- **Terugdraaien:** `docker compose -p stroomdijk down` en eventueel `~/stroomdijk/` weggooien. Dan is alles van Stroomdijk weg, en er is niets aan het eigen systeem veranderd. Bij de wifitest zet je wlan0 daarna weer uit.

## Nog niet in dit prototype

Grafieken en historie, batterij, warmtepomp en kosten, slim sturen, inloggen op de app, toegang van buitenaf, updates, reservekopie en de echte captive portal op poort 80.

## Open vragen

1. P1 voor het product: veel klanten hebben straks een dongle van hun leverancier (zoals Zonneplan Connect) die niet officieel uit te lezen is. Krijgt het Stroomdijk-kastje dan een eigen P1-meter mee, of werken we met een dongle met doorgeefpoort? Dat raakt de prijs en de inhoud van het kastje. Ook uitzoeken of de Zonneplan Connect blijft werken naast een tweede meter.
2. Mag `stroomdijk-ha` de Envoy ook uitlezen, naast het eigen dashboard? Mijn voorstel: ja, met controle achteraf.
3. SolarEdge: akkoord dat we die als laatste doen, en hem overslaan als de daglimiet niet past naast het eigen dashboard?
4. Anker: bij een klant zonder het eigen dashboard zou Stroomdijk de enige zijn die de meter uitleest. Moeten we voor later uitzoeken of dat officieel via Modbus kan (Modbus TCP staat in de Anker-app), of laten we de Anker in het product voorlopig weg?
5. Wifi testen: mag wlan0 daarvoor aan? De kabel blijft de hoofdverbinding.
6. Poorten 8090 (app), 8091 (instelpagina) en 8124 (Stroomdijk-HA) goed? In dit prototype is er geen inlog op de app, hij is alleen bereikbaar in het thuisnetwerk en via Tailscale.
7. Uitrollen naar de Pi met `rsync` vanaf de Mac (voorstel), of een `git clone` op de Pi?

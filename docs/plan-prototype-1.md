# Plan prototype 1: van kastje aansluiten tot gevuld dashboard

Status: plan, nog niet gebouwd. Datum: 2026-11-16 (versie 2, na keuze voor de hele flow).

## Doel

Het Stroomdijk-model in het klein laten werken. De klant sluit het kastje aan en zet het op de wifi. Het kastje zoekt het netwerk af, de klant koppelt de gevonden energieapparaten met een paar klikken, en daarna vult het dashboard zich vanzelf met de live waarden van het net en de zonnepanelen.

Dat breken we op in drie delen:

1. **Wifi instellen.** Heeft het kastje geen netwerk, dan start het een eigen hotspot met een instelpagina. De klant kiest daar zijn wifi en typt het wachtwoord.
2. **Zoeken en koppelen.** Home Assistant zoekt het netwerk af (zeroconf, SSDP, DHCP, Bluetooth). Stroomdijk laat alleen de energieapparaten zien die het vond en loopt met de klant door het koppelen. Apparaten die niet vanzelf gevonden worden (zoals SolarEdge via de cloud) kun je met de hand toevoegen.
3. **Dashboard.** Na het koppelen herkent Stroomdijk zelf welke sensor bij welke rol hoort (net, fasen, zon per bron) en toont die live. Je hoeft niets in te stellen.

Klaar als: op de Pi de hele route werkt, van hotspot tot gevuld dashboard. Jouw eigen dashboard en de Anker-meter merken daar niets van.

## Wat er nu op de Pi staat (bekeken op 2026-11-16, alleen gelezen)

De Pi draait Debian 13 en hangt via de kabel aan het netwerk (eth0, 192.168.1.244). Wifi (wlan0) staat uit ("unavailable", waarschijnlijk geblokkeerd of nog geen wifi-land ingesteld). NetworkManager en avahi draaien. Docker compose staat in `~/docker/compose.yaml` met vier containers, allemaal op het host-netwerk: `home` (nginx, poort 80), `energie-dashboard` (8080), `mosquitto` (1883) en `homeassistant` (2026.11.1, 8123). Poort 8090 en 8091 zijn vrij.

In Home Assistant zitten nu geen P1- of zonnepanelenkoppelingen. Alle energiewaarden komen van het dashboard via MQTT discovery (topic `thuisenergie/state`, elke 10 seconden). De netwaarden komen van de Anker Smart Meter (Modbus), de zon van de Solarbank (Modbus), Enphase (lokale Envoy) en SolarEdge (cloud-API, het dashboard vraagt die elke 10 minuten op, dus zo'n 144 keer per dag).

De MQTT-sensoren hebben een `unique_id` zonder adres (`thuisenergie_<sleutel>`), maar hun entity-id bevat het huisadres. Entity-id's en apparaatnamen van dit huis komen daarom nooit in git.

Volgens je antwoord staan er in je netwerk een Enphase Envoy, SolarEdge, een P1-dongle en de Anker Solarbank met meter. De P1-dongle is nog niet aan Home Assistant gekoppeld en ik weet nog niet welk merk het is.

## Architectuur

```
  telefoon klant
     |  (1) wifi "Stroomdijk-xxxx"  -> instelpagina :8091
     |  (2) daarna thuisnetwerk     -> app :8090
     v
  +--------------------------+      +----------------------------+
  | stroomdijk-setup         |      | stroomdijk (app)           |
  |  host-netwerk            |      |  eigen bridge-netwerk      |
  |  praat met NetworkManager|      |  - HA-client (WebSocket)   |
  |  via D-Bus               |      |  - koppel-wizard           |
  |  hotspot + wifi kiezen   |      |  - rollen + dashboard      |
  +--------------------------+      +----------------------------+
                                           | ws://host.docker.internal:8123
                                           | long-lived token (gebruiker "stroomdijk", beheerder)
                                           v
                                    Home Assistant (bestaand)
                                     - zoekt het netwerk af
                                     - koppelt via config flows
                                     - bewaart inloggegevens van apparaten
```

Er zijn twee containers, allebei in een eigen compose-project `stroomdijk` in een eigen map `~/stroomdijk/` op de Pi. `~/docker/compose.yaml` en de bestaande containers raken we niet aan.

**De app (`stroomdijk`, poort 8090)** draait op een eigen bridge-netwerk met een limiet op geheugen (256 MB) en CPU (0,5). Hij praat alleen met Home Assistant, via de officiële WebSocket-API:

- Gevonden apparaten ophalen: `config_entries/flow/progress` geeft de koppelingen die Home Assistant zelf ontdekt heeft en die nog bevestigd moeten worden. Stroomdijk filtert op een lijst met energie-integraties die we toestaan.
- Koppelen: de config flow doorlopen via de API (`config/config_entries/flow`). Home Assistant geeft per stap aan welke velden het nodig heeft (bijvoorbeeld e-mail en wachtwoord van Enlighten voor de Envoy). Stroomdijk maakt daar een eigen, eenvoudig scherm van. De ingevulde gegevens gaan rechtstreeks naar Home Assistant en blijven op het kastje. Stroomdijk bewaart ze zelf niet en zet ze nooit in een log.
- Rollen vullen: na het koppelen leest Stroomdijk de device- en entity-registry en bepaalt met regels per integratie welke sensor bij welke rol hoort. Lukt dat niet met een vaste regel, dan valt hij terug op `device_class` en `state_class`. Een rol is iets als `net_vermogen`, `net_fase_l1` of `zon_bron`.
- Live waarden: abonneren op wijzigingen van alleen de gekozen entiteiten (push, geen pollen). De browser krijgt ze via Server-Sent Events.

Koppelen kan alleen met een token van een beheerder. Daarom maak je in Home Assistant een aparte gebruiker "stroomdijk" met beheerrechten en een eigen long-lived token. Die kun je los intrekken. Het token zet je zelf in `~/stroomdijk/geheim/ha_token` (`chmod 600`). Het gaat read-only de container in en komt nooit in git, in compose of in een log.

**De setup (`stroomdijk-setup`, poort 8091)** is een klein programma op het host-netwerk dat via D-Bus met NetworkManager praat (`/run/dbus` gemount). Zonder netwerkverbinding, of in testmodus, start hij op wlan0 een hotspot "Stroomdijk-xxxx" met de instelpagina op `http://10.42.0.1:8091`. Daar ziet de klant de wifi-netwerken in de buurt. Hij kiest er een en typt het wachtwoord, en NetworkManager maakt de verbinding. Daarna stopt de hotspot en is de app te vinden op `http://stroomdijk.local:8090` (via avahi). Het wifi-wachtwoord gaat alleen naar NetworkManager.

In het echte product komt de instelpagina op poort 80, zodat telefoons hem vanzelf openen (captive portal). Op jouw Pi bezet nginx poort 80, dus daar gebruiken we 8091 en zet de QR-code op het kastje de link er direct in. Dat verschil is bewust en alleen voor het testen.

Taal: Python 3.13 met `aiohttp` voor de app. Voor de setup komt `dbus-fast` erbij, om met NetworkManager te praten. De pagina's zijn gewone HTML met wat JavaScript, zonder build-stap. Images worden op de Pi gebouwd (arm64).

## Apparaten in prototype 1

| Apparaat | Hoe gevonden | Koppeling in HA | Bijzonderheden |
|---|---|---|---|
| P1-dongle | zeroconf (als het een HomeWizard is) | officiële integratie, lokaal | Als eerste koppelen, het minste risico. In de HomeWizard-app moet "Lokale API" aan staan. Merk nog bevestigen. |
| Enphase Envoy | zeroconf | officiële integratie `enphase_envoy`, lokaal | Vraagt een Enlighten-account. Het dashboard leest de Envoy ook. Na het koppelen controleren we of het dashboard gewoon doorloopt. |
| SolarEdge | niet vanzelf, met de hand toevoegen | officiële integratie `solaredge`, cloud | Site-id en API-sleutel. SolarEdge heeft een daglimiet op het aantal verzoeken en het dashboard gebruikt er al zo'n 144 per dag van. Hoeveel Home Assistant erbij vraagt, zoek ik eerst uit, en we koppelen SolarEdge pas als laatste. |
| Anker Solarbank en meter | eventueel als netwerkapparaat | geen | Stroomdijk koppelt deze bewust niet. De meter accepteert maar één Modbus-verbinding en die is van het dashboard. Er is geen officiële Home Assistant-integratie, alleen onofficiële cloudkoppelingen, en die gebruiken we niet. In de app staat hij als "gevonden, niet gekoppeld" met uitleg. |
| Bestaande MQTT-sensoren van het dashboard | zitten al in HA | MQTT | Stroomdijk herkent ze als bron "eigen meetsysteem" via de `unique_id`. In jouw huis zijn dat voorlopig de netwaarden van de Anker-meter. |

**Dubbel tellen voorkomen.** Na het koppelen van Enphase en SolarEdge staan dezelfde panelen er twee keer in, via MQTT en native. Per rol kiest Stroomdijk één bron. Native koppelingen gaan voor, maar je kunt het per rol omzetten in de app.

## Mapstructuur van de repo

```
software/
  CLAUDE.md, README.md, .gitignore
  docs/
    beslissingen.md
    plan-prototype-1.md
    testen-op-de-pi.md
  app/                        (container stroomdijk)
    pyproject.toml
    stroomdijk/
      __main__.py
      config.py               (instellingen en lokaal statusbestand)
      ha_client.py            (WebSocket: inloggen, registries, states, abonneren, opnieuw verbinden)
      ontdekken.py            (gevonden flows ophalen en filteren op toegestane integraties)
      koppelen.py             (config flow doorlopen, stappen vertalen naar schermen)
      rollen.py               (regels per integratie, entiteiten naar rollen, bronkeuze)
      integraties.toml        (toegestane integraties en hun rolregels, zonder huisgegevens)
      web.py                  (/, /koppelen, /api/now, /api/stream, /healthz)
      static/
    tests/
      nep_ha.py               (nep-Home Assistant met flows, registries en states)
      test_*.py
  setup/                      (container stroomdijk-setup)
    stroomdijk_setup/
      __main__.py
      netwerk.py              (NetworkManager via D-Bus: scannen, hotspot, verbinden)
      web.py                  (instelpagina)
      static/
    tests/
  deploy/
    Dockerfile.app
    Dockerfile.setup
    compose.yaml              (project stroomdijk, poorten 8090 en 8091, limieten)
    naar-pi.sh                (rsync naar ~/stroomdijk, build, up)
  scripts/
    controleer-ha.sh
```

Wat Stroomdijk zelf onthoudt (gekozen bronnen per rol, welke koppelingen Stroomdijk zelf heeft gemaakt) staat in een lokaal statusbestand op de Pi, in `~/stroomdijk/data/`. Dat bestand komt nooit in git.

## Mijlpalen

Elke mijlpaal is klein, werkt op zichzelf en wordt apart gecommit. De volgorde is bewust: eerst lezen, dan koppelen, en de wifi als laatste, omdat die het diepst in de Pi ingrijpt.

**M0. Voorbereiding (door jou).** Een backup van Home Assistant maken. In Home Assistant een gebruiker "stroomdijk" met beheerrechten aanmaken, als die gebruiker een long-lived token maken en dat in `~/stroomdijk/geheim/ha_token` zetten. Merk van de P1-dongle doorgeven.

**M1. Verbinding en overzicht, alleen lezen.** Een script op de Pi dat inlogt via WebSocket en drie lijsten laat zien: de gekoppelde integraties, de door Home Assistant gevonden maar nog niet gekoppelde apparaten, en de energiesensoren. Klaar als: we zwart op wit zien of de Envoy en de P1-dongle al gevonden zijn.

**M2. App-kern met tests op de Mac.** HA-client, rollen en regels, met een nep-Home Assistant voor de tests. Klaar als: `pytest` groen is zonder Pi.

**M3. Dashboard vult zichzelf.** De container `stroomdijk` op poort 8090 toont net (afname en teruglevering, fasen, spanning) en zon per bron. Alles herkend uit wat er nu in Home Assistant zit, dus de MQTT-sensoren, zonder handwerk. Klaar als: het dashboard op de Pi live meeloopt, en `docker stats` en de reactietijd van het eigen dashboard niet veranderen.

**M4. Gevonden apparaten.** De pagina "Apparaten" toont wat Home Assistant gevonden heeft, gefilterd op energie, plus een knop om SolarEdge met de hand toe te voegen. De Anker staat er met uitleg bij en zonder koppelknop. Hier wordt nog niets gekoppeld. Klaar als: de lijst klopt met wat er in je netwerk staat.

**M5. Koppelen, één apparaat per keer.** De koppel-wizard die de config flow van Home Assistant doorloopt. Eerst de P1-dongle, dan de Envoy en als laatste SolarEdge. Na elke koppeling controleren we het eigen dashboard en de MQTT-verbinding. Stroomdijk noteert welke koppelingen hij zelf heeft gemaakt, zodat we die later precies zo weer kunnen verwijderen. Bestaande koppelingen (MQTT, DeWarmte, Roborock en de rest) laat hij altijd met rust. Klaar als: de nieuwe sensoren vanzelf in de rollen van het dashboard vallen, zonder dubbel tellen.

**M6. Wifi instellen.** De container `stroomdijk-setup` met hotspot en instelpagina. Op jouw Pi testen we dit op wlan0, terwijl de kabelverbinding gewoon blijft. Daarvoor moet jij eenmalig wifi aanzetten op de Pi (wifi-land instellen en de blokkade opheffen, daar is sudo voor nodig). De test: setup in testmodus starten, met de telefoon verbinden met "Stroomdijk-xxxx", een wifi kiezen en controleren dat de Pi verbindt terwijl de kabel de standaardroute houdt. Daarna de hotspot weer uit. Klaar als: de hele route werkt en de kabel, Tailscale, Bluetooth in Home Assistant en het dashboard ongestoord blijven.

**M7. Generale repetitie en een nacht draaien.** De volledige route op een rij in `docs/testen-op-de-pi.md`, daarna een nacht en een dag laten lopen. Uitkomsten in `docs/beslissingen.md`.

## Testen zonder het eigen dashboard te raken

Alles van Stroomdijk staat in `~/stroomdijk/` met compose-project `stroomdijk`. We draaien nooit compose in `~/docker/` en veranderen daar geen bestanden.

Stroomdijk praat nooit rechtstreeks met de Anker-meter, de Solarbank, Mosquitto of het dashboard. De Anker wordt bewust niet gekoppeld.

Koppelen in je eigen Home Assistant doen we op jouw verzoek. Om het veilig te houden:

- Vooraf maken we een backup.
- We koppelen één apparaat per keer, met daarna steeds een controle.
- Alleen integraties uit de toegestane lijst mogen gekoppeld worden.
- Stroomdijk verwijdert of wijzigt nooit koppelingen die hij niet zelf heeft gemaakt.
- Een knop "Stroomdijk-koppelingen verwijderen" ruimt alleen zijn eigen koppelingen op.

Bij elke stap meten we het eigen dashboard: de reactietijd van `http://127.0.0.1:8080/api/now`, de logs (meter en MQTT verbonden) en `docker stats`.

De app heeft limieten op geheugen en CPU. De setup draait alleen als hij nodig is of als we hem testen, en raakt eth0 niet aan.

Op de Mac testen we alles tegen een nep-Home Assistant en een nep-NetworkManager.

Terugdraaien: `docker compose -p stroomdijk down` in `~/stroomdijk`, de Stroomdijk-koppelingen verwijderen (of de backup terugzetten) en wlan0 weer uitzetten.

## Nog niet in dit prototype

Home Assistant zelf installeren en onboarden op een leeg kastje. Op jouw Pi is dat al gedaan, maar voor een nieuw kastje moet Stroomdijk de eerste gebruiker en het token zelf regelen. Verder nog niet: historie en grafieken, batterij en warmtepomp, sturen, inloggen op de app, toegang van buitenaf, updates en de echte captive portal op poort 80.

## Open vragen

1. Welk merk is de P1-dongle, en zit hij al ergens anders aan vast (bijvoorbeeld een app of een cloud)?
2. Bij een klant zonder jouw dashboard is Stroomdijk de enige die de Anker-meter zou uitlezen. Moeten we voor later uitzoeken hoe we de Anker officieel via Modbus koppelen (Modbus TCP staat officieel in de Anker-app), of laten we de Anker in het product voorlopig buiten beschouwing?
3. SolarEdge: akkoord dat we die als laatste koppelen en eerst uitzoeken of de daglimiet samen met het dashboard past? Desnoods slaan we hem in dit prototype over.
4. Wifi testen op de Pi: vind je het goed dat wlan0 daarvoor aangaat? De kabel blijft de hoofdverbinding. Een aandachtspunt: wifi en Bluetooth zitten op dezelfde chip, en Home Assistant gebruikt Bluetooth. Dat controleren we in M6.
5. Poorten 8090 (app) en 8091 (instelpagina) goed? Geen inlog op de app in dit prototype, alleen bereikbaar in het thuisnetwerk en via Tailscale. Akkoord?
6. Uitrollen naar de Pi met `rsync` vanaf de Mac (voorstel), of een `git clone` op de Pi?
7. Ter info, buiten dit project: in `~/docker/compose.yaml`, de nginx-config en de apparaatnaam van de MQTT-sensoren staat het huisadres. Dat komt niet in de Stroomdijk-repo. Als het dashboard later in het product komt, moet het er wel uit.

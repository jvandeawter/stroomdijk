# Plan prototype 1: live net en zon via Home Assistant

Status: plan, nog niet gebouwd. Datum: 2026-11-16.

## Doel

Een eerste, kleine Stroomdijk-app die in een eigen Docker-container op de bestaande Raspberry Pi draait, via de officiële Home Assistant-API de live waarden van het stroomnet (afname, teruglevering, per fase) en de zonnepanelen ophaalt, en die op één webpagina toont. Niet meer dan dat. Geen sturen, geen historie, geen wizard. Wel al zo opgezet dat het later per huis instelbaar is: de app weet niet welk merk erachter zit, alleen welke Home Assistant-entiteit bij welke rol hoort.

Klaar als: op `http://<pi>:8090` een pagina staat die binnen een paar seconden na elke wijziging in Home Assistant de nieuwe waarden laat zien, en het bestaande dashboard aantoonbaar niets merkt.

## Wat er nu op de Pi staat (bekeken op 2026-11-16, alleen gelezen)

Docker compose staat in `~/docker/compose.yaml` met vier containers, allemaal met `network_mode: host`: `home` (nginx, poort 80), `energie-dashboard` (poort 8080), `mosquitto` (poort 1883) en `homeassistant` (versie 2026.11.1, poort 8123). In gebruik zijn verder onder meer 22, 111, 1400 en 5900. Poort 8090 is vrij. De Pi heeft 8 GB geheugen (zo'n 6,5 GB beschikbaar) en ruim 100 GB vrije schijf, dus een kleine extra container is geen probleem.

In Home Assistant zijn geen native P1- of zonne-integraties ingesteld (geen DSMR, HomeWizard, Enphase of SolarEdge). Alle energiewaarden komen van het eigen dashboard, dat ze via MQTT discovery naar Home Assistant stuurt (topic `thuisenergie/state`, ongeveer elke 10 seconden). Belangrijk om te weten: de "P1-waarden" komen niet uit een P1-poort, maar uit de Anker Smart Meter die het dashboard via Modbus uitleest. De zonwaarden komen van de Solarbank (Modbus), Enphase (lokale Envoy) en SolarEdge (cloud-API), ook allemaal via het dashboard.

De sensoren hebben een nette `unique_id` zonder adres (`thuisenergie_<sleutel>`), maar hun entity-id in Home Assistant bevat wel het huisadres, omdat Home Assistant die afleidt van de apparaatnaam. Daarom komen echte entity-id's nooit in git: de app zoekt ze op via de `unique_id`, of ze staan in een lokaal bestand dat in `.gitignore` staat (zie hieronder).

Verder zitten er integraties in Home Assistant die voor dit prototype niet nodig zijn (onder meer DeWarmte, Roborock, Sonos, mobile_app). DeWarmte is een onofficiële koppeling; die gebruiken we als productbasis niet, volgens de afspraak in CLAUDE.md.

## Welke entiteiten we gebruiken

De app werkt met rollen. Per rol hoort één Home Assistant-entiteit. Voor dit huis vullen we die in met de MQTT-sensoren van het dashboard, bij een ander huis kunnen dat sensoren van een HomeWizard, DSMR, Enphase of SolarEdge-integratie zijn. Hieronder de rol, de `unique_id` waarmee we hem in dit huis vinden, en de eenheid.

| Rol | unique_id in dit huis | Eenheid |
|---|---|---|
| net_vermogen (plus is afname, min is teruglevering) | thuisenergie_grid_power | W |
| net_afname | thuisenergie_grid_import_power | W |
| net_teruglevering | thuisenergie_grid_export_power | W |
| net_fase_l1, l2, l3 | thuisenergie_grid_l1_power (l2, l3) | W |
| spanning_l1, l2, l3 | thuisenergie_grid_l1_voltage (l2, l3) | V |
| net_afname_totaal | thuisenergie_grid_import_total | kWh |
| net_teruglevering_totaal | thuisenergie_grid_export_total | kWh |
| zon_vermogen_totaal | thuisenergie_solar_power | W |
| zon_bron (meerdere toegestaan) | thuisenergie_solarbank_pv_power, thuisenergie_enphase_power, thuisenergie_solaredge_power | W |
| zon_vandaag (optioneel) | thuisenergie_enphase_today | kWh |

Batterij, huisverbruik, prijzen en batterijopbrengst bestaan ook, maar laten we in prototype 1 bewust weg. De prijzen komen bovendien uit een onofficiële Zonneplan-koppeling, en die nemen we niet over.

Let op: de sensor "Zonne-opwek totaal" is een vermogen in W (het totaal van alle bronnen nu), geen energietotaal. En `thuisenergie_enphase_power` stond in de registry niet als entiteit, alleen in de definitielijst van het dashboard; in mijlpaal 1 controleren we of hij er echt is.

## Architectuur

```
  browser (Mac, telefoon)
        |  http://<pi>:8090   (pagina + live stroom via Server-Sent Events)
        v
  +---------------------------+
  | container "stroomdijk"    |   eigen compose-project, eigen map, eigen netwerk
  |  Python-app               |
  |   - HA-client (WebSocket) |
  |   - kleine webserver      |
  +---------------------------+
        |  ws://host.docker.internal:8123/api/websocket
        |  long-lived token (alleen in lokaal bestand)
        v
  Home Assistant (bestaand, ongewijzigd)
        ^
        |  MQTT discovery (bestaand)
  energie-dashboard (bestaand, ongewijzigd) --- Anker-meter, omvormers
```

De app draait in een eigen container `stroomdijk`, gestart vanuit een eigen compose-bestand in een eigen map op de Pi (`~/stroomdijk/`), met projectnaam `stroomdijk`. Zo raken we `~/docker/compose.yaml` en de bestaande containers nooit aan: een `docker compose up` of `down` in de ene map doet niets met de andere.

De container gebruikt geen host-netwerk maar een eigen bridge-netwerk met alleen poort 8090 naar buiten. Home Assistant bereikt hij via `host.docker.internal` (met `extra_hosts: host.docker.internal:host-gateway`). We geven de container een geheugenlimiet (256 MB) en een CPU-limiet (0,5), zodat hij het dashboard nooit kan verdringen, en `restart: unless-stopped`.

Hoe de app met Home Assistant praat: via de officiële WebSocket-API. Bij het starten logt hij in met het token, haalt eenmalig de entity registry op (om `unique_id` naar entity-id te vertalen) en de huidige toestand (`get_states`), en abonneert zich daarna op wijzigingen van alleen onze entiteiten (`subscribe_trigger` of `subscribe_events` op `state_changed`, gefilterd). Dat is push, dus geen pollen en vrijwel geen extra belasting. Valt de verbinding weg, dan probeert de app het opnieuw met oplopende wachttijd (1, 2, 4 tot maximaal 60 seconden) en toont de pagina "verbinding met Home Assistant kwijt". De REST-API (`/api/states/<entity>`) gebruiken we alleen als eenvoudige controle in een testscript, niet in de app zelf.

De browser krijgt de waarden via Server-Sent Events (`/api/stream`) en een momentopname via `/api/now`. Daarnaast is er `/healthz` voor Docker en voor onze eigen controle.

Het token: de eigenaar van de Pi maakt in Home Assistant zelf een long-lived access token aan en zet het in `~/stroomdijk/geheim/ha_token` op de Pi (map `geheim/` staat al in `.gitignore`). Advies is om daar eerst een aparte Home Assistant-gebruiker voor te maken (bijvoorbeeld "stroomdijk", geen beheerder), zodat het token niet de volledige rechten van het eigen beheeraccount heeft en apart in te trekken is. Home Assistant kent geen alleen-lezen tokens, dus een aparte gebruiker is de beste beperking die we hebben. Het token gaat als bestand de container in (read-only gemount), nooit als regel in compose en nooit in een log.

Taal en bibliotheken: Python 3.13, net als het dashboard, met `aiohttp` voor zowel de WebSocket-client als de webserver. Eén afhankelijkheid, makkelijk te onderhouden. De pagina is één HTML-bestand met wat CSS en JavaScript, zonder build-stap. Het image bouwen we op de Pi zelf (arm64), op basis van `python:3.13-slim`.

## Configuratie

Per huis één bestand `config/huis.toml` (staat in `.gitignore`), met de rollen en hoe ze gevonden worden. In git staat alleen een voorbeeld, `config/huis.example.toml`, zonder echte entity-id's:

```toml
[home_assistant]
url = "ws://host.docker.internal:8123/api/websocket"
token_file = "/run/geheim/ha_token"

[rollen]
net_vermogen = { unique_id = "thuisenergie_grid_power" }
zon_vermogen_totaal = { unique_id = "thuisenergie_solar_power" }
zon_bron = [
  { unique_id = "thuisenergie_solarbank_pv_power", label = "Solarbank" },
  { unique_id = "thuisenergie_solaredge_power", label = "SolarEdge" },
]
# of rechtstreeks: net_vermogen = { entity_id = "sensor.voorbeeld_net" }
```

Zo kan een rol zowel via `unique_id` als via `entity_id` gevonden worden. De `unique_id`'s van dit huis bevatten geen adres en mogen daarom in het voorbeeld.

## Mapstructuur van de repo

```
software/
  CLAUDE.md
  README.md
  .gitignore
  docs/
    beslissingen.md
    plan-prototype-1.md
    testen-op-de-pi.md        (mijlpaal 4)
  app/
    pyproject.toml
    stroomdijk/
      __init__.py
      __main__.py             (start: config lezen, HA-client en webserver)
      config.py               (huis.toml lezen en controleren)
      ha_client.py            (WebSocket: inloggen, registry, states, abonneren, opnieuw verbinden)
      rollen.py               (unique_id naar entity-id, waarden per rol, eenheden)
      web.py                  (/, /api/now, /api/stream, /healthz)
      static/
        index.html
    tests/
      nep_ha.py               (kleine nep-Home Assistant WebSocket-server voor tests)
      test_config.py
      test_rollen.py
      test_ha_client.py
  config/
    huis.example.toml
  deploy/
    Dockerfile
    compose.yaml              (projectnaam stroomdijk, poort 8090, limieten)
    naar-pi.sh                (rsync van Mac naar ~/stroomdijk op de Pi, daarna build en up)
  scripts/
    controleer-ha.sh          (REST-check met het token: zie ik de entiteiten?)
```

## Mijlpalen

Elke mijlpaal is klein, werkt op zichzelf en wordt apart gecommit.

**M0. Voorbereiding door de eigenaar van de Pi.** Aparte Home Assistant-gebruiker aanmaken, als die gebruiker een long-lived token maken en dat in `~/stroomdijk/geheim/ha_token` op de Pi zetten (`chmod 600`). Dit doet de eigenaar zelf, wij typen geen wachtwoorden of tokens.

**M1. Verbinding bewijzen, nog zonder container.** Script `scripts/controleer-ha.sh` dat op de Pi met `curl` en het token `/api/` en de states van onze entiteiten opvraagt, en kort Python-script dat via WebSocket inlogt en de entity registry ophaalt. Hier checken we ook of een gebruiker zonder beheerrechten de registry mag lezen en of de Enphase-sensor bestaat. Klaar als: de lijst rollen met entity-id en huidige waarde in de terminal staat.

**M2. App-kern met tests op de Mac.** `config.py`, `rollen.py` en `ha_client.py` plus de nep-Home Assistant voor tests. Getest: inloggen, verkeerd token, registry vertalen, ontbrekende entiteit, `unavailable`, wegvallende verbinding en opnieuw verbinden. Klaar als: `pytest` groen is op de Mac, zonder Pi of echte Home Assistant.

**M3. Webpagina.** `web.py` en `index.html`: grote tegel net (afname of teruglevering, met kleur), tegel zon totaal met de bronnen eronder, de drie fasen en spanningen, tijd van laatste update en een duidelijke melding als Home Assistant of een sensor wegvalt. Lokaal te draaien op de Mac tegen de nep-Home Assistant. Klaar als: de pagina live meebeweegt met de nepwaarden.

**M4. Container op de Pi.** `Dockerfile`, `deploy/compose.yaml` en `deploy/naar-pi.sh`, plus `docs/testen-op-de-pi.md`. Eerste keer starten tegen de echte Home Assistant. Klaar als: `http://<pi>:8090` de echte waarden toont en de controles hieronder zijn gedaan.

**M5. Een nacht laten draaien.** Container een nacht en een dag laten lopen. Kijken naar geheugen, herstarts, en of de pagina na een herstart van Home Assistant vanzelf weer bijwerkt. Klaar als: geen ingrijpen nodig was en de resultaten kort in `docs/beslissingen.md` staan.

## Testen zonder het bestaande dashboard te raken

Op de Mac testen we alles tegen een nep-Home Assistant, dus zonder Pi. Op de Pi geldt het volgende.

De app leest alleen Home Assistant. Hij praat nooit met de Anker-meter, de Solarbank, de omvormers, Mosquitto of het dashboard. Daarmee blijft de enige Modbus-verbinding van het dashboard.

Alles van Stroomdijk staat in `~/stroomdijk/` met compose-projectnaam `stroomdijk`. We draaien nooit een compose-commando in `~/docker/` en passen daar niets aan. Geen `sudo` nodig: Docker draait al als gebruiker admin.

Eigen netwerk, eigen poort (8090), geheugenlimiet en CPU-limiet, zodat de app zelfs bij een fout het dashboard niet kan verdringen.

Voor en na het starten meten we kort: `docker stats --no-stream` voor alle containers, en de reactietijd van `http://127.0.0.1:8080/api/now` (een paar keer achter elkaar). Die mag niet merkbaar veranderen. We kijken ook in de logs van het dashboard of de MQTT-verbinding en de meter blijven werken.

Terugdraaien kan altijd met één commando in `~/stroomdijk`: `docker compose -p stroomdijk down`. Dan is alles van Stroomdijk weg en draait de rest gewoon door.

## Nog niet in dit prototype

Native integraties in Home Assistant toevoegen (Enphase, SolarEdge, P1), historie en grafieken, batterij en warmtepomp, sturen, inloggen op de app, toegang van buitenaf, installatiewizard en updates. Dat komt in latere prototypes.

## Open vragen

1. "P1-meter": in Home Assistant zit geen P1-koppeling. De netwaarden komen van de Anker Smart Meter via het dashboard. Is het goed dat prototype 1 die waarden gebruikt als "net"? Of heb je ook een P1-dongle (bijvoorbeeld HomeWizard) die we in Home Assistant zouden moeten koppelen?
2. Zonnepanelen: nu komt alles via het dashboard (MQTT). Om echt te testen of Stroomdijk merkonafhankelijk werkt, zou een native Home Assistant-integratie voor Enphase of SolarEdge interessant zijn. Dat is wel een wijziging in jouw Home Assistant en kan een extra verbinding naar de Envoy of de SolarEdge-cloud geven (SolarEdge heeft een daglimiet op API-verzoeken, die zou je dan delen met het dashboard). Wil je dat in een volgend prototype, of nu al? Mijn voorstel: niet in prototype 1.
3. Mag ik voor de token een aparte Home Assistant-gebruiker voorstellen (geen beheerder), of wil je liever je eigen account gebruiken?
4. Poort 8090 goed? En alleen bereikbaar in het thuisnetwerk (en via Tailscale), dus geen inlog op de app in dit prototype, akkoord?
5. Uitrollen naar de Pi: met `rsync` vanaf de Mac (voorstel), of een `git clone` op de Pi met een eigen deploy key?
6. Wil je de entiteiten per rol vinden via `unique_id` (voorstel, werkt ook als Home Assistant de entity-id ooit hernoemt) of liever gewoon vaste entity-id's in je lokale `huis.toml`?
7. Ter info, buiten dit project: in `~/docker/compose.yaml`, de nginx-config en de apparaatnaam van de MQTT-sensoren staat het huisadres. Dat komt niet in de Stroomdijk-repo, maar als het dashboard later de basis van het product wordt, moet dat eruit.

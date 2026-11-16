# Beslissingen

## 2026-11-16: eigen project en map
De software krijgt een eigen map met git, los van Jeroens thuissysteem en de website.

## 2026-11-16: geen apart testkastje
We testen voorlopig op de bestaande Raspberry Pi 5. De Stroomdijk-app draait daar in een eigen container naast het bestaande dashboard en Home Assistant, en leest gegevens via Home Assistant.

## 2026-11-16: productmodel zoeken en koppelen
De klant sluit het kastje aan, zet het op de wifi via een eigen hotspot met instelpagina, en daarna zoekt het kastje (via Home Assistant) het netwerk af. De klant koppelt de gevonden energieapparaten in de Stroomdijk-app en het dashboard vult zich vanzelf. Prototype 1 laat die hele route zien. Waarom: dat is de kern van "ontzorgd, zonder technische kennis".

## 2026-11-16: Stroomdijk staat los van het eigen dashboard
Het eigen dashboard op de Pi blijft zoals het is en Stroomdijk gebruikt er niets van (geen MQTT-sensoren, bestanden of koppelingen). Stroomdijk is het product voor klanten en leest zelf de apparaten uit via een eigen Home Assistant. Waarom: we testen dan het echte product, en het eigen systeem loopt geen risico.

## 2026-11-16: eigen Home Assistant voor Stroomdijk
Stroomdijk krijgt een eigen Home Assistant (container stroomdijk-ha, poort 8124, host-netwerk voor het zoeken, zonder Bluetooth) en richt die zelf in, net als op een nieuw klantkastje. Apparaten worden gekoppeld via de config flows van Home Assistant en de officiële WebSocket-API. Inloggegevens blijven op het kastje. De Anker Solarbank en meter koppelt Stroomdijk niet (maar één Modbus-verbinding, geen officiële integratie).

## 2026-11-16: dashboard in de stijl van het eigen dashboard
Het Stroomdijk-dashboard krijgt de look en indeling van het eigen dashboard, maar wordt opnieuw gebouwd in deze repo, zonder code te kopiëren. Waarom: het eigen dashboard is huis-specifiek, het product moet werken met elke combinatie van apparaten.

## 2026-11-16: mockup goedgekeurd
De klikbare mockup in mockup/index.html (wifi, inrichten, apparaten, koppelen, dashboard) is akkoord en is de richting voor de schermen van prototype 1. Waarom: zo bouwen we naar een beeld dat al is goedgekeurd.

## 2026-11-16: prototype 1 eerst alleen zon
De P1-dongle in het testhuis is een Zonneplan Connect. Daarvoor is geen officiële lokale koppeling gevonden, alleen een onofficiële via de Zonneplan-cloud, en die gebruiken we niet. Prototype 1 koppelt daarom in dit huis eerst alleen zon (Enphase, eventueel SolarEdge). Hoe Stroomdijk bij klanten met zo'n leveranciersdongle aan P1-gegevens komt, is een open punt voor het product.

## 2026-11-16: Stroomdijk richt zijn Home Assistant zelf in
Stroomdijk doorloopt de onboarding van zijn eigen Home Assistant via de API, meteen na de eerste start. Niemand hoeft een token te maken. Waarom: een klant moet niets met Home Assistant hoeven doen, en een niet-ingerichte Home Assistant koppelt anders zelf apparaten (zoals Sonos en Bluetooth) zonder te vragen.

## 2026-11-16: geen default_config in de Stroomdijk-HA
De Stroomdijk-HA laadt alleen wat nodig is (frontend, config, zeroconf, ssdp, dhcp, recorder, history, energy). Waarom: default_config start ook go2rtc en Bluetooth, die botsen met een andere Home Assistant op dezelfde Pi.

## 2026-11-16: demomodus en live via Server-Sent Events
De app heeft een demomodus met nepwaarden (STROOMDIJK_DEMO=1), zodat je het dashboard kunt bekijken zonder gekoppelde apparaten. Live waarden gaan via Server-Sent Events: eenvoudig, één richting, en de browser verbindt vanzelf opnieuw.

## 2026-11-16: de app bevestigt de HTTP-config van Home Assistant
Home Assistant 2026.11 zet de poort uit configuration.yaml eerst op proef. Zonder bevestiging binnen 5 minuten valt hij terug op 8123. De app roept daarom bij elke verbinding http/config/promote aan als de proefconfig actief is en werkt. Waarom: op een Pi met een tweede Home Assistant mag Stroomdijk nooit naar 8123 terugvallen.

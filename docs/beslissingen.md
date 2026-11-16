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

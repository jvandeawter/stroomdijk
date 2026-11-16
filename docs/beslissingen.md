# Beslissingen

## 2026-11-16: eigen project en map
De software krijgt een eigen map met git, los van Jeroens thuissysteem en de website.

## 2026-11-16: geen apart testkastje
We testen voorlopig op de bestaande Raspberry Pi 5. De Stroomdijk-app draait daar in een eigen container naast het bestaande dashboard en Home Assistant, en leest gegevens via Home Assistant.

## 2026-11-16: productmodel zoeken en koppelen
De klant sluit het kastje aan, zet het op de wifi via een eigen hotspot met instelpagina, en daarna zoekt het kastje (via Home Assistant) het netwerk af. De klant koppelt de gevonden energieapparaten in de Stroomdijk-app en het dashboard vult zich vanzelf. Prototype 1 laat die hele route zien. Waarom: dat is de kern van "ontzorgd, zonder technische kennis".

## 2026-11-16: koppelen via Home Assistant config flows
Stroomdijk koppelt apparaten door de config flows van Home Assistant te doorlopen via de officiële WebSocket-API, met een token van een aparte beheerdersgebruiker "stroomdijk". Inloggegevens van apparaten gaan rechtstreeks naar Home Assistant en blijven op het kastje. De Anker Solarbank en meter koppelt Stroomdijk niet (maar één Modbus-verbinding, geen officiële integratie).

## 2026-11-16: testen in de eigen Home Assistant
Op verzoek testen we het koppelen in de bestaande Home Assistant op de Pi, met vooraf een backup, één apparaat per keer, alleen toegestane integraties, en Stroomdijk verwijdert alleen koppelingen die hij zelf maakte.

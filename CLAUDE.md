# Stroomdijk software

Dit is de software van Stroomdijk: een kastje voor de meterkast plus een maandabonnement, waarmee een huishouden al zijn energiebronnen op één plek ziet en slim kan sturen. Merkonafhankelijk en zonder contractbinding. Achtergrond staat in de map erboven: Projectplan Stroomdijk, Concurrentieanalyse Stroomdijk en Vragenlijst klantonderzoek.

## Productafspraken

- Home Assistant is de basis voor koppelingen met apparaten. De Stroomdijk-app (dashboard, berekeningen, later slim sturen) draait daarbovenop en praat met Home Assistant via de officiële API.
- Gebruik geen onofficiële of afgeschermde API's als basis voor het product (zoals Zonneplan, Robo-Charge of DeWarmte). Alleen officiële of lokale koppelingen.
- Het product moet stabiel zijn en bij een klant draaien zonder dat iemand ernaar omkijkt.
- Noem PLUS, Jeroens baan of nevenwerkzaamheden nergens in dit project. Het staat daar los van.
- Merk- en bedrijfsnaam is alleen "Stroomdijk". Geen persoonsnaam of woonplaats in de software, teksten of mails.

## Ontwikkelen en testen

- Er is voorlopig geen apart testkastje. We testen op de bestaande Raspberry Pi 5 van Jeroen (192.168.1.244, Docker, Home Assistant draait er al).
- Die Pi draait ook Jeroens eigen energiedashboard. Dat mag nooit stuk of trager worden. De Stroomdijk-app draait in een eigen Docker-container met een eigen poort en raakt de bestaande containers en bestanden niet aan.
- Lees nooit rechtstreeks de Anker-meter uit: die accepteert maar één Modbus-verbinding en die is van het dashboard. Gebruik de gegevens via Home Assistant.
- Geen wachtwoorden, tokens of sleutels in de code of in git. Die staan in een lokaal bestand dat in .gitignore staat; Jeroen vult ze zelf in.

## Werkwijze

- Alles staat in git. Kleine stappen, elke stap werkend opleveren en committen met een duidelijke Nederlandse omschrijving.
- Beslissingen over opzet en techniek kort vastleggen in docs/beslissingen.md (datum, besluit, waarom).
- Bij twijfel over scope of aanpak eerst vragen. Niet raden.

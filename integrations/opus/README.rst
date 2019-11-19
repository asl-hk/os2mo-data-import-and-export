************************
Integration til OPUS Løn
************************


Indledning
==========
Denne integration gør det muligt at hente og opdatere organisations- og
medarbejderoplysninger fra XML dumps fra OPUS Løn til OS2MO

Opsætning
=========

For at kunne afvikle integrationen, kræves adgang til en mappe med xml-dumps fra
OPUS. Oplysninger om stien til denne mapper er øjeblikket skrevet direkte i
importkoden og kan ikke ændres i runtime.

Den forventede sti for mappen med opus dumps er:
``/opt/magenta/dataimport/opus``

De enkelte dumps forventes at være navngivet systematisk som:
``ZLPE<data + tid>_delta.xml``

Eksempelvis ``ZLPE20190902224224_delta.xml``.


Nuværende implementeringslogik for import fra Opus:
===================================================

 * Data indlæses i form at et xml-dump.
 * Hvis data indeholder information om enhedstyper, oprettes disse enhedstyper som
   klasser, hvis ikke, får alle enheder typen ``Enhed``.
 * SE-, CVR-, EAN-m p-numre og telefon indlæses på enheder, hvis disse oplysninger
   tilgængelige.
 * Hvis data indeholder postadresser på enheder eller medarejdere, slås disse
   adresser op på DAR, og hvis det er muligt at få en entydigt match, gemmes
   DAR-uuid'en på enheden eller personen. Adresser med adressebeskyttelse importeres
   ikke.
 * Telefon og email importeres for medarbejdere, hvis de findes i data.
 * Ansættelsestyper og titler oprettes som klasser og sættes på de tilhørende
   engagementer.
 * Information om ledere importeres direkte fra data, de to informationer
   ``superiorLevel`` og ``subordinateLevel`` konkateneres til et lederniveau.
 * Information om roller importeres direkte fra data.

IT-Systemer
===========

En import fra OPUS vil oprette IT-systemet 'Opus' i MO. Alle medarbejdere som har
en værdi i feltet ``userId`` vil få skrevet deres OPUS brugernavn på dette
IT-system.

.. _AD Integration til SD Opus:

AD-Integration
==============

OPUS Importen understøtter at anvende komponenten `Integration til Active Directory`_
til at berige objekterne fra OPUS med information fra Active Directory. I øjebliket
er det muligt at importere felterne ``ObjectGuid`` og ``SamAccountName``.

Hvis AD integrationen er aktiv, vil importeren oprette IT-systemet 'Active Directory'
og oprette alle brugere der findes i AD med bruernavnet fundet i ``SamAccountName``.
Brugere med en AD konto vil blive oprettet med deres AD ``ObjectGuid`` som UUID på
deres brugerobjekt.

cpr-mapning
===========

For at kunne lave en frisk import uden at få nye UUID'er på medarbejderne, er det
muligt at give importen adgang til et csv-udtræk som parrer cpr-numre med UUID'er.
Disse UUID'er vil altid få forrang og garanterer derfor at en medarbejde får netop
denne UUID, hvis vedkomendes cpr-nummer er i csv-udtrækket.
Udtrækket kan produceres fra en kørende instans af MO ved hjælp ved værktøkjet
``cpr_uuid.py``, som findes under ``exports``.

Anendelse af integrationen
==========================

For at anvende integrationen, kræves udover de nævnte xml-dumps, at der oprettes
en gyldig konfiguration i ``settings.json``. De påkrævede nøgler er:

 * ``mox.base``: Adressen på LoRa.
 * ``mora.base``: Adressen på MO.
 * ``opus.import.run_db``: Stien til den database som gemmer informaion om kørsler
   af integrationen. Hvis integrationen skal køre som mere end et engangsimport er
   har denne fil en vigtig betydning.
 * ``municipality.name``: Navnet på kommunen.

Til at hjælpe med afviklingen af selve importen, findes en hjælpefunktion i
``opus_helpers.py`` som til at afvikle selve importen og initialisere databasen i
``opus.import.run_db`` korrekt. Dette modul forventer at finde en cpr-mapning og
vil fejler hvis ikke filen ``settings/cpr_uuid_map.csv`` eksisterer. Hvis den
nuværende import er den første, findes der ikke nogen mapning, og der må oprettes
en tom fil.
   
Løbende opdatering af Opus data i MO
====================================

Der er skrevet et program som foretager løbende opdateringer til MO efterhåden som
der sker ændringer i Opus data. Dette foregår ved, at integrationen hver gang den
afvikles kigger efter det ældste xml-dump som endnu ikke er importeret og importerer
alle ændringer i dette som er nyere end den seneste importering. Et objekt regnes som
opdateret hvis parameteren ``lastChanged`` på objektet er nyere end tidspunktet for
det senest importerede xml-dump. Alle andre objekter ignoreres.

Hvis et objekt er nyt, foretages en sammenligning af de enkelte felter, og de som er
ændret opdateres i MO med virkning fra ``lastChanged`` datoen. En undtagelse for
dette er engagementer, som vil blive oprettet med virkign fra ``entryDate`` datoen,
og alså således kan oprettes med virkning i fortiden.

Også opdateringsmodulet forventer at finde en cpr-mapning, som vil blive anvendt til
at knytte bestemte UUID'er på bestemte personer, hvis disse har været importeret
tidligere. Denne funktionalitet er nyttig, hvis man får brug for at re-importere alle
Opus-data, og vælger at arbejde sig igennem gamle dumps for at importere historik. I
daglig brug vil mapningen ikke have nogen betydning, da oprettede brugere her altid
vil være nye.

Opsætning af agenten til re-import
---------------------------------

For at kunne sammenligne objekter mellem MO og Opus, har intgrationen brug for at
kende de klasser som felterne mappes til MO. Det er derfor nødvendigt at oprette
disse nøgler i ``settings.json``:

 * ``opus.addresses.employee.dar``: "69ec097c-d068-f3e2-c754-930f482a0d27",
 * ``opus.addresses.employee.phone``: "a8363c6c-903b-5d77-4f2d-4683318ba366",
 * ``opus.addresses.employee.email``: "ea236ff3-f314-d8ae-119c-a30bec6af7ff",
    opus.addresses.unit.se``: "5a7323ee-9e14-e2c4-4af7-5361ce52a483",
    ``opus.addresses.unit.cvr``: "f55e1d31-7190-5612-5076-4c16372fb9f3",
    ``opus.addresses.unit.ean``: "5d98f945-66de-f0db-4e76-408991d74ad8",
    ``opus.addresses.unit.pnr``: "5c110de0-297e-ad17-e9f6-1b55711c3fb7",
    ``opus.addresses.unit.phoneNumber``: "7e700527-d442-9e26-c84f-16742cb2c1b4",
    ``opus.addresses.unit.dar``: "fbc84274-81c5-6a5d-60e3-f6ebe0a77d56",
    ``opus.it_systems.ad``: "2916e98c-941b-4abe-be79-9734ae42abd3",
    ``opus.it_systems.opus``: "92ba091f-38ba-4950-a450-9b85b9e7b2e1"

Klasserne oprettes i forbindelse med førstegangsimporten, og UUID'erne kan findes ved
hjæp af disse tre end-points i MO:

 * ``/service/o/<org_uuiud>/f/org_unit_address_type/``
 * ``/service/o/<org_uuiud>/f/employee_address_type/``
 * ``/service/o/<org_uuiud>/it/``
   
Værdien af org_uuid findes ved at tilgå:

 * ``/service/o/``


Nuværende begrænsninger omkring re-import
----------------------------------------

 * IT systemet Opus håndteres endnu ikke.
 * Ændringer i roller håndteres endnu ikke.
 * Koden kan fejle, hvis en leder afskediges mens vedkommende stadig er leder.
 * Der oprettes ikke automatisk nye enhedstyper, alle enheder forventes at have typen 'Enhed'
 * Der oprettes ikke automatisk nye engagementstyper.
 * Der oprettes ikke automatisk nye lederniveauer.


run_db.sqlite
=============

For at holde rede på hvornår MO sidst er opdateret fra Opus, findes en SQLite
database som indeholder to rækker for hver færdiggjort kørsel. Adressen på denne
database er angivet i ``settings.json`` under nøglen ``opus.import.run_db``.

Programmet ``db_overview.py`` er i stand til at læse denne database og giver et
outut som dette:

::

   id: 1, dump date: 2019-09-02 22:41:28, status: Running since 2019-11-19 08:32:30.575527
   id: 2, dump date: 2019-09-02 22:41:28, status: Import ended: 2019-11-19 08:55:32.455146
   id: 3, dump date: 2019-09-03 22:40:12, status: Running diff update since 2019-11-19 10:18:35.859294
   id: 4, dump date: 2019-09-03 22:40:12, status: Diff update ended: 2019-11-19 10:19:15.806079
   id: 5, dump date: 2019-09-04 22:40:12, status: Running diff update since 2019-11-19 10:19:16.006959
   id: 6, dump date: 2019-09-04 22:40:12, status: Diff update ended: 2019-11-19 10:19:48.980694
   id: 7, dump date: 2019-09-05 22:40:12, status: Running diff update since 2019-11-19 10:19:49.187977
   id: 8, dump date: 2019-09-05 22:40:12, status: Diff update ended: 2019-11-19 10:20:23.547771
   id: 9, dump date: 2019-09-06 22:40:13, status: Running diff update since 2019-11-19 10:20:23.745032
   id: 10, dump date: 2019-09-06 22:40:13, status: Diff update ended: 2019-11-19 10:20:54.931163
   id: 11, dump date: 2019-09-09 22:40:12, status: Running diff update since 2019-11-19 10:20:55.123478
   id: 12, dump date: 2019-09-09 22:40:12, status: Diff update ended: 2019-11-19 10:21:35.481189
   id: 13, dump date: 2019-09-10 22:40:12, status: Running diff update since 2019-11-19 10:21:35.682252
   id: 14, dump date: 2019-09-10 22:40:12, status: Diff update ended: 2019-11-19 10:22:12.298526
   id: 15, dump date: 2019-09-11 22:41:48, status: Running diff update since 2019-11-19 10:22:12.496829
   id: 16, dump date: 2019-09-11 22:41:48, status: Diff update ended: 2019-11-19 10:22:45.317372
   id: 17, dump date: 2019-09-12 22:40:12, status: Running diff update since 2019-11-19 10:22:45.517679
   id: 18, dump date: 2019-09-12 22:40:12, status: Diff update ended: 2019-11-19 10:23:20.548220
   id: 19, dump date: 2019-09-13 22:40:14, status: Running diff update since 2019-11-19 10:23:20.744435
   id: 20, dump date: 2019-09-13 22:40:14, status: Diff update ended: 2019-11-19 10:23:51.416625
   id: 21, dump date: 2019-09-16 22:40:12, status: Running diff update since 2019-11-19 10:23:51.610555
   id: 22, dump date: 2019-09-16 22:40:12, status: Diff update ended: 2019-11-19 10:24:44.799932
   id: 23, dump date: 2019-09-17 22:40:12, status: Running diff update since 2019-11-19 10:24:45.000445
   id: 24, dump date: 2019-09-17 22:40:12, status: Diff update ended: 2019-11-19 10:25:25.651491
   (True, 'Status ok')


Ved starten af alle opus_diff_import kørsler, skrives en linje med status ``Running``
og efter hver kørsel skrives en linje med status ``Diff update ended``. En kørsel kan
ikke startes hvis den nyeste linje har status ``Running``, da dette enten betyder at
integrationen allerede kører, eller at den seneste kørsel fejlede.

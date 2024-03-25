# Handelsregister API 

## Main Project
[bundesAPI/handelsregister](https://github.com/bundesAPI/handelsregister)

Das Handelsregister stellt ein öffentliches Verzeichnis dar, das im Rahmen des Registerrechts Eintragungen über die angemeldeten Kaufleute in einem bestimmten geografischen Raum führt. 
Eintragungspflichtig sind die im HGB, AktG und GmbHG abschließend aufgezählten Tatsachen oder Rechtsverhältnisse. Eintragungsfähig sind weitere Tatsachen, wenn Sinn und Zweck des Handelsregisters die Eintragung erfordern und für ihre Eintragung ein erhebliches Interesse des Rechtsverkehrs besteht.

Die Einsichtnahme in das Handelsregister sowie in die dort eingereichten Dokumente ist daher gemäß § 9 Abs. 1 HGB jeder und jedem zu Informationszwecken gestattet, wobei es unzulässig ist, mehr als 60 Abrufe pro Stunde zu tätigen (vgl. [Nutzungsordnung](https://www.handelsregister.de/rp_web/information.xhtml)). Die Recherche nach einzelnen Firmen, die Einsicht in die Unternehmensträgerdaten und die Nutzung der Handelsregisterbekanntmachungen ist kostenfrei möglich.

## Handelsregister

### Initial Setup: 

```
conda create -n handelsregister-api python mechanize beautifulsoup4 Flask pytest
conda env export > environment.yaml
pip freeze > requirements.txt
```
### Setup

    cd ./Path/to/Directory
    git clone https://github.com/jaschn12/handelsregister.git 
    cd ./handelsregister
    conda env create -f environment.yaml

    conda activate handelsregister-api

### Run search
    python handelsregister.py -s hotel st georg knerr -so all

### Datenstruktur

***URL:*** https://www.handelsregister.de/rp_web/erweitertesuche.xhtml

### To Do
- ~~create an output level between nothing and debug -> logging.INFO~~
- ~~create logging.info() code~~
- ~~after each http request: check for error code~~
- add retry and timeouts for request
- change user agent regularly
- ~~exit with error codes~~
- ~~check for Exception raising parts and make them error-proof~~

### Installation with conda
Example installation and execution with conda:
```commandline
git clone https://github.com/bundesAPI/handelsregister.git
cd handelsregister
conda create -n handelsregister-api python mechanize beautifulsoup4 pytest
conda activate handelsregister-api
python handelsregister.py -s deutsche bahn -so all
```
Run tests:
```commandline
python -m pytest
```


### Command-line Interface

Das CLI ist _work in progress_ und 

```
python handelsregister.py -h
usage: handelsregister.py [-h] [-d] [-f] -s SCHLAGWOERTER
                          [-so {all,min,exact}] [-ad] [-cd] [-hd] [-si]
                          [-docs]

A handelsregister CLI

options:
  -h, --help            show this help message and exit
  -d, --debug           Enable debug mode and activate logging
  -d, --debug           Enable info mode and activate logging
  -f, --force           Force a fresh pull and skip the cache
  -s SCHLAGWOERTER, --schlagwoerter SCHLAGWOERTER
                        Search for the provided keywords
  -so {all,min,exact}, --schlagwortOptionen {all,min,exact}
                        Keyword options: all=contain all keywords; min=contain
                        at least one keyword; exact=contain the exact company
                        name.
  -ad, --currentHardCopy
                        Download the 'Aktueller Abdruck'.
  -cd, --chronologicalHardCopy
                        Download the 'Chronologischer Abdruck'.
  -hd, --historicalHardCopy
                        Download the 'Historischer Abdruck'.
  -si, --structuredContent
                        Download the structured content as XML file.
  -docs, --downloadAllDocuments
                        Download all documents in the documents view.
```

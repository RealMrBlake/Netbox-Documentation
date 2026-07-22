# NetBox Documentation

Ein in NetBox integriertes Markdown-Wiki für Betriebsdokumentationen und Anleitungen.

## Funktionen

- Dokumentationen direkt in NetBox schreiben und als sicher bereinigten Rich Text anzeigen
- Word-ähnlicher WYSIWYG-Editor mit Schriftarten, Schriftgrößen, Farben, Ausrichtung und Tabellen
- Hierarchische Ordner und Unterordner für eine BookStack-ähnliche Struktur
- Breite Editoransicht und Fokusmodus innerhalb des NetBox-Layouts
- Bilder direkt vom eigenen Gerät in die Dokumentation hochladen
- Formatierte Word-Inhalte inklusive Tabellen und unterstützten Zwischenablage-Bildern einfügen
- Eine Dokumentation mehreren Objekten zuordnen und umgekehrt
- Unbegrenzt viele Objektzuordnungen pro Dokumentation; nur identische Doppelzuordnungen werden verhindert
- Unterstützte Standardobjekte: Region, Standort, Location, Rack, Gerät, VM, VM-Cluster und Mandant/Kunde
- DOCX, XLSX/XLSM, textbasierte PDF-, Markdown- und Textdateien importieren
- Originaldatei optional zusammen mit der Dokumentation aufbewahren
- Dokumentationen über die globale NetBox-Suche und per REST-API finden
- NetBox-Berechtigungen, Änderungsprotokoll, Tags und Custom Fields verwenden

## Kompatibilität

Die Version `0.3.3` zielt auf NetBox 4.x (mindestens 4.0). Vor einem produktiven Rollout sollte das Plugin gegen die konkret eingesetzte NetBox-Minor-Version in einer Testinstanz geprüft werden.

## Installation

### Installation aus dem Git-Repository

Das Plugin kann ohne vorheriges Klonen direkt aus dem Git-Repository in das Python-Virtualenv von NetBox installiert werden:

```bash
source /opt/netbox/venv/bin/activate
pip install git+https://git.mrblake.cc/MrBlake/Netbox-DokiWiki.git@main
```

### In `local_requirements.txt` eintragen

Damit das Plugin bei NetBox-Updates und einer erneuten Installation der Python-Abhängigkeiten automatisch installiert wird, folgende Zeile in `/opt/netbox/local_requirements.txt` eintragen:

```text
git+https://git.mrblake.cc/MrBlake/Netbox-DokiWiki.git@main
```

Falls die Datei noch nicht existiert, kann sie erstellt werden:

```bash
echo 'git+https://git.mrblake.cc/MrBlake/Netbox-DokiWiki.git@main' | sudo tee -a /opt/netbox/local_requirements.txt
```

Danach die lokalen Abhängigkeiten installieren:

```bash
source /opt/netbox/venv/bin/activate
pip install -r /opt/netbox/local_requirements.txt
```

Bei einem privaten Repository muss der NetBox-Server Zugriff auf das Repository besitzen. Zugangsdaten sollten nicht direkt in `local_requirements.txt` gespeichert werden; stattdessen sollte ein geeigneter Git-Credential-Helper oder ein nur lesbarer Deployment-Zugang verwendet werden.

### NetBox konfigurieren

In `configuration.py`:

```python
PLUGINS = [
    "netbox_documentation",
]

PLUGINS_CONFIG = {
    "netbox_documentation": {
        "max_import_size_mb": 25,
        "keep_imported_file": True,
        "allowed_object_types": [
            "dcim.region",
            "dcim.site",
            "dcim.location",
            "dcim.rack",
            "dcim.device",
            "virtualization.virtualmachine",
            "virtualization.cluster",
            "tenancy.tenant",
        ],
    }
}
```

TinyMCE wird als Python-Abhängigkeit des Plugins installiert und über einen lokalen, gecachten Plugin-Endpunkt bereitgestellt. `collectstatic` übernimmt die Dateien zusätzlich in NetBox. Der Editor benötigt deshalb weder Zugriff auf ein CDN noch einen API-Key. Das verwendete TinyMCE wird im GPL-Modus betrieben. Kann das Script nicht geladen werden, bleibt als Rückfall ein normales HTML-Textfeld verfügbar.

Danach die Migrationen und statischen Dateien aktualisieren und NetBox neu starten:

```bash
cd /opt/netbox/netbox
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

Für Docker-Installationen das Paket in das NetBox-Image aufnehmen, Plugin und Konfiguration setzen und anschließend das Image neu bauen. Die hochgeladenen Originaldateien liegen im konfigurierten NetBox-`MEDIA_ROOT`; dieses Verzeichnis muss persistent gespeichert und gesichert werden.

## Berechtigungen

Die benötigten Rechte können in NetBox unter **Admin → Benutzer → Berechtigungen** vergeben werden:

- `netbox_documentation.view_document`
- `netbox_documentation.add_document`, `change_document`, `delete_document`
- `netbox_documentation.view_documentassignment` sowie die entsprechenden Änderungsrechte
- `netbox_documentation.import_document` für Office-/PDF-Importe

Objektbezogene NetBox-Constraints sollten zusätzlich passend zu Mandanten und Verantwortungsbereichen gesetzt werden. Nicht veröffentlichte Dokumente sind als Redaktionsstatus gedacht; sie ersetzen keine Objektberechtigung.

## Importverhalten

| Format | Übernahme |
|---|---|
| DOCX | Überschriften, Absätze, Listen, Links und einfache Tabellen nach Markdown |
| XLSX/XLSM | Jedes Tabellenblatt als eigene Markdown-Tabelle; Formelergebnisse nur, wenn Excel sie zuvor gespeichert hat |
| PDF | Extrahierbarer Text, nach Seiten gegliedert |
| MD/TXT | Direkte Übernahme (UTF-8) |

Alte binäre `.doc`- und `.xls`-Dateien müssen vorher in `.docx` bzw. `.xlsx` konvertiert werden. Gescannte PDFs benötigen OCR, die in dieser Version bewusst noch nicht enthalten ist. Komplexe Word-/PDF-Layouts, eingebettete Bilder und Excel-Formatierungen können nicht verlustfrei nach Markdown übertragen werden.

## REST-API

Nach Aktivierung stehen die üblichen NetBox-Plugin-Endpunkte bereit:

- `/api/plugins/documentation/documents/`
- `/api/plugins/documentation/assignments/`
- `/api/plugins/documentation/folders/`

## Entwicklung und Tests

```bash
pip install -e ".[test]"
pytest
```

Für vollständige UI-/API-Tests muss NetBox im selben Virtualenv verfügbar sein. Die reinen Importtests befinden sich unter `netbox_documentation/tests/`.

## Nächste sinnvolle Ausbaustufen

- OCR für gescannte PDFs (z. B. Tesseract/OCRmyPDF als optionaler Worker)
- eingebettete DOCX-Bilder als NetBox-Medien übernehmen
- echte Dokumentrevisionen mit Vergleich und Freigabeprozess
- asynchroner Massenimport großer Excel-Bestände über NetBox-RQ
- Vorlagen und automatisch vererbte Dokumentation entlang Region → Standort → Gerät

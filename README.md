# NetBox Documentation

Ein in NetBox integriertes Markdown-Wiki für Betriebsdokumentationen und Anleitungen.

## Funktionen

- Dokumentationen direkt in NetBox schreiben und als sicher bereinigten Rich Text anzeigen
- Word-ähnlicher WYSIWYG-Editor mit Schriftarten, Schriftgrößen, Farben, Ausrichtung und Tabellen
- Hierarchische Ordner und Unterordner für eine BookStack-ähnliche Struktur
- Breite Editoransicht und Fokusmodus innerhalb des NetBox-Layouts
- Bilder direkt vom eigenen Gerät in die Dokumentation hochladen
- Formatierte Word-Inhalte inklusive Tabellen und unterstützten Zwischenablage-Bildern einfügen
- Mehrere Dokumentationen mit Ordnern, Zuordnungen und Anhängen als ZIP exportieren und wieder importieren
- Druckoptimierte A4-Ansicht zum Drucken oder Speichern als PDF
- Seitenfüllende Großansicht per Schaltfläche oder Klick auf eine Tabelle
- Lesbare Tabellen mit vollständigen Zellrahmen und horizontalem Inhalts-Scrolling
- Tabellen-Presets, farbige Kopfzeilen und Zellhervorhebungen im WYSIWYG-Editor
- Excel-Mehrblattimport: je Arbeitsblatt eine Dokumentation in einem gewählten Zielordner
- Zweistufige Excel-Vorschau mit Blattauswahl und frei änderbaren Dokumenttiteln
- Optionales Glätten von Excel-Tabellen in kompakte Feld-/Wert-Textblöcke
- Eine Dokumentation mehreren Objekten zuordnen und umgekehrt
- Unbegrenzt viele Objektzuordnungen pro Dokumentation; nur identische Doppelzuordnungen werden verhindert
- Unterstützte Standardobjekte: Region, Standort, Location, Rack, Gerät, VM, VM-Cluster und Mandant/Kunde
- DOCX, XLSX/XLSM, textbasierte PDF-, Markdown- und Textdateien importieren
- Originaldatei optional zusammen mit der Dokumentation aufbewahren
- Dokumentationen über die globale NetBox-Suche und per REST-API finden
- NetBox-Berechtigungen, Änderungsprotokoll, Tags und Custom Fields verwenden

## Kompatibilität

Die Version `0.7.0` zielt auf NetBox 4.x (mindestens 4.0). Vor einem produktiven Rollout sollte das Plugin gegen die konkret eingesetzte NetBox-Minor-Version in einer Testinstanz geprüft werden.

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
        "max_archive_size_mb": 250,
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

Für große Excel-Dateien kann auf der Importseite **„Excel mit mehreren Arbeitsblättern – je Blatt eine Dokumentation“** aktiviert werden. Dazu ist ein Zielordner verpflichtend. Jedes nicht leere Arbeitsblatt wird als eigene Dokumentation mit dem Blattnamen als Titel angelegt und erhält eine eigene Kopie der Original-Exceldatei als Anhang. Normale eingebettete PNG-, JPEG-, GIF- und WebP-Bilder werden dem jeweiligen Dokument als Medienanhang hinzugefügt. Diagramme, SmartArt, Steuerelemente und extern verknüpfte Bilder können nicht zuverlässig übernommen werden.

Vor dem Anlegen erscheint eine Vorschauseite mit allen erkannten Arbeitsblättern. Dort können einzelne Blätter abgewählt, die zukünftigen Dokumenttitel geändert und die jeweils erzeugte Dokumentation aufgeklappt werden. Erst die abschließende Bestätigung schreibt Dokumentationen und Anhänge in die Datenbank. Nicht bestätigte Vorschauen sind an den Benutzer gebunden und werden nach 24 Stunden bereinigt.

Mit **„Excel-Tabellen glätten“** werden normale Zellen ohne künstliche Datensatz- oder Feldbezeichnungen in ihrer Lesereihenfolge übernommen. Zellen einer Excel-Zeile erscheinen als einzelne Textzeilen eines Absatzes; zwischen Excel-Zeilen wird ein Absatz eingefügt. Bereiche, die in Excel ausdrücklich über **Einfügen → Tabelle** als strukturierte Tabelle gekennzeichnet wurden, bleiben dagegen als Tabelle erhalten. Rein optisch mit Rahmen oder Farben formatierte Bereiche gelten nicht als Tabelle. Nicht geglättete Tabellen werden in der Dokumentansicht automatisch kompakt dargestellt und bei Bedarf innerhalb des Inhalts horizontal scrollbar, ohne das NetBox-Layout zu verbreitern.

## REST-API

Nach Aktivierung stehen die üblichen NetBox-Plugin-Endpunkte bereit:

- `/api/plugins/documentation/documents/`
- `/api/plugins/documentation/assignments/`
- `/api/plugins/documentation/folders/`
- `/api/plugins/documentation/attachments/`

## ZIP-Archiv

Unter **Dokumentation → ZIP Export & Import** können mehrere Ordner über ein Suchfeld hinzugefügt und gemeinsam heruntergeladen werden. Optional werden alle Unterordner rekursiv einbezogen. Dokumentationen, die durch überlappende Ordnerauswahlen mehrfach gefunden werden, landen nur einmal im Archiv. Das Archiv enthält:

- Dokumentinhalt und Metadaten
- vollständige Ordnerpfade
- Zuordnungen zu NetBox-Objekten
- importierte Dateien und Editor-Bilder

Beim Import kann gewählt werden, ob Dokumentationen mit derselben Kennung aktualisiert oder als neue Kopie angelegt werden. Zuordnungen zu nicht vorhandenen beziehungsweise nicht erlaubten NetBox-Objekten werden übersprungen. Eingebettete Bild-URLs werden auf die neu gespeicherten Anhänge umgeschrieben.

Archive werden vor dem Import auf sichere Pfade, Dateianzahl, Dateitypen, Kompressionsverhältnis und entpackte Gesamtgröße geprüft. Das Größenlimit wird mit `max_archive_size_mb` in `PLUGINS_CONFIG` festgelegt.

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

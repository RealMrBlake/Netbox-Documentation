# NetBox Documentation

A wiki for operational documentation and how-tos, integrated into NetBox.

| | |
|---|---|
| **Plugin name** | `netbox_documentation` |
| **Package** | `netbox-documentation` |
| **NetBox** | `>=4.0` |
| **Python** | `>=3.10` |
| **Repository** | <https://git.mrblake.cc/MrBlake/Netbox-Documentation> |

## Features

- Write documentation directly in NetBox, displayed as safely sanitised rich text
- Word-like WYSIWYG editor with fonts, font sizes, colours, alignment and tables
- Hierarchical folders and sub-folders for a BookStack-like structure
- Wide editor view and TinyMCE full-screen mode
- Optionally assign documents and folders to tenants and tenant groups
- Upload images from your own device directly into a document
- Paste formatted Word content including tables and supported clipboard images
- Export and re-import multiple documents with folders, assignments and attachments as ZIP
- Print-optimised A4 view for printing or saving as PDF
- Full-page view via button or by clicking a table
- Readable tables with full cell borders and horizontal content scrolling
- Table presets, coloured header rows and cell highlighting in the editor
- Excel multi-sheet import: one document per worksheet in a chosen target folder
- Two-step Excel preview with sheet selection and editable document titles
- Optional flattening of Excel tables into compact field/value text blocks
- Assign one document to many objects and vice versa (unlimited; only identical duplicates are prevented)
- Supported objects: region, site, location, rack, device, VM, VM cluster and tenant/customer
- Import DOCX, XLSX/XLSM, text-based PDF, Markdown and text files
- Optionally keep the original file together with the document
- Find documents via NetBox global search and the REST API
- NetBox permissions, changelog, tags and custom fields

## Compatibility

- NetBox `>=4.0`
- Python `>=3.10`

Test the plugin against your exact NetBox minor version in a staging instance
before a production rollout.

## Installation

All paths assume a standard installation under `/opt/netbox`.

### 1. Install the package

```bash
/opt/netbox/venv/bin/pip install --upgrade --force-reinstall \
  "git+https://git.mrblake.cc/MrBlake/Netbox-Documentation.git@main"
```

For reproducible production installs, replace `main` with a release tag or a
full commit ID.

### 2. Add the plugin to `local_requirements.txt`

This makes `upgrade.sh` reinstall the plugin automatically on every NetBox upgrade:

```bash
grep -qxF "git+https://git.mrblake.cc/MrBlake/Netbox-Documentation.git@main" /opt/netbox/local_requirements.txt \
  || echo "git+https://git.mrblake.cc/MrBlake/Netbox-Documentation.git@main" | sudo tee -a /opt/netbox/local_requirements.txt
```

If the repository is private, the NetBox server needs a read-only deploy token
or an SSH key. Do not store credentials in `local_requirements.txt`.

### 3. Enable the plugin

In `/opt/netbox/netbox/netbox/configuration.py`:

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
    },
}
```

If other plugins are already configured, add `netbox_documentation` to the
existing list and dictionary instead of replacing them.

### 4. Apply migrations, collect static files, restart

```bash
cd /opt/netbox/netbox
/opt/netbox/venv/bin/python manage.py migrate netbox_documentation
/opt/netbox/venv/bin/python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

TinyMCE is installed as a Python dependency and served via a local, cached
plugin endpoint; `collectstatic` also copies the files into NetBox. The editor
therefore needs neither CDN access nor an API key (TinyMCE runs in GPL mode). If
the script cannot be loaded, a plain HTML text field is used as a fallback.

For Docker installations, add the package to your NetBox image, set plugin and
configuration, and rebuild the image. Uploaded files live in NetBox's
`MEDIA_ROOT`, which must be persistent and backed up.

## Update

```bash
/opt/netbox/venv/bin/pip install --upgrade --force-reinstall \
  "git+https://git.mrblake.cc/MrBlake/Netbox-Documentation.git@main"

cd /opt/netbox/netbox
/opt/netbox/venv/bin/python manage.py migrate netbox_documentation
/opt/netbox/venv/bin/python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

`--force-reinstall` makes pip pick up branch changes even if the package
version has not been bumped.

When NetBox itself is upgraded, `upgrade.sh` reinstalls the plugin from
`local_requirements.txt` and runs migrations and `collectstatic`:

```bash
sudo /opt/netbox/upgrade.sh
sudo systemctl restart netbox netbox-rq
```

Check the installed version and migrations:

```bash
/opt/netbox/venv/bin/pip show netbox-documentation
cd /opt/netbox/netbox
/opt/netbox/venv/bin/python manage.py showmigrations netbox_documentation
```

> **Migrating from the old repository name:** earlier versions were installed
> from `Netbox-DokiWiki.git`. Replace that line in
> `/opt/netbox/local_requirements.txt` with the URL above.

## Uninstall

1. Remove `"netbox_documentation"` from `PLUGINS` and `PLUGINS_CONFIG`.
2. Remove the line from `/opt/netbox/local_requirements.txt`.
3. Uninstall the package and restart NetBox:

```bash
/opt/netbox/venv/bin/pip uninstall netbox-documentation
sudo systemctl restart netbox netbox-rq
```

## Configuration

| Key | Default | Description |
|---|---|---|
| `max_import_size_mb` | `25` | Maximum size of a single imported file |
| `max_archive_size_mb` | `250` | Maximum size of a ZIP archive import |
| `keep_imported_file` | `True` | Keep the original file as an attachment |
| `allowed_object_types` | see above | Object types documents can be assigned to |

## Usage

### Permissions

Grant permissions under **Admin → Users → Permissions**:

- `netbox_documentation.view_document`
- `netbox_documentation.add_document`, `change_document`, `delete_document`
- `netbox_documentation.view_documentassignment` and the corresponding change permissions
- `netbox_documentation.import_document` for Office/PDF imports

Set object-level constraints matching your tenants and areas of responsibility.
Unpublished documents are an editorial status, not a replacement for object
permissions.

### Import behaviour

| Format | Imported content |
|---|---|
| DOCX | Headings, paragraphs, lists, links and simple tables |
| XLSX/XLSM | Each worksheet as its own table; formula results only if Excel saved them |
| PDF | Extractable text, split by page |
| MD/TXT | Taken over directly (UTF-8) |

Legacy binary `.doc` and `.xls` files must be converted to `.docx`/`.xlsx`
first. Scanned PDFs require OCR, which is not included yet. Complex Word/PDF
layouts, embedded images and Excel formatting cannot be converted losslessly.

For large Excel files, enable **"Excel with multiple worksheets — one document
per sheet"** on the import page (a target folder is required). Every non-empty
worksheet becomes its own document titled after the sheet, with its own copy of
the original Excel file attached. Embedded PNG, JPEG, GIF and WebP images are
added as media attachments; charts, SmartArt, controls and externally linked
images cannot be imported reliably.

A preview page lists all detected worksheets first. Sheets can be deselected,
titles changed and the resulting documents expanded. Only the final
confirmation writes documents and attachments to the database. Unconfirmed
previews are bound to the user and cleaned up after 24 hours.

**"Flatten Excel tables"** takes over normal cells in reading order without
artificial record or field labels: cells of one row become lines of a paragraph,
rows are separated by paragraphs. Ranges explicitly formatted as a table in
Excel (**Insert → Table**) stay tables. Non-flattened tables are shown compactly
and scroll horizontally inside the content without widening the NetBox layout.

### ZIP archive

Under **Documentation → ZIP Export & Import**, multiple folders can be added via
a search field and downloaded together, optionally including all sub-folders.
Documents found by overlapping folder selections are included only once. The
archive contains:

- document content and metadata
- full folder paths
- assignments to NetBox objects
- imported files and editor images

On import, choose whether documents with the same identifier are updated or
created as new copies. Assignments to missing or disallowed objects are skipped.
Embedded image URLs are rewritten to the newly stored attachments.

Archives are checked for safe paths, file count, file types, compression ratio
and total extracted size before import. The size limit is set with
`max_archive_size_mb`.

### REST API

- `/api/plugins/documentation/documents/`
- `/api/plugins/documentation/assignments/`
- `/api/plugins/documentation/folders/`
- `/api/plugins/documentation/attachments/`

## Development and tests

```bash
pip install -e ".[test]"
pytest
```

Full UI/API tests require NetBox in the same virtualenv. The pure import tests
are located in `netbox_documentation/tests/`.

## Roadmap

- OCR for scanned PDFs (e.g. Tesseract/OCRmyPDF as an optional worker)
- Import embedded DOCX images as NetBox media
- Real document revisions with diff and approval workflow
- Asynchronous bulk import of large Excel datasets via NetBox RQ
- Templates and inherited documentation along region → site → device

## License

Apache License 2.0.

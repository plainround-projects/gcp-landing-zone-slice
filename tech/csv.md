# CSV (comma-separated values)

## 1. What it is

CSV is a plain-text format for a table. Each line is a row. The values in a row are separated by commas. The first line usually holds the column names. Spreadsheet programs open it as a grid, and any text editor shows it as it is. There is no schema: nothing in the file says that a column is a number or a date.

## 2. Why this repository uses it

The lesson needs "sensitive data" that the perimeter can protect, so that the attack in step 5 has something real to try to leak. The file `data/customers.csv` holds **made-up** customers. The repository never reads it as a table: it is only uploaded to the bucket and read back. Making it up means no real person's data is in the repository or in the cloud project.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `data/customers.csv` | The made-up table. |
| `scripts/upload-sample.sh` | Copies it into the sensitive bucket with `gcloud storage cp`. |
| `scripts/read-dry-run.sh`, `scripts/attack.sh` | Read the object back (`gcloud storage cat`) as normal traffic and as the attack. |
| `design/landing-zone.yaml` | Names the object (`sensitive_data.object: customers.csv`). |

## 4. How it works underneath

A reader splits each line at commas and each value becomes a text field. A value that contains a comma must be wrapped in double quotes (`"Smith, Jo"`), and a double quote inside it is doubled. Python's standard `csv` module handles those rules; splitting a line with `line.split(",")` does not. Line endings differ between systems, so tools accept `\n` and `\r\n`.

Cloud Storage treats the file as an opaque object: bytes under a name. It does not know it is a table, which is why the perimeter and IAM protect it by the bucket, not by the content.

## 5. Walkthrough of this repository's use

`scripts/upload-sample.sh`

```bash
gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA" 2>/dev/null \
  || gcloud storage cp "$ROOT/data/customers.csv" "gs://$BUCKET/customers.csv"
gcloud storage ls -l "gs://$BUCKET/"
```

- `gcloud storage cp SOURCE DESTINATION` copies a local file to `gs://BUCKET/customers.csv`.
- `--impersonate-service-account="$DATA_READER_SA"` runs the copy as the data-reader identity; the `2>/dev/null || ...` fallback runs it as you when the impersonation is not allowed yet.
- `gcloud storage ls -l "gs://$BUCKET/"` lists the bucket with sizes, as a check that the upload worked.

Reading it back as normal traffic:

`scripts/read-dry-run.sh`

```bash
echo "== normal traffic: the data reader reads the object from this machine"
gcloud storage cat "gs://$BUCKET/customers.csv" --impersonate-service-account="$DATA_READER_SA" | head -2
```

`gcloud storage cat` prints the object; `| head -2` keeps the header and the first row, so no more of the data than needed reaches the terminal.

## 6. Try it yourself

```bash
head -2 data/customers.csv | cut -c1-80
```
Expected: `customer_id,name,city` (the column names) and then one made-up row, `C-0001,Ada Example,Springfield`.

```bash
wc -l < data/customers.csv
```
Expected: `6` (the header plus five rows); macOS pads the number with spaces.

```bash
.venv/bin/python -c "
import csv
rows = list(csv.DictReader(open('data/customers.csv', newline='')))
print(len(rows), list(rows[0].keys()))"
```
Expected: `5 ['customer_id', 'name', 'city']`: the row count (without the header) and the column names, taken from the header line.

```bash
.venv/bin/python -c "
import csv, io
print(list(csv.reader(io.StringIO('a,\"b, c\",d\n'))))"
```
Expected: `[['a', 'b, c', 'd']]`. The quoted comma stays inside its value.

## 7. Mistakes people make

- **Splitting on commas by hand.** Quoted values break it. Use the `csv` module.
- **Real personal data in a sample file.** This file is made up on purpose.
- **Assuming types.** `007` is text in the file; a spreadsheet may turn it into 7.
- **Forgetting `newline=''`** when opening a CSV file in Python, which can corrupt line endings inside quoted values.
- **Treating the object's content as the protection.** The control is on the bucket and the perimeter, not on the file.

## 8. Check yourself

1. What does a comma do in a CSV line? *It separates two values.*
2. How is a value that contains a comma written? *Wrapped in double quotes.*
3. Why is `customers.csv` made up? *So no real person's data is in the repository or the project.*
4. Which Python module reads CSV correctly? *`csv`.*
5. Does Cloud Storage know the file is a table? *No; it stores bytes under a name.*

## 9. Further reading

- `csv` module: <https://docs.python.org/3.12/library/csv.html>
- RFC 4180, the common CSV format: <https://www.rfc-editor.org/rfc/rfc4180>
- `gcloud storage cp`: <https://cloud.google.com/sdk/gcloud/reference/storage/cp>

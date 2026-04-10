# Other-Tag Grouper (PyQt6)

This tool lets you group `raw_value` entries tagged as `Other` for one configured category.

## What it does

- Loads rows from `../data-extraction-summary.csv`
- Keeps only rows where `tag == "Other"`
- Keeps only rows from one configured category
- Shows **one question at a time**
- Displays all relevant values for that question in one view:
  - all `Other` raw values (green if assigned to at least one term)
  - user-defined general terms
  - values already assigned to the selected term
- Supports assigning and unassigning values
- Supports assigning the same raw value to multiple terms
- Preloads existing terms from `data-items.json` for the selected category/question
- Still allows creating and deleting terms freely (no validation rules)
- Automatically loads the last saved session on startup (if available)
- If no session is available, it attempts to load existing grouping results from `other_tag_grouping_export.json`
- Supports session save/load and export

## Configure category (in script)

Open `other_tag_grouper.py` and set:

```python
TARGET_CATEGORY = "Target platform (RQ1)"
```

You can also adjust:

- `CSV_PATH`
- `SESSION_PATH`
- `EXPORT_PATH`

## Run

From `slr-data-extraction-tool/`:

```bash
python3 other_tag_grouper.py
```

## Buttons

- **Create Term**: adds a new general term for current question
- **Assign Selected Values -> Term**: assigns selected raw values to selected term (values can belong to multiple terms)
- **<- Remove Selected Values From Term**: removes selected values from selected term
- **Delete Selected Term**: deletes term and unassigns its values
- **Save Session**: writes current in-progress grouping to `other_tag_grouping_session.json`
- **Export Grouping**: writes final grouped export to `other_tag_grouping_export.json`

## Export format

Export JSON contains:

- `category`
- `questions`
  - `terms`
    - each term with `term_origin` (`existing` or `new`), `raw_values`, aggregated `paper_ids`, and `paper_count`
  - `ungrouped_raw_values`
    - each value with its `paper_ids` and `paper_count`

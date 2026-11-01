# Process and roster checks

The rehearsal can also ask whether the exported data supports what the organisation does.
The organisation describes this itself in a small JSON file, and optionally supplies a list
of its members. Both files stay on the local machine. The tool never guesses processes from
the package.

```
lsofframp rehearse PACKAGE... -o DIR --process FILE [--roster FILE --roster-as-of YYYY-MM-DD]
```

## Process file

Schema: `schemas/process.v0.1.json`. Example: `examples/process.example.json`.

```json
{
  "schema_version": "0.1",
  "processes": [
    {
      "name": "Member administration",
      "items": [
        {"label": "Member contact list", "select": {"kind": "contact"}},
        {
          "label": "Membership folder",
          "select": {"path_prefix": "Members"},
          "requires_shared_with": "board@example.org"
        }
      ]
    }
  ]
}
```

- A process has a unique `name` and at least one item. An item has a `label` (unique inside
  its process), a `select` and, optionally, `requires_shared_with`.
- `select` takes exactly one of `kind` (for example `file`, `contact`, `calendar_event`),
  `path_prefix` (a folder inside the package, written with `/`) or `object_id` (an
  identifier from the Manifest).
- `requires_shared_with` names the person or address that must still have access.
- Unknown fields are refused, so a misspelt key is an error and not a silent no-op.

## States

Each item receives one state and a reason. A process shows the least favourable state of
its items, in this order, and is always shown together with its items. There is no score.

| State | Meaning |
| --- | --- |
| `not_usable` | The data is there but a check says it cannot support the item: a read problem under the selection, nobody of the required kind has access, or the required person is inactive on the roster. |
| `unknown` | The package or the inputs do not say. Examples: the selector matched nothing, the package does not say who has access, sharing goes through a group or domain whose members are not listed, no roster was given, the person is not on the roster, the file format could not be classified. |
| `needs_conversion` | The files exist but use a format that is not an open standard. |
| `usable` | Objects were found and none of the checks found a problem. This is not a guarantee that the data is complete or correct. |

A selector that matches nothing is `unknown`, never `usable`. For kinds the package reader
cannot produce yet (contacts, calendar events, mail), the reason says so, because finding
none proves nothing.

## Roster file

A CSV file, UTF-8, comma or semicolon separated, with a header row.

| Column | Required | Meaning |
| --- | --- | --- |
| `email` | yes | Address of the person. Compared without regard to case. Each address may appear once. |
| `active` | yes | `true`/`false`, `yes`/`no`, `ja`/`nein` or `1`/`0`. |
| `name`, `role` | no | Kept for the user's own reference; not written to any output. |

Other columns are ignored. The organisation states with `--roster-as-of` which day the
roster reflects; the tool does not guess this and refuses a date in the future. A roster is
refused as a whole if a row is invalid, so that a typing error cannot silently remove a
person from the check.

## What reaches the Evidence Pack

The Evidence Pack gets a `processes` section with the SHA-256 of the process file, the
result of every process and item, the identifiers of the objects that decided an item, and,
if a roster was given, only its SHA-256, its row count and its as-of date. Names, addresses
and any other roster content are never written, and error messages name rows and columns,
not values. If no process file was given, `processes` is `null`, which means "not checked".

## Current limits

- Generic ZIP and folder packages usually carry no sharing information, so items with
  `requires_shared_with` will report `unknown` until provider modules exist.
- Contacts, calendar events and mail are not read yet (planned readers for VCF, ICS, MBOX).
- File formats are recognised by extension only.
- Groups and domains are not expanded, since the package normally does not list members.

# Threat model



Status: Draft

Date: 2026-10-28



## What is being protected



- **The contents of the export package.** Mail, calendars, contacts,

  documents and permission data of the organization, often personal data.

- **The user's machine.** LSofframp opens files it did not create.

- **The integrity of the result.** A finding that is wrong gives a false

  sense of safety or a false alarm.



## Trust boundaries



- The export package is **untrusted input**. It was produced by a third party

  and may be damaged, truncated or deliberately crafted.

- The user's local file system is trusted to hold the package and the

  output, but LSofframp must not write outside the directories it is given.

- There is no network boundary in normal operation. LSofframp makes no network

  calls (see ADR 0001).



## Threats and planned mitigations



| # | Threat | Mitigation |

|---|--------|------------|

| 1 | Archive entries with paths such as `../` or absolute paths write outside the working directory | Never extract to disk by entry name. Read entries as streams and resolve any path against a fixed root before use |

| 2 | Zip bombs and very large entries exhaust memory or disk | Stream entries, enforce limits on entry size, total size, entry count and compression ratio, report an exceeded limit as a finding |

| 3 | Symlinks or special files inside a package point to files elsewhere | Do not follow links inside packages. Report them as findings |

| 4 | Malformed MBOX, ICS, VCF, CSV or JSON crashes a reader | Each reader catches parse errors per item, records the item as unreadable and continues |

| 5 | XML-based formats (ODF, OOXML) with entity expansion or external references | Use a hardened XML parser, disable external entities and network access |

| 6 | Office documents with macros or embedded objects | Never execute or render documents. Detect and report macros and embedded objects only |

| 7 | Parser vulnerabilities in third-party libraries | Keep dependencies few and pinned, review licenses and advisories, avoid parsers that need native code where a standard-library option is enough |

| 8 | The Evidence Pack leaks personal data | Record metadata and checksums, not file contents. Make the included fields explicit. Provide an option to redact file names and addresses |

| 9 | The Evidence Pack or Manifest is altered after creation | Include a checksum of the source package and of the report. Signing is out of scope for the first prototype and is stated as a limitation |

| 10 | A result is misleading (a skipped check read as a pass) | "Unknown" is a separate result (ADR 0002). Every report lists the checks that were not run |

| 11 | Dependencies or tooling make network calls | Review each dependency. Tests run without network access |

| 12 | Test fixtures contain real personal data | Fixtures are synthetic only. Real packages are never committed |

| 13 | Logs and error messages expose file names or content | Errors name the entry and the reason, not its content. Debug output is off by default |

| 14 | Provider-specific link in a document leads to a live service | Links are listed as strings. They are never opened or resolved by the tool |



## Out of scope



- Detecting malware or deciding whether a package is safe to open in other

  software.

- A compromised user machine.

- Verifying that the provider's export is authentic or complete beyond what the

  package itself lets us check.

- Cryptographic signing of the Evidence Pack in the first prototype.



## Open questions



- Concrete limits for entry size, total size and compression ratio.

- Whether a hardened XML parser from a third party is needed or the standard

  library with restricted settings is sufficient.

- Which fields of the Evidence Pack are redactable.


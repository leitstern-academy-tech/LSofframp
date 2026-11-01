# 0001: Process export packages locally only



Status: Accepted

Date: 2026-10-28



## Context



LSofframp inspects export packages that contain mail, calendars, contacts,

documents and permission data. For small organizations this data is often

personal data under GDPR and may include confidential material about members,

students or customers.



The tool could obtain the data in three ways: by logging in to the live cloud

account, by accepting uploads to a hosted analysis service, or by reading an

export package that the organization already holds on its own machine.



## Decision



LSofframp reads export packages from the local file system and does all

analysis on the user's machine. It does not ask for account credentials, does

not store passwords or tokens, and does not send package contents to any

server.



## Consequences



- The tool never becomes a processor of the organization's personal data on

  behalf of a third party, which keeps the privacy and security review simple.

- Results depend on what the provider put into the export. Anything the

  provider omitted cannot be discovered through the live account. The Evidence

  Pack reports such gaps as unknowns instead of hiding them.

- No automatic comparison against the live account is possible. The check

  tests the package, not the service.

- Large packages are limited by the user's own hardware. Readers must stream

  rather than load whole archives into memory.

- Dependencies must not make network calls at runtime. This has to be checked

  for every new dependency.



## Alternatives considered



- **Live account access (OAuth or API keys):** gives a fuller picture, but the

  tool would hold credentials with broad access. Rejected for security and

  because it changes what is being tested: the package, not the service.

- **Hosted upload service:** easier to use, but would make the maintainer a

  recipient of sensitive data and add operational and legal obligations out of

  proportion to a small open-source project. Rejected.



## Notes



Local-first processing is a common and widely used pattern. It is not claimed

as an original element of this project.


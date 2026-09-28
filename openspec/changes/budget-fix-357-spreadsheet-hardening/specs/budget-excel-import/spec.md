## ADDED Requirements

### Requirement: Prepare-import bounds workbook processing before parsing
Budget service's `prepare-import` step SHALL reject an upload before full parsing when any of these limits is exceeded: total uncompressed archive size, uncompressed size of any single archive member, compression ratio, number of archive members, worksheet row or column extent, or number of populated cells. The worksheet check SHALL be based on the cells actually present in the file, not on the declared used range, and SHALL NOT allocate memory in proportion to the used range. A rejected upload SHALL receive a 400 response naming the limit that was exceeded, and SHALL NOT be stored.

#### Scenario: Sparse workbook with a huge used range
- **WHEN** a user uploads a small `.xlsx` whose only cells are `A1` and `XFD1048576`
- **THEN** the service rejects it with 400 without iterating the used range, and memory use stays bounded

#### Scenario: Compression bomb
- **WHEN** a user uploads an `.xlsx` under the upload size cap whose worksheet XML decompresses beyond the uncompressed-size or ratio limit
- **THEN** the service rejects it with 400 before handing it to the spreadsheet parser

#### Scenario: Realistic donor template
- **WHEN** a user uploads a typical donor budget template (hundreds of rows, tens of columns)
- **THEN** it passes the limits and is processed as before

### Requirement: Workbook parsing does not block the service
Budget service SHALL parse uploaded workbooks outside the request event loop, with a bounded number of concurrent parses per process, so that one upload cannot stall unrelated requests.

#### Scenario: Concurrent request during a parse
- **WHEN** a large but within-limits workbook is being parsed
- **THEN** an unrelated budget API request on the same instance is served without waiting for the parse to finish

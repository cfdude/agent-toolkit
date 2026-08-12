# Sprint Plan: Large Dataset Handling
## Data Commons MCP Server v1.2.0

**Sprint Goal**: Implement pagination-based streaming for large datasets with automatic CSV export

**Sprint Capacity**: 70 story points
**Planned Points**: 71 points

---

## Sprint Backlog

### Epic: Phase 1 - Pagination Infrastructure (26 points)

#### DC-001: Add pagination support to API client
**Story Points**: 5
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need the Data Commons client to support paginated API requests so that large datasets can be fetched incrementally.

**Acceptance Criteria**:
- [ ] Add `fetch_observations_page()` method to `clients.py`
- [ ] Accept optional `page_token` parameter for continuation
- [ ] Return response object with `next_token` field when more pages exist
- [ ] Handle `nextToken` from DC REST V2 API response
- [ ] Maintain backward compatibility with existing `fetch_obs()` method

**Technical Notes**:
- Wrap existing `datacommons_client` library calls
- Parse `nextToken` from raw API response
- Create `ObservationPage` data model if needed

---

#### DC-002: Create path resolver utility
**Story Points**: 3
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need a secure path resolver that organizes output files by type and prevents path traversal attacks.

**Acceptance Criteria**:
- [ ] Create `utils/path_resolver.py`
- [ ] Sanitize filenames (remove special chars, handle reserved names)
- [ ] Organize files into subdirectories: `observations/`, `search/`, `metadata/`, `exports/`
- [ ] Verify resolved paths stay within storage root
- [ ] Raise `PathSecurityError` on escape attempts

**Technical Notes**:
- Adapt from FRED's `path_resolver.py` implementation
- Use regex `[^A-Za-z0-9._-]` for sanitization
- Block Windows reserved names (CON, PRN, AUX, etc.)

---

#### DC-003: Create CSV streamer utility
**Story Points**: 5
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need a CSV streamer that writes API response pages directly to disk without accumulating in memory.

**Acceptance Criteria**:
- [ ] Create `utils/csv_streamer.py`
- [ ] Implement context manager for streaming writes
- [ ] Flatten nested observation structure to CSV rows
- [ ] Initialize headers dynamically on first page
- [ ] Buffer writes for efficiency (configurable chunk size)
- [ ] Support progress callbacks

**Technical Notes**:
- Use `csv.DictWriter` for streaming
- Flatten: entity_dcid → place_dcid, facet observations → rows
- Yield rows via generator to minimize memory

---

#### DC-004: Create pagination handler
**Story Points**: 8
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need a pagination handler that orchestrates the fetch-stream loop for large datasets.

**Acceptance Criteria**:
- [ ] Create `utils/pagination_handler.py`
- [ ] Implement `fetch_with_auto_streaming()` method
- [ ] Fetch first page and check for `nextToken`
- [ ] If no pagination, return data directly ("screen" mode)
- [ ] If paginated, stream all pages to CSV ("file" mode)
- [ ] Track rows_written and pages_fetched
- [ ] Support progress callbacks for SSE transport

**Technical Notes**:
- Inject `DataCommonsClient` and `CSVStreamer` dependencies
- Respect `DC_MAX_PAGES` safety limit
- Return standardized response dict with output_mode

---

#### DC-005: Unit tests for Phase 1 utilities
**Story Points**: 5
**Priority**: P0
**Type**: Test

**Description**:
As a developer, I need comprehensive unit tests for all Phase 1 utilities to ensure reliability.

**Acceptance Criteria**:
- [ ] `test_path_resolver.py` - sanitization, subdirs, security
- [ ] `test_csv_streamer.py` - flattening, streaming, headers
- [ ] `test_pagination_handler.py` - mock paginated responses
- [ ] All tests pass with >90% coverage for utils/
- [ ] Test edge cases: empty responses, single page, many pages

**Technical Notes**:
- Use pytest fixtures for mock API responses
- Mock `nextToken` sequences for pagination tests
- Test file cleanup in teardown

---

### Epic: Phase 2 - Output Handler Integration (13 points)

#### DC-006: Create output handler orchestrator
**Story Points**: 5
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need an output handler that decides whether to return data directly or stream to file based on response characteristics.

**Acceptance Criteria**:
- [ ] Create `utils/output_handler.py`
- [ ] Support `output` modes: "auto", "screen", "file"
- [ ] In "auto" mode, use first-page `nextToken` detection
- [ ] Generate timestamped filenames
- [ ] Return standardized response dicts for both modes
- [ ] Include metadata (rows_written, file_size_bytes, etc.)

**Technical Notes**:
- Compose `PaginationHandler`, `CSVStreamer`, `PathResolver`
- Filename format: `observations_{variable}_{YYYYMMDD_HHMMSS}.csv`
- Keep token estimation as fallback for single-page size check

---

#### DC-007: Update get_observations tool with output parameters
**Story Points**: 5
**Priority**: P0
**Type**: Feature

**Description**:
As an MCP client, I need the `get_observations` tool to accept output configuration parameters so I can control how large results are handled.

**Acceptance Criteria**:
- [ ] Add `output: Literal["auto", "screen", "file"]` parameter (default: "auto")
- [ ] Add `format: Literal["csv", "json"]` parameter (default: "csv")
- [ ] Add `multi_file: bool` parameter (default: False)
- [ ] Integrate with `OutputHandler` for response generation
- [ ] Update tool docstring with new parameter documentation
- [ ] Maintain backward compatibility (existing calls work unchanged)

**Technical Notes**:
- Wire output handler into existing tool function
- Pass transport context for progress callbacks
- Preserve existing response structure when output_mode="screen"

---

#### DC-008: Integration tests for output handler
**Story Points**: 3
**Priority**: P0
**Type**: Test

**Description**:
As a developer, I need integration tests that verify end-to-end behavior of the output handling system.

**Acceptance Criteria**:
- [ ] Test: paginated response automatically streams to CSV
- [ ] Test: single-page response returns directly
- [ ] Test: `output="file"` forces file output regardless of size
- [ ] Test: `output="screen"` returns data directly
- [ ] Test: generated CSV is valid and contains expected data
- [ ] Test: file metadata in response is accurate

**Technical Notes**:
- May need to mock DC API or use small real queries
- Verify CSV can be read back with pandas
- Check file paths are correctly resolved

---

### Epic: Phase 3 - Transport Abstraction (16 points)

#### DC-009: Create transport abstraction layer
**Story Points**: 5
**Priority**: P1
**Type**: Feature

**Description**:
As a developer, I need a transport abstraction that allows the same code to work with both STDIO and SSE transports.

**Acceptance Criteria**:
- [ ] Create `utils/transport.py`
- [ ] Define `Transport` abstract base class
- [ ] Implement `STDIOTransport` (no-op progress)
- [ ] Implement `SSETransport` (emits progress events)
- [ ] Add `supports_streaming()` method
- [ ] Transport is injected into output handler

**Technical Notes**:
- STDIO: `send_progress()` is no-op
- SSE: `send_progress()` emits event via callback
- Factory function to create transport from config

---

#### DC-010: Update CLI with transport flag
**Story Points**: 3
**Priority**: P1
**Type**: Feature

**Description**:
As a user, I need CLI options to select the transport mode so I can use the server with different MCP clients.

**Acceptance Criteria**:
- [ ] Add `--transport` flag: choices ["stdio", "sse"], default "stdio"
- [ ] Add `--port` flag for SSE server (default: 8080)
- [ ] STDIO mode uses existing `run_stdio_server()`
- [ ] SSE mode starts HTTP server with SSE endpoint
- [ ] Update `serve` command help text

**Technical Notes**:
- Use click for CLI options
- SSE mode requires uvicorn + sse-starlette (optional deps)
- Graceful error if SSE deps not installed

---

#### DC-011: Implement SSE server
**Story Points**: 8
**Priority**: P1
**Type**: Feature

**Description**:
As a Claude Code user, I need an SSE transport option so I can receive progress updates during large data fetches.

**Acceptance Criteria**:
- [ ] Create HTTP server with MCP-compatible SSE endpoint
- [ ] Emit progress events during pagination
- [ ] Support tool calls via HTTP POST
- [ ] Handle client disconnection (cancel in-progress operations)
- [ ] Add to optional dependencies in pyproject.toml

**Technical Notes**:
- Use sse-starlette for SSE implementation
- Use uvicorn as ASGI server
- Progress events: `{"type": "progress", "data": {...}}`
- May need FastAPI or Starlette for HTTP routing

---

### Epic: Phase 4 - Enhancements (11 points)

#### DC-012: Implement multi-file export
**Story Points**: 5
**Priority**: P1
**Type**: Feature

**Description**:
As a data analyst, I need the option to export observations with companion metadata files so I can preserve relational integrity.

**Acceptance Criteria**:
- [ ] When `multi_file=True`, generate companion CSVs
- [ ] `{base}.places.csv` - Place DCID → name/type lookup
- [ ] `{base}.sources.csv` - Data source metadata
- [ ] Main observations file uses base name
- [ ] Response includes `companion_files` dict with paths
- [ ] Deduplicate place entries in lookup file

**Technical Notes**:
- Create `MultiFileExporter` class
- Collect unique places during streaming
- Write companion files after main CSV complete

---

#### DC-013: Add data lineage headers to CSV
**Story Points**: 2
**Priority**: P2
**Type**: Feature

**Description**:
As a data analyst, I need query metadata in CSV headers so I can understand how the data was generated.

**Acceptance Criteria**:
- [ ] Write 6-7 comment lines at top of CSV
- [ ] Include: server version, variable, place, child_type, date filter, timestamp
- [ ] Configurable via `DC_INCLUDE_LINEAGE` env var
- [ ] Headers are valid CSV comments (# prefix)

**Technical Notes**:
- Write before CSV headers in `CSVStreamer`
- Keep minimal to avoid bloat
- Compatible with pandas `read_csv(comment='#')`

---

#### DC-014: Update configuration and settings
**Story Points**: 2
**Priority**: P0
**Type**: Feature

**Description**:
As a developer, I need new configuration options for all large dataset handling features.

**Acceptance Criteria**:
- [ ] Add to `settings.py`:
  - `DC_STORAGE_DIR` (default: "./datacommons-data")
  - `DC_OUTPUT_FORMAT` (default: "csv")
  - `DC_MAX_PAGES` (default: 100)
  - `DC_DEFAULT_TRANSPORT` (default: "stdio")
  - `DC_SSE_PORT` (default: 8080)
  - `DC_MULTI_FILE_EXPORT` (default: False)
  - `DC_INCLUDE_LINEAGE` (default: True)
- [ ] Environment variable support for all options
- [ ] Validation for invalid values

**Technical Notes**:
- Use pydantic-settings pattern
- Document all options in README

---

### Epic: Documentation & Release (5 points)

#### DC-015: Update documentation and version
**Story Points**: 3
**Priority**: P1
**Type**: Documentation

**Description**:
As a user, I need updated documentation explaining the new large dataset handling features.

**Acceptance Criteria**:
- [ ] Update README with new features section
- [ ] Document new tool parameters
- [ ] Document environment variables
- [ ] Add usage examples for CSV export
- [ ] Update version to 1.2.0 in version.py

**Technical Notes**:
- Include example responses for both modes
- Document STDIO vs SSE transport differences

---

#### DC-016: Add dependencies and update pyproject.toml
**Story Points**: 2
**Priority**: P0
**Type**: Chore

**Description**:
As a developer, I need the project dependencies updated to support new features.

**Acceptance Criteria**:
- [ ] Add `tiktoken>=0.5.0` to dependencies
- [ ] Add optional `sse` extras: `sse-starlette>=1.0.0`, `uvicorn>=0.20.0`
- [ ] Update version in pyproject.toml
- [ ] Run `uv sync` to update lock file
- [ ] All existing tests still pass

**Technical Notes**:
- tiktoken is optional (graceful fallback if not installed)
- SSE deps only needed for `--transport sse` mode

---

## Sprint Summary

| Epic | Stories | Points |
|------|---------|--------|
| Phase 1: Pagination Infrastructure | DC-001 to DC-005 | 26 |
| Phase 2: Output Handler Integration | DC-006 to DC-008 | 13 |
| Phase 3: Transport Abstraction | DC-009 to DC-011 | 16 |
| Phase 4: Enhancements | DC-012 to DC-014 | 9 |
| Documentation & Release | DC-015 to DC-016 | 5 |
| **Total** | **16 stories** | **69 points** |

---

## Execution Order

**Critical Path** (must complete in order):
```
DC-014 (config) → DC-002 (path resolver) → DC-003 (csv streamer) →
DC-001 (pagination API) → DC-004 (pagination handler) → DC-005 (tests) →
DC-006 (output handler) → DC-007 (tool update) → DC-008 (integration tests)
```

**Parallel Work** (can happen alongside critical path):
- DC-009 + DC-010 + DC-011 (transport layer) - after DC-006
- DC-012 + DC-013 (enhancements) - after DC-007
- DC-015 + DC-016 (docs/release) - after all features

**Recommended Sprint Order**:

| Day | Stories | Focus |
|-----|---------|-------|
| 1 | DC-014, DC-016 | Configuration setup |
| 2-3 | DC-002, DC-003 | Core utilities |
| 4-5 | DC-001, DC-004 | Pagination infrastructure |
| 6 | DC-005 | Phase 1 testing |
| 7-8 | DC-006, DC-007 | Output handler integration |
| 9 | DC-008 | Integration testing |
| 10-11 | DC-009, DC-010 | Transport abstraction |
| 12-13 | DC-011 | SSE server |
| 14 | DC-012, DC-013 | Enhancements |
| 15 | DC-015 | Documentation & release |

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] No regressions in existing tests (123 tests)
- [ ] Code reviewed (self-review for solo dev)
- [ ] Documentation updated where applicable
- [ ] Version bumped to 1.2.0

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| DC API doesn't support pagination as documented | High | Verify with real API calls before deep implementation |
| SSE transport complexity | Medium | Defer to Phase 3, can ship without it |
| Token estimation accuracy | Low | Secondary concern with pagination-first approach |
| Backward compatibility breaks | High | Extensive integration testing, default params |

---

## Out of Scope (Future Sprints)

- Smart chunking by region
- SPARQL-based pre-flight queries
- search_indicators streaming (if needed)
- Background job manager (replaced by pagination)
- Parallel page fetching

# Large Dataset Handling Implementation Plan
## Data Commons MCP Server

**Date**: 2025-12-06 (Revised)
**Version**: 1.1.3rc1 → 1.2.0
**Reference**: mcp-fred server architecture + Data Commons pagination API

---

## Executive Summary

This plan implements intelligent large dataset handling for the Data Commons MCP server using **pagination-based streaming** as the primary mechanism. Unlike the original FRED-inspired approach that relied on post-fetch size detection, this architecture leverages the Data Commons REST V2 API's native pagination (`nextToken`) to stream results directly to CSV without accumulating large datasets in memory.

**Key Design Decision**: First-page detection replaces pre-flight cost estimation. We fetch the first page, check for `nextToken` presence, and immediately switch to streaming mode if pagination is detected.

---

## 1. Architecture Overview

### Current State (datacommons-mcp)
```
datacommons_mcp/
├── server.py           # MCP tools (search_indicators, get_observations)
├── clients.py          # DC API client wrapper
├── services.py         # Business logic layer
├── data_models/        # Pydantic models
│   ├── settings.py     # Configuration
│   ├── observations.py # Response models
│   └── search.py       # Search models
├── cli.py              # CLI entry point
└── version.py          # Version string
```

### Target State (with pagination streaming)
```
datacommons_mcp/
├── server.py           # MCP tools (unchanged interface, enhanced internals)
├── clients.py          # DC API client wrapper + pagination support
├── services.py         # Business logic layer
├── data_models/        # Pydantic models
│   ├── settings.py     # Enhanced configuration
│   ├── observations.py # Response models
│   ├── search.py       # Search models
│   └── jobs.py         # NEW: Job state models (for SSE transport)
├── utils/              # NEW: Utility layer
│   ├── __init__.py
│   ├── pagination_handler.py  # Core pagination + streaming logic
│   ├── csv_streamer.py        # Direct-to-disk CSV writing
│   ├── json_to_csv.py         # Response flattening
│   ├── file_writer.py         # Chunked buffered writes
│   ├── path_resolver.py       # Security & organization
│   ├── output_handler.py      # Decision orchestration
│   └── transport.py           # STDIO vs SSE abstraction
├── cli.py              # CLI entry point (STDIO + HTTP modes)
└── version.py          # Version string
```

---

## 2. Core Mechanism: Pagination-Based Streaming

### 2.1 How It Works

The Data Commons REST V2 API returns paginated responses with `nextToken` when results exceed a single page. Instead of accumulating all pages in memory then deciding what to do, we **stream directly to CSV as we paginate**.

```
┌─────────────────────────────────────────────────────────────────┐
│                 PAGINATION STREAMING FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. FIRST PAGE FETCH                                             │
│     ┌─────────────┐                                              │
│     │ API Request │ → Response + nextToken?                      │
│     └─────────────┘                                              │
│            │                                                     │
│            ▼                                                     │
│  2. DETECTION                                                    │
│     ┌─────────────────────────────────────────┐                  │
│     │ Has nextToken?                          │                  │
│     │   NO  → Small dataset, return directly  │                  │
│     │   YES → Large dataset, start streaming  │                  │
│     └─────────────────────────────────────────┘                  │
│            │ (YES)                                               │
│            ▼                                                     │
│  3. STREAMING LOOP                                               │
│     ┌─────────────────────────────────────────┐                  │
│     │ Open CSV file                           │                  │
│     │ Write page 1 rows                       │                  │
│     │                                         │                  │
│     │ WHILE nextToken:                        │                  │
│     │   Fetch next page                       │                  │
│     │   Write rows to CSV (buffered)          │                  │
│     │   Update progress (if SSE transport)    │                  │
│     │                                         │                  │
│     │ Close CSV file                          │                  │
│     └─────────────────────────────────────────┘                  │
│            │                                                     │
│            ▼                                                     │
│  4. RESPONSE                                                     │
│     ┌─────────────────────────────────────────┐                  │
│     │ Return file metadata to MCP client      │                  │
│     │ {                                       │                  │
│     │   "output_mode": "file",                │                  │
│     │   "file_path": "/path/to/data.csv",     │                  │
│     │   "rows_written": 15000,                │                  │
│     │   "pages_fetched": 15                   │                  │
│     │ }                                       │                  │
│     └─────────────────────────────────────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Why This Is Better Than FRED's Approach

| Aspect | FRED Approach | Pagination Streaming |
|--------|---------------|---------------------|
| Memory usage | Accumulates full response, then decides | Never holds more than one page |
| Detection | Post-fetch token/row estimation | First-page `nextToken` presence |
| API efficiency | Full fetch before file write | Single pass, fetch → write |
| Timeout risk | High for massive datasets | Low - controlled page-by-page |
| Pre-flight cost | Requires estimation logic | Zero - detection is free |

### 2.3 Implementation

```python
class PaginationHandler:
    """Core pagination and streaming logic."""

    def __init__(
        self,
        client: DataCommonsClient,
        csv_streamer: CSVStreamer,
        config: OutputConfig,
    ):
        self._client = client
        self._csv_streamer = csv_streamer
        self._config = config

    async def fetch_with_auto_streaming(
        self,
        request: ObservationRequest,
        output_mode: Literal["auto", "screen", "file"],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        Fetch observations with automatic streaming for large results.

        Returns screen response for small datasets, file response for large.
        """
        # Fetch first page
        first_page = await self._client.fetch_observations_page(request)

        # Check for pagination
        has_more_pages = first_page.next_token is not None

        if output_mode == "screen" or (output_mode == "auto" and not has_more_pages):
            # Small dataset - return directly
            return {
                "output_mode": "screen",
                "data": first_page.to_response_dict(),
            }

        # Large dataset detected - stream to CSV
        file_path = self._csv_streamer.create_output_path(request)
        rows_written = 0
        pages_fetched = 1

        with self._csv_streamer.open(file_path, request) as writer:
            # Write first page
            rows_written += writer.write_page(first_page)

            # Stream remaining pages
            next_token = first_page.next_token
            while next_token:
                page = await self._client.fetch_observations_page(
                    request, page_token=next_token
                )
                rows_written += writer.write_page(page)
                pages_fetched += 1
                next_token = page.next_token

                if progress_callback:
                    progress_callback(rows_written, pages_fetched)

        return {
            "output_mode": "file",
            "file_path": str(file_path),
            "rows_written": rows_written,
            "pages_fetched": pages_fetched,
            "file_size_bytes": file_path.stat().st_size,
        }
```

---

## 3. Transport Modes: STDIO vs SSE

### 3.1 The Problem

- **Claude Desktop**: STDIO only - request → processing → response. No mid-stream updates.
- **Claude Code**: Supports HTTP/SSE - can stream progress updates during processing.

### 3.2 Solution: Transport Abstraction

```python
class Transport(ABC):
    """Abstract base for MCP transport modes."""

    @abstractmethod
    async def send_progress(self, progress: dict) -> None:
        """Send progress update to client."""

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this transport supports incremental updates."""


class STDIOTransport(Transport):
    """STDIO transport - no streaming, batch response only."""

    async def send_progress(self, progress: dict) -> None:
        # No-op for STDIO - progress is not sent
        pass

    def supports_streaming(self) -> bool:
        return False


class SSETransport(Transport):
    """Server-Sent Events transport - supports streaming."""

    def __init__(self, event_emitter: Callable):
        self._emit = event_emitter

    async def send_progress(self, progress: dict) -> None:
        await self._emit({
            "type": "progress",
            "data": progress,
        })

    def supports_streaming(self) -> bool:
        return True
```

### 3.3 CLI Entry Points

```python
# cli.py updates

@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio")
@click.option("--port", type=int, default=8080, help="Port for SSE server")
def serve(transport: str, port: int):
    """Start the MCP server."""
    if transport == "stdio":
        # Standard STDIO mode (Claude Desktop compatible)
        run_stdio_server()
    else:
        # HTTP/SSE mode (Claude Code compatible)
        run_sse_server(port=port)
```

### 3.4 Progress Reporting by Transport

| Event | STDIO Behavior | SSE Behavior |
|-------|----------------|--------------|
| Page fetched | Silent | Emits progress event |
| Rows written | Silent | Emits progress event |
| File complete | Returns final response | Emits completion + final response |
| Error | Returns error response | Emits error event + response |

**SSE Progress Event Example**:
```json
{
    "type": "progress",
    "data": {
        "status": "processing",
        "pages_fetched": 8,
        "rows_written": 8000,
        "current_page_size": 1000,
        "has_more": true
    }
}
```

---

## 4. Component Specifications

### 4.1 CSV Streamer

**Purpose**: Stream paginated responses directly to CSV without memory accumulation.

```python
class CSVStreamer:
    """Stream API responses directly to CSV files."""

    def __init__(
        self,
        path_resolver: PathResolver,
        config: OutputConfig,
    ):
        self._resolver = path_resolver
        self._config = config
        self._fieldnames = None
        self._writer = None

    def create_output_path(self, request: ObservationRequest) -> Path:
        """Generate output path for a request."""
        timestamp = datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"observations_{request.variable_dcid}_{timestamp}.csv"
        return self._resolver.resolve(filename, subdir="observations")

    @contextmanager
    def open(self, path: Path, request: ObservationRequest):
        """Context manager for streaming writes."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write lineage header
        with open(path, "w", newline="", encoding="utf-8") as f:
            self._write_lineage_header(f, request)

            self._writer = None
            self._fieldnames = None

            yield self

            # Ensure final flush
            if hasattr(f, 'flush'):
                f.flush()

    def write_page(self, page: ObservationPage) -> int:
        """Write a page of results, initializing headers on first call."""
        rows = list(self._flatten_page(page))

        if not rows:
            return 0

        if self._writer is None:
            self._fieldnames = list(rows[0].keys())
            self._writer = csv.DictWriter(
                self._file,
                fieldnames=self._fieldnames,
            )
            self._writer.writeheader()

        self._writer.writerows(rows)
        return len(rows)

    def _flatten_page(self, page: ObservationPage) -> Iterator[dict]:
        """Flatten a page of observations to CSV rows."""
        for entity_dcid, entity_data in page.by_entity.items():
            for facet in entity_data.ordered_facets:
                for obs in facet.observations:
                    yield {
                        "place_dcid": entity_dcid,
                        "place_name": page.get_name(entity_dcid),
                        "date": obs.date,
                        "value": obs.value,
                        "variable_dcid": page.variable_dcid,
                        "facet_id": facet.facet_id,
                    }

    def _write_lineage_header(self, f, request: ObservationRequest) -> None:
        """Write minimal query metadata as CSV comments."""
        f.write(f"# Data Commons MCP Server v{__version__}\n")
        f.write(f"# Variable: {request.variable_dcid}\n")
        f.write(f"# Place: {request.place_dcid}\n")
        if request.child_place_type:
            f.write(f"# Child Type: {request.child_place_type}\n")
        f.write(f"# Date Filter: {request.date_type}\n")
        f.write(f"# Generated: {datetime.now(dt.UTC).isoformat()}\n")
```

### 4.2 Multi-File Export

**Purpose**: Preserve relational integrity by generating companion metadata files.

```python
class MultiFileExporter:
    """Generate multiple related CSV files for complex queries."""

    def export(
        self,
        response: ObservationsResponse,
        base_path: Path,
    ) -> dict[str, Path]:
        """
        Generate multiple CSV files:
        - {base}_observations.csv - Main data
        - {base}_places.csv - Place DCID → name/type mappings
        - {base}_sources.csv - Data source metadata
        """
        paths = {}

        # Main observations
        obs_path = base_path.with_suffix(".observations.csv")
        paths["observations"] = self._write_observations(response, obs_path)

        # Place lookup
        places_path = base_path.with_suffix(".places.csv")
        paths["places"] = self._write_places(response, places_path)

        # Source metadata
        if response.source_metadata or response.alternative_sources:
            sources_path = base_path.with_suffix(".sources.csv")
            paths["sources"] = self._write_sources(response, sources_path)

        return paths

    def _write_places(self, response: ObservationsResponse, path: Path) -> Path:
        """Write place DCID → name/type lookup table."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["dcid", "name", "type"])
            writer.writeheader()

            seen = set()
            for obs in response.place_observations:
                if obs.place.dcid not in seen:
                    writer.writerow({
                        "dcid": obs.place.dcid,
                        "name": obs.place.name,
                        "type": obs.place.types[0] if obs.place.types else "",
                    })
                    seen.add(obs.place.dcid)

        return path
```

### 4.3 Path Resolver (Unchanged from Original)

Security and organization remain the same:

```
{storage_directory}/
├── observations/           # get_observations results
├── search/                 # search_indicators results
├── metadata/               # DCID mappings, source info
└── exports/                # Multi-file export bundles
```

### 4.4 Token Estimator (Simplified Role)

With pagination streaming, token estimation is **secondary** - used only for small datasets that return in a single page to decide if they fit in context.

```python
class TokenEstimator:
    """Estimate tokens for small, single-page responses."""

    def __init__(self, safe_token_limit: int = 50_000):
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._safe_limit = safe_token_limit

    def fits_in_context(self, data: dict) -> bool:
        """Check if a single-page response fits in context window."""
        json_str = json.dumps(data, separators=(",", ":"))
        tokens = len(self._encoding.encode(json_str))
        # Use 25% of safe limit as threshold (assume 75% context used)
        return tokens < (self._safe_limit * 0.25)
```

---

## 5. Configuration Updates

### 5.1 Environment Variables

```python
# settings.py additions

# Storage
DC_STORAGE_DIR: str = "./datacommons-data"
DC_OUTPUT_FORMAT: str = "csv"  # csv | json

# Pagination
DC_PAGE_SIZE: int = 1000  # Rows per API page (if configurable)
DC_MAX_PAGES: int = 100   # Safety limit to prevent runaway pagination

# Transport
DC_DEFAULT_TRANSPORT: str = "stdio"  # stdio | sse
DC_SSE_PORT: int = 8080

# File output
DC_EXPAND_TIME_SERIES: bool = True
DC_MULTI_FILE_EXPORT: bool = False  # Generate companion metadata files
DC_INCLUDE_LINEAGE: bool = True     # Add query metadata to CSV headers

# Token estimation (for single-page responses only)
DC_SAFE_TOKEN_LIMIT: int = 50000
```

### 5.2 Backward Compatibility

Existing tool interfaces remain unchanged. New parameters are optional:

```python
async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    # ... existing params ...

    # NEW optional params
    output: Literal["auto", "screen", "file"] = "auto",
    format: Literal["csv", "json"] = "csv",
    multi_file: bool = False,
) -> dict:
```

---

## 6. Tool Interface Updates

### 6.1 get_observations Enhancement

```python
@mcp.tool()
async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str = "latest",
    date_range_start: str | None = None,
    date_range_end: str | None = None,
    # NEW parameters
    output: Literal["auto", "screen", "file"] = "auto",
    format: Literal["csv", "json"] = "csv",
    multi_file: bool = False,
) -> dict:
    """
    Fetches observations for a statistical variable from Data Commons.

    Large Dataset Handling (Pagination-Based):
    - output="auto" (default): Returns data directly if single page,
      streams to CSV if pagination detected (nextToken present)
    - output="screen": Always return data directly (may truncate if too large)
    - output="file": Always stream to file regardless of size

    When data is written to file, returns:
    {
        "status": "success",
        "output_mode": "file",
        "file_path": "/path/to/observations.csv",
        "rows_written": 15000,
        "pages_fetched": 15,
        "file_size_bytes": 2456789,
        "variable": {...},
        "source_metadata": {...}
    }

    With multi_file=True, also generates:
    - {base}.places.csv - Place DCID → name/type lookup
    - {base}.sources.csv - Data source metadata
    """
```

---

## 7. Improvements Over FRED (Revised)

### 7.1 Multi-File Export ✓ APPROVED

Data Commons responses contain rich relational data: place hierarchies with DCIDs, variable metadata, source provenance. When flattening to a single CSV, you either duplicate metadata on every row (bloating the file) or lose it entirely. Multi-file export generates a main `observations.csv` plus companion files like `places.csv` (DCID→name→type mappings) and `sources.csv` (data provenance), preserving referential integrity for proper joins in pandas or databases.

### 7.2 Query Cost Estimation Tool ✗ REMOVED

Replaced by first-page detection. The API doesn't support pre-flight counts, and users want the data regardless of size. First-page `nextToken` check provides free detection without additional API calls.

### 7.3 Smart Chunking ○ OPTIONAL/SECONDARY

With pagination handling timeouts natively, smart chunking becomes a secondary optimization rather than a requirement. May implement later if specific use cases demand it (e.g., SPARQL-based region splitting for parallel fetches).

### 7.4 Data Lineage Headers ✓ APPROVED (Minimal)

Minimal query metadata in CSV headers (6-7 lines) for reproducibility:
```csv
# Data Commons MCP Server v1.2.0
# Variable: Count_Person
# Place: country/USA
# Child Type: County
# Date Filter: latest
# Generated: 2025-12-06T14:30:00Z
place_dcid,place_name,date,value,...
```

### 7.5 Incremental Progress ✓ APPROVED (Transport-Dependent)

Progress updates work on platforms that support it (SSE transport for Claude Code), silent on platforms that don't (STDIO for Claude Desktop). No behavioral difference - just visibility.

---

## 8. Implementation Phases (Revised)

### Phase 1: Pagination Infrastructure
**Scope**: 5 files, ~600 lines

| Component | Priority | Notes |
|-----------|----------|-------|
| `clients.py` pagination support | P0 | Add `fetch_observations_page()` with nextToken |
| `utils/pagination_handler.py` | P0 | Core streaming logic |
| `utils/csv_streamer.py` | P0 | Direct-to-disk CSV writing |
| `utils/path_resolver.py` | P0 | Adapted from FRED |
| Unit tests | P0 | |

**Deliverable**: Pagination-based streaming to CSV working.

### Phase 2: Output Handler Integration
**Scope**: 3 files, ~300 lines

| Component | Priority | Notes |
|-----------|----------|-------|
| `utils/output_handler.py` | P0 | Decision orchestration |
| `server.py` get_observations update | P0 | Add output/format params |
| Integration tests | P0 | |

**Deliverable**: `output="auto"` with automatic file streaming.

### Phase 3: Transport Abstraction
**Scope**: 3 files, ~400 lines

| Component | Priority | Notes |
|-----------|----------|-------|
| `utils/transport.py` | P1 | STDIO vs SSE abstraction |
| `cli.py` updates | P1 | --transport flag |
| SSE server implementation | P1 | HTTP endpoint |

**Deliverable**: Progress streaming on SSE transport.

### Phase 4: Enhancements
**Scope**: 2 files, ~300 lines

| Component | Priority | Notes |
|-----------|----------|-------|
| Multi-file export | P1 | Companion metadata CSVs |
| Data lineage headers | P2 | Query metadata in files |
| search_indicators streaming | P2 | If needed for large results |

**Deliverable**: Full feature parity with improvements.

---

## 9. Testing Strategy

### Unit Tests
```
tests/
├── utils/
│   ├── test_pagination_handler.py
│   ├── test_csv_streamer.py
│   ├── test_path_resolver.py
│   ├── test_output_handler.py
│   └── test_transport.py
└── test_multi_file_export.py
```

### Integration Tests
```python
# Test: Paginated response streams to file
async def test_pagination_streams_to_csv():
    response = await get_observations(
        variable_dcid="Count_Person",
        place_dcid="country/USA",
        child_place_type="County",
        date="latest",
        output="auto",
    )
    assert response["output_mode"] == "file"
    assert response["pages_fetched"] > 1
    assert Path(response["file_path"]).exists()

# Test: Single-page response returns directly
async def test_single_page_returns_screen():
    response = await get_observations(
        variable_dcid="Count_Person",
        place_dcid="geoId/06",  # California only
        date="latest",
        output="auto",
    )
    assert response["output_mode"] == "screen"
    assert "data" in response

# Test: Multi-file export generates companion files
async def test_multi_file_export():
    response = await get_observations(
        variable_dcid="Count_Person",
        place_dcid="country/USA",
        child_place_type="State",
        output="file",
        multi_file=True,
    )
    base_path = Path(response["file_path"])
    assert base_path.with_suffix(".places.csv").exists()
```

### Pagination Mock Tests
```python
# Mock API responses with nextToken to test streaming logic
async def test_pagination_loop_handles_all_pages():
    mock_pages = [
        MockPage(data=[...], next_token="token1"),
        MockPage(data=[...], next_token="token2"),
        MockPage(data=[...], next_token=None),  # Final page
    ]
    # Assert all pages written, no data loss
```

---

## 10. Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
tiktoken = ">=0.5.0"  # Token estimation (optional, for single-page checks)

[project.optional-dependencies]
sse = ["sse-starlette>=1.0.0", "uvicorn>=0.20.0"]  # For SSE transport
```

---

## 11. Success Criteria

| Metric | Target |
|--------|--------|
| All US counties query completes | < 60 seconds |
| Memory usage during pagination | < 50MB (single page buffer) |
| No context truncation with auto mode | 100% |
| SSE progress updates | Every page fetch |
| Backward compatibility | All existing tests pass |
| New test coverage | > 90% for utils/ |

---

## Appendix A: API Pagination Reference

From Data Commons REST V2 API documentation:

```
Response Structure:
{
    "byVariable": {
        "<variable_dcid>": {
            "byEntity": {
                "<entity_dcid>": { ... }
            }
        }
    },
    "nextToken": "abc123..."  // Present if more pages exist
}

Next Page Request:
POST /v2/observation
{
    ...original params...,
    "pageToken": "abc123..."
}
```

## Appendix B: Sample Outputs

**Screen Response** (small dataset):
```json
{
    "output_mode": "screen",
    "data": {
        "variable": {...},
        "place_observations": [...],
        "source_metadata": {...}
    }
}
```

**File Response** (large dataset):
```json
{
    "output_mode": "file",
    "file_path": "/Users/rob/datacommons-data/observations/observations_Count_Person_20251206_143022.csv",
    "rows_written": 15234,
    "pages_fetched": 16,
    "file_size_bytes": 1847293,
    "variable": {
        "dcid": "Count_Person",
        "name": "Total Population"
    },
    "source_metadata": {
        "source_id": "census.gov",
        "url": "https://www.census.gov"
    }
}
```

**Multi-File Response**:
```json
{
    "output_mode": "file",
    "file_path": "/path/to/observations_Count_Person_20251206_143022.csv",
    "companion_files": {
        "places": "/path/to/observations_Count_Person_20251206_143022.places.csv",
        "sources": "/path/to/observations_Count_Person_20251206_143022.sources.csv"
    },
    "rows_written": 15234,
    "pages_fetched": 16
}
```

## Appendix C: Transport Comparison

| Feature | STDIO (Claude Desktop) | SSE (Claude Code) |
|---------|------------------------|-------------------|
| Progress updates | No | Yes - per page |
| Cancellation | No | Yes - client disconnect |
| Multiple concurrent | No | Yes |
| Streaming partial results | No | Possible (future) |
| Configuration | Default | `--transport sse --port 8080` |

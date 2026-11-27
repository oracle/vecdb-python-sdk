# SDK logging

Configure SDK logging with `VECDB_DEBUG`. Set it before the first import of
`oracle_vecdb`; the SDK reads it once when the package loads.

Set the value in the shell:

```bash
VECDB_DEBUG=INFO python your_app.py
```

Or set it in Python before importing the SDK:

```python
import os

os.environ.setdefault("VECDB_DEBUG", "INFO")

import oracle_vecdb
```

`setdefault` keeps a value supplied by the shell. Replace it with a direct
assignment when the script should always choose its own level.

## Levels

Values are case-insensitive, and surrounding whitespace is ignored.

| `VECDB_DEBUG` value | Output |
| --- | --- |
| Unset or empty | No SDK console output by default. Application-configured Python logging can still receive SDK records. |
| `INFO` | Successful operation summaries and errors. |
| `DEBUG`, `1`, `true`, `yes`, `on` | INFO output plus retry decisions. |
| `TRACE` | DEBUG output plus operation starts, batch details, and HTTP and deserialization timings. |
| `WARNING`, `WARN`, `ERROR` | Failed operation summaries. These summaries are emitted at ERROR. |
| `CRITICAL`, `FATAL` | Critical threshold; the SDK currently emits no critical events. |
| `OFF`, `0`, `false`, `no` | Suppress SDK logging, including records from child loggers. |
| `NOTSET` | Use the effective level from the parent logger. |

An unsupported value raises `ValueError` during package import. There is no
numeric verbosity scale. `TRACE` is a detail mode at the DEBUG threshold.
Changing the environment after import does not reconfigure the SDK. Choose
`TRACE` before import to receive phase timings.

## Python logging

The SDK uses the `oracle_vecdb` logger and its `operations`, `ords`, `auth`, and
`performance` child loggers. When `VECDB_DEBUG` is unset, the SDK adds no console
handler. When enabled, it supplies a stderr fallback so the environment
variable works on its own. An application handler on the emitting logger, the
package logger, or a reachable parent takes precedence over that fallback.

Use standard Python logging to choose destinations, formats, and runtime
thresholds. For example, attach a `FileHandler` or `RotatingFileHandler` to
`logging.getLogger("oracle_vecdb")`. The SDK does not configure the root logger,
change dependency logger levels, or enable HTTP wire debugging. `OFF` is a
package-wide stop and cannot be overridden by lowering a child logger's level.

## Events and privacy

Each public SDK operation emits one INFO success summary or ERROR failure
summary. DEBUG includes retry decisions; TRACE adds operation starts, batch
details, and phase timings. Nested operations carry correlation IDs, and
excess detail is capped while completion summaries remain available.

Structured fields are available on each Python `LogRecord` as `record.vecdb`.
They include the event and operation names, correlation IDs, outcome, timing,
counts, HTTP status, and normalized error codes when known. The SDK excludes
request and response payloads, vectors, metadata, SQL, credentials, headers,
URLs, resource names, and free-form exception text. Logging failures do not
change SDK results or exceptions.

## Configuration behavior

Logging is controlled independently of `Configuration` and OAuth arguments;
there are no per-client logging options. Set `VECDB_DEBUG` before importing the
package. A request's `debug_flags` parameter is for server-side VecDB behavior
and does not control SDK logging.

# Changelog

## 0.7.0 (2026-11-26)

- At times the Ministry's server only accepts `AES256-GCM-SHA384`, which Python's
  default SSL context does not offer. A request to that server that fails to
  connect is retried with a context that also allows that cipher (the server
  still picks a modern one when it offers it), and that context is used first
  from then on. Requests to other servers are not affected.

## 0.6.1 (2026-11-26)

- Fix: `PreciosCarburantesConnectionError` can be raised without arguments again.

## 0.6.0 (2026-11-26)

- Retry a request once, after 2 seconds, when the connection fails or the server
  answers 5xx. 4xx answers are not retried.
- `PreciosCarburantesConnectionError.status` holds the HTTP status, if any.
- The client options after `session` are keyword-only.

## 0.5.0 (2026-11-26)

- Remove the cipher exception added in 0.4.0.

## 0.4.0 (2026-11-26)

- Allow the `AES256-GCM-SHA384` cipher for the Ministry's server.
- Unexpected response formats raise `PreciosCarburantesError` instead of
  `KeyError` or `ValueError`.

## 0.3.0 (2026-11-26)

- `parse_schedule()`, `Schedule.is_open()` and `next_change()` for opening hours.

## 0.2.0 (2026-11-26)

- `get_station_by_id()`, from the Geoportal Gasolineras website, which also lists
  stations with restricted sales.
- `Station.municipality_id` and `Station.province_id` are optional.

## 0.1.0 (2026-11-26)

- First release: provinces, municipalities, stations by municipality or province,
  and a single station.

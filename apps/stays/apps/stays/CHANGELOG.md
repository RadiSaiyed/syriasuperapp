# Changelog — Stays API

All notable changes for the Booking-like enhancements. Dates in YYYY-MM-DD.

## 2025-10-26

- Property listing (GET /properties)
  - Filters: rating_band (5, 4+, 3+, 2+, 1+), available_only=true (requires check_in/check_out), policy filters (free_cancellation, breakfast_included, non_refundable, pay_at_property, no_prepayment)
  - Sorting: distance (requires center_lat/center_lon), price_preview (requires check_in/check_out)
  - Result extras: image_url, badges (top_rated, popular_choice), distance_km, favorites_count, price_preview_total_cents, price_preview_nightly_cents
  - Headers: X-Total-Count, Link (prev/next), Vary: Authorization, ETag + 304 support

- Availability search (POST /search_availability)
  - Facets: price_histogram, rating_bands; policy flags in results
  - Short TTL caching (memory/Redis)
  - Grouping by property and advanced sorts (best_value, recommended, distance)

- New/expanded public endpoints
  - GET /properties/top: rating_band filter, pagination (limit/offset), headers (X-Total-Count, Link), ETag
  - GET /properties/nearby: rating_band filter, distance_km per item, pagination (limit/offset), headers (X-Total-Count, Link), ETag
  - GET /cities/popular: rating_bands in response, pagination (limit/offset), headers (X-Total-Count, Link), ETag
  - GET /suggest: cities + properties suggestions, caching + ETag

- Caching & Rate Limits
  - In-memory cache with optional Redis backend (CACHE_BACKEND=redis, CACHE_REDIS_URL)
  - Lifespan-based cache prewarm for popular cities and top picks
  - Per-endpoint rate limits with headers (X-RateLimit-*); 429 returns Retry-After. Optional Redis backend for limiter

- Internal
  - Moved startup cache warmup to FastAPI lifespan (removed on_event warning)
  - Tests added: facets/policies, ETag 304, rate headers, pagination headers


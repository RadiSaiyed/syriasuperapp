from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
try:
    from starlette.middleware.forwarded import ForwardedMiddleware as _ForwardedOrProxy
except Exception:
    try:
        from starlette.middleware.proxy_headers import ProxyHeadersMiddleware as _ForwardedOrProxy
    except Exception:
        _ForwardedOrProxy = None  # type: ignore
from sqlalchemy import text
from contextlib import asynccontextmanager

from .config import settings
from .database import engine
from .models import Base
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
from .routers import auth as auth_router
from .routers import host as host_router
from .routers import public as public_router
from .routers import reservations as reservations_router
from .routers import favorites as favorites_router
from .routers import reviews as reviews_router
from .routers import webhooks as webhooks_router
from .routers import payments_webhook as payments_webhook_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.CACHE_ENABLED and getattr(settings, "CACHE_PREWARM", False):
            try:
                from .utils.cache import cache
                from sqlalchemy import func
                from .database import SessionLocal
                from .models import Property, Unit, Review, Reservation, PropertyImage
                from .schemas import CityPopularOut, PropertyOut
                limit_cities = 8
                limit_props = 12
                with SessionLocal() as db:
                    # Popular cities
                    rows = (
                        db.query(Property.city, func.count(Property.id))
                        .filter(Property.city.isnot(None))
                        .group_by(Property.city)
                        .order_by(func.count(Property.id).desc())
                        .limit(limit_cities)
                        .all()
                    )
                    cities_out = []
                    for (city, cnt) in rows:
                        if not city:
                            continue
                        avg = (
                            db.query(func.avg(Review.rating))
                            .filter(Review.property_id.in_(db.query(Property.id).filter(Property.city == city)))
                            .scalar()
                        )
                        avg_rating = float(avg) if avg is not None else None
                        prop_ids = [pid for (pid,) in db.query(Property.id).filter(Property.city == city).all()]
                        min_price = None
                        if prop_ids:
                            unit_min = db.query(func.min(Unit.price_cents_per_night)).filter(Unit.property_id.in_(prop_ids)).scalar()
                            min_price = int(unit_min) if unit_min is not None else None
                        img = (
                            db.query(PropertyImage)
                            .join(Property, Property.id == PropertyImage.property_id)
                            .filter(Property.city == city)
                            .order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc())
                            .first()
                        )
                        image_url = img.url if img else None
                        cities_out.append(CityPopularOut(city=city, property_count=int(cnt), avg_rating=avg_rating, image_url=image_url, min_price_cents=min_price))
                    cache.set(("cities_popular", limit_cities), cities_out, settings.CACHE_DEFAULT_TTL_SECS)

                    # Top properties: global and per top 3 cities
                    props = db.query(Property).order_by(Property.created_at.desc()).limit(2000).all()
                    if props:
                        prop_ids = [p.id for p in props]
                        aggs = (
                            db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
                            .filter(Review.property_id.in_(prop_ids))
                            .group_by(Review.property_id)
                            .all()
                        )
                        rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
                        pops = (
                            db.query(Reservation.property_id, func.count(Reservation.id))
                            .filter(Reservation.property_id.in_(prop_ids))
                            .group_by(Reservation.property_id)
                            .all()
                        )
                        pop_map = {pid: int(cnt) for (pid, cnt) in pops}
                        imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(prop_ids)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
                        first_img: dict = {}
                        for im in imgs:
                            if im.property_id not in first_img:
                                first_img[im.property_id] = im.url
                        def build_top(props_list):
                            rows2 = []
                            for p in props_list:
                                ravg, rcnt = rating_map.get(p.id, (0.0, 0))
                                pop = pop_map.get(p.id, 0)
                                score = (ravg or 0.0) * 0.7 + min(pop, 100) / 100.0 * 0.3
                                rows2.append((p, score, ravg or None, rcnt))
                            rows2.sort(key=lambda t: (t[1], t[2] or 0.0, t[3]), reverse=True)
                            out: list[PropertyOut] = []
                            for (p, _score, ravg, rcnt) in rows2[:limit_props]:
                                out.append(PropertyOut(
                                    id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
                                    address=p.address, latitude=p.latitude, longitude=p.longitude,
                                    rating_avg=ravg, rating_count=rcnt, image_url=first_img.get(p.id),
                                ))
                            return out
                        # Global
                        cache.set(("top_props", "_all_", limit_props), build_top(props), settings.CACHE_DEFAULT_TTL_SECS)
                        # Top 3 cities
                        top3 = [c for (c, _cnt) in rows[:3]] if rows else []
                        for city in top3:
                            city_props = [p for p in props if p.city == city]
                            cache.set(("top_props", city or "_all_", limit_props), build_top(city_props), settings.CACHE_DEFAULT_TTL_SECS)
            except Exception:
                pass
        yield

    app = FastAPI(title="Stays API", version="0.1.0", lifespan=lifespan)

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    # Trusted hosts + forwarded headers
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    proxy_trusted = getattr(settings, "PROXY_TRUSTED_IPS", None)
    if proxy_trusted and _ForwardedOrProxy:
        try:
            app.add_middleware(_ForwardedOrProxy, trusted_hosts=proxy_trusted)
        except Exception:
            pass

    backend = (getattr(settings, "RATE_LIMIT_BACKEND", "") or "").lower()
    common_excludes = ["/health", "/health/deps", "/metrics", "/info", "/openapi.yaml", "/openapi.json", "/ui", "/docs"]
    if backend == "redis":
        app.add_middleware(
            RedisRateLimiter,
            redis_url=settings.REDIS_URL,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
            prefix=settings.RATE_LIMIT_REDIS_PREFIX,
            exclude_paths=common_excludes,
        )
    else:
        app.add_middleware(
            SlidingWindowLimiter,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
            exclude_paths=common_excludes,
        )

    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health():
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "env": settings.ENV}

    REQ = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
    REQ_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )

    @app.middleware("http")
    async def _metrics_mw(request, call_next):
        import time
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        try:
            route = getattr(request.scope.get("route"), "path", None) or request.url.path
            REQ.labels(request.method, route, str(response.status_code)).inc()
            REQ_DURATION.labels(request.method, route).observe(duration)
        except Exception:
            pass
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(auth_router.router)
    app.include_router(public_router.router)
    app.include_router(host_router.router)
    app.include_router(reservations_router.router)
    app.include_router(favorites_router.router)
    app.include_router(reviews_router.router)
    app.include_router(webhooks_router.router)
    app.include_router(payments_webhook_router.router)
    # Dev-only helpers
    if settings.ENV.lower() == "dev":
        try:
            from .routers import dev_seed as dev_seed_router
            app.include_router(dev_seed_router.router)
        except Exception:
            pass
    return app


app = create_app()

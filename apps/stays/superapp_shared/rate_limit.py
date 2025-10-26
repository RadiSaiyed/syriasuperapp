class SlidingWindowLimiter:
    def __init__(self, app, *, limit_per_minute: int = 60, auth_boost: int = 1):
        self.app = app
        self.limit_per_minute = limit_per_minute
        self.auth_boost = auth_boost

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class RedisRateLimiter:
    def __init__(self, app, *, redis_url: str, limit_per_minute: int = 60, auth_boost: int = 1, prefix: str = "rl"):
        self.app = app
        self.redis_url = redis_url
        self.limit_per_minute = limit_per_minute
        self.auth_boost = auth_boost
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


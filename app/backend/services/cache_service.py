import json
from typing import Any, List, Optional

import redis

from app.backend.config.settings import settings


class CacheService:
    def __init__(self):
        self.client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True
        )

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.client.set(key, json.dumps(value), ex=ttl)

    def get_json(self, key: str) -> Optional[Any]:
        cached = self.client.get(key)

        if cached is None:
            return None

        return json.loads(cached)

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def push_json(
        self,
        key: str,
        value: Any,
        max_length: Optional[int] = None
    ) -> None:
        self.client.rpush(key, json.dumps(value))

        if max_length:
            self.client.ltrim(key, -max_length, -1)

    def get_list_json(self, key: str) -> List[Any]:
        items = self.client.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

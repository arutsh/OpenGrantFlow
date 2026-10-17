"""check_daily_cap: UTC-day counter for the anonymous site assistant (design.md Decision 5)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import anyio
import fakeredis
import pytest
import redis

from app.services import rate_limiter
from app.services.rate_limiter import CapStoreUnavailable, check_daily_cap, hash_client_ip

_NOON = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _run(fake, now, coro_fn):
    async def _inner():
        with (
            patch.object(rate_limiter, "get_redis_client", return_value=fake),
            patch.object(rate_limiter, "_utc_now", return_value=now),
        ):
            return await coro_fn()

    return anyio.run(_inner)


def _fake():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


def test_counts_up_to_limit_then_blocks():
    fake = _fake()

    async def _calls():
        return [await check_daily_cap("sa-ip", "abc", 3) for _ in range(4)]

    results = _run(fake, _NOON, _calls)
    assert [allowed for allowed, _ in results] == [True, True, True, False]
    assert results[-1][1] == 12 * 3600


def test_key_is_utc_day_scoped_with_48h_ttl():
    fake = _fake()
    _run(fake, _NOON, lambda: check_daily_cap("sa-ip", "abc", 3))

    async def _inspect():
        return await fake.ttl("rate_limit:sa-ip:abc:20261011")

    assert 0 < anyio.run(_inspect) <= 48 * 3600


def test_midnight_rollover_starts_a_fresh_count():
    fake = _fake()
    before = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)
    after = datetime(2026, 10, 12, 0, 0, 1, tzinfo=timezone.utc)

    _run(fake, before, lambda: check_daily_cap("sa-ip", "abc", 1))
    blocked = _run(fake, before, lambda: check_daily_cap("sa-ip", "abc", 1))
    assert blocked == (False, 1)
    assert _run(fake, after, lambda: check_daily_cap("sa-ip", "abc", 1)) == (True, 0)


def _broken():
    broken = MagicMock()
    broken.pipeline = MagicMock(side_effect=redis.ConnectionError("down"))
    return broken


@pytest.mark.parametrize("limit", [0, None])
def test_unlimited_never_touches_redis(limit):
    broken = _broken()
    for _ in range(3):
        assert _run(broken, _NOON, lambda: check_daily_cap("sa-ip", "abc", limit)) == (True, 0)
    broken.pipeline.assert_not_called()


def test_redis_error_raises_instead_of_allowing():
    broken = _broken()
    with pytest.raises(CapStoreUnavailable):
        _run(broken, _NOON, lambda: check_daily_cap("sa-ip", "abc", 5))


def test_ip_subject_is_keyed_hash_not_raw_ip():
    subject = hash_client_ip("203.0.113.7")
    assert len(subject) == 32
    assert "203.0.113.7" not in subject
    assert subject == hash_client_ip("203.0.113.7")
    assert subject != hash_client_ip("203.0.113.8")


def test_ttl_is_set_on_every_count_without_being_refreshed():
    fake = _fake()
    key = "rate_limit:sa-ip:abc:20261011"

    async def _ttl_after_existing_key_without_one():
        await fake.set(key, 5)
        await check_daily_cap("sa-ip", "abc", 10)
        first = await fake.ttl(key)
        await fake.expire(key, 100)
        await check_daily_cap("sa-ip", "abc", 10)
        return first, await fake.ttl(key)

    first, second = _run(fake, _NOON, _ttl_after_existing_key_without_one)
    assert first > 0
    assert second <= 100


@pytest.mark.parametrize(
    "a, b",
    [
        ("2001:db8:1:2::1", "2001:db8:1:2:ffff:ffff:ffff:ffff"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("2001:DB8:1:2::1", "2001:db8:1:2::1"),
    ],
)
def test_ip_subject_collapses_same_client(a, b):
    assert hash_client_ip(a) == hash_client_ip(b)


@pytest.mark.parametrize(
    "a, b", [("2001:db8:1:2::1", "2001:db8:1:3::1"), ("203.0.113.7", "203.0.113.8")]
)
def test_ip_subject_keeps_distinct_clients_apart(a, b):
    assert hash_client_ip(a) != hash_client_ip(b)


def test_ip_hash_key_is_derived_not_the_raw_encryption_key():
    raw = rate_limiter.settings.ENCRYPTION_KEY.encode()
    assert rate_limiter._ip_hash_key() != raw
    assert len(rate_limiter._ip_hash_key()) == 32

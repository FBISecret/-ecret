import argparse
import asyncio
import contextlib
import json
import logging
import os
import random
import signal
import sys
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Optional, Tuple

try:
    import tls_client
    _HAS_TLS_CLIENT = True
except ImportError:
    _HAS_TLS_CLIENT = False

if not _HAS_TLS_CLIENT:
    try:
        from curl_cffi import requests as curl_requests
        _HAS_CURL_CFFI = True
    except ImportError:
        _HAS_CURL_CFFI = False
    if not _HAS_CURL_CFFI:
        raise SystemExit(
            "tls_client veya curl_cffi gerekli: pip install tls-client veya pip install curl_cffi"
        )

try:
    from websockets.asyncio.client import connect
except ImportError:
    from websockets import connect

try:
    from websockets.proxy import Proxy
except Exception:
    Proxy = None

DEFAULT_CLIENT_TOKEN = "e1393935a959b4020a4491574f6490129f678acdaa92760471263db43487f823"

logger = logging.getLogger("kickbot")


def load_config_file(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit("Config root must be a JSON object.")
    return data


def generate_user_agent() -> str:
    bases = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X)",
    ]
    chrome = f"{random.randint(123, 129)}.0.{random.randint(6000, 8200)}.{random.randint(10, 999)}"
    return f"{random.choice(bases)} AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome} Safari/537.36"


@dataclass(slots=True)
class Settings:
    channel: str
    viewer_goal: int
    max_concurrent: Optional[int]
    proxy_file: str
    client_token: str
    proxy_permits: int = 10
    keepalive_range: Tuple[float, float] = (13.0, 21.0)
    ping_period: int = 6
    retry_delay_range: Tuple[float, float] = (2.0, 6.0)
    ramp_delay_range: Tuple[float, float] = (0.35, 1.35)
    auto_start: bool = False
    status_interval: float = 45.0
    proxy_cooldown: float = 45.0
    log_file: Optional[str] = None
    verbose: bool = False
    http_gate: Optional[int] = None
    http_rps: Optional[float] = 120.0
    log_queue: Optional["Queue[str]"] = None
    config_source: Optional[str] = None

    def effective_concurrency(self, proxy_count: int) -> int:
        per_proxy_cap = proxy_count * self.proxy_permits if proxy_count else self.viewer_goal
        requested = self.max_concurrent or self.viewer_goal
        return max(1, min(requested, per_proxy_cap, self.viewer_goal))


@dataclass(slots=True)
class ProxyEntry:
    raw: str
    http_url: str
    ws_proxy: Optional["Proxy"]

    @property
    def label(self) -> str:
        if "@" in self.raw:
            return self.raw.split("@", 1)[1]
        return self.raw


class ProxyPool:
    def __init__(self, entries: list[ProxyEntry], invalid: int = 0, cooldown: float = 45.0):
        self._entries = entries
        self._invalid = invalid
        self.cooldown = max(0.0, cooldown)
        self._cooldowns: dict[str, float] = {}

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def invalid(self) -> int:
        return self._invalid

    def sample(self) -> Optional[ProxyEntry]:
        if not self._entries:
            return None
        now = time.monotonic()
        ready = [entry for entry in self._entries if self._cooldowns.get(entry.raw, 0.0) <= now]
        if ready:
            return random.choice(ready)
        return min(
            self._entries,
            key=lambda entry: self._cooldowns.get(entry.raw, now + self.cooldown),
        )

    def mark_failure(self, proxy: Optional[ProxyEntry]) -> None:
        if proxy:
            self._cooldowns[proxy.raw] = time.monotonic() + self.cooldown

    def mark_success(self, proxy: Optional[ProxyEntry]) -> None:
        if proxy:
            self._cooldowns.pop(proxy.raw, None)

    @classmethod
    def from_file(cls, path: str, cooldown: float) -> "ProxyPool":
        if not os.path.exists(path):
            logger.warning("Proxy file not found (%s). Running without proxies.", path)
            return cls([], 0, cooldown)

        with open(path, "r", encoding="utf-8") as file:
            raw_lines = [line.strip() for line in file if line.strip()]

        valid_entries: list[ProxyEntry] = []
        invalid = 0
        for line in raw_lines:
            entry = build_proxy_entry(line)
            if entry:
                valid_entries.append(entry)
            else:
                invalid += 1

        if valid_entries:
            logger.info("Loaded %d proxies.", len(valid_entries))
        else:
            logger.warning("No valid proxies, continuing without proxies.")

        if invalid:
            logger.warning("Skipped %d malformed lines.", invalid)

        if Proxy is None and valid_entries:
            logger.warning("WebSocket proxy support unavailable. WS traffic will be direct.")

        return cls(valid_entries, invalid, cooldown)


def build_proxy_entry(line: str) -> Optional[ProxyEntry]:
    if "@" in line:
        auth_part, host_part = line.rsplit("@", 1)
        if ":" not in auth_part or ":" not in host_part:
            return None
        username, password = auth_part.split(":", 1)
        host, port = host_part.rsplit(":", 1)
        http_url = f"http://{username}:{password}@{host}:{port}"
    else:
        if ":" not in line:
            return None
        host, port = line.rsplit(":", 1)
        http_url = f"http://{host}:{port}"
    ws_proxy = None
    if Proxy is not None:
        try:
            ws_proxy = Proxy.from_url(http_url)
        except Exception:
            ws_proxy = None
    return ProxyEntry(raw=line, http_url=http_url, ws_proxy=ws_proxy)


class _HttpClient:
    def __init__(self, client_token: str, proxy: Optional[ProxyEntry]):
        if _HAS_TLS_CLIENT:
            self._session = tls_client.Session(
                client_identifier="chrome_126", random_tls_extension_order=True
            )
            self._session.timeout = 25
            self._session.headers.update({
                "User-Agent": generate_user_agent(),
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://kick.com",
                "Referer": "https://kick.com/",
                "Accept-Language": "en-US,en;q=0.9",
            })
            if proxy:
                self._session.proxies = {"http": proxy.http_url, "https": proxy.http_url}
        else:
            self._session = curl_requests.Session()
            self._session.headers.update({
                "User-Agent": generate_user_agent(),
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://kick.com",
                "Referer": "https://kick.com/",
                "Accept-Language": "en-US,en;q=0.9",
            })
            if proxy:
                self._session.proxies = {"http": proxy.http_url, "https": proxy.http_url}

        self.client_token = client_token
        self.request_timeout = 25
        self._backend = "tls_client" if _HAS_TLS_CLIENT else "curl_cffi"

    def _get(self, url: str) -> Any:
        try:
            if _HAS_TLS_CLIENT:
                resp = self._session.get(url, timeout_seconds=self.request_timeout)
            else:
                resp = self._session.get(url, timeout=self.request_timeout)
        except Exception as exc:
            raise RuntimeError(f"{url} request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise RuntimeError(f"{url} returned {resp.status_code}: {resp.text[:120]}")
        return resp

    def _get_json(self, url: str) -> Any:
        return self._get(url).json()

    async def fetch_token(self) -> str:
        def _work() -> str:
            self._get("https://kick.com")
            self._session.headers.update({"X-CLIENT-TOKEN": self.client_token})
            data = self._get_json("https://websockets.kick.com/viewer/v1/token")
            return data["data"]["token"]
        return await asyncio.to_thread(_work)

    async def fetch_channel_id(self, channel: str) -> int:
        def _work() -> int:
            data = self._get_json(f"https://kick.com/api/v2/channels/{channel}")
            channel_id = data.get("id") or data.get("data", {}).get("id")
            if channel_id is None:
                raise ValueError("No channel id in API response.")
            return int(channel_id)
        return await asyncio.to_thread(_work)

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass


@dataclass(slots=True)
class StatsSnapshot:
    active: int
    total: int
    failures: int
    retries: int


class StatsTracker:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active = 0
        self._total = 0
        self._failures = 0
        self._retries = 0

    async def connection_started(self) -> None:
        async with self._lock:
            self._active += 1
            self._total += 1

    async def connection_closed(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1

    async def record_retry(self) -> None:
        async with self._lock:
            self._retries += 1

    async def snapshot(self) -> StatsSnapshot:
        async with self._lock:
            return StatsSnapshot(
                active=self._active,
                total=self._total,
                failures=self._failures,
                retries=self._retries,
            )


class AsyncRateLimiter:
    def __init__(self, rate: Optional[float]) -> None:
        cleaned = None
        if rate is not None:
            cleaned = float(rate)
            if cleaned <= 0:
                cleaned = None
        self.rate = cleaned
        self._lock = asyncio.Lock()
        self._next_time = 0.0

    async def wait(self) -> None:
        if self.rate is None:
            return
        interval = 1.0 / self.rate
        async with self._lock:
            now = time.monotonic()
            if self._next_time <= now:
                self._next_time = now + interval
                return
            wait_time = self._next_time - now
            self._next_time += interval
        await asyncio.sleep(wait_time)


class GuiQueueHandler(logging.Handler):
    def __init__(self, queue: "Queue[str]") -> None:
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            return
        try:
            self.queue.put_nowait(msg)
        except Exception:
            pass


def configure_logging(settings: Settings) -> None:
    level = logging.DEBUG if settings.verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_file:
        handlers.append(logging.FileHandler(settings.log_file, encoding="utf-8"))
    if settings.log_queue is not None:
        queue_handler = GuiQueueHandler(settings.log_queue)
        queue_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
        handlers.append(queue_handler)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        handlers=handlers,
        force=True,
    )


def format_worker_label(worker_id: int, proxy: Optional[ProxyEntry]) -> str:
    origin = proxy.label if proxy else "proxyless"
    return f"[{worker_id:04d} | {origin[:30]}]"


def retry_delay(settings: Settings) -> float:
    low, high = settings.retry_delay_range
    if low > high:
        low, high = high, low
    return random.uniform(low, high)


def ramp_delay(settings: Settings) -> float:
    low, high = settings.ramp_delay_range
    if low > high:
        low, high = high, low
    return random.uniform(low, high)


async def status_reporter(
    stats: StatsTracker, settings: Settings, stop_event: asyncio.Event
) -> None:
    interval = max(5.0, settings.status_interval)
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            snapshot = await stats.snapshot()
            logger.info(
                "Status | active=%d total=%d errors=%d retries=%d",
                snapshot.active,
                snapshot.total,
                snapshot.failures,
                snapshot.retries,
            )
            continue
        break

    snapshot = await stats.snapshot()
    logger.info(
        "Final | active=%d total=%d errors=%d retries=%d",
        snapshot.active,
        snapshot.total,
        snapshot.failures,
        snapshot.retries,
    )


async def maintain_view_connection(
    token: str,
    channel_id: int,
    worker_id: int,
    settings: Settings,
    proxy: Optional[ProxyEntry],
    stop_event: asyncio.Event,
) -> None:
    headers = {
        "User-Agent": generate_user_agent(),
        "Origin": "https://kick.com",
        "Cookie": f"client_token={settings.client_token}",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }
    url = f"wss://websockets.kick.com/viewer/v1/connect?token={token}"

    connect_kwargs = {
        "additional_headers": headers,
        "ping_interval": None,
        "open_timeout": 25,
        "close_timeout": 20,
    }

    if proxy and proxy.ws_proxy:
        connect_kwargs["proxy"] = proxy.ws_proxy

    handshake_payload = json.dumps(
        {"type": "channel_handshake", "data": {"message": {"channelId": channel_id}}}
    )
    ping_payload = json.dumps({"type": "ping"})

    async with connect(url, **connect_kwargs) as ws:
        label = format_worker_label(worker_id, proxy)
        await ws.send(handshake_payload)
        logger.info("%s websocket opened.", label)

        iteration = 0
        low, high = settings.keepalive_range
        low, high = (low, high) if low <= high else (high, low)

        while True:
            delay = random.uniform(low, high)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                logger.info("%s stop signal received.", label)
                break
            except asyncio.TimeoutError:
                pass

            iteration += 1
            payload = ping_payload if iteration % settings.ping_period == 0 else handshake_payload
            await ws.send(payload)

        await ws.close()
        logger.info("%s websocket closed.", label)


async def viewer_worker(
    worker_id: int,
    settings: Settings,
    proxy_pool: ProxyPool,
    http_gate: asyncio.Semaphore,
    http_rate_limiter: AsyncRateLimiter,
    stop_event: asyncio.Event,
    stats: StatsTracker,
) -> None:
    while not stop_event.is_set():
        proxy = proxy_pool.sample()
        label = format_worker_label(worker_id, proxy)
        token: Optional[str] = None
        channel_id: Optional[int] = None
        need_retry = False

        if stop_event.is_set():
            break
        await asyncio.sleep(ramp_delay(settings))
        if stop_event.is_set():
            break
        await http_rate_limiter.wait()

        async with http_gate:
            client = _HttpClient(settings.client_token, proxy)
            try:
                token = await client.fetch_token()
                channel_id = await client.fetch_channel_id(settings.channel)
            except Exception as exc:
                need_retry = True
                logger.warning("%s Token/Channel fetch failed: %s", label, exc)
                await stats.record_retry()
                proxy_pool.mark_failure(proxy)
            finally:
                client.close()

        if need_retry or token is None or channel_id is None:
            if stop_event.is_set():
                break
            await asyncio.sleep(retry_delay(settings))
            continue

        await stats.connection_started()
        delay_after_error = None
        try:
            await maintain_view_connection(
                token, channel_id, worker_id, settings, proxy, stop_event
            )
            proxy_pool.mark_success(proxy)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("%s Connection lost: %s", label, exc)
            await stats.record_failure()
            proxy_pool.mark_failure(proxy)
            delay_after_error = retry_delay(settings)
        finally:
            await stats.connection_closed()

        if stop_event.is_set():
            break

        if delay_after_error:
            await asyncio.sleep(delay_after_error)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kick.com Viewer Bot"
    )
    parser.add_argument("--config", help="JSON config file path")
    parser.add_argument("-c", "--channel", help="Kick channel name")
    parser.add_argument("-n", "--viewers", type=int, help="Target viewer count (max 10000)")
    parser.add_argument("-m", "--max-concurrency", type=int, help="Max WS connections")
    parser.add_argument("-p", "--proxy-file", help="Proxy file (default: proxy.txt)")
    parser.add_argument("--client-token", help="Kick client_token")
    parser.add_argument("--proxy-permits", type=int, help="Connections per proxy (default 5)")
    parser.add_argument("--retry-delay", type=float, nargs=2, metavar=("MIN", "MAX"),
                        help="Retry delay range (s)")
    parser.add_argument("--ramp-delay", type=float, nargs=2, metavar=("MIN", "MAX"),
                        help="Ramp jitter range (s)")
    parser.add_argument("--keepalive", type=float, nargs=2, metavar=("MIN", "MAX"),
                        help="Keepalive interval range (s, default 13-21)")
    parser.add_argument("--ping-period", type=int, help="Ping every N messages (default 6)")
    parser.add_argument("--auto-start", action=argparse.BooleanOptionalAction, default=None,
                        help="Skip ENTER confirmation")
    parser.add_argument("--proxy-cooldown", type=float,
                        help="Proxy cooldown after error (s, default 45)")
    parser.add_argument("--status-interval", type=float,
                        help="Status output interval (s, default 45)")
    parser.add_argument("--http-gate", type=int,
                        help="Concurrent token/channel requests")
    parser.add_argument("--http-rps", type=float,
                        help="HTTP requests per second limit (0=unlimited, default 120)")
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=None,
                        help="Verbose logging")
    return parser.parse_args()


def pick_value(cli_value: Any, config_value: Any, default: Any) -> Any:
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    return default


def pick_range(
    cli_value: Optional[Tuple[float, float]],
    config_value: Optional[Tuple[float, float]],
    default: Tuple[float, float],
) -> Tuple[float, float]:
    value = cli_value if cli_value is not None else config_value
    if value is None:
        return default
    if len(value) != 2:
        raise SystemExit("Ranges must have exactly 2 values (min max).")
    low, high = float(value[0]), float(value[1])
    if low > high:
        low, high = high, low
    return (low, high)


def pick_bool(cli_value: Optional[bool], config_value: Optional[bool], default: bool) -> bool:
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return bool(config_value)
    return default


def build_settings(args: argparse.Namespace, *, log_queue: Optional["Queue[str]"] = None) -> Settings:
    config: dict[str, Any] = {}
    if args.config:
        config = load_config_file(args.config)

    channel_source = pick_value(args.channel, config.get("channel"), None)
    if not channel_source:
        channel_source = input("Channel name: ").strip()
    channel = channel_source.lower()
    if not channel:
        raise SystemExit("Channel name cannot be empty.")

    if args.viewers is None and "viewers" not in config:
        while True:
            raw = input("How many viewers? (e.g. 1000): ").strip()
            try:
                viewers_value = int(raw)
                if viewers_value <= 0:
                    raise ValueError
                break
            except ValueError:
                print("Enter a positive integer (e.g. 1000).")
        requested_viewers = viewers_value
    else:
        requested_viewers = pick_value(args.viewers, config.get("viewers"), 10_000)

    viewer_goal = max(1, min(10_000, int(requested_viewers)))

    max_concurrency = pick_value(args.max_concurrency, config.get("max_concurrency"), None)
    if max_concurrency is not None:
        max_concurrency = max(1, int(max_concurrency))
    proxy_file = pick_value(args.proxy_file, config.get("proxy_file"), "proxy.txt")
    client_token = pick_value(args.client_token, config.get("client_token"), DEFAULT_CLIENT_TOKEN)
    proxy_permits = max(1, int(pick_value(args.proxy_permits, config.get("proxy_permits"), 10)))
    retry_range = pick_range(args.retry_delay, config.get("retry_delay"), (2.0, 6.0))
    ramp_delay_range = pick_range(args.ramp_delay, config.get("ramp_delay"), (0.15, 0.75))
    keepalive_range = pick_range(args.keepalive, config.get("keepalive"), (13.0, 21.0))
    ping_period = max(1, int(pick_value(args.ping_period, config.get("ping_period"), 6)))
    auto_start = pick_bool(args.auto_start, config.get("auto_start"), False)
    status_interval = max(5.0, float(pick_value(args.status_interval, config.get("status_interval"), 45.0)))
    proxy_cooldown = max(0.0, float(pick_value(args.proxy_cooldown, config.get("proxy_cooldown"), 45.0)))
    base_gate = (viewer_goal // 150) or 1
    default_http_gate = min(viewer_goal, max(80, base_gate))
    raw_http_gate = pick_value(args.http_gate, config.get("http_gate"), default_http_gate)
    if raw_http_gate is None:
        http_gate = None
    else:
        raw_gate_value = int(raw_http_gate)
        http_gate = None if raw_gate_value <= 0 else max(1, raw_gate_value)
    default_http_rps = min(90.0, max(25.0, viewer_goal / 800.0))
    http_rps_value = pick_value(args.http_rps, config.get("http_rps"), default_http_rps)
    if http_rps_value is None:
        http_rps = None
    else:
        http_rps = float(http_rps_value)
        if http_rps <= 0:
            http_rps = None
    log_file = pick_value(args.log_file, config.get("log_file"), None)
    verbose = pick_bool(args.verbose, config.get("verbose"), False)

    return Settings(
        channel=channel,
        viewer_goal=viewer_goal,
        max_concurrent=max_concurrency,
        proxy_file=proxy_file,
        client_token=client_token,
        proxy_permits=proxy_permits,
        keepalive_range=keepalive_range,
        ping_period=ping_period,
        retry_delay_range=retry_range,
        ramp_delay_range=ramp_delay_range,
        auto_start=auto_start,
        status_interval=status_interval,
        proxy_cooldown=proxy_cooldown,
        log_file=log_file,
        verbose=verbose,
        http_gate=http_gate,
        http_rps=http_rps,
        log_queue=log_queue,
        config_source=args.config,
    )


async def run_bot(settings: Settings, external_stop_event: Optional[asyncio.Event] = None) -> None:
    proxy_pool = ProxyPool.from_file(settings.proxy_file, settings.proxy_cooldown)
    slot_count = settings.effective_concurrency(proxy_pool.count)

    backend_name = "tls_client" if _HAS_TLS_CLIENT else "curl_cffi"
    print(f"\n{'='*50}")
    print(f"  KICK VIEWER BOT")
    print(f"  HTTP backend: {backend_name}")
    print(f"  Channel: {settings.channel}")
    print(f"  Target: {settings.viewer_goal} viewers")
    print(f"  Proxies: {proxy_pool.count} valid, {proxy_pool.invalid} invalid")
    print(f"  Active slots: {slot_count}")
    print(f"{'='*50}\n")

    if not settings.auto_start:
        if settings.log_queue is None:
            input("Press ENTER to start...")

    if slot_count <= 0:
        raise SystemExit("No workers to run.")

    stop_event = external_stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    allow_signal_handlers = (
        external_stop_event is None and threading.current_thread() is threading.main_thread()
    )
    if allow_signal_handlers:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: stop_event.set())

    if settings.http_gate is None:
        http_gate_size = slot_count
    else:
        http_gate_size = max(1, min(settings.http_gate, slot_count))
    http_gate = asyncio.Semaphore(http_gate_size)
    http_rate_limiter = AsyncRateLimiter(settings.http_rps)
    stats = StatsTracker()
    status_task = asyncio.create_task(
        status_reporter(stats, settings, stop_event), name="status-reporter"
    )

    workers = [
        asyncio.create_task(
            viewer_worker(
                i + 1, settings, proxy_pool, http_gate, http_rate_limiter, stop_event, stats
            ),
            name=f"viewer-{i+1}",
        )
        for i in range(slot_count)
    ]

    logger.info("%d workers ready. Press CTRL+C to stop.", len(workers))

    try:
        await stop_event.wait()
    finally:
        stop_event.set()
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        status_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await status_task
        logger.info("Bot stopped.")


def main() -> None:
    args = parse_args()
    settings = build_settings(args)
    configure_logging(settings)
    try:
        asyncio.run(run_bot(settings))
    except KeyboardInterrupt:
        print("\nCTRL+C caught, exiting...")


if __name__ == "__main__":
    main()

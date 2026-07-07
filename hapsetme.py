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
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict
import platform


if platform.system() == 'Windows':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        
       
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

try:
    import tls_client
except ImportError as exc:
    raise SystemExit(
        "❌ tls_client modülü gerekli: pip install tls-client"
    ) from exc

try:
    import aiohttp
except ImportError as exc:
    raise SystemExit(
        "❌ aiohttp modülü gerekli: pip install aiohttp"
    ) from exc

try:
    from websockets.asyncio.client import connect
    from websockets.exceptions import (
        ConnectionClosed,
        WebSocketException,
    )
except ImportError:
    try:
        from websockets import connect
        from websockets.exceptions import (
            ConnectionClosed,
            WebSocketException,
        )
    except ImportError as exc:
        raise SystemExit(
            "❌ websockets modülü gerekli: pip install websockets"
        ) from exc

try:
    from websockets.proxy import Proxy
except ImportError:
    Proxy = None


DEFAULT_CLIENT_TOKEN = "e1393935a959b4020a4491574f6490129f678acdaa92760471263db43487f823"
MAX_VIEWERS_LIMIT = 50000
VERSION = "3.0.0"
DISCORD_INVITE = "discord.gg/hapsetme"
YOUTUBE_CHANNEL = "https://www.youtube.com/@ARGOSEVENGENCX"


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[35m'
    WHITE = '\033[37m'
    BLACK = '\033[30m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
  
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    @staticmethod
    def rgb(r: int, g: int, b: int) -> str:
        return f'\033[38;2;{r};{g};{b}m'
    
    @staticmethod
    def rainbow_text(text: str, offset: int = 0) -> str:
        result = []
        for i, char in enumerate(text):
            if char.isspace():
                result.append(char)
                continue
            hue = ((i + offset) * 15) % 360
            r, g, b = Colors._hsl_to_rgb(hue / 360.0, 1.0, 0.6)
            result.append(f'{Colors.rgb(r, g, b)}{char}')
        return ''.join(result) + Colors.END
    
    @staticmethod
    def _hsl_to_rgb(h: float, s: float, l: float) -> tuple:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        
        if s == 0:
            r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return int(r * 255), int(g * 255), int(b * 255)
    
    @staticmethod
    def hyperlink(url: str, text: str) -> str:
        return f'\033]8;;{url}\033\\{text}\033]8;;\033\\'


ASCII_LOGO = (
    f"{Colors.MAGENTA}\n"
    "    ██╗  ██╗██╗ ██████╗██╗  ██╗    ██╗   ██╗██╗███████╗██╗    ██╗\n"
    "    ██║ ██╔╝██║██╔════╝██║ ██╔╝    ██║   ██║██║██╔════╝██║    ██║\n"
    "    █████╔╝ ██║██║     █████╔╝     ██║   ██║██║█████╗  ██║ █╗ ██║\n"
    "    ██╔═██╗ ██║██║     ██╔═██╗     ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║\n"
    "    ██║  ██╗██║╚██████╗██║  ██╗     ╚████╔╝ ██║███████╗╚███╔███╔╝\n"
    f"    ╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝      ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝\n{Colors.END}\n"
    f"{Colors.RED}\n"
    "        ██╗  ██╗ █████╗ ██████╗ ███████╗███████╗████████╗███╗   ███╗███████╗\n"
    "        ██║  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝╚══██╔══╝████╗ ████║██╔════╝\n"
    "        ███████║███████║██████╔╝███████╗█████╗     ██║   ██╔████╔██║█████╗  \n"
    "        ██╔══██║██╔══██║██╔═══╝ ╚════██║██╔══╝     ██║   ██║╚██╔╝██║██╔══╝  \n"
    "        ██║  ██║██║  ██║██║     ███████║███████╗   ██║   ██║ ╚═╝ ██║███████╗\n"
    f"        ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚══════╝\n{Colors.END}\n"
    f"{Colors.YELLOW}                    [ discord.gg/hapsetme ]{Colors.END}\n"
)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    clear_screen()
    try:
        print(ASCII_LOGO)
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}")
        print(f"{Colors.MAGENTA}   💬 Discord:{Colors.END} {Colors.CYAN}{DISCORD_INVITE}{Colors.END}")
        print(f"{Colors.RED}   🎥 YouTube:{Colors.END} {Colors.CYAN}youtube.com/@ARGOSEVENGENCXD{Colors.END}")
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}")
    except UnicodeEncodeError:
        
        print("\n" + "~"*60)
        print("  KICK BOT v" + VERSION + " - OZGURLUK MODU")
        print("  BY WITCH - HAPSETME")
        print("~"*60 + "\n")
    
    try:
        print(f"\n{Colors.CYAN}>> Sistem: {platform.system()} {platform.release()}{Colors.END}")
        print(f"{Colors.CYAN}>> Python: 3.12.6{Colors.END}")
        print(f"{Colors.CYAN}>> Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")
    except UnicodeEncodeError:
        
        print(f"\n{Colors.CYAN}Sistem: {platform.system()} {platform.release()}{Colors.END}")
        print(f"{Colors.CYAN}Python: 3.12.6{Colors.END}")
        print(f"{Colors.CYAN}Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")


class ConnectionState(Enum):
    
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    STOPPED = "stopped"
    
    def color(self) -> str:
        
        colors = {
            ConnectionState.INITIALIZING: Colors.BLUE,
            ConnectionState.CONNECTING: Colors.YELLOW,
            ConnectionState.CONNECTED: Colors.GREEN,
            ConnectionState.RECONNECTING: Colors.MAGENTA,
            ConnectionState.FAILED: Colors.RED,
            ConnectionState.STOPPED: Colors.WHITE,
        }
        return colors.get(self, Colors.END)


class ProxyType(Enum):
    
    HTTP = "http"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    
    def icon(self) -> str:
        
        icons = {
            ProxyType.HTTP: "🌐",
            ProxyType.SOCKS4: "🧦",
            ProxyType.SOCKS5: "🧦",
        }
        return icons.get(self, "🔌")


@dataclass
class ProxyMetrics:
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_response_time: float = 0.0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0


@dataclass
class ProxyEntry:
    
    raw: str
    ip: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: ProxyType = ProxyType.HTTP
    country: Optional[str] = None
    city: Optional[str] = None
    is_anonymous: bool = True
    metrics: ProxyMetrics = field(default_factory=ProxyMetrics)
    is_active: bool = True
    cooldown_until: Optional[datetime] = None
    
    @property
    def http_url(self) -> str:
        
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"http://{self.ip}:{self.port}"
    
    @property
    def ws_proxy(self) -> Optional["Proxy"]:
       
        if Proxy is not None:
            try:
                return Proxy.from_url(self.http_url)
            except Exception:
                return None
        return None
    
    @property
    def label(self) -> str:
        
        base = f"{self.ip}:{self.port}"
        if self.country:
            base = f"{base} [{self.country}]"
        return base
    
    @property
    def display(self) -> str:
        
        status = "🟢" if self.is_active and not self.is_on_cooldown() else "🔴"
        success_rate = f"{self.success_rate:.1f}%"
        return f"{status} {self.proxy_type.icon()} {self.ip}:{self.port} [{success_rate}]"
    
    @property
    def success_rate(self) -> float:
        
        if self.metrics.total_requests == 0:
            return 100.0
        return (self.metrics.successful_requests / self.metrics.total_requests) * 100
    
    def is_on_cooldown(self) -> bool:
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True
        return False


@dataclass
class ConnectionMetrics:
    
    connection_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    reconnects: int = 0
    errors: List[Tuple[datetime, str]] = field(default_factory=list)
    state: ConnectionState = ConnectionState.INITIALIZING
    
    @property
    def duration(self) -> Optional[timedelta]:
        
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def display_state(self) -> str:
        
        return f"{self.state.color()}{self.state.value}{Colors.END}"


@dataclass
class StreamInfo:
    
    channel_id: int
    channel_name: str
    stream_title: str
    streamer_name: str
    category: str
    tags: List[str]
    viewer_count: int
    started_at: datetime
    quality_options: List[str]
    playback_url: str


@dataclass
class BotStats:
    
    start_time: datetime = field(default_factory=datetime.now)
    total_connections: int = 0
    active_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_retries: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    connection_history: List[ConnectionMetrics] = field(default_factory=list)
    
    @property
    def uptime(self) -> timedelta:
        
        return datetime.now() - self.start_time
    
    @property
    def uptime_str(self) -> str:
        seconds = int(self.uptime.total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    @property
    def success_rate(self) -> float:
        
        if self.total_connections == 0:
            return 0.0
        return (self.successful_connections / self.total_connections) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            "uptime_seconds": self.uptime.total_seconds(),
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "success_rate": self.success_rate,
            "total_retries": self.total_retries,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": self.total_messages_received,
            "errors_by_type": dict(self.errors_by_type)
        }


class ColoredFormatter(logging.Formatter):
    
    
    COLORS = {
        'DEBUG': Colors.CYAN,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.MAGENTA + Colors.BOLD,
    }
    
    ICONS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🔥',
    }
    
    def format(self, record):
        log_message = super().format(record)
        color = self.COLORS.get(record.levelname, '')
        icon = self.ICONS.get(record.levelname, '')
        return f"{color}{icon} {log_message}{Colors.END}"


class Spinner:
    
    
    def __init__(self, message: str = "İşlem devam ediyor"):
        self.message = message
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.running = False
        self.task = None
    
    async def start(self):
        
        self.running = True
        self.task = asyncio.create_task(self._spin())
    
    async def _spin(self):
        
        i = 0
        while self.running:
            print(f'\r{Colors.CYAN}{self.spinner_chars[i % len(self.spinner_chars)]}{Colors.END} {self.message}', end='', flush=True)
            i += 1
            await asyncio.sleep(0.1)
        print('\r' + ' ' * (len(self.message) + 10), end='\r', flush=True)
    
    async def stop(self):
        
        self.running = False
        if self.task:
            await self.task


class ProgressBar:
    
    
    def __init__(self, total: int, width: int = 40, prefix: str = ''):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
    
    def update(self, n: int = 1):
        
        self.current = min(self.current + n, self.total)
        self._draw()
    
    def _draw(self):
        
        percent = self.current / self.total
        filled = int(self.width * percent)
        bar = '█' * filled + '░' * (self.width - filled)
        
        color = Colors.GREEN
        if percent < 0.3:
            color = Colors.RED
        elif percent < 0.6:
            color = Colors.YELLOW
        
        print(f'\r{self.prefix} [{color}{bar}{Colors.END}] {self.current}/{self.total} (%{percent*100:.1f})', end='', flush=True)
        
        if self.current >= self.total:
            print()


def setup_logging(
    verbose: bool = False,
    log_file: Optional[str] = None,
    json_log: Optional[str] = None,
    queue: Optional[Queue] = None
) -> None:
    
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    
    logger.handlers.clear()
    
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_formatter = ColoredFormatter(
        '%(asctime)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    
    if json_log:
        json_handler = JSONFileHandler(json_log)
        json_handler.setLevel(logging.INFO)
        logger.addHandler(json_handler)
    
    
    if queue:
        queue_handler = QueueHandler(queue)
        queue_handler.setLevel(logging.INFO)
        queue_formatter = logging.Formatter('%(asctime)s | %(message)s')
        queue_handler.setFormatter(queue_formatter)
        logger.addHandler(queue_handler)


class JSONFileHandler(logging.Handler):
   
    
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self._ensure_file_exists()
        
    def _ensure_file_exists(self):
        
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno
            }
            
           
            with open(self.filename, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            
            logs.append(log_entry)
            
           
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception:
            pass


class QueueHandler(logging.Handler):
    
    
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.queue.put_nowait(msg)
        except Exception:
            pass


class UserAgentManager:
    
    BROWSERS = {
        'chrome': {
            'templates': [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36",
            ],
            'icon': '🌐'
        },
        'firefox': {
            'templates': [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{version}) Gecko/20100101 Firefox/{version}",
                "Mozilla/5.0 (X11; Linux i686; rv:{version}) Gecko/20100101 Firefox/{version}",
            ],
            'icon': '🦊'
        },
        'safari': {
            'templates': [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{version} Safari/605.1.15",
            ],
            'icon': '🧭'
        },
        'edge': {
            'templates': [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36 Edg/{edge_version}",
            ],
            'icon': '🌍'
        }
    }
    
    def __init__(self, custom_file: Optional[str] = None):
        self.agents: List[str] = []
        self.custom_agents: List[str] = []
        self.load_agents(custom_file)
        self._lock = asyncio.Lock()
        
    def load_agents(self, custom_file: Optional[str] = None):
        if custom_file and Path(custom_file).exists():
            with open(custom_file, 'r', encoding='utf-8') as f:
                self.custom_agents = [line.strip() for line in f if line.strip()]
            logging.info(f"{Colors.GREEN}✅ {len(self.custom_agents)} custom User-Agent yüklendi{Colors.END}")
        
        self._generate_modern_agents()
        
    def _generate_modern_agents(self, count: int = 100):
        agents = []
        
        for _ in range(count):
            browser = random.choice(list(self.BROWSERS.keys()))
            data = self.BROWSERS[browser]
            template = random.choice(data['templates'])
            
            if browser == 'chrome':
                version = f"{random.randint(120, 130)}.0.{random.randint(6000, 6500)}.{random.randint(100, 200)}"
                agents.append(template.format(version=version))
            elif browser == 'firefox':
                version = f"{random.randint(110, 125)}.0"
                agents.append(template.format(version=version))
            elif browser == 'safari':
                version = f"{random.randint(15, 17)}.{random.randint(0, 5)}"
                agents.append(template.format(version=version))
            elif browser == 'edge':
                chrome_version = f"{random.randint(120, 130)}.0.{random.randint(6000, 6500)}.{random.randint(100, 200)}"
                edge_version = f"{random.randint(115, 125)}.0.{random.randint(1800, 1900)}.{random.randint(50, 100)}"
                agents.append(template.format(chrome_version=chrome_version, edge_version=edge_version))
        
        self.agents = agents + self.custom_agents
        logging.info(f"{Colors.GREEN}✅ Toplam {len(self.agents)} User-Agent hazır{Colors.END}")
    
    async def get_random(self) -> str:
        async with self._lock:
            return random.choice(self.agents) if self.agents else generate_user_agent()
    
    async def get_rotated(self, count: int) -> List[str]:
        async with self._lock:
            if len(self.agents) < count:
                return random.choices(self.agents, k=count)
            return random.sample(self.agents, count)


def generate_user_agent() -> str:
    chrome_version = f"{random.randint(120, 130)}.0.{random.randint(6000, 6500)}.{random.randint(100, 200)}"
    platforms = [
        f"Windows NT {random.choice(['10.0', '11.0'])}; Win64; x64",
        "Macintosh; Intel Mac OS X 10_15_7",
        "X11; Linux x86_64",
        "iPhone; CPU iPhone OS 17_{} like Mac OS X".format(random.randint(0, 5)),
    ]
    platform = random.choice(platforms)
    return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"


class ProxyPool:
    
    
    def __init__(
        self,
        proxy_file: Optional[str] = None,
        cooldown: float = 45.0,
        max_failures: int = 3,
        test_timeout: float = 5.0
    ):
        self.cooldown = max(0.0, cooldown)
        self.max_failures = max_failures
        self.test_timeout = test_timeout
        self.proxies: List[ProxyEntry] = []
        self.proxy_file_path: Optional[str] = None
        self._lock = asyncio.Lock()
        self._healthy_proxies: Set[str] = set()
        self._dead_proxies: Set[str] = set()
        
        if proxy_file:
            self.load_from_file(proxy_file)
        else:
            default_files = ["proxy.txt", "proxies.txt", "proxy_list.txt"]
            found = False
            for default_file in default_files:
                if os.path.exists(default_file):
                    logging.info(f"{Colors.GREEN}✅ Proxy dosyası otomatik bulundu: {default_file}{Colors.END}")
                    self.load_from_file(default_file)
                    found = True
                    break
            
            if not found:
                logging.info(f"{Colors.YELLOW}ℹ️ Proxy dosyası belirtilmedi, proxysiz mod aktif{Colors.END}")
    
    def load_from_file(self, path: str) -> None:
        if not os.path.exists(path):
            logging.warning(f"{Colors.YELLOW}⚠️ Proxy dosyası bulunamadı: {path}, proxysiz mod aktif{Colors.END}")
            return
        
        self.proxy_file_path = path  # Dosya yolunu sakla
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        valid_count = 0
        invalid_count = 0
        
        for line in lines:
            entry = self._parse_proxy_line(line)
            if entry:
                self.proxies.append(entry)
                valid_count += 1
            else:
                invalid_count += 1
        
        if valid_count > 0:
            logging.info(f"{Colors.GREEN}✅ {valid_count} geçerli proxy yüklendi{Colors.END}")
        if invalid_count > 0:
            logging.warning(f"{Colors.YELLOW}⚠️ {invalid_count} geçersiz proxy satırı atlandı{Colors.END}")
        
        if valid_count == 0:
            logging.warning(f"{Colors.YELLOW}⚠️ Hiç geçerli proxy bulunamadı, proxysiz mod çalışacak{Colors.END}")
    
    def _parse_proxy_line(self, line: str) -> Optional[ProxyEntry]:
        try:
            proxy_type = ProxyType.HTTP
            username = None
            password = None
            ip = None
            port = None
            
           
            if line.startswith(('http://', 'socks4://', 'socks5://')):
                if line.startswith('socks4://'):
                    proxy_type = ProxyType.SOCKS4
                    line = line[9:]
                elif line.startswith('socks5://'):
                    proxy_type = ProxyType.SOCKS5
                    line = line[10:]
                else:
                    line = line[7:]  # http://
            
            
            if '@' in line:
                auth, address = line.split('@', 1)
                if ':' in auth:
                    username, password = auth.split(':', 1)
                else:
                    username = auth
                    password = ''
            else:
                address = line
            
           
            if ':' in address:
                ip, port_str = address.split(':', 1)
                port = int(port_str)
            else:
                return None
            
            return ProxyEntry(
                raw=line,
                ip=ip,
                port=port,
                username=username,
                password=password,
                proxy_type=proxy_type
            )
            
        except Exception as e:
            logging.debug(f"Proxy parse hatası: {line} -> {e}")
            return None
    
    async def get_proxy(self, strategy: str = 'smart') -> Optional[ProxyEntry]:
        async with self._lock:
            if not self.proxies:
                return None
            
            now = datetime.now()
            available = [
                p for p in self.proxies
                if p.is_active
                and not p.is_on_cooldown()
                and p.metrics.consecutive_failures < self.max_failures
            ]
            
            if not available:
                logging.debug(f"{Colors.YELLOW}⚠️ Tüm proxy'ler kullanılamaz durumda, proxysiz devam ediliyor{Colors.END}")
                return None
            
            if strategy == 'round_robin':
                proxy = available[len(self._healthy_proxies) % len(available)]
            elif strategy == 'smart':
                def score(p: ProxyEntry) -> float:
                    success_score = p.success_rate / 100
                    usage_score = 1.0 / (p.metrics.total_requests + 1)
                    return success_score * 0.7 + usage_score * 0.3
                
                proxy = max(available, key=score)
            else:
                proxy = random.choice(available)
            
            proxy.metrics.total_requests += 1
            proxy.metrics.last_used = now
            
            return proxy
    
    async def mark_success(self, proxy: Optional[ProxyEntry]):
        
        if not proxy:
            return
        
        async with self._lock:
            proxy.metrics.successful_requests += 1
            proxy.metrics.consecutive_failures = 0
            proxy.cooldown_until = None
            self._healthy_proxies.add(proxy.raw)
            self._dead_proxies.discard(proxy.raw)
    
    async def mark_failure(
        self,
        proxy: Optional[ProxyEntry],
        error: Optional[str] = None
    ):
        
        if not proxy:
            return
        
        async with self._lock:
            proxy.metrics.failed_requests += 1
            proxy.metrics.consecutive_failures += 1
            proxy.metrics.last_error = error
            
            if proxy.metrics.consecutive_failures >= self.max_failures:
                cooldown_time = self.cooldown * (2 ** (proxy.metrics.consecutive_failures - self.max_failures))
                proxy.cooldown_until = datetime.now() + timedelta(seconds=cooldown_time)
                self._dead_proxies.add(proxy.raw)
                self._healthy_proxies.discard(proxy.raw)
            else:
                proxy.cooldown_until = datetime.now() + timedelta(seconds=10)
    
    def display_proxy_list(self):
        if not self.proxies:
            print(f"{Colors.YELLOW}>> Proxy listesi boş, direkt bağlantı kullanılacak{Colors.END}")
            return
        
        working = len([p for p in self.proxies if not p.is_on_cooldown() and p.metrics.consecutive_failures < self.max_failures])
        on_cooldown = len([p for p in self.proxies if p.is_on_cooldown()])
        dead = len([p for p in self.proxies if p.metrics.consecutive_failures >= self.max_failures])
        
        print(f"\n{Colors.CYAN}>> PROXY DURUMU ({len(self.proxies)} toplam){Colors.END}")
        print(f"{Colors.WHITE}{'~'*60}{Colors.END}")
        print(f"{Colors.GREEN}✅ Çalışan: {working}{Colors.END} | {Colors.YELLOW}⏳ Cooldown: {on_cooldown}{Colors.END} | {Colors.RED}❌ Ölü: {dead}{Colors.END}")
        print(f"{Colors.WHITE}{'~'*60}{Colors.END}")
        
        if working == 0:
            print(f"{Colors.RED}⚠️  UYARI: Hiç çalışan proxy yok! Proxysiz mod aktif olacak.{Colors.END}")
        
        print(f"\n{Colors.CYAN}>> İLK 10 PROXY{Colors.END}")
        for i, proxy in enumerate(self.proxies[:10], 1):
            if proxy.is_on_cooldown():
                status = f"{Colors.YELLOW}[COOLDOWN]{Colors.END}"
            elif proxy.metrics.consecutive_failures >= self.max_failures:
                status = f"{Colors.RED}[ÖLÜ]{Colors.END}"
            else:
                status = f"{Colors.GREEN}[OK]{Colors.END}"
            
            print(f"{status} {i:2d}. {proxy.ip}:{proxy.port} | Başarı: %{proxy.success_rate:.1f} | İstek: {proxy.metrics.total_requests}")
        
        if len(self.proxies) > 10:
            print(f"{Colors.WHITE}... ve {len(self.proxies) - 10} proxy daha var{Colors.END}")
        print()
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total": len(self.proxies),
            "healthy": len(self._healthy_proxies),
            "dead": len(self._dead_proxies),
            "cooldown": len([p for p in self.proxies if p.is_on_cooldown()]),
            "avg_success_rate": sum(p.success_rate for p in self.proxies) / len(self.proxies) if self.proxies else 0
        }
    
    async def validate_proxies(self, max_concurrent: int = 100, verbose: bool = False) -> None:
        if not self.proxies:
            return
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.YELLOW}🔍 PROXY DOĞRULAMA{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
        
        total = len(self.proxies)
        print(f"{Colors.CYAN}📊 {total} proxy test ediliyor...{Colors.END}\n")
        
        working_proxies = []
        tested = 0
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def test_proxy_strict(proxy: ProxyEntry) -> bool:
            async with semaphore:
                try:
                    try:
                        conn = asyncio.open_connection(proxy.ip, proxy.port)
                        reader, writer = await asyncio.wait_for(conn, timeout=1.5)
                        writer.close()
                        try:
                            await writer.wait_closed()
                        except (ConnectionResetError, OSError):
                            pass
                    except:
                        return False
                    
                    try:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                'http://www.google.com',
                                proxy=proxy.http_url,
                                timeout=aiohttp.ClientTimeout(total=4),
                                ssl=False,
                                allow_redirects=False
                            ) as response:
                                if response.status in [200, 301, 302]:
                                    return True
                    except:
                        pass
                    
                    return False
                except Exception:
                    return False
        
        tasks = []
        for proxy in self.proxies:
            task = asyncio.create_task(test_proxy_strict(proxy))
            tasks.append((proxy, task))
        
        for proxy, task in tasks:
            try:
                is_working = await task
                tested += 1
                
                if is_working:
                    working_proxies.append(proxy)
                    self._healthy_proxies.add(proxy.raw)
                
                if tested % 10 == 0 or tested == total:
                    percent = (tested / total) * 100
                    print(f"\r{Colors.CYAN}🔍 İlerleme: {tested}/{total} (%{percent:.0f}) | Çalışan: {len(working_proxies)}{Colors.END}{' '*20}", end='', flush=True)
                
            except Exception:
                tested += 1
        
        print()  # Yeni satır
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}📊 SONUÇ{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.GREEN}✅ Çalışan: {len(working_proxies)}{Colors.END}")
        print(f"{Colors.RED}❌ Ölü: {total - len(working_proxies)}{Colors.END}")
        if total > 0:
            print(f"{Colors.YELLOW}📈 Başarı: %{(len(working_proxies)/total*100):.1f}{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
        
        self.proxies = working_proxies
        
        if self.proxy_file_path and working_proxies:
            try:
                with open(self.proxy_file_path, 'w', encoding='utf-8') as f:
                    f.write("# Doğrulanmış Proxy'ler (Google test)\n")
                    f.write(f"# Test: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Toplam: {len(working_proxies)}\n\n")
                    for proxy in working_proxies:
                        f.write(f"{proxy.raw}\n")
                
                print(f"{Colors.GREEN}✅ {self.proxy_file_path} güncellendi{Colors.END}\n")
            except Exception as e:
                print(f"{Colors.RED}❌ Dosya hatası: {e}{Colors.END}\n")
        
        if not working_proxies:
            print(f"{Colors.RED}⚠️  Çalışan proxy yok! Proxysiz mod aktif.{Colors.END}\n")
        
        print()  # Yeni satır
        
        dead_count = total - len(working_proxies)
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}📊 SONUÇ{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.GREEN}✅ Çalışan: {len(working_proxies)}{Colors.END}")
        print(f"{Colors.RED}❌ Ölü: {dead_count}{Colors.END}")
        if total > 0:
            print(f"{Colors.YELLOW}📈 Başarı: %{(len(working_proxies)/total*100):.1f}{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
        
        self.proxies = working_proxies
        
        if self.proxy_file_path and working_proxies:
            try:
                with open(self.proxy_file_path, 'w', encoding='utf-8') as f:
                    f.write("# Doğrulanmış Çalışan Proxy'ler\n")
                    f.write(f"# Test Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Toplam: {len(working_proxies)} çalışan proxy\n\n")
                    for proxy in working_proxies:
                        f.write(f"{proxy.raw}\n")
                
                print(f"{Colors.GREEN}✅ {self.proxy_file_path} dosyası güncellendi (sadece çalışan proxy'ler){Colors.END}\n")
            except Exception as e:
                print(f"{Colors.RED}❌ Dosya güncellenemedi: {e}{Colors.END}\n")
        
        if not working_proxies:
            print(f"{Colors.RED}⚠️  HİÇ ÇALIŞAN PROXY YOK! Proxysiz mod aktif olacak.{Colors.END}\n")


class TokenBucket:
    
    
    def __init__(self, rate: float, capacity: Optional[float] = None):
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: float = 1.0) -> bool:
       
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def acquire(self, tokens: float = 1.0):
        
        while True:
            if await self.consume(tokens):
                return
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


class AdaptiveRateLimiter:
    
    
    def __init__(self, initial_rate: float, min_rate: float = 1.0, max_rate: float = 1000.0):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.error_rate = 0.0
        self.total_requests = 0
        self.error_count = 0
        self._lock = asyncio.Lock()
        self._bucket = TokenBucket(initial_rate)
        self._last_adjustment = time.monotonic()
    
    async def acquire(self):
        
        await self._bucket.acquire()
        
        async with self._lock:
            self.total_requests += 1
            
            now = time.monotonic()
            if now - self._last_adjustment > 10:
                await self._adjust_rate()
                self._last_adjustment = now
    
    async def record_error(self):
        
        async with self._lock:
            self.error_count += 1
            self.error_rate = self.error_count / max(1, self.total_requests)
    
    async def _adjust_rate(self):
        
        if self.error_rate > 0.1:
            self.current_rate = max(self.min_rate, self.current_rate * 0.8)
            logging.debug(f"📉 Rate düşürüldü: {self.current_rate:.2f}/s (hata: %{self.error_rate:.2f})")
        elif self.error_rate < 0.01 and self.current_rate < self.max_rate:
            self.current_rate = min(self.max_rate, self.current_rate * 1.2)
            logging.debug(f"📈 Rate artırıldı: {self.current_rate:.2f}/s")
        
        self._bucket = TokenBucket(self.current_rate)


class PrioritySemaphore:
    
    
    def __init__(self, value: int = 1):
        self.value = value
        self._low_prio_queue: asyncio.Queue = asyncio.Queue()
        self._high_prio_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
    
    async def acquire(self, priority: bool = False):
        
        queue = self._high_prio_queue if priority else self._low_prio_queue
        fut = asyncio.Future()
        await queue.put(fut)
        
        async with self._lock:
            if self.value > 0 and (priority or self._high_prio_queue.empty()):
                self.value -= 1
                fut.set_result(True)
                await queue.get()
        
        return await fut
    
    def release(self):
        
        self.value += 1
        self._wakeup_next()
    
    def _wakeup_next(self):
        
        if not self._high_prio_queue.empty():
            fut = self._high_prio_queue.get_nowait()
            if not fut.done():
                self.value -= 1
                fut.set_result(True)
        elif not self._low_prio_queue.empty():
            fut = self._low_prio_queue.get_nowait()
            if not fut.done():
                self.value -= 1
                fut.set_result(True)
    
    @contextlib.asynccontextmanager
    async def guard(self, priority: bool = False):
        
        await self.acquire(priority)
        try:
            yield
        finally:
            self.release()


class StatsCollector:
    
    
    def __init__(self):
        self._stats = BotStats()
        self._lock = asyncio.Lock()
        self._listeners: List[Callable] = []
        self._snapshots: List[Dict] = []
        self._max_snapshots = 100
    
    async def record_connection_start(self) -> int:
        
        async with self._lock:
            self._stats.total_connections += 1
            self._stats.active_connections += 1
            return self._stats.total_connections
    
    async def record_connection_success(self, metrics: ConnectionMetrics):
        
        async with self._lock:
            self._stats.successful_connections += 1
            self._stats.connection_history.append(metrics)
            if len(self._stats.connection_history) > 1000:
                self._stats.connection_history = self._stats.connection_history[-1000:]
    
    async def record_connection_close(self):
        
        async with self._lock:
            self._stats.active_connections = max(0, self._stats.active_connections - 1)
    
    async def record_error(self, error_type: str):
        
        async with self._lock:
            self._stats.errors_by_type[error_type] += 1
    
    async def record_retry(self):
        
        async with self._lock:
            self._stats.total_retries += 1
    
    async def record_bytes(self, sent: int = 0, received: int = 0):
        
        async with self._lock:
            self._stats.total_bytes_sent += sent
            self._stats.total_bytes_received += received
    
    async def record_messages(self, sent: int = 0, received: int = 0):
        
        async with self._lock:
            self._stats.total_messages_sent += sent
            self._stats.total_messages_received += received
    
    async def take_snapshot(self) -> Dict:
        
        async with self._lock:
            snapshot = self._stats.to_dict()
            snapshot['timestamp'] = datetime.now().isoformat()
            
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots:]
            
            return snapshot
    
    async def get_stats(self) -> BotStats:
        
        async with self._lock:
            return self._stats
    
    def add_listener(self, callback: Callable):
        
        self._listeners.append(callback)
    
    async def notify_listeners(self):
        
        stats = await self.get_stats()
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(stats)
                else:
                    listener(stats)
            except Exception as e:
                logging.error(f"Listener hatası: {e}")


class KickAPIClient:
    
    
    def __init__(
        self,
        client_token: str,
        proxy: Optional[ProxyEntry] = None,
        timeout: int = 25
    ):
        self.client_token = client_token
        self.proxy = proxy
        self.timeout = timeout
        self.session: Optional[tls_client.Session] = None
        self._create_session()
    
    def _create_session(self):
        
        self.session = tls_client.Session(
            client_identifier=f"chrome_{random.randint(120, 130)}",
            random_tls_extension_order=True
        )
        self.session.timeout = self.timeout
        
        self.session.headers.update({
            "User-Agent": generate_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://kick.com",
            "Referer": "https://kick.com/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        
        if self.proxy:
            self.session.proxies = {
                "http": self.proxy.http_url,
                "https": self.proxy.http_url
            }
    
    async def fetch_token(self) -> str:
        
        def _fetch():
            self.session.get("https://kick.com")
            self.session.headers.update({"X-CLIENT-TOKEN": self.client_token})
            
            response = self.session.get(
                "https://websockets.kick.com/viewer/v1/token",
                timeout_seconds=self.timeout
            )
            
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Token request failed: {response.status_code}"
                )
            
            data = response.json()
            return data["data"]["token"]
        
        return await asyncio.to_thread(_fetch)
    
    async def fetch_channel_info(self, channel: str) -> StreamInfo:
        
        def _fetch():
            response = self.session.get(
                f"https://kick.com/api/v2/channels/{channel}",
                timeout_seconds=self.timeout
            )
            
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Channel request failed: {response.status_code}"
                )
            
            data = response.json()
            
            channel_id = data.get("id") or data.get("data", {}).get("id")
            if not channel_id:
                raise ValueError("Channel ID not found")
            
            return StreamInfo(
                channel_id=int(channel_id),
                channel_name=channel,
                stream_title=data.get("title", "Offline"),
                streamer_name=data.get("user", {}).get("username", channel),
                category=data.get("category", {}).get("name", "Unknown"),
                tags=data.get("tags", []),
                viewer_count=data.get("viewer_count", 0),
                started_at=datetime.fromisoformat(data.get("started_at", datetime.now().isoformat())),
                quality_options=data.get("playback_urls", []),
                playback_url=data.get("playback_url", "")
            )
        
        return await asyncio.to_thread(_fetch)
    
    def close(self):
        
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass


class WebSocketConnection:
    
    
    def __init__(
        self,
        connection_id: int,
        token: str,
        channel_id: int,
        proxy: Optional[ProxyEntry],
        user_agent: str,
        stats: StatsCollector,
        settings: 'BotSettings'
    ):
        self.id = connection_id
        self.token = token
        self.channel_id = channel_id
        self.proxy = proxy
        self.user_agent = user_agent
        self.stats = stats
        self.settings = settings
        
        self.ws: Optional[Any] = None
        self.metrics = ConnectionMetrics(
            connection_id=connection_id,
            start_time=datetime.now()
        )
        self.state = ConnectionState.INITIALIZING
        self._stop_event = asyncio.Event()
        self._reconnect_count = 0
        self._last_pong = datetime.now()
    
    @property
    def label(self) -> str:
        
        proxy_label = self.proxy.label if self.proxy else "🌐 proxyless"
        label_text = f"[{self.id:04d} | {proxy_label[:20]}]"
        return Colors.rainbow_text(label_text, offset=self.id * 10)
    
    async def connect(self) -> bool:
        
        headers = {
            "User-Agent": self.user_agent,
            "Origin": "https://kick.com",
            "Cookie": f"client_token={self.settings.client_token}",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        url = f"wss://websockets.kick.com/viewer/v1/connect?token={self.token}&EIO=4&transport=websocket"
        
        connect_kwargs = {
            "additional_headers": headers,
            "ping_interval": None,
            "open_timeout": self.settings.ws_timeout,
            "close_timeout": 20,
            "max_size": 2**20,
        }
        
        if self.proxy and self.proxy.ws_proxy:
            connect_kwargs["proxy"] = self.proxy.ws_proxy
        
        try:
            self.state = ConnectionState.CONNECTING
            self.ws = await connect(url, **connect_kwargs)
            
            handshake = json.dumps({
                "type": "channel_handshake",
                "data": {
                    "message": {
                        "channelId": self.channel_id
                    }
                }
            })
            
            await self.ws.send(handshake)
            await self.stats.record_messages(sent=1)
            
            self.state = ConnectionState.CONNECTED
            self.metrics.state = ConnectionState.CONNECTED
            
            
            success_msg = "WebSocket baglandi!"
            rainbow_msg = Colors.rainbow_text(success_msg, offset=self.id)
            logging.info(f"{self.label} {rainbow_msg}")
            
            return True
            
        except Exception as e:
            self.state = ConnectionState.FAILED
            self.metrics.errors.append((datetime.now(), str(e)))
            logging.debug(f"{self.label} {Colors.RED}❌ Bağlantı hatası: {e}{Colors.END}")
            return False
    
    async def maintain(self):
        
        iteration = 0
        
        while not self._stop_event.is_set() and self.ws:
            try:
                low, high = self.settings.keepalive_range
                delay = random.uniform(low, high)
                
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=delay
                    )
                    break
                except asyncio.TimeoutError:
                    pass
                
                if self._stop_event.is_set():
                    break
                
                iteration += 1
                
                if iteration % self.settings.ping_period == 0:
                    payload = json.dumps({"type": "ping"})
                else:
                    payload = json.dumps({
                        "type": "channel_handshake",
                        "data": {
                            "message": {
                                "channelId": self.channel_id
                            }
                        }
                    })
                
                await self.ws.send(payload)
                await self.stats.record_messages(sent=1)
                self.metrics.messages_sent += 1
                
                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(),
                        timeout=self.settings.read_timeout
                    )
                    await self.stats.record_messages(received=1)
                    await self.stats.record_bytes(received=len(message))
                    self.metrics.messages_received += 1
                    self.metrics.bytes_received += len(message)
                    
                    if message and 'pong' in str(message).lower():
                        self._last_pong = datetime.now()
                        
                except asyncio.TimeoutError:
                    continue
                    
            except ConnectionClosed:
                logging.debug(f"{self.label} {Colors.YELLOW}⚠️ Bağlantı kapandı{Colors.END}")
                break
                
            except Exception as e:
                logging.debug(f"{self.label} {Colors.RED}❌ Mesaj hatası: {e}{Colors.END}")
                self.metrics.errors.append((datetime.now(), str(e)))
                break
    
    async def stop(self):
        
        self._stop_event.set()
        self.state = ConnectionState.STOPPED
        self.metrics.state = ConnectionState.STOPPED
        self.metrics.end_time = datetime.now()
        
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.close(), timeout=1.0)
            except (asyncio.TimeoutError, Exception):
                pass
        
        await self.stats.record_connection_close()
    
    async def run(self) -> bool:
       
        await self.stats.record_connection_start()
        
        try:
            if await self.connect():
                await self.stats.record_connection_success(self.metrics)
                await self.maintain()
                return True
        except Exception as e:
            logging.error(f"{self.label} {Colors.RED}❌ Çalışma hatası: {e}{Colors.END}")
            self.metrics.errors.append((datetime.now(), str(e)))
            await self.stats.record_error(type(e).__name__)
        
        return False


class ViewerWorker:
    
    
    def __init__(
        self,
        worker_id: int,
        channel: str,
        settings: 'BotSettings',
        proxy_pool: ProxyPool,
        http_gate: PrioritySemaphore,
        http_limiter: AdaptiveRateLimiter,
        stats: StatsCollector,
        ua_manager: UserAgentManager
    ):
        self.id = worker_id
        self.channel = channel
        self.settings = settings
        self.proxy_pool = proxy_pool
        self.http_gate = http_gate
        self.http_limiter = http_limiter
        self.stats = stats
        self.ua_manager = ua_manager
        
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._connection: Optional[WebSocketConnection] = None
        self._retry_count = 0
        self._last_error: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        
        return self._task is not None and not self._task.done()
    
    async def _get_auth_data(self) -> Tuple[Optional[str], Optional[int]]:
        token = None
        channel_id = None
        
        try:
            await self.http_limiter.acquire()
            
            async with self.http_gate.guard(priority=True):
                proxy = await self.proxy_pool.get_proxy()
                
                client = KickAPIClient(
                    self.settings.client_token,
                    proxy,
                    self.settings.http_timeout
                )
                
                try:
                    token = await client.fetch_token()
                    stream_info = await client.fetch_channel_info(self.channel)
                    channel_id = stream_info.channel_id
                    
                    await self.proxy_pool.mark_success(proxy)
                    
                except Exception as e:
                    await self.proxy_pool.mark_failure(proxy, str(e))
                    await self.stats.record_error(type(e).__name__)
                    await self.http_limiter.record_error()
                    raise
                    
                finally:
                    client.close()
            
            self._retry_count = 0
            
        except Exception as e:
            logging.debug(f"Worker {self.id} auth hatası: {e}")
            self._last_error = str(e)
            await self.stats.record_retry()
        
        return token, channel_id
    
    async def run(self):
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(random.uniform(*self.settings.ramp_delay_range))
                
                if self._stop_event.is_set():
                    break
                
                token, channel_id = await self._get_auth_data()
                
                if not token or not channel_id:
                    await asyncio.sleep(self._get_retry_delay())
                    continue
                
                user_agent = await self.ua_manager.get_random()
                proxy = await self.proxy_pool.get_proxy()
                
                self._connection = WebSocketConnection(
                    connection_id=self.id,
                    token=token,
                    channel_id=channel_id,
                    proxy=proxy,
                    user_agent=user_agent,
                    stats=self.stats,
                    settings=self.settings
                )
                
                success = await self._connection.run()
                
                if success:
                    await self.proxy_pool.mark_success(proxy)
                else:
                    await self.proxy_pool.mark_failure(proxy, "connection_failed")
                    self._retry_count += 1
                    await self.stats.record_retry()
                    await asyncio.sleep(self._get_retry_delay())
                
            except asyncio.CancelledError:
                break
                
            except Exception as e:
                logging.error(f"Worker {self.id} beklenmeyen hata: {e}")
                self._retry_count += 1
                await self.stats.record_error(type(e).__name__)
                await asyncio.sleep(self._get_retry_delay())
    
    def _get_retry_delay(self) -> float:
        
        base = random.uniform(*self.settings.retry_delay_range)
        multiplier = min(2 ** self._retry_count, 60)
        return base * multiplier
    
    async def start(self):
        
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name=f"worker-{self.id}")
    
    async def stop(self):
        
        self._stop_event.set()
        
       
        if self._connection:
            try:
                await asyncio.wait_for(self._connection.stop(), timeout=2.0)
            except asyncio.TimeoutError:
                logging.debug(f"Worker {self.id} connection stop timeout")
        
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


@dataclass
class BotSettings:
    
    channel: str
    viewer_goal: int
    max_concurrent: Optional[int] = None
    proxy_file: Optional[str] = None
    client_token: str = DEFAULT_CLIENT_TOKEN
    proxy_permits: int = 10
    keepalive_range: Tuple[float, float] = (13.0, 21.0)
    ping_period: int = 6
    retry_delay_range: Tuple[float, float] = (2.0, 6.0)
    ramp_delay_range: Tuple[float, float] = (0.15, 0.75)
    status_interval: float = 30.0
    proxy_cooldown: float = 45.0
    http_timeout: int = 25
    ws_timeout: int = 30
    read_timeout: float = 10.0
    http_gate: Optional[int] = None
    http_rps: Optional[float] = 120.0
    log_file: Optional[str] = None
    json_log: Optional[str] = None
    verbose: bool = False
    auto_start: bool = False
    user_agent_file: Optional[str] = None
    max_retries: int = 10
    
    def effective_concurrency(self, proxy_count: int) -> int:
        requested = self.max_concurrent or self.viewer_goal
        return max(1, min(requested, MAX_VIEWERS_LIMIT))
    
    def display(self):
        
        print(f"\n{Colors.CYAN}⚙️  BOT YAPILANDIRMASI{Colors.END}")
        print(f"{Colors.WHITE}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}📺 Kanal:{Colors.END} {self.channel}")
        print(f"{Colors.GREEN}🎯 Hedef:{Colors.END} {self.viewer_goal} izleyici")
        print(f"{Colors.GREEN}🌐 Proxy:{Colors.END} {self.proxy_file or 'Belirtilmedi (proxysiz)'}")
        print(f"{Colors.GREEN}🔄 Keepalive:{Colors.END} {self.keepalive_range[0]}-{self.keepalive_range[1]} sn")
        print(f"{Colors.GREEN}⏱️  Retry:{Colors.END} {self.retry_delay_range[0]}-{self.retry_delay_range[1]} sn")
        print(f"{Colors.GREEN}🚦 HTTP Gate:{Colors.END} {self.http_gate or 'Otomatik'}")
        print(f"{Colors.GREEN}📊 HTTP RPS:{Colors.END} {self.http_rps or 'Limitsiz'}")
        print(f"{Colors.WHITE}{'='*60}{Colors.END}\n")


class KickViewerBot:
    
    def __init__(self, settings: BotSettings):
        self.settings = settings
        self.proxy_pool = ProxyPool(settings.proxy_file, settings.proxy_cooldown)
        self.stats = StatsCollector()
        self.ua_manager = UserAgentManager(settings.user_agent_file)
        
        http_gate_size = self._calculate_http_gate_size()
        self.http_gate = PrioritySemaphore(http_gate_size)
        self.http_limiter = AdaptiveRateLimiter(
            initial_rate=settings.http_rps or 100.0,
            min_rate=10.0,
            max_rate=200.0
        )
        
        self.workers: List[ViewerWorker] = []
        self._stop_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task] = None
        self._shutdown_lock = threading.Lock()
        self._shutdown_initiated = False
    
    def _calculate_http_gate_size(self) -> int:
        
        if self.settings.http_gate is not None:
            return max(1, self.settings.http_gate)
        
        base = self.settings.viewer_goal // 75
        return min(self.settings.viewer_goal, max(50, base))
    
    async def initialize(self):
        print_banner()
        
        proxy_count = self.proxy_pool.stats['total']
        if proxy_count > 0:
            await self.proxy_pool.validate_proxies(max_concurrent=50)
            proxy_count = self.proxy_pool.stats['total']
        
        worker_count = self.settings.effective_concurrency(proxy_count)
        
        print(f"{Colors.CYAN}🔄 {worker_count:,} worker oluşturuluyor...{Colors.END}")
        
        for i in range(worker_count):
            worker = ViewerWorker(
                worker_id=i + 1,
                channel=self.settings.channel,
                settings=self.settings,
                proxy_pool=self.proxy_pool,
                http_gate=self.http_gate,
                http_limiter=self.http_limiter,
                stats=self.stats,
                ua_manager=self.ua_manager
            )
            self.workers.append(worker)
        
        print(f"{Colors.GREEN}✅ {worker_count:,} worker oluşturuldu{Colors.END}")
        
        print(f"\n{Colors.CYAN}╔{'═'*68}╗{Colors.END}")
        print(f"{Colors.CYAN}║{Colors.END} {Colors.rainbow_text('⚙️  YAPILANDIRMA', offset=0)}{' '*50}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}╠{'═'*68}╣{Colors.END}")
        
        kanal_line = f"{Colors.rainbow_text('📺 Kanal:', offset=10)} {Colors.GREEN}{self.settings.channel}{Colors.END}"
        print(f"{Colors.CYAN}║{Colors.END} {kanal_line}{' '*(57-len(self.settings.channel))}{Colors.CYAN}║{Colors.END}")
        
        hedef_line = f"{Colors.rainbow_text('� Hedef:', offset=30)} {Colors.GREEN}{self.settings.viewer_goal:,} izleyici{Colors.END}"
        print(f"{Colors.CYAN}║{Colors.END} {hedef_line}{' '*(50-len(f'{self.settings.viewer_goal:,}'))}{Colors.CYAN}║{Colors.END}")
        
        proxy_text = f"{proxy_count} çalışan proxy" if proxy_count > 0 else "Proxysiz mod"
        proxy_line = f"{Colors.rainbow_text('🌐 Proxy:', offset=50)} {Colors.YELLOW}{proxy_text}{Colors.END}"
        print(f"{Colors.CYAN}║{Colors.END} {proxy_line}{' '*(56-len(proxy_text))}{Colors.CYAN}║{Colors.END}")
        
        keepalive_line = f"{Colors.rainbow_text('� Keepalive:', offset=70)} {Colors.CYAN}{self.settings.keepalive_range[0]}-{self.settings.keepalive_range[1]} sn{Colors.END}"
        print(f"{Colors.CYAN}║{Colors.END} {keepalive_line}{' '*45}{Colors.CYAN}║{Colors.END}")
        
        gate_line = f"{Colors.rainbow_text('🚦 HTTP Gate:', offset=90)} {Colors.CYAN}{self.http_gate.value}{Colors.END}"
        print(f"{Colors.CYAN}║{Colors.END} {gate_line}{' '*(53-len(str(self.http_gate.value)))}{Colors.CYAN}║{Colors.END}")
        
        print(f"{Colors.CYAN}╚{'═'*68}╝{Colors.END}\n")
        
        if proxy_count > 0:
            self.proxy_pool.display_proxy_list()
        
        print(f"\n{Colors.GREEN}✅ {worker_count:,} worker hazır (Hedef: {self.settings.viewer_goal:,}){Colors.END}")
        if proxy_count > 0:
            working_proxies = len([p for p in self.proxy_pool.proxies if not p.is_on_cooldown() and p.metrics.consecutive_failures < self.proxy_pool.max_failures])
            print(f"{Colors.CYAN}ℹ️  {working_proxies} doğrulanmış proxy ile başlanacak{Colors.END}")
        else:
            print(f"{Colors.YELLOW}⚠️  Proxysiz mod - Tüm bağlantılar direkt yapılacak{Colors.END}")
        print()
    
    async def _get_ip_info(self) -> dict:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://ipapi.co/json/', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ip = data.get('ip', 'Bilinmiyor')
                        city = data.get('city', '')
                        country = data.get('country_name', '')
                        location = f"{city}, {country}" if city and country else country or 'Bilinmiyor'
                        return {'ip': ip, 'location': location}
        except Exception:
            pass
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org?format=json', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {'ip': data.get('ip', 'Bilinmiyor'), 'location': 'Bilinmiyor'}
        except Exception:
            pass
        
        return {'ip': 'Bilinmiyor', 'location': 'Bilinmiyor'}
    
    async def monitor_stats(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(self.settings.status_interval)
            
            stats = await self.stats.get_stats()
            proxy_stats = self.proxy_pool.stats
            
            print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.WHITE}📊 CANLI İSTATİSTİKLER{Colors.END}")
            print(f"{Colors.CYAN}{'='*70}{Colors.END}")
            
            print(f"{Colors.YELLOW}⏱️  Çalışma:{Colors.END} {stats.uptime_str}")
            
            active_color = Colors.GREEN if stats.active_connections > 0 else Colors.RED
            print(f"{active_color}🔗 Aktif:{Colors.END} {stats.active_connections}/{len(self.workers)}")
            print(f"{Colors.GREEN}✅ Başarılı:{Colors.END} {stats.successful_connections}")
            print(f"{Colors.RED}❌ Başarısız:{Colors.END} {stats.failed_connections}")
            print(f"{Colors.MAGENTA}🔄 Retry:{Colors.END} {stats.total_retries}")
            
            rate_color = Colors.GREEN if stats.success_rate > 80 else Colors.YELLOW if stats.success_rate > 50 else Colors.RED
            print(f"{rate_color}📈 Başarı Oranı:{Colors.END} %{stats.success_rate:.1f}")
            
            print(f"{Colors.BLUE}📥 Transfer:{Colors.END} ↓{stats.total_bytes_received/1024:.1f}KB ↑{stats.total_bytes_sent/1024:.1f}KB")
            
            if proxy_stats['total'] > 0:
                healthy_color = Colors.GREEN if proxy_stats['healthy'] > 0 else Colors.RED
                dead_color = Colors.RED if proxy_stats['dead'] > 0 else Colors.GREEN
                print(f"{healthy_color}🌐 Sağlıklı Proxy:{Colors.END} {proxy_stats['healthy']} "
                      f"{dead_color}Ölü:{Colors.END} {proxy_stats['dead']} "
                      f"{Colors.YELLOW}Cooldown:{Colors.END} {proxy_stats['cooldown']}")
            
            if stats.errors_by_type:
                print(f"\n{Colors.RED}⚠️  SON HATALAR:{Colors.END}")
                top_errors = sorted(stats.errors_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
                for error, count in top_errors:
                    print(f"  {Colors.RED}•{Colors.END} {error}: {count}")
            
            print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
            
            await self.stats.notify_listeners()
    
    async def run(self):
        
        await self.initialize()
        
        if not self.settings.auto_start:
            print(f"\n{Colors.YELLOW}🚀 Başlatmak için ENTER'a basın (iptal için CTRL+C)...{Colors.END}")
            input()
            print()
        
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            
            with self._shutdown_lock:
                if not self._shutdown_initiated:
                    self._shutdown_initiated = True
                    loop.call_soon_threadsafe(self._stop_event.set)
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                signal.signal(sig, lambda s, f: signal_handler())
        
        self._monitor_task = asyncio.create_task(self.monitor_stats())
        
        logging.info(f"{Colors.GREEN}🚀 {len(self.workers)} worker başlatılıyor...{Colors.END}")
        
        for worker in self.workers:
            worker._task = asyncio.create_task(worker.run(), name=f"worker-{worker.id}")
        
        logging.info(f"{Colors.GREEN}✅ Tüm worker'lar aktif. Çıkmak için CTRL+C{Colors.END}\n")
        
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        
        if self._shutdown_initiated:
            logging.info(f"{Colors.YELLOW}>> Kapatiliyor, lutfen bekleyin...{Colors.END}")
        
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        
        logging.info(f"{Colors.YELLOW}>> {len(self.workers)} isci durduruluyor...{Colors.END}")
        
        stop_tasks = [worker.stop() for worker in self.workers]
        try:
            await asyncio.wait_for(
                asyncio.gather(*stop_tasks, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logging.warning(f"{Colors.RED}>> Bazi isciler zaman asimina ugradi, zorla kapatiliyor...{Colors.END}")
            
            for worker in self.workers:
                if worker._task and not worker._task.done():
                    worker._task.cancel()
        
        stats = await self.stats.get_stats()
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}📊 FİNAL İSTATİSTİKLERİ{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.YELLOW}⏱️  Çalışma:{Colors.END} {stats.uptime_str}")
        print(f"{Colors.GREEN}✅ Başarılı Bağlantı:{Colors.END} {stats.successful_connections}")
        print(f"{Colors.RED}❌ Başarısız Bağlantı:{Colors.END} {stats.failed_connections}")
        print(f"{Colors.MAGENTA}🔄 Toplam Retry:{Colors.END} {stats.total_retries}")
        print(f"{Colors.GREEN}📈 Başarı Oranı:{Colors.END} %{stats.success_rate:.1f}")
        print(f"{Colors.BLUE}📥 Toplam Transfer:{Colors.END} ↓{stats.total_bytes_received/1024:.1f}KB")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
        
        logging.info(f"{Colors.GREEN}✅ Bot durduruldu.{Colors.END}")
    
    async def stop(self):
        with self._shutdown_lock:
            if not self._shutdown_initiated:
                self._shutdown_initiated = True
                self._stop_event.set()
        await self.cleanup()


def load_config_file(path: str) -> Dict[str, Any]:
    
    config_path = Path(path)
    if not config_path.exists():
        raise SystemExit(f"❌ Konfigürasyon dosyası bulunamadı: {path}")
    
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    if not isinstance(data, dict):
        raise SystemExit("❌ Konfigürasyon dosyası JSON nesnesi olmalı")
    
    return data


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="Kick.com Gelismis Asenkron Izleyici Botu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ornek:\n"
            "  python hapsetme.py -c example -n 500\n"
            "  python hapsetme.py -c example -n 1000 -p proxies.txt\n"
        )
    )

    parser.add_argument("-c", "--channel",    type=str,   default=None,  help="Hedef Kick kanal adi")
    parser.add_argument("-n", "--viewers",    type=int,   default=None,  help="Gonderilecek izleyici sayisi")
    parser.add_argument("-p", "--proxy-file", dest="proxy_file", type=str, default=None, help="Proxy dosyasi")
    parser.add_argument("--config",           type=str,   default=None,  help="JSON config dosyasi")
    parser.add_argument("--client-token",     dest="client_token", type=str, default=None)
    parser.add_argument("--max-concurrent",   dest="max_concurrent", type=int, default=None)
    parser.add_argument("--proxy-permits",    dest="proxy_permits", type=int, default=None)
    parser.add_argument("--keepalive",        nargs=2,    type=float,    default=None)
    parser.add_argument("--ping-period",      dest="ping_period", type=int, default=None)
    parser.add_argument("--retry-delay",      dest="retry_delay", nargs=2, type=float, default=None)
    parser.add_argument("--ramp-delay",       dest="ramp_delay",  nargs=2, type=float, default=None)
    parser.add_argument("--status-interval",  dest="status_interval", type=float, default=None)
    parser.add_argument("--proxy-cooldown",   dest="proxy_cooldown", type=float, default=None)
    parser.add_argument("--http-timeout",     dest="http_timeout", type=int, default=None)
    parser.add_argument("--ws-timeout",       dest="ws_timeout",   type=int, default=None)
    parser.add_argument("--read-timeout",     dest="read_timeout", type=float, default=None)
    parser.add_argument("--http-gate",        dest="http_gate",    type=int, default=None)
    parser.add_argument("--http-rps",         dest="http_rps",     type=float, default=None)
    parser.add_argument("--log-file",         dest="log_file",     type=str, default=None)
    parser.add_argument("--json-log",         dest="json_log",     type=str, default=None)
    parser.add_argument("--user-agent-file",  dest="user_agent_file", type=str, default=None)
    parser.add_argument("--max-retries",      dest="max_retries",  type=int, default=None)
    parser.add_argument("--auto-start",       dest="auto_start",   action="store_true", default=False)
    parser.add_argument("--verbose", "-v",    action="store_true", default=False)
    parser.add_argument("--quiet",  "-q",     action="store_true", default=False)
    parser.add_argument("--validate-proxies", dest="validate_proxies", action="store_true", default=False)

    args = parser.parse_args()

    config: Dict[str, Any] = {}
    
    if args.config:
        config = load_config_file(args.config)
    
    channel = args.channel or config.get("channel")
    if not channel:
        print(f"\n{Colors.RED}")
        print(f"        ██╗  ██╗ █████╗ ██████╗ ███████╗███████╗████████╗███╗   ███╗███████╗")
        print(f"        ██║  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝╚══██╔══╝████╗ ████║██╔════╝")
        print(f"        ███████║███████║██████╔╝███████╗█████╗     ██║   ██╔████╔██║█████╗  ")
        print(f"        ██╔══██║██╔══██║██╔═══╝ ╚════██║██╔══╝     ██║   ██║╚██╔╝██║██╔══╝  ")
        print(f"        ██║  ██║██║  ██║██║     ███████║███████╗   ██║   ██║ ╚═╝ ██║███████╗")
        print(f"        ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚══════╝")
        print(f"{Colors.END}")
        
        print(f"{Colors.CYAN}        {'~'*62}{Colors.END}")
        print(f"{Colors.MAGENTA}        💬 Discord:{Colors.END} {Colors.CYAN}{DISCORD_INVITE}{Colors.END}")
        print(f"{Colors.RED}        🎥 YouTube:{Colors.END} {Colors.CYAN}youtube.com/@ARGOSEVENGENCXD{Colors.END}")
        print(f"{Colors.CYAN}        {'~'*62}{Colors.END}")
        
        print(f"\n{Colors.CYAN}{'~'*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}   📺 KANAL SEÇİMİ - HANGİ KANALA BASKIN YAPALIM?{Colors.END}")
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}\n")
        
        print(f"   {Colors.WHITE}Kick kanalı:{Colors.END} {Colors.YELLOW}(örnek: {Colors.GREEN}argoazap{Colors.YELLOW}){Colors.END}")
        print(f"   {Colors.MAGENTA}Discord için '1'{Colors.END} {Colors.WHITE}|{Colors.END} {Colors.RED}YouTube için '2'{Colors.END}")
        
        print(f"\n{Colors.RED}      ██╗  ██╗ █████╗ ██████╗ ███████╗███████╗████████╗███╗   ███╗███████╗{Colors.END}")
        print(f"{Colors.RED}      ██║  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝╚══██╔══╝████╗ ████║██╔════╝{Colors.END}")
        print(f"{Colors.RED}      ███████║███████║██████╔╝███████╗█████╗     ██║   ██╔████╔██║█████╗  {Colors.END}")
        print(f"{Colors.RED}      ██╔══██║██╔══██║██╔═══╝ ╚════██║██╔══╝     ██║   ██║╚██╔╝██║██╔══╝  {Colors.END}")
        print(f"{Colors.RED}      ██║  ██║██║  ██║██║     ███████║███████╗   ██║   ██║ ╚═╝ ██║███████╗{Colors.END}")
        print(f"{Colors.RED}      ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚══════╝{Colors.END}\n")
        
        print(f"{Colors.CYAN}      ╔{'═'*60}╗{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.BOLD}{Colors.MAGENTA}💬 DISCORD SUNUCUMUZ{Colors.END}{' '*39}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ╠{'═'*60}╣{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}1.{Colors.END} {Colors.WHITE}OSINT BOT{Colors.END} {Colors.YELLOW}(248 Milyon Veri){Colors.END}{' '*26}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}2.{Colors.END} {Colors.WHITE}Discord ID Sorgu{Colors.END}{' '*36}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}3.{Colors.END} {Colors.WHITE}SMS Bomber{Colors.END}{' '*42}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}4.{Colors.END} {Colors.WHITE}Craftrise Checker{Colors.END}{' '*35}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}5.{Colors.END} {Colors.WHITE}Roblox Hile{Colors.END}{' '*41}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}6.{Colors.END} {Colors.WHITE}Morphvox Ayar{Colors.END}{' '*39}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.GREEN}7.{Colors.END} {Colors.WHITE}Mobil Sövüş Uygulaması{Colors.END}{' '*30}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END}{' '*60}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.YELLOW}💡 Bu araçlar için Discord sunucumuza katılmanı{Colors.END}{' '*6}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ║{Colors.END} {Colors.YELLOW}   tavsiye ederiz!{Colors.END} {Colors.CYAN}→ discord.gg/hapsetme{Colors.END}{' '*16}{Colors.CYAN}║{Colors.END}")
        print(f"{Colors.CYAN}      ╚{'═'*60}╝{Colors.END}\n")
        
        while True:
            channel_input = input(f"\n   {Colors.CYAN}➤ {Colors.END}").strip().lower()
            
            if channel_input in ["1", "d", "discord"]:
                
                discord_url = f"https://{DISCORD_INVITE}"
                print(f"\n{Colors.CYAN}   >> Discord açılıyor...{Colors.END}")
                try:
                    import webbrowser
                    webbrowser.open(discord_url)
                    print(f"{Colors.GREEN}   ✓ Tarayıcıda açıldı!{Colors.END}\n")
                except Exception:
                    print(f"{Colors.YELLOW}   ⚠ Link: {discord_url}{Colors.END}\n")
                continue
            elif channel_input in ["2", "y", "youtube"]:
                
                print(f"\n{Colors.RED}   >> YouTube açılıyor...{Colors.END}")
                try:
                    import webbrowser
                    webbrowser.open(YOUTUBE_CHANNEL)
                    print(f"{Colors.GREEN}   ✓ Tarayıcıda açıldı!{Colors.END}\n")
                except Exception:
                    print(f"{Colors.YELLOW}   ⚠ Link: {YOUTUBE_CHANNEL}{Colors.END}\n")
                continue
            elif channel_input:
               
                channel = channel_input
                break
            else:
                print(f"{Colors.RED}   ❌ Kanal adı lazım kanka{Colors.END}")
        
        print(f"\n   {Colors.GREEN}✓ Hedef kilitlendi → {Colors.BOLD}{Colors.CYAN}{channel}{Colors.END}")
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}\n")
    
    if args.viewers is not None:
        viewers = args.viewers
    elif "viewers" in config:
        viewers = config["viewers"]
    else:
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}   🎯 İZLENME HEDEFİ - KAÇ KİŞİYLE BASALIM?{Colors.END}")
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}\n")
        
        print(f"   {Colors.WHITE}Kaç izlenme patlatacağız?{Colors.END}")
        print(f"   {Colors.YELLOW}💪 Cesur ol:{Colors.END} {Colors.GREEN}1000+{Colors.END} {Colors.YELLOW}|{Colors.END} {Colors.CYAN}🚀 Daha çok cesur ol:{Colors.END} {Colors.GREEN}10,000+{Colors.END} {Colors.YELLOW}|{Colors.END} {Colors.RED}🔥 Daha daha fazla:{Colors.END} {Colors.GREEN}50,000{Colors.END}")
        
        try:
            viewers = int(input(f"\n   {Colors.CYAN}➤ {Colors.END}").strip())
        except ValueError:
            raise SystemExit(f"\n{Colors.RED}   ❌ Rakam lazım kanka{Colors.END}\n")
        
        if viewers < 1:
            print(f"\n   {Colors.RED}❌ En az 1 olmalı, ciddiye al!{Colors.END}")
            viewers = 1
        elif viewers > MAX_VIEWERS_LIMIT:
            print(f"\n   {Colors.YELLOW}⚠ Çok yüksek! Maksimum {MAX_VIEWERS_LIMIT:,} olarak ayarlandı{Colors.END}")
            viewers = MAX_VIEWERS_LIMIT
        elif viewers < 100:
            print(f"\n   {Colors.YELLOW}💡 Sadece {viewers}? Daha fazla dene, {Colors.GREEN}1000+{Colors.YELLOW} öneriyoruz!{Colors.END}")
        
        print(f"\n   {Colors.GREEN}✓ Hedef kilitlendi → {Colors.BOLD}{Colors.CYAN}{viewers:,} izlenme{Colors.END} {Colors.RED}🔥{Colors.END}")
        print(f"{Colors.CYAN}{'~'*70}{Colors.END}\n")
    
    viewers = max(1, min(MAX_VIEWERS_LIMIT, int(viewers)))
    
    def pick(key: str, default: Any = None) -> Any:
        arg_value = getattr(args, key, None)
        if arg_value is not None:
            return arg_value
        return config.get(key, default)
    
    def pick_range(key: str, default: Tuple[float, float]) -> Tuple[float, float]:
        arg_value = getattr(args, key, None)
        if arg_value and len(arg_value) == 2:
            low, high = float(arg_value[0]), float(arg_value[1])
            return (low, high) if low <= high else (high, low)
        
        config_value = config.get(key)
        if config_value and len(config_value) == 2:
            low, high = float(config_value[0]), float(config_value[1])
            return (low, high) if low <= high else (high, low)
        
        return default
    
    return BotSettings(
        channel=channel,
        viewer_goal=viewers,
        max_concurrent=pick("max_concurrent"),
        proxy_file=pick("proxy_file"),
        client_token=pick("client_token", DEFAULT_CLIENT_TOKEN),
        proxy_permits=pick("proxy_permits", 10),
        keepalive_range=pick_range("keepalive", (13.0, 21.0)),
        ping_period=pick("ping_period", 6),
        retry_delay_range=pick_range("retry_delay", (2.0, 6.0)),
        ramp_delay_range=pick_range("ramp_delay", (0.15, 0.75)),
        status_interval=pick("status_interval", 30.0),
        proxy_cooldown=pick("proxy_cooldown", 45.0),
        http_timeout=pick("http_timeout", 25),
        ws_timeout=pick("ws_timeout", 30),
        read_timeout=pick("read_timeout", 10.0),
        http_gate=pick("http_gate"),
        http_rps=pick("http_rps", 120.0),
        log_file=pick("log_file"),
        json_log=pick("json_log"),
        verbose=pick("verbose", False) and not args.quiet,
        auto_start=pick("auto_start", False),
        user_agent_file=pick("user_agent_file"),
        max_retries=pick("max_retries", 10)
    )


async def async_main():
    try:
        settings = parse_args()

        setup_logging(
            verbose=settings.verbose,
            log_file=settings.log_file,
            json_log=settings.json_log
        )

        bot = KickViewerBot(settings)
        await bot.run()
        
    except KeyboardInterrupt:
        logging.info(f"{Colors.YELLOW}⚠️ CTRL+C ile durduruldu{Colors.END}")
        try:
            await bot.stop()
        except:
            pass
    except Exception as e:
        print(f"\n{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.RED}❌ KRITIK HATA{Colors.END}")
        print(f"{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.YELLOW}Hata: {e}{Colors.END}")
        print(f"{Colors.YELLOW}Tip: {type(e).__name__}{Colors.END}")
        
        import traceback
        print(f"\n{Colors.CYAN}Stack Trace:{Colors.END}")
        traceback.print_exc()
        
        print(f"\n{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.YELLOW}Lütfen bu hatayı Discord'da paylaşın: {DISCORD_INVITE}{Colors.END}")
        print(f"{Colors.RED}{'='*70}{Colors.END}\n")
        
        try:
            await bot.stop()
        except:
            pass
        
        input(f"\n{Colors.CYAN}Kapatmak için ENTER'a basın...{Colors.END}")
        sys.exit(1)


def main():
    if platform.system() == 'Windows':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            
            def console_ctrl_handler(ctrl_type):
                if ctrl_type in (0, 2):  # CTRL_C_EVENT or CTRL_CLOSE_EVENT
                    print(f"\n{Colors.YELLOW}⚠️ Kapatılıyor...{Colors.END}")
                    return True
                return False
            
            HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
            handler = HANDLER_ROUTINE(console_ctrl_handler)
            kernel32.SetConsoleCtrlHandler(handler, 1)
        except Exception as e:
            print(f"{Colors.YELLOW}[UYARI] CTRL+C handler kurulamadı: {e}{Colors.END}")
    
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ Program sonlandırıldı.{Colors.END}")
    except SystemExit as e:
        if e.code and e.code != 0:
            sys.exit(e.code)
    except Exception as e:
        print(f"\n{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.RED}❌ MAIN FONKSIYON HATASI{Colors.END}")
        print(f"{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.YELLOW}Hata: {e}{Colors.END}")
        
        import traceback
        traceback.print_exc()
        
        print(f"\n{Colors.RED}{'='*70}{Colors.END}\n")
        input(f"{Colors.CYAN}Kapatmak için ENTER'a basın...{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()

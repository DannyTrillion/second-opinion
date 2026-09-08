"""
Public Binance market-data client (no API keys, no account scope).

Design rules:
- Certificate verification is never disabled. We look for a CA bundle in this order:
  certifi (if installed), the interpreter default, then the macOS/Linux system bundle.
  If none works we fail with an actionable message.
- Every fetch is cached on disk so a decision can be replayed byte-for-byte.
- `offline=True` serves only from the cache / fixtures and never touches the network.
"""
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

HOSTS = [
    "https://data-api.binance.vision",  # public market-data mirror, no auth
    "https://api.binance.com",
    "https://api1.binance.com",
]

SYSTEM_CA_CANDIDATES = [
    "/etc/ssl/cert.pem",                       # macOS
    "/etc/ssl/certs/ca-certificates.crt",      # Debian/Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",        # RHEL/Fedora
]


def _ssl_contexts() -> List[ssl.SSLContext]:
    """Verified contexts to try, in order. Never an unverified one."""
    ctxs: List[ssl.SSLContext] = []
    try:
        import certifi  # type: ignore
        ctxs.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    ctxs.append(ssl.create_default_context())
    for path in SYSTEM_CA_CANDIDATES:
        if os.path.exists(path):
            try:
                ctxs.append(ssl.create_default_context(cafile=path))
            except Exception:
                pass
    return ctxs


class DataError(RuntimeError):
    pass


class BinancePublicData:
    def __init__(self, cache_dir: Optional[Path] = None, offline: bool = False, timeout: int = 15,
                 fixtures_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir or os.environ.get("SECOND_OPINION_CACHE", Path.home() / ".second_opinion" / "cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.timeout = timeout
        self.fixtures_dir = fixtures_dir
        self._ctxs = _ssl_contexts()
        self.last_source = "cache"

    # ------------------------------------------------------------------ http
    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        if self.offline:
            raise DataError("offline mode: refusing network call to %s" % path)
        qs = urllib.parse.urlencode(params)
        last_err: Optional[Exception] = None
        for host in HOSTS:
            url = "%s%s?%s" % (host, path, qs)
            req = urllib.request.Request(url, headers={"User-Agent": "second-opinion/0.1", "Accept": "application/json"})
            for ctx in self._ctxs:
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                        self.last_source = host
                        return json.loads(resp.read().decode("utf-8"))
                except urllib.error.URLError as e:
                    last_err = e
                    if "CERTIFICATE_VERIFY_FAILED" in str(e):
                        continue  # try the next CA bundle, never disable verification
                    break  # network/DNS problem: try next host
                except Exception as e:  # pragma: no cover
                    last_err = e
                    break
        hint = ""
        if last_err and "CERTIFICATE_VERIFY_FAILED" in str(last_err):
            hint = " (no usable CA bundle: run 'pip install certifi' or macOS 'Install Certificates.command')"
        if last_err is not None and "400" in str(last_err) and path == "/api/v3/klines":
            raise DataError("symbol %s is not a Binance spot market (HTTP 400)" % params.get("symbol"))
        raise DataError("all Binance hosts failed for %s: %s%s" % (path, last_err, hint))

    # ---------------------------------------------------------------- cache
    def _cache_path(self, name: str) -> Path:
        return self.cache_dir / name

    def _read_json(self, p: Path) -> Any:
        return json.loads(p.read_text(encoding="utf-8"))

    def _fixture(self, name: str) -> Optional[Path]:
        if self.fixtures_dir:
            p = self.fixtures_dir / name
            if p.exists():
                return p
        return None

    # ------------------------------------------------------------ endpoints
    def klines(self, symbol: str, interval: str = "1d", limit: int = 1000, max_age_s: int = 3600) -> List[list]:
        """Daily candles. Cached; refreshed when older than max_age_s unless offline."""
        name = "%s_%s.json" % (symbol.upper(), interval)
        cp = self._cache_path(name)
        if not self.offline and (not cp.exists() or time.time() - cp.stat().st_mtime > max_age_s):
            try:
                rows = self._get("/api/v3/klines", {"symbol": symbol.upper(), "interval": interval, "limit": limit})
                cp.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
                return rows
            except DataError:
                if not cp.exists() and not self._fixture(name):
                    raise
        if cp.exists():
            self.last_source = "cache"
            return self._read_json(cp)
        fx = self._fixture(name)
        if fx:
            self.last_source = "fixture"
            return self._read_json(fx)
        raise DataError("no candles for %s (offline and nothing cached)" % symbol)

    def depth(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        name = "%s_depth.json" % symbol.upper()
        if not self.offline:
            try:
                book = self._get("/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})
                self._cache_path(name).write_text(json.dumps(book, separators=(",", ":")), encoding="utf-8")
                return book
            except DataError:
                pass
        cp = self._cache_path(name)
        if cp.exists():
            self.last_source = "cache"
            return self._read_json(cp)
        fx = self._fixture(name)
        if fx:
            self.last_source = "fixture"
            return self._read_json(fx)
        raise DataError("no order book for %s" % symbol)

    def exchange_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Symbol filters (LOT_SIZE, NOTIONAL...). Returns None when the symbol is unknown."""
        name = "exchangeInfo_%s.json" % symbol.upper()
        info = None
        cp = self._cache_path(name)
        if cp.exists() and time.time() - cp.stat().st_mtime < 86400:
            info = self._read_json(cp)
        elif not self.offline:
            try:
                info = self._get("/api/v3/exchangeInfo", {"symbol": symbol.upper()})
                cp.write_text(json.dumps(info, separators=(",", ":")), encoding="utf-8")
            except DataError as e:
                if "400" in str(e):
                    return None
        if info is None:
            name = "exchangeInfo.json"
        if info is None:
            for p in (self._cache_path(name), self._fixture(name)):
                if p and p.exists():
                    info = self._read_json(p)
                    break
        if not info:
            return None
        for s in info.get("symbols", []):
            if s.get("symbol") == symbol.upper():
                return s
        return None

    def last_price(self, symbol: str) -> float:
        rows = self.klines(symbol)
        return float(rows[-1][4])

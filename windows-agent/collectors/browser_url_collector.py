from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
from urllib.parse import urlparse

from core.config_loader import agent_data_path


BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "vivaldi.exe",
    "opera.exe",
    "opera_gx.exe",
    "chromium.exe",
}


@dataclass
class BrowserUrl:
    url: str
    domain: str
    title: str | None = None


class BrowserUrlResolver:
    def __init__(self, config: dict):
        self.config = config
        self.cache_dir = agent_data_path(config, "browser_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_seen_by_process: dict[str, BrowserUrl] = {}
        self.last_scan_at: dict[str, float] = {}
        self.last_title_by_process: dict[str, str] = {}

    def resolve(self, process_name: str, window_title: str) -> BrowserUrl | None:
        process_key = (process_name or "").lower()
        if process_key not in BROWSER_PROCESSES:
            return None

        now = time.time()
        page_title = self._clean_browser_title(window_title, process_key)
        last_title = self.last_title_by_process.get(process_key)
        if page_title == last_title and now - self.last_scan_at.get(process_key, 0) < 2:
            return self.last_seen_by_process.get(process_key)
        self.last_scan_at[process_key] = now
        title_changed = page_title != last_title
        self.last_title_by_process[process_key] = page_title

        candidates = self._chrome_like_candidates(process_key) if process_key != "firefox.exe" else self._firefox_candidates()
        for db_path in candidates:
            resolved = self._resolve_from_history(db_path, process_key, page_title)
            if resolved:
                self.last_seen_by_process[process_key] = resolved
                return resolved
        if title_changed:
            self.last_seen_by_process.pop(process_key, None)
        return self.last_seen_by_process.get(process_key) if not title_changed else None

    def _resolve_from_history(self, db_path: Path, process_key: str, page_title: str) -> BrowserUrl | None:
        copied = self._copy_history(db_path, process_key)
        if not copied:
            return None
        rows = self._recent_firefox_rows(copied) if process_key == "firefox.exe" else self._recent_chrome_rows(copied)
        if not rows:
            return None

        normalized_title = self._normalize_title(page_title)
        for url, title in rows:
            history_title = self._normalize_title(title)
            if normalized_title and (normalized_title in history_title or history_title in normalized_title):
                return self._to_browser_url(url, title)

        return self._best_history_match(page_title, rows)

    def _recent_chrome_rows(self, db_path: Path) -> list[tuple[str, str | None]]:
        cutoff = self._chrome_time(datetime.now(timezone.utc) - timedelta(minutes=30))
        try:
            with sqlite3.connect(db_path) as conn:
                return conn.execute(
                    """
                    SELECT url, title
                    FROM urls
                    WHERE last_visit_time >= ?
                    ORDER BY last_visit_time DESC
                    LIMIT 80
                    """,
                    (cutoff,),
                ).fetchall()
        except sqlite3.Error:
            return []

    def _recent_firefox_rows(self, db_path: Path) -> list[tuple[str, str | None]]:
        cutoff = int((time.time() - 1800) * 1_000_000)
        try:
            with sqlite3.connect(db_path) as conn:
                return conn.execute(
                    """
                    SELECT url, title
                    FROM moz_places
                    WHERE last_visit_date >= ?
                    ORDER BY last_visit_date DESC
                    LIMIT 80
                    """,
                    (cutoff,),
                ).fetchall()
        except sqlite3.Error:
            return []

    def _copy_history(self, db_path: Path, process_key: str) -> Path | None:
        if not db_path.exists():
            return None
        target = self.cache_dir / f"{process_key}-{abs(hash(str(db_path))) % 100000}.sqlite"
        try:
            for suffix in ("", "-wal", "-shm"):
                stale = Path(f"{target}{suffix}")
                if stale.exists():
                    stale.unlink()
            shutil.copy2(db_path, target)
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{db_path}{suffix}")
                if sidecar.exists():
                    shutil.copy2(sidecar, Path(f"{target}{suffix}"))
            return target
        except OSError:
            return None

    def _chrome_like_candidates(self, process_key: str) -> list[Path]:
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        roaming = Path(os.environ.get("APPDATA", ""))
        user_data_roots = {
            "chrome.exe": local / "Google" / "Chrome" / "User Data",
            "msedge.exe": local / "Microsoft" / "Edge" / "User Data",
            "brave.exe": local / "BraveSoftware" / "Brave-Browser" / "User Data",
            "vivaldi.exe": local / "Vivaldi" / "User Data",
            "chromium.exe": local / "Chromium" / "User Data",
        }
        direct_history_paths = {
            "opera.exe": [
                roaming / "Opera Software" / "Opera Stable" / "History",
                local / "Programs" / "Opera" / "profile" / "data" / "History",
            ],
            "opera_gx.exe": [
                roaming / "Opera Software" / "Opera GX Stable" / "History",
            ],
        }
        root = user_data_roots.get(process_key)
        candidates: list[Path] = []
        if root and root.exists():
            profiles = [root / "Default", *sorted(root.glob("Profile *"))]
            candidates.extend(profile / "History" for profile in profiles)
        candidates.extend(path for path in direct_history_paths.get(process_key, []) if path.exists())
        return candidates

    def _firefox_candidates(self) -> list[Path]:
        roaming = Path(os.environ.get("APPDATA", ""))
        profiles = roaming / "Mozilla" / "Firefox" / "Profiles"
        if not profiles.exists():
            return []
        return [profile / "places.sqlite" for profile in sorted(profiles.glob("*"))]

    def _to_browser_url(self, url: str | None, title: str | None) -> BrowserUrl | None:
        if not url:
            return None
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        if not domain:
            return None
        return BrowserUrl(url=url, domain=domain, title=title)

    @staticmethod
    def _chrome_time(value: datetime) -> int:
        chrome_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return int((value - chrome_epoch).total_seconds() * 1_000_000)

    @staticmethod
    def _clean_browser_title(title: str, process_key: str) -> str:
        suffixes = {
            "chrome.exe": [" - Google Chrome"],
            "msedge.exe": [" - Microsoft Edge"],
            "brave.exe": [" - Brave"],
            "firefox.exe": [" - Mozilla Firefox"],
            "vivaldi.exe": [" - Vivaldi"],
            "opera.exe": [" - Opera"],
            "opera_gx.exe": [" - Opera"],
            "chromium.exe": [" - Chromium"],
        }
        cleaned = title or ""
        for suffix in suffixes.get(process_key, []):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)]
        return cleaned.strip()

    @staticmethod
    def _normalize_title(title: str | None) -> str:
        return " ".join((title or "").lower().split())

    def _best_history_match(self, page_title: str, rows: list[tuple[str, str | None]]) -> BrowserUrl | None:
        page_tokens = self._tokens(page_title)
        if not page_tokens:
            return None

        best: tuple[int, str | None, str | None] | None = None
        for url, title in rows:
            parsed = urlparse(url or "")
            candidate_text = f"{title or ''} {parsed.netloc} {parsed.path}"
            candidate_tokens = self._tokens(candidate_text)
            overlap = page_tokens & candidate_tokens
            score = len(overlap)
            if "crazygames" in page_tokens and "crazygames" in candidate_tokens:
                score += 4
            if score >= 2 and (best is None or score > best[0]):
                best = (score, url, title)

        if not best:
            return None
        return self._to_browser_url(best[1], best[2])

    @staticmethod
    def _tokens(value: str | None) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9]{3,}", (value or "").lower()))
        return tokens - {"www", "com", "http", "https", "html", "google", "chrome", "microsoft", "edge", "mozilla", "firefox"}

import cv2
import os
import platform
import shutil
import subprocess
import threading
import logging
import time
from pathlib import Path

try:
    from config import SystemState
except ImportError:
    SystemState = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_video_dir():
    if SystemState is not None:
        return str(SystemState.VIDEO_DIR)
    return str(Path(__file__).parent.absolute() / "Video_Analiz")


def _get_supported_exts():
    if SystemState is not None:
        return tuple(SystemState.SUPPORTED_VIDEO_EXTS)
    return (".mp4", ".avi", ".mov", ".mkv")


def list_local_videos():
    """Video_Analiz klasorundeki desteklenen videolari alfabetik listele."""
    vdir = _get_video_dir()
    try:
        os.makedirs(vdir, exist_ok=True)
    except Exception:
        pass
    exts = _get_supported_exts()
    try:
        files = [f for f in os.listdir(vdir) if f.lower().endswith(exts)]
    except FileNotFoundError:
        return []
    files.sort(key=str.lower)
    return [os.path.join(vdir, f) for f in files]


def is_youtube_url(s):
    if not isinstance(s, str):
        return False
    low = s.lower()
    return ("youtube.com/" in low or "youtu.be/" in low or "youtube-nocookie.com/" in low)


def is_rtsp_url(s):
    if not isinstance(s, str):
        return False
    low = s.strip().lower()
    return low.startswith(("rtsp://", "rtmp://"))


def is_youtube_live_url(s):
    if not is_youtube_url(s):
        return False
    low = str(s).lower()
    return ("/live" in low or "livestream" in low or "live_stream" in low)


def is_stream_url(s):
    if not isinstance(s, str):
        return False
    low = s.strip().lower()
    if is_youtube_url(s):
        return True
    return low.startswith(("rtsp://", "rtmp://", "http://", "https://"))


def is_video_file(s):
    if not isinstance(s, (str, os.PathLike)):
        return False
    p = str(s)
    if is_stream_url(p):
        return False
    # Sadece mevcut dosya + destekli uzanti video sayilir (klasor adi degil).
    return os.path.isfile(p) and p.lower().endswith(_get_supported_exts())


JS_RUNTIME_HELP = (
    "YouTube cozumu icin JS calisma ortami (Node.js/Deno) gerekli. "
    "Windows: winget install OpenJS.NodeJS.LTS  |  "
    "Dogrulama: yt-dlp --verbose <url>  |  "
    "Detay: https://github.com/yt-dlp/yt-dlp/wiki/EJS"
)


def _yt_dlp_exe():
    exe = shutil.which("yt-dlp")
    if exe:
        return exe
    # venv aktif degilken PATH'e dusmeyebilir; python'un yanindaki Scripts'e bak.
    import sys as _sys
    try:
        from pathlib import Path as _P
        cand = _P(_sys.executable).parent / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        if cand.is_file():
            return str(cand)
    except Exception:
        pass
    return None


def _yt_base_cmd():
    exe = _yt_dlp_exe()
    if exe:
        return [exe]
    # Son care: modul olarak cagir (pip paketi kuruluysa calisir).
    try:
        import sys as _sys
        __import__("yt_dlp")
        return [_sys.executable, "-m", "yt_dlp"]
    except Exception:
        pass
    raise RuntimeError("[X] yt-dlp bulunamadi. Cozum: pip install yt-dlp")


def _friendly_yt_error(raw):
    low = (raw or "").lower()
    if "js runtime" in low or "/ejs" in low or "ejs " in low:
        return f"[X] YouTube icin Node.js gerekli. {JS_RUNTIME_HELP}"
    if "requested format is not available" in low:
        return ("[X] Bu video icin direkt stream formati yok (DASH). "
                "Otomatik indirme deneniyor; ffmpeg yoksa sadece progressive videolar acilir.")
    if "sign in to confirm" in low or "bot" in low:
        return "[X] YouTube giris/bot dogrulamasi istedi. Baska video deneyin veya once Video_Analiz'e indirin."
    short = (raw or "").strip().replace("\n", " ")
    return f"[X] yt-dlp cozumu basarisiz: {short[-300:]}"


def resolve_youtube_url(youtube_url, timeout=30):
    """YouTube URL'ini OpenCV'nin acabilecegi tek URL'e cevir.

    Sira: progressive (18/22, ses+video) -> DASH mp4 video-only
    (135/134/133/160, tespit icin ses gerekmez) -> yoksa DASH_FALLBACK
    (cagiran indir-sonra-oynat yapar).
    """
    base = _yt_base_cmd()
    js = ["--js-runtimes", "node", "--js-runtimes", "deno"]
    candidates = [
        "18/22",
        "135/134/133/160",
        "best[height<=480][ext=mp4]/best[height<=480]",
    ]
    last_err = ""
    for fmt in candidates:
        cmd = base + js + ["-g", "--no-playlist", "-f", fmt, str(youtube_url)]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError("[X] yt-dlp zaman asimina ugradi.")
        if out.returncode != 0:
            last_err = (out.stderr or out.stdout or "").strip()
            continue
        urls = [l.strip() for l in (out.stdout or "").strip().splitlines() if l.strip()]
        if len(urls) == 1:
            return urls[0]
        if len(urls) > 1:
            continue
    raw = last_err or "Uygun direkt format yok"
    logger.warning(f"yt-dlp direkt stream basarisiz, indirme denenebilir: {raw[-300:]}")
    if "js runtime" in raw.lower() or "/ejs" in raw.lower():
        raise RuntimeError(_friendly_yt_error(raw))
    raise RuntimeError("[DASH_FALLBACK] Direkt oynatilabilir format yok, indirilerek oynatilacak.")


def _youtube_id(url):
    import re as _re
    import hashlib as _hl
    s = str(url)
    m = _re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", s)
    if m:
        return m.group(1)[:32]
    m = _re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", s)
    if m:
        return m.group(1)[:32]
    m = _re.search(r"/shorts/([A-Za-z0-9_-]{6,})", s)
    if m:
        return m.group(1)[:32]
    return "vid_" + _hl.md5(s.encode("utf-8", "ignore")).hexdigest()[:12]


def download_youtube_to_cache(youtube_url, timeout=180, max_cache_files=10, max_file_mb=1500):
    """VOD YouTube videosunu Video_Analiz'e indirip local path dondur."""
    exe_cmd = _yt_base_cmd()
    vdir = _get_video_dir()
    os.makedirs(vdir, exist_ok=True)
    vid = _youtube_id(youtube_url)
    target = os.path.join(vdir, f"_yt_{vid}.mp4")
    if os.path.isfile(target) and os.path.getsize(target) > 1024 * 100:
        logger.info(f"[*] YouTube cache kullaniliyor: {target}")
        return target
    # Kota: eski _yt_ cache'leri temizle (disk dolmasin).
    try:
        yt_files = sorted(
            [os.path.join(vdir, f) for f in os.listdir(vdir) if f.startswith("_yt_") and f.endswith(".mp4")],
            key=lambda p: os.path.getmtime(p)
        )
        while len(yt_files) >= max_cache_files:
            old = yt_files.pop(0)
            try:
                os.remove(old)
                logger.info(f"[*] Eski YouTube cache silindi: {old}")
            except Exception:
                pass
    except Exception:
        pass
    # ffmpeg varsa merge yapar, yoksa progressive tek dosya indirir.
    cmd = exe_cmd + ["--js-runtimes", "node", "--js-runtimes", "deno",
                     "--no-playlist", "-f", "mp4/best[height<=720]/best",
                     "--merge-output-format", "mp4", "-o", target, str(youtube_url)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("[X] YouTube indirme zaman asimina ugradi.")
    if out.returncode != 0:
        raw = (out.stderr or out.stdout or "").strip()
        raise RuntimeError(_friendly_yt_error(raw))
    if not os.path.isfile(target):
        raise RuntimeError("[X] Indirme bitti ama dosya bulunamadi.")
    logger.info(f"[+] YouTube indirildi: {target}")
    return target


class OmniEngine:
    def __init__(self, source=0, loop_video=True):
        self.arch = platform.machine()
        self.os_type = platform.system()
        self.source = source
        self.loop_video = loop_video
        self.video_fps = 25.0
        self._yt_local = None
        # Transport durumu
        self.paused = False
        self._next_pts = None
        self._last_success = time.monotonic()
        self._stream_opened_at = time.monotonic()
        self._reconnects = 0
        # Asenkron gecis: generation ile eski yavas isler iptal edilir.
        self._gen = 0
        self._gen_lock = threading.Lock()
        self._connecting = False
        self._pending_label = ""
        self._connect_error = ""
        # Saglik takibi: sifir-frame acilislar "basari" sayilmaz.
        self._fail_cycles = 0
        self._frames_since_swap = 0
        self._dl_attempted = False
        self.cap = None
        self.lock = threading.Lock()

        self._open_source(source)

        self.ret, self.frame = False, None
        self.is_running = False
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.frame_read_time = 0.0
        self.drop_count = 0
        self.loop_count = 0

    # --- Kaynak siniflandirma ---
    # Ayri tipler: camera | video | youtube-vod | youtube-live | rtsp | stream
    def _classify(self, source):
        if isinstance(source, int):
            return "camera"
        s = str(source).strip()
        if s.isdigit():
            return "camera"
        if is_youtube_url(s):
            return "youtube-live" if is_youtube_live_url(s) else "youtube-vod"
        if is_rtsp_url(s):
            return "rtsp"
        if is_stream_url(s):
            return "stream"
        if is_video_file(s):
            return "video"
        # http(s) disiplini disinda kalan string: dosya yolu kabul et (hata open'da belli olur).
        if s.lower().endswith(_get_supported_exts()):
            return "video"
        return "camera"

    def _label_for(self, source, stype):
        if stype == "camera":
            return f"CAM {source}"
        if stype == "video":
            return f"VIDEO: {os.path.basename(str(source))}"
        if stype in ("youtube", "youtube-vod"):
            return f"YT-VOD: {str(source)[:44]}"
        if stype == "youtube-live":
            return f"YT-LIVE: {str(source)[:44]}"
        if stype == "rtsp":
            return f"RTSP: {str(source)[:44]}"
        return f"STREAM: {str(source)[:48]}"

    def _update_state(self, source, stype):
        if SystemState is not None:
            SystemState.SOURCE_TYPE = stype
            SystemState.CURRENT_SOURCE = str(source)
            SystemState.CURRENT_SOURCE_LABEL = self._label_for(source, stype)
            try:
                SystemState.PLAY_PAUSED = bool(self.paused)
                SystemState.SEEKABLE = self._seekable_locked(stype)
            except Exception:
                pass

    def _seekable_locked(self, stype=None):
        st = stype if stype is not None else getattr(self, "source_type", "camera")
        if st == "video":
            return True
        if st in ("youtube-vod", "youtube") and getattr(self, "_yt_local", None):
            return True
        return False

    def _open_camera(self, source):
        try:
            cam_id = int(str(source).strip())
            cap_src = cam_id
        except (ValueError, TypeError):
            cap_src = source
        # [OFANSIF PERSPEKTIF] - Virtual Cam Injection/Hooking engelleme & MSMF API Zorlama
        if self.os_type == "Windows" and isinstance(cap_src, int):
            logger.info("[*] Windows OS Tespit Edildi. MSMF (Media Foundation) API deneniyor...")
            cap = cv2.VideoCapture(cap_src, cv2.CAP_MSMF)
            if not cap.isOpened():
                logger.warning("[!] MSMF baslatilamadi. DSHOW API'ye (Fallback) geciliyor.")
                cap = cv2.VideoCapture(cap_src, cv2.CAP_DSHOW)
            try:
                cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            except Exception:
                pass
        elif self.arch == "aarch64" and isinstance(cap_src, int):
            cap = cv2.VideoCapture(cap_src, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(cap_src)
        if not cap.isOpened():
            raise RuntimeError(f"[Kritik Hata] Kamera kaynagi ({source}) donanimsal olarak baslatilamadi.")
        # [PERFORMANS OPTIMIZASYONU] - I/O darbogazini asmak icin MJPG ve Zero-Buffer (sadece kamera).
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 5)
        except Exception:
            pass
        return cap

    def _open_video_file_raw(self, path):
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"[X] Video dosyasi acilamadi: {path}")
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 5)
        except Exception:
            pass
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            fps = float(fps) if fps and 1 <= fps <= 120 else 25.0
        except Exception:
            fps = 25.0
        return cap, fps

    def _open_video_file(self, path):
        cap, fps = self._open_video_file_raw(path)
        self.video_fps = fps
        return cap

    def _open_stream(self, url):
        cap = cv2.VideoCapture(str(url))
        if not cap.isOpened():
            raise RuntimeError(f"[X] Stream acilamadi: {url}")
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _open_rtsp(self, url):
        # Dusuk gecikme: TCP transport + kisa timeout + kucuk probe.
        prev = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
        opts = "rtsp_transport;tcp|stimeout;5000000|max_delay;500000|analyzeduration;1000000|probesize;1000000"
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = opts if not prev else prev + "|" + opts
        try:
            cap = cv2.VideoCapture(str(url))
        finally:
            if prev:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = prev
            else:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        if not cap.isOpened():
            raise RuntimeError(f"[X] RTSP acilamadi: {url}")
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _build_source(self, source):
        """Agir acma isi: self'e dokunmadan (cap, stype, yt_local, fps, resolved) dondur.

        Worker thread icinde cagrilir; takas _swap_built ile atomik yapilir.
        Boylece yavas acilis okuma dongusunu ve ekrani bloklamaz.
        """
        stype = self._classify(source)
        yt_local = None
        fps = getattr(self, "video_fps", 25.0)
        resolved = source
        if stype == "camera":
            cap = self._open_camera(source)
        elif stype == "video":
            cand = str(source)
            if not os.path.isfile(cand):
                join_cand = os.path.join(_get_video_dir(), os.path.basename(cand))
                if os.path.isfile(join_cand):
                    cand = join_cand
            if not os.path.isfile(cand):
                raise RuntimeError(f"[X] Video dosyasi bulunamadi: {source}")
            cap, fps = self._open_video_file_raw(cand)
            resolved = cand
        elif stype in ("youtube", "youtube-vod"):
            if stype == "youtube":
                stype = "youtube-vod"
            # VOD politikasi: indir+loop varsayilan (stabil hiz + seek).
            # Etiket de bunu soyler: "VOD=indir+loop / LIVE=direkt".
            try:
                logger.info("[*] YouTube-VOD indiriliyor (loop+seek icin)...")
                local = download_youtube_to_cache(str(source))
                cap, fps = self._open_video_file_raw(local)
                yt_local = local
            except Exception as e:
                msg = str(e)
                # Node.js/JS eksikse indirme de cozum de calismaz: net hata ver.
                if "Node.js" in msg or "JS calisma" in msg or "js runtime" in msg.lower():
                    raise
                logger.warning(f"[!] YouTube indirme basarisiz ({msg[-200:]}), direkt stream deneniyor...")
                stream_url = resolve_youtube_url(str(source))
                cap = self._open_stream(stream_url)
                logger.info(f"[*] YouTube-VOD direkt stream acildi (hiz pacing ile): {source}")
        elif stype == "youtube-live":
            stream_url = resolve_youtube_url(str(source))
            cap = self._open_stream(stream_url)
            logger.info(f"[*] YouTube-LIVE acildi: {source}")
        elif stype == "rtsp":
            cap = self._open_rtsp(source)
            logger.info(f"[*] RTSP acildi (dusuk gecikme): {source}")
        else:  # stream (http/hls generic)
            cap = self._open_stream(source)
        return cap, stype, yt_local, fps, resolved

    def _swap_built(self, source, stype, cap, yt_local, fps):
        with self.lock:
            old = self.cap
            self.cap = cap
            self.source = source
            self.source_type = stype
            self._yt_local = yt_local
            if stype in ("video", "youtube-vod") or yt_local:
                try:
                    self.video_fps = float(fps) or 25.0
                except Exception:
                    pass
        # Eski cap'i gecikmeli birak: okuma dongusunde surmekte olan
        # cap.read() (oz. MSMF) ile yarisip "can't grab frame" gurultusune
        # yol acmamak icin. Kisa gecikme, hizli art arda gecislerde birikmez.
        if old is not None:
            def _late_release(c=old):
                try:
                    time.sleep(0.3)
                except Exception:
                    pass
                try:
                    c.release()
                except Exception:
                    pass
            threading.Thread(target=_late_release, daemon=True).start()
        self._update_state(source, stype)
        self._last_success = time.monotonic()
        self._stream_opened_at = time.monotonic()
        # NOT: _reconnects/_fail_cycles burada SIFIRLANMAZ. Sifir-frame acilis
        # "basari" sayilmaz; sayaclar ilk gercek framelerde (_update) sifirlanir.
        # Boylece oynatilamayan stream sonsuz reconnect dongusune girmez.
        self._frames_since_swap = 0
        self._next_pts = None
        self._live_pts = None
        logger.info(f"[+] Goruntu kaynagi acildi [{stype}]: {source}")
        return stype

    def _set_connecting(self, on, label=""):
        self._connecting = bool(on)
        self._pending_label = str(label or "")
        if not on:
            self._pending_label = ""
        if SystemState is not None:
            try:
                SystemState.CONNECTING = bool(on)
                SystemState.CONNECTING_LABEL = str(label or "")
            except Exception:
                pass

    def is_connecting(self):
        return bool(self._connecting)

    def request_switch(self, new_source, on_done=None, reset_health=True):
        """Bloklamayan gecis: agir acma isci thread'de, eski frame ekranda kalir.

        on_done(ok, stype_or_err): basari/hata bildirimi (isci thread'den cagrilir).
        reset_health: watchdog tetiklemesinde False verilir ki fail sayaci yasasin.
        Donus: generation id (iptal takibi icin).
        """
        with self._gen_lock:
            self._gen += 1
            mygen = self._gen
        label = str(new_source)[:60]
        self._connect_error = ""
        if reset_health:
            # Yeni kullanici niyeti: saglik sayaclarini sifirla.
            self._fail_cycles = 0
            self._reconnects = 0
            self._dl_attempted = False
        self._set_connecting(True, label)
        logger.info(f"[*] Kaynak gecisi baslatildi (async #{mygen}): {new_source}")

        def _worker():
            try:
                cap, stype, yt_local, fps, resolved = self._build_source(new_source)
            except Exception as e:
                if mygen == self._gen:
                    self._connect_error = str(e)
                    self._set_connecting(False)
                    logger.warning(f"[X] Kaynak gecisi basarisiz: {e}")
                    if SystemState is not None:
                        try:
                            SystemState.CONNECT_ERROR = str(e)[:300]
                        except Exception:
                            pass
                    if on_done is not None:
                        try:
                            on_done(False, e)
                        except Exception:
                            pass
                else:
                    logger.info(f"[*] Gecis #{mygen} iptal (daha yeni istek var).")
                return
            if mygen != self._gen:
                try:
                    cap.release()
                except Exception:
                    pass
                logger.info(f"[*] Gecis #{mygen} iptal edildi, yeni cap birakildi.")
                return
            try:
                st = self._swap_built(new_source, stype, cap, yt_local, fps)
            except Exception as e:
                if mygen == self._gen:
                    self._connect_error = str(e)
                    self._set_connecting(False)
                    if on_done is not None:
                        try:
                            on_done(False, e)
                        except Exception:
                            pass
                return
            # Basarili takas: sayaclari sifirla, frame'i SIFIRLAMA (son iyi frame kalsin).
            self.drop_count = 0
            self.loop_count = 0
            self.paused = False
            if SystemState is not None:
                try:
                    SystemState.PLAY_PAUSED = False
                except Exception:
                    pass
            if mygen == self._gen:
                self._set_connecting(False)
            if on_done is not None:
                try:
                    on_done(True, st)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()
        return mygen

    def _open_source(self, source):
        """Senkron acma (init / watchdog uyumlulugu icin korunur)."""
        cap, stype, yt_local, fps, resolved = self._build_source(source)
        return self._swap_built(source, stype, cap, yt_local, fps)

    def switch_source(self, new_source):
        """Senkron gecis (geriye donuk uyumluluk). UI/web artik request_switch kullanmali."""
        stype = self._open_source(new_source)
        # Son iyi frame'i SIFIRLAMA: yeni frame gelene kadar eski goruntu kalir.
        self.drop_count = 0
        self.loop_count = 0
        self.paused = False
        self._fail_cycles = 0
        self._reconnects = 0
        self._dl_attempted = False
        self._next_pts = None
        self._last_success = time.monotonic()
        self._stream_opened_at = time.monotonic()
        self._set_connecting(False)
        if SystemState is not None:
            try:
                SystemState.PLAY_PAUSED = False
            except Exception:
                pass
        return stype

    def get_source_label(self):
        if SystemState is not None:
            return str(getattr(SystemState, "CURRENT_SOURCE_LABEL", str(self.source)))
        return self._label_for(self.source, getattr(self, "source_type", "camera"))

    # --- Transport kontrolleri (duraklat / ileri-geri sar) ---
    def is_paused(self):
        return bool(self.paused)

    def is_seekable(self):
        return self._seekable_locked()

    def pause(self):
        self.paused = True
        if SystemState is not None:
            SystemState.PLAY_PAUSED = True
        return True

    def resume(self):
        self.paused = False
        # PTS saatini sifirla ki resume'de yigilmis bekleme patlamasin.
        self._next_pts = None
        if SystemState is not None:
            SystemState.PLAY_PAUSED = False
        return True

    def toggle_pause(self):
        if self.paused:
            return self.resume()
        return self.pause()

    def seek(self, seconds):
        """Seekable kaynakta gorece sar (+/- sn). Seekable degilse False."""
        if not self.is_seekable():
            return False
        try:
            with self.lock:
                cap = self.cap
                if cap is None:
                    return False
                cur = cap.get(cv2.CAP_PROP_POS_MSEC) or 0
                target = max(0.0, float(cur) + float(seconds) * 1000.0)
                ok = cap.set(cv2.CAP_PROP_POS_MSEC, target)
            self._next_pts = None
            return bool(ok)
        except Exception:
            return False

    def seek_to(self, seconds):
        if not self.is_seekable():
            return False
        try:
            with self.lock:
                cap = self.cap
                if cap is None:
                    return False
                ok = cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds) * 1000.0))
            self._next_pts = None
            return bool(ok)
        except Exception:
            return False

    def get_position_sec(self):
        try:
            with self.lock:
                cap = self.cap
                if cap is None:
                    return 0.0
                if not self.is_seekable():
                    return 0.0
                return max(0.0, float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0) / 1000.0)
        except Exception:
            return 0.0

    def get_duration_sec(self):
        try:
            with self.lock:
                cap = self.cap
                if cap is None:
                    return 0.0
                if not self.is_seekable():
                    return 0.0
                fps = cap.get(cv2.CAP_PROP_FPS) or 0
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                if fps and fps > 0 and frames and frames > 0:
                    return float(frames) / float(fps)
                return 0.0
        except Exception:
            return 0.0

    def get_playback_info(self):
        pos = self.get_position_sec()
        dur = self.get_duration_sec()
        info = {
            "source_type": getattr(self, "source_type", "camera"),
            "label": self.get_source_label(),
            "paused": self.is_paused(),
            "seekable": self.is_seekable(),
            "pos": round(pos, 1),
            "dur": round(dur, 1),
            "loop": bool(self.loop_video),
            "connecting": bool(self._connecting),
            "pending": str(getattr(self, "_pending_label", "")),
            "connect_error": str(getattr(self, "_connect_error", "")),
        }
        if SystemState is not None:
            try:
                SystemState.PLAY_PAUSED = info["paused"]
                SystemState.SEEKABLE = info["seekable"]
                SystemState.PLAY_POS_SEC = info["pos"]
                SystemState.PLAY_DUR_SEC = info["dur"]
            except Exception:
                pass
        return info

    def start(self):
        if self.cap is None or not self.cap.isOpened():
            logger.error("[X] Goruntu kaynagi cevrimdisi. Motor baslatilamiyor.")
            return
        if self.is_running:
            return
        self.is_running = True
        if not self.thread.is_alive():
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()

    def _rewind_video(self):
        try:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.loop_count += 1
            if self.loop_count <= 3 or self.loop_count % 100 == 0:
                logger.info(f"[*] Video basa sarildi (sonsuz dongu #{self.loop_count}): {self.source}")
            return True
        except Exception:
            return False

    def _on_stream_unhealthy(self, reason):
        """Basarisiz canli dongu: say, VOD direkt 3+ kez olduyse indirmeye dus.

        Okuma dongusunu bloklamaz; agir isler isci thread'e verilir.
        """
        self._fail_cycles += 1
        stype = getattr(self, "source_type", "")
        yt_direct = stype in ("youtube-vod", "youtube") and not getattr(self, "_yt_local", None)
        if yt_direct and self._fail_cycles >= 3 and not self._dl_attempted:
            self._dl_attempted = True
            self._set_connecting(True, "YouTube indiriliyor...")
            logger.info("[*] Direkt stream frame uretmiyor, indirme fallback baslatildi.")
            mygen = self._gen
            src = self.source

            def _dl_worker():
                try:
                    local = download_youtube_to_cache(str(src))
                except Exception as e:
                    if mygen == self._gen:
                        self._connect_error = str(e)
                        self._set_connecting(False)
                        if SystemState is not None:
                            try:
                                SystemState.CONNECT_ERROR = str(e)[:300]
                            except Exception:
                                pass
                        logger.warning(f"[X] YouTube indirme fallback basarisiz: {e}")
                    return
                if mygen != self._gen:
                    return
                try:
                    cap, fps = self._open_video_file_raw(local)
                except Exception as e:
                    if mygen == self._gen:
                        self._connect_error = str(e)
                        self._set_connecting(False)
                    return
                if mygen != self._gen:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    return
                self._swap_built(src, "youtube-vod", cap, local, fps)
                self._fail_cycles = 0
                self._reconnects = 0
                self._set_connecting(False)
                logger.info(f"[+] YouTube indirildi, loop ile oynatiliyor: {local}")

            threading.Thread(target=_dl_worker, daemon=True).start()
            return
        if self._reconnects < 20 and not self._connecting:
            self._reconnects += 1
            logger.warning(f"[!] {reason}, async reconnect...")
            try:
                self.request_switch(self.source, reset_health=False)
            except Exception:
                pass

    def _reopen_current(self):
        """Watchdog reconnect: ayni kaynagi kisa backoff ile yeniden ac."""
        src = self.source
        delay = min(1.0 + 0.5 * self._reconnects, 5.0)
        time.sleep(delay)
        try:
            self._open_source(src)
            self._reconnects += 1
            self._last_success = time.monotonic()
            logger.info(f"[*] Kaynak yeniden baglandi (deneme {self._reconnects}): {src}")
            return True
        except Exception as e:
            self._reconnects += 1
            logger.warning(f"[!] Reconnect basarisiz ({self._reconnects}): {e}")
            return False

    def _refresh_youtube_live(self):
        """Expire olan googlevideo URL'ini taze resolve ile yenile."""
        try:
            fresh = resolve_youtube_url(str(self.source))
            with self.lock:
                old = self.cap
                self.cap = self._open_stream(fresh)
                self._stream_opened_at = time.monotonic()
            if old is not None:
                try:
                    old.release()
                except Exception:
                    pass
            logger.info("[*] YouTube-LIVE URL tazelendi.")
            return True
        except Exception as e:
            logger.warning(f"[!] YouTube-LIVE tazeleme basarisiz: {e}")
            return False

    def _update(self):
        error_count = 0
        LIVE_TYPES = ("rtsp", "youtube-live", "youtube-vod", "stream", "youtube")
        while self.is_running:
            with self.lock:
                cap = self.cap
                stype = getattr(self, "source_type", "camera")
                paused = bool(self.paused)
            if cap is None:
                time.sleep(0.05)
                continue

            # --- PAUSE ---
            if paused:
                seekable = self._seekable_locked(stype)
                if seekable:
                    # Dosya: okuma, son frame ekranda kalir.
                    time.sleep(0.05)
                    continue
                # Canli: buffer sismemesi icin oku-at (ekrana yazma).
                try:
                    cap.grab()
                except Exception:
                    pass
                time.sleep(0.03)
                continue

            # --- Stale watchdog (canli): basarili frame yoksa async reconnect ---
            # Okuma dongusu BLOKLANMAZ: isci thread acar, son iyi frame ekranda kalir.
            # Takas sonrasi ilk saniyeler buffering toleransi (ozellikle YouTube).
            if stype in LIVE_TYPES + ("camera",):
                try:
                    since_swap = time.monotonic() - float(getattr(self, "_stream_opened_at", 0.0) or 0.0)
                except Exception:
                    since_swap = 99.0
                stale_limit = 8.0 if stype in ("youtube-vod", "youtube", "youtube-live") else 4.0
                if stype != "camera" and since_swap > stale_limit and (time.monotonic() - self._last_success) > stale_limit:
                    self._last_success = time.monotonic()
                    if self._reconnects < 20 and not self._connecting:
                        self._on_stream_unhealthy(f"Stale frame [{stype}]")
                        error_count = 0
                    elif self._reconnects >= 20:
                        logger.error("[X] Reconnect limiti asildi, motor duruyor.")
                        self.is_running = False
                        break
                    time.sleep(0.2)
                    continue

            t0 = time.perf_counter()
            ret, frame = cap.read()
            self.frame_read_time = (time.perf_counter() - t0) * 1000

            if not ret or frame is None:
                # Video dosyasi + indirilmis YouTube VOD: sonsuz dongu icin basa sar.
                if (stype == "video" or (stype in ("youtube-vod", "youtube") and getattr(self, "_yt_local", None))) and self.loop_video:
                    if self._rewind_video():
                        error_count = 0
                        self._next_pts = None
                        continue
                # Canli tipler: retry + periyodik refresh/reconnect (hepsi async).
                if stype in LIVE_TYPES:
                    # Dosya destekli VOD zaten yukarida loop'a girdi; buraya dusen
                    # VOD direkt stream'dir (seek yok) -> canli gibi retry.
                    error_count += 1
                    self.drop_count += 1
                    # YouTube-LIVE'da 10 failde URL tazele (expire olasiligi).
                    if stype == "youtube-live" and error_count == 10 and not self._connecting:
                        try:
                            self.request_switch(self.source, reset_health=False)
                        except Exception:
                            pass
                    time.sleep(0.2)
                    if error_count > 50:
                        if self._reconnects < 20 and not self._connecting:
                            self._on_stream_unhealthy("Stream 50 fail")
                            error_count = 0
                            continue
                        if self._reconnects >= 20:
                            logger.error("[X] Stream baglantisi koptu (50 basarisiz okuma).")
                            self.is_running = False
                            break
                    continue
                error_count += 1
                self.drop_count += 1
                if error_count % 3 == 0:
                    logger.warning(f"[!] Frame Drop Tespit Edildi (Kayip: {error_count}/10) [{stype}]")

                if error_count > 10:
                    # Video dosyasi gercekten bittiyse ve loop kapaliysa cik.
                    if stype == "video":
                        logger.error("[X] Video dosyasi bitti ve loop kapali.")
                        self.is_running = False
                        break
                    logger.error("[X] Goruntu baglantisi tamamen koptu. Kaynak ele gecirilmis veya baglanti kesilmis olabilir.")
                    self.is_running = False
                    break

                time.sleep(0.001)
                continue

            error_count = 0
            self._last_success = time.monotonic()
            # Saglik dogrulama: ust uste 5 gercek frame = saglikli stream.
            # Sifir-frame acilislar sayac sifirlamaz (sonsuz reconnect olmaz).
            try:
                self._frames_since_swap += 1
                if self._frames_since_swap >= 5:
                    self._fail_cycles = 0
                    self._reconnects = 0
            except Exception:
                pass
            # Kamera aynalama sadece canli kamerada; video/stream orijinal akista kalir.
            if stype == "camera":
                try:
                    frame = cv2.flip(frame, 1)
                except Exception:
                    pass
            self.frame = frame
            # Seekable kaynakta PTS saati: monotonik, suruklenmesiz pacing.
            if stype == "video" or (stype in ("youtube-vod", "youtube") and getattr(self, "_yt_local", None)):
                try:
                    interval = 1.0 / max(1.0, float(getattr(self, "video_fps", 25.0)))
                    now = time.monotonic()
                    if self._next_pts is None:
                        self._next_pts = now + interval
                    else:
                        # Geride kaldıysak saati bugune cek (yigilma patlamasin).
                        if self._next_pts < now - 0.5:
                            self._next_pts = now + interval
                    wait = self._next_pts - time.monotonic()
                    if wait > 0.002:
                        time.sleep(min(wait, 0.25))
                    self._next_pts += interval
                except Exception:
                    pass
            else:
                # Direkt canli stream: ag hizliysa spin olup "hizli video" olur.
                # Max ~30fps tavan koy (realtime'i yavaslatmaz, hizliyi frenler).
                try:
                    now = time.monotonic()
                    last = getattr(self, "_live_pts", None)
                    min_interval = 1.0 / 30.0
                    if last is not None:
                        wait = min_interval - (now - last)
                        if wait > 0.002:
                            time.sleep(min(wait, 0.1))
                    self._live_pts = time.monotonic()
                except Exception:
                    pass

    def get_frame(self):
        # Paylasilan buffer'i disari verme: kopya don (UI/detector mutate edemez).
        frm = self.frame
        if frm is None:
            return None
        try:
            return frm.copy()
        except Exception:
            return frm

    def stop(self):
        self.is_running = False
        try:
            if self.thread.is_alive():
                self.thread.join(timeout=3)
        except Exception:
            pass
        with self.lock:
            if self.cap and self.cap.isOpened():
                try:
                    self.cap.release()
                except Exception:
                    pass
        logger.info("[+] I/O Goruntu Motoru Guvenli Sekilde Izole Edildi ve Kapatildi.")

"""Tk menu politikasi: tek servis thread'inde tek Tk interpreter, guvenli kapatma.

Koken: Tk pencereleri daha once her `[C]/[S]` tusunda ayri bir worker
thread'de `tk.Tk()` ile aciliyordu. Windows'ta Tcl interpreter
thread-affinity ister; farkli thread'lerde yaratilan `StringVar`/after
callback'leri GC baska thread'de kosunca su log kirliligi cikiyordu:

    Variable.__del__: main thread is not in main loop
    Tcl_AsyncDelete: async handler deleted by the wrong thread

Cozum: tum menuler tek bir dedicated Tk servis thread'inde sirayla calisir.
Ayni thread yaratir + kapatir -> yanlis-thread delete olmaz. Video dongusu
bloklanmaz cunku cagri kuyruga atilir, main thread beklemez.
Kapatma sirasinda `shutdown()` aktif pencereyi kendi thread'inde kapatir,
daemon abort olmaz.
"""
import os
import queue
import threading

TK_LOCK = threading.Lock()
_active = {"root": None}

_svc_lock = threading.Lock()
_svc_thread = None
_svc_queue = queue.Queue()
_svc_stop = {"flag": False}


def tk_enabled():
    """OMNIVISION_TK=0 ise Tk menuler kapali (web paneli kullanilir)."""
    try:
        return str(os.getenv("OMNIVISION_TK", "1")).strip() != "0"
    except Exception:
        return True


def register(root):
    with TK_LOCK:
        _active["root"] = root


def unregister(root):
    with TK_LOCK:
        if _active.get("root") is root:
            _active["root"] = None


def is_active():
    with TK_LOCK:
        r = _active.get("root")
    if r is None:
        return False
    try:
        return bool(r.winfo_exists())
    except Exception:
        return False


def _svc_loop():
    while True:
        try:
            job = _svc_queue.get(timeout=0.2)
        except Exception:
            with _svc_lock:
                if _svc_stop["flag"] and _svc_queue.empty():
                    break
            continue
        if job is None:
            try:
                _svc_queue.task_done()
            except Exception:
                pass
            break
        fn = job
        try:
            fn()
        except Exception:
            pass
        finally:
            try:
                _svc_queue.task_done()
            except Exception:
                pass


def ensure_service():
    global _svc_thread
    with _svc_lock:
        if _svc_thread is not None and _svc_thread.is_alive():
            return _svc_thread
        _svc_stop["flag"] = False
        _svc_thread = threading.Thread(target=_svc_loop, name="TkService", daemon=True)
        _svc_thread.start()
        return _svc_thread


def submit(fn):
    """Menu builder'i Tk servis thread'inde calistir (non-blocking).

    Video dongusunu bloklamaz; menuler siraya girer, tek seferde tek pencere.
    Donus: True (kuyruga alindi) / False (Tk kapali).
    """
    if not tk_enabled():
        print("[!] Tk menuler kapali (OMNIVISION_TK=0). Web paneli kullanin: / -> GORUNTU KAYNAGI.")
        return False
    ensure_service()
    try:
        _svc_queue.put_nowait(fn)
        return True
    except Exception:
        return False


def safe_close(root, after_ids=None, trace_pairs=None):
    """Bekleyen after/trace'leri iptal edip pencereyi kapat.

    Ayni thread'den cagrilmali (servis thread'i saglar). quit+update+destroy
    sirasi Tcl_AsyncDelete riskini azaltir. Her thread'den cagrilabilir
    (hatalar yutulur).
    """
    try:
        for aid in list(after_ids or []):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass
    try:
        for var, tid in list(trace_pairs or []):
            try:
                var.trace_remove("write", tid)
            except Exception:
                pass
    except Exception:
        pass
    # StringVar referanslarini serbest birak (GC'nin baska thread'de
    # tk.call yapmasini engelle). Closure'larin tuttugu var'lar icin de
    # _pending kuyruklarini temizle.
    try:
        pend = getattr(root, "_pending", None)
        if isinstance(pend, list):
            pend.clear()
    except Exception:
        pass
    try:
        for attr in ("_tk_vars",):
            bucket = getattr(root, attr, None)
            if isinstance(bucket, list):
                bucket.clear()
    except Exception:
        pass
    try:
        # Once cocuk widget'lari tek tek yok et (ic Tcl var'lari ayni thread'de olur).
        try:
            for child in list(root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            root.update_idletasks()
        except Exception:
            pass
        try:
            root.quit()
        except Exception:
            pass
        try:
            root.update()
        except Exception:
            pass
        root.destroy()
    except Exception:
        pass
    finally:
        # Kalan Tcl var'larinin __del__'i bu thread'de kossun diye GC'yi simdi tetikle.
        try:
            import gc as _gc
            _gc.collect()
        except Exception:
            pass
        unregister(root)


def schedule(root, ms, func, bucket=None):
    """root.after guvenli sarmalayici; id'yi bucket listesine yazar."""
    try:
        if not root.winfo_exists():
            return None
    except Exception:
        return None
    try:
        aid = root.after(ms, func)
    except Exception:
        return None
    if bucket is not None:
        try:
            bucket.append(aid)
        except Exception:
            pass
        try:
            vars_bucket = getattr(root, "_tk_vars", None)
            if vars_bucket is None:
                root._tk_vars = vars_bucket = []
        except Exception:
            pass
    return aid


def track_var(root, var):
    """StringVar'i root'a bagla ki GC zamansiz tk.call yapmasin."""
    try:
        bucket = getattr(root, "_tk_vars", None)
        if bucket is None:
            root._tk_vars = bucket = []
        bucket.append(var)
    except Exception:
        pass
    return var


def shutdown(timeout=3.0):
    """Aktif pencereyi kapatip servis thread'ini durdur (cikis sirasinda cagir)."""
    with TK_LOCK:
        r = _active.get("root")
    if r is not None:
        # Kapatma istegi servis thread'ine verilir (dogru thread kapatir).
        def _close():
            try:
                safe_close(r, getattr(r, "_after_ids", None))
            except Exception:
                pass
        try:
            if threading.current_thread().name == "TkService":
                _close()
            else:
                _svc_queue.put(_close)
        except Exception:
            pass
    with _svc_lock:
        _svc_stop["flag"] = True
    try:
        _svc_queue.put_nowait(None)
    except Exception:
        pass
    th = None
    with _svc_lock:
        th = _svc_thread
    if th is not None and th is not threading.current_thread():
        try:
            th.join(timeout=timeout)
        except Exception:
            pass

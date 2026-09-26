import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox

from config import SystemState
import tk_policy

try:
    from omni_engine import list_local_videos
except ImportError:
    def list_local_videos():
        return []

_menu_lock = threading.Lock()
_menu_open = False


def open_media_menu(engine=None, detector=None):
    """Goruntu kaynagi secim paneli ([C] ile acilir). Tek instance.

    Non-blocking: Tk servis thread'ine kuyruklanir.
    """
    if not tk_policy.tk_enabled():
        print("[!] Tk kapali (OMNIVISION_TK=0). Web panelinden kaynak secin.")
        return False
    with _menu_lock:
        if _menu_open:
            print("[!] Medya menusu zaten acik.")
            return False
        if tk_policy.is_active():
            print("[!] Baska bir menu acik, once onu kapatin.")
            return False
        globals()["_menu_open"] = True

    def _job(_e=engine, _d=detector):
        try:
            _open_media_menu_blocking(_e, _d)
        finally:
            with _menu_lock:
                globals()["_menu_open"] = False

    return tk_policy.submit(_job)


def _apply_source(engine, detector, new_source, root=None, status_var=None):
    """Kaynak gecisi ister. Worker thread asla Tcl'e dokunmaz.

    Sonuc isci thread'den queue'ya duz veri olarak duser; menu thread'indeki
    poller (_refresh_pos) UI'yi gunceller. Boylece capraz-thread Tcl temasi
    (Tcl_AsyncDelete / Variable.__del__) olmaz.
    """
    if engine is None:
        err = "[X] Engine bagli degil."
        print(err)
        if status_var is not None:
            try:
                status_var.set(err)
            except Exception:
                pass
        return False
    use_async = hasattr(engine, "request_switch")
    if not use_async:
        # Eski motor: senkron fallback (menu thread'inde).
        try:
            stype = engine.switch_source(new_source)
            if detector is not None and hasattr(detector, "reset_history"):
                try:
                    detector.reset_history()
                except Exception:
                    pass
            msg = f"[+] Kaynak degisti [{stype}]: {engine.get_source_label()}"
            print(msg)
            if status_var is not None:
                try:
                    status_var.set(msg)
                except Exception:
                    pass
            if root is not None:
                try:
                    messagebox.showinfo("OmniVision", msg, parent=root)
                except Exception:
                    pass
                tk_policy.safe_close(root, getattr(root, "_after_ids", None), getattr(root, "_trace_pairs", None))
            return True
        except Exception as e:
            raw = str(e)
            print(f"[X] Kaynak acilamadi: {raw}")
            short = raw[-260:] if len(raw) > 260 else raw
            err = f"[X] Kaynak acilamadi: {short}"
            if status_var is not None:
                try:
                    status_var.set(err)
                except Exception:
                    pass
            if root is not None:
                try:
                    messagebox.showerror("OmniVision", err, parent=root)
                except Exception:
                    pass
            return False

    label = str(new_source)[:60]
    if status_var is not None:
        try:
            status_var.set(f"[*] Baglaniyor: {label} ...")
        except Exception:
            pass
    if root is None:
        # UI yok: senkron dene.
        try:
            engine.switch_source(new_source)
            return True
        except Exception as e:
            print(f"[X] Kaynak acilamadi: {e}")
            return False

    try:
        pend = getattr(root, "_pending", None)
        if pend is None:
            root._pending = pend = []
        q = queue.Queue()

        def _on_done(ok, payload, _q=q):
            # ISCi THREAD: sadece duz veri koy, Tcl'e dokunma.
            try:
                _q.put((bool(ok), str(payload)[:300]))
            except Exception:
                pass

        gen = engine.request_switch(new_source, on_done=_on_done)
        pend.append((gen, q, label))
    except Exception as e:
        err = f"[X] Gecis baslatilamadi: {e}"
        print(err)
        if status_var is not None:
            try:
                status_var.set(err)
            except Exception:
                pass
        return False
    return True


def _poll_switches(root, status_var, engine=None, detector=None):
    """Bekleyen gecis sonuclarini menu thread'inde uygula. True: menu kapandi."""
    pend = getattr(root, "_pending", None)
    if not pend:
        return False
    done = []
    remaining = []
    for gen, q, label in list(pend):
        last = None
        try:
            while True:
                last = q.get_nowait()
        except Exception:
            pass
        if last is None:
            remaining.append((gen, q, label))
        else:
            done.append((gen, last))
    if not done:
        return False
    # Cift tiklamada en guncel generation kazanir, eskiler atilir.
    done.sort(key=lambda x: x[0])
    _gen, (ok, text) = done[-1]
    root._pending = remaining
    try:
        if ok:
            if detector is not None and hasattr(detector, "reset_history"):
                try:
                    detector.reset_history()
                except Exception:
                    pass
            try:
                msg = f"[+] Kaynak degisti [{text}]: {engine.get_source_label()}" if engine else "[+] Kaynak degisti."
            except Exception:
                msg = "[+] Kaynak degisti."
            print(msg)
            if status_var is not None:
                status_var.set(msg)
            try:
                messagebox.showinfo("OmniVision", msg, parent=root)
            except Exception:
                pass
            tk_policy.safe_close(root, getattr(root, "_after_ids", None), getattr(root, "_trace_pairs", None))
            return True
        raw = text
        print(f"[X] Kaynak acilamadi: {raw}")
        short = raw
        if len(short) > 260:
            short = short[:260] + "... (detay konsolda)" if "Node.js" in short else short[-260:]
        err = f"[X] Kaynak acilamadi: {short}"
        if status_var is not None:
            status_var.set(err)
        # Basarisizda menu ACIK kalir: kullanici baska secim yapabilir.
        try:
            messagebox.showerror("OmniVision", err, parent=root)
        except Exception:
            pass
    except Exception:
        pass
    return False


def _open_media_menu_blocking(engine=None, detector=None):
    root = tk.Tk()
    root._after_ids = []
    root._trace_pairs = []
    tk_policy.register(root)
    root.title("OMNIVISION - GORUNTU KAYNAGI")
    root.geometry("520x780")
    root.attributes('-topmost', True)
    root.configure(bg="#121212")

    cur = engine.get_source_label() if engine is not None else str(SystemState.CURRENT_SOURCE_LABEL)
    tk.Label(root, text="[ GORUNTU KAYNAGI SEC ]", font=("Courier", 14, "bold"),
             bg="#121212", fg="#00ff00").pack(pady=10)
    tk.Label(root, text=f"Mevcut: {cur}", font=("Courier", 10, "bold"),
             bg="#121212", fg="#00ffff", wraplength=480, justify="center").pack(pady=(0, 8))

    status_var = tk_policy.track_var(root, tk.StringVar(master=root, value="Kamera, Video_Analiz veya URL secin. Video sonsuz dongude oynar."))
    tk.Label(root, textvariable=status_var, font=("Courier", 9),
             bg="#121212", fg="#aaaaaa", wraplength=480, justify="center").pack(pady=(0, 8))

    # --- Kameralar ---
    cam_frame = tk.LabelFrame(root, text=" CANLI KAMERALAR ", font=("Courier", 10, "bold"),
                              bg="#121212", fg="#ffb700")
    cam_frame.pack(fill=tk.X, padx=20, pady=5)
    for cam_id in (0, 1, 2):
        b = tk.Button(cam_frame, text=f">>> KAMERA {cam_id} <<<",
                      font=("Courier", 11, "bold"), bg="#1e1e1e", fg="white",
                      relief=tk.FLAT, command=lambda c=cam_id: _apply_source(engine, detector, c, root, status_var))
        b.pack(fill=tk.X, padx=10, pady=3)

    # --- Video_Analiz klasoru ---
    vid_frame = tk.LabelFrame(root, text=" VIDEO_ANALIZ KLASORU (SONSUZ DONGU) ", font=("Courier", 10, "bold"),
                              bg="#121212", fg="#00ff00")
    vid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

    list_frame = tk.Frame(vid_frame, bg="#121212")
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set,
                         font=("Courier", 10), bg="#1e1e1e", fg="#ffffff",
                         selectbackground="#ff0000", highlightthickness=0)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    videos = list_local_videos()
    if not videos:
        listbox.insert(tk.END, "(Video_Analiz klasoru bos — .mp4/.avi/.mov/.mkv atin)")
    else:
        for vp in videos:
            listbox.insert(tk.END, os.path.basename(vp))

    def play_selected_video():
        if not videos:
            status_var.set("[!] Video_Analiz klasoru bos.")
            return
        sel = listbox.curselection()
        if not sel:
            status_var.set("[!] Once listeden bir video secin.")
            return
        idx = sel[0]
        if idx >= len(videos):
            return
        _apply_source(engine, detector, videos[idx], root, status_var)

    tk.Button(vid_frame, text=">>> SECILI VIDEOYU OYNAT (LOOP) <<<",
              font=("Courier", 11, "bold"), bg="#8b0000", fg="white",
              relief=tk.FLAT, command=play_selected_video).pack(fill=tk.X, padx=10, pady=5)

    # --- Oynatma kontrolleri (duraklat / ileri-geri) ---
    play_frame = tk.LabelFrame(root, text=" OYNATMA (SPACE / , / .) ", font=("Courier", 10, "bold"),
                               bg="#121212", fg="#ffb700")
    play_frame.pack(fill=tk.X, padx=20, pady=5)
    pos_var = tk_policy.track_var(root, tk.StringVar(master=root, value="--:-- / --:--"))
    tk.Label(play_frame, textvariable=pos_var, font=("Courier", 10, "bold"),
             bg="#121212", fg="#ffffff").pack(pady=2)

    def _refresh_pos():
        # Once bekleyen gecis sonuclarini uygula (menu kapanmissa dur).
        try:
            if _poll_switches(root, status_var, engine, detector):
                return
        except Exception:
            pass
        try:
            if engine is not None and hasattr(engine, "get_playback_info"):
                info = engine.get_playback_info()
                if info.get("seekable") and info.get("dur"):
                    pos_var.set(f"{'|| DURAKLATILDI' if info['paused'] else '>> OYNATILIYOR'}  "
                                f"{info['pos']:.0f}sn / {info['dur']:.0f}sn")
                else:
                    lbl = "DURAKLATILDI" if info.get("paused") else "CANLI"
                    pos_var.set(f"{lbl} (seek yok: {info.get('source_type')})")
        except Exception:
            pass
        # Pencere kapandiysa tekrar zamanlama (invalid command name guard).
        tk_policy.schedule(root, 500, _refresh_pos, root._after_ids)

    btn_row = tk.Frame(play_frame, bg="#121212")
    btn_row.pack(fill=tk.X, padx=10, pady=5)
    tk.Button(btn_row, text="⏸/▶ DURAKLAT",
              font=("Courier", 10, "bold"), bg="#1e1e1e", fg="white", relief=tk.FLAT,
              command=lambda: (engine.toggle_pause() if engine else None, _refresh_pos())).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    tk.Button(btn_row, text="◀◀ -10sn",
              font=("Courier", 10, "bold"), bg="#1e1e1e", fg="white", relief=tk.FLAT,
              command=lambda: status_var.set("[+] -10sn" if (engine and engine.seek(-10)) else "[!] Bu kaynakta seek yok (canli).")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    tk.Button(btn_row, text="+10sn ▶▶",
              font=("Courier", 10, "bold"), bg="#1e1e1e", fg="white", relief=tk.FLAT,
              command=lambda: status_var.set("[+] +10sn" if (engine and engine.seek(10)) else "[!] Bu kaynakta seek yok (canli).")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    _refresh_pos()

    # --- RTSP (canli, dusuk gecikme) ---
    rtsp_frame = tk.LabelFrame(root, text=" RTSP CANLI (SEEK YOK) ", font=("Courier", 10, "bold"),
                               bg="#121212", fg="#ff8800")
    rtsp_frame.pack(fill=tk.X, padx=20, pady=5)
    rtsp_var = tk_policy.track_var(root, tk.StringVar(master=root))
    rtsp_entry = tk.Entry(rtsp_frame, textvariable=rtsp_var, font=("Courier", 10),
                          bg="#1e1e1e", fg="#ffffff", insertbackground="white", relief=tk.FLAT)
    rtsp_entry.pack(fill=tk.X, padx=10, pady=5)
    rtsp_entry.insert(0, "rtsp://ip:554/stream")

    def play_rtsp():
        url = rtsp_var.get().strip()
        if not url or url.startswith("rtsp://ip"):
            status_var.set("[!] Gecerli bir rtsp:// URL girin.")
            return
        _apply_source(engine, detector, url, root, status_var)

    tk.Button(rtsp_frame, text=">>> RTSP BAGLAN <<<",
              font=("Courier", 11, "bold"), bg="#663300", fg="white",
              relief=tk.FLAT, command=play_rtsp).pack(fill=tk.X, padx=10, pady=5)

    # --- YouTube (VOD indirilir / LIVE direkt) ---
    yt_frame = tk.LabelFrame(root, text=" YOUTUBE (VOD=indir+loop / LIVE=direkt) ", font=("Courier", 10, "bold"),
                             bg="#121212", fg="#00ffff")
    yt_frame.pack(fill=tk.X, padx=20, pady=5)
    url_var = tk_policy.track_var(root, tk.StringVar(master=root))
    url_entry = tk.Entry(yt_frame, textvariable=url_var, font=("Courier", 10),
                         bg="#1e1e1e", fg="#ffffff", insertbackground="white", relief=tk.FLAT)
    url_entry.pack(fill=tk.X, padx=10, pady=5)
    url_entry.insert(0, "https://youtube.com/watch?v=...")

    def play_url():
        url = url_var.get().strip()
        if not url or url.startswith("https://youtube.com/watch?v=..."):
            status_var.set("[!] Gecerli bir YouTube URL girin.")
            return
        status_var.set("[*] YouTube indiriliyor (loop+seek icin, ilk sefer biraz surer)...")
        _apply_source(engine, detector, url, root, status_var)

    tk.Button(yt_frame, text=">>> YOUTUBE BAGLAN <<<",
              font=("Courier", 11, "bold"), bg="#003366", fg="white",
              relief=tk.FLAT, command=play_url).pack(fill=tk.X, padx=10, pady=5)

    tk.Label(root, text=f"Klasor: {SystemState.VIDEO_DIR}", font=("Courier", 8),
             bg="#121212", fg="#666666", wraplength=480).pack(pady=5)

    try:
        root.mainloop()
    finally:
        tk_policy.safe_close(root, getattr(root, "_after_ids", None), getattr(root, "_trace_pairs", None))

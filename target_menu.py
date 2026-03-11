import tkinter as tk
from config import SystemState

def open_target_menu():
    """Taktiksel Hedef Seçim Paneli (Arama ve Demir Hafıza Entegreli)"""
    root = tk.Tk()
    root.title("OMNIVISION - HEDEF KONTROL PANELİ")
    root.geometry("450x600")
    root.attributes('-topmost', True) # Her zaman en üstte kal
    root.configure(bg="#121212")

    # --- DEMİR HAFIZA (IRON-CLAD MEMORY) ---
    # Listeyi filtrelerken eski seçimlerin silinmemesi için hafıza kümesi
    selected_memory = set(SystemState.ACTIVE_TARGET_IDS)
    current_displayed_ids = []

    # Sınıfları ID'ye göre değil, A'dan Z'ye alfabetik olarak sırala
    class_map = SystemState.MODEL_CLASSES
    sorted_classes = sorted(class_map.items(), key=lambda x: x[1].lower())

    # --- ARAYÜZ BİLEŞENLERİ ---
    tk.Label(root, text="[ İZLENECEK HEDEFLERİ SEÇİN ]", font=("Courier", 14, "bold"), bg="#121212", fg="#00ff00").pack(pady=10)

    # 1. Arama Çubuğu (Search Radar)
    search_frame = tk.Frame(root, bg="#121212")
    search_frame.pack(fill=tk.X, padx=20, pady=5)
    
    tk.Label(search_frame, text="[ ARAMA ]:", font=("Courier", 12, "bold"), bg="#121212", fg="#00ffff").pack(side=tk.LEFT)
    
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Courier", 12, "bold"), 
                            bg="#1e1e1e", fg="#ffffff", insertbackground="white", relief=tk.FLAT)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    search_entry.focus() # Menü açıldığında imleç direkt aramada başlar!

    # 2. Liste Çerçevesi
    frame = tk.Frame(root, bg="#121212")
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, 
                         font=("Courier", 12), bg="#1e1e1e", fg="#ffffff", selectbackground="#ff0000", highlightthickness=0)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    # --- DİNAMİK FİLTRELEME MOTORU ---
    def update_list(*args):
        search_term = search_var.get().lower()
        listbox.delete(0, tk.END)
        current_displayed_ids.clear()
        
        for cls_id, cls_name in sorted_classes:
            if search_term in cls_name.lower():
                listbox.insert(tk.END, f" ID: {cls_id:02d} | {cls_name.upper()}")
                current_displayed_ids.append(cls_id)
                
                # Eğer bu ID hafızadaysa, listeye eklendiğinde anında kırmızı (seçili) yap
                if cls_id in selected_memory:
                    listbox.select_set(listbox.size() - 1)

    # --- TIKLAMA VE HAFIZA SENKRONİZASYONU ---
    def on_select(event):
        selected_indices = listbox.curselection()
        # Ekranda görünenlerden hangileri seçiliyse hafızaya al, değilse hafızadan sil
        for i, cls_id in enumerate(current_displayed_ids):
            if i in selected_indices:
                selected_memory.add(cls_id)
            else:
                selected_memory.discard(cls_id)

    # Tetikleyicileri Bağla
    listbox.bind('<<ListboxSelect>>', on_select)
    search_var.trace_add("write", update_list) # Klavyeye her basıldığında listeyi güncelle

    # --- ONAY VE KİLİTLEME ---
    def apply_selection():
        SystemState.ACTIVE_TARGET_IDS = list(selected_memory)
        SystemState.ACTIVE_TARGET_NAMES = [class_map[cid].upper() for cid in SystemState.ACTIVE_TARGET_IDS]
        root.destroy() # Arayüzü kapat, karargaha dön

    btn = tk.Button(root, text=">>> HEDEFLERİ KİLİTLE <<<", command=apply_selection, 
                    bg="#8b0000", fg="white", font=("Courier", 14, "bold"), relief=tk.FLAT)
    btn.pack(pady=15, fill=tk.X, padx=20)

    # Başlangıçta listeyi tam doldur
    update_list()

    root.mainloop()
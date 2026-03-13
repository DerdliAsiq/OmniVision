import speech_recognition as sr

print("\n" + "="*50)
print("[*] SİSTEMDEKİ MİKROFONLAR TARANIYOR...")
print("="*50)

try:
    mics = sr.Microphone.list_microphone_names()
    for index, name in enumerate(mics):
        print(f"[{index}] -> {name}")
except Exception as e:
    print(f"[X] Mikrofonlar listelenemedi: {e}")

print("\n[*] Varsayılan Mikrofon Test Ediliyor...")
r = sr.Recognizer()

try:
    with sr.Microphone() as source:
        print("[*] Gürültü kalibrasyonu yapılıyor (1 saniye sessiz kal)...")
        r.adjust_for_ambient_noise(source, duration=1)
        
        print("\n[🎙️] DİNLİYORUM... (Lütfen 3 saniye boyunca mikrofona konuş!)")
        # Sadece 5 saniye bekler, ses gelmezse timeout atar
        audio = r.listen(source, timeout=5, phrase_time_limit=5)
        
        print(f"\n[+] BAŞARILI! Ses verisi yakalandı. Boyut: {len(audio.get_wav_data())} bayt.")
        print("[+] J.A.R.V.I.S. kulakları operasyona tamamen hazır!")
        
except sr.WaitTimeoutError:
    print("\n[X] HATA: 5 saniye boyunca hiçbir ses duyulmadı (Mikrofon sağır veya sessizde).")
except Exception as e:
    print(f"\n[X] KRİTİK HATA: {e}")
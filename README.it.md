# <img src="icon.png" width="40" height="40" align="absmiddle"> Ultimora

**Ultimora** è un widget desktop moderno e leggero scritto in Python con PyQt6. Mostra le ultime notizie dei tuoi feed RSS preferiti accanto a una card meteo.

https://github.com/user-attachments/assets/a176b590-960d-4478-868c-571e036402e7

## Requisiti
- Linux (GNOME/Mint/XFCE)
- Python 3.8+

Si può usare in due modi: il pacchetto `.deb` (consigliato, versione più recente) oppure la versione Python manuale.

---

## 1. Installazione con il pacchetto .deb (consigliata)

Scarica l'ultimo `.deb` dalla pagina Releases di questo repository, poi installalo. Le dipendenze vengono installate in automatico:

```bash
sudo apt install ./ultimora_*.deb
```

Avvialo cliccando su **News** nel menu delle applicazioni, oppure da terminale:

```bash
ultimora
```

### Funzioni
- Notizie da qualsiasi feed RSS/XML, tutte le notizie caricate, scorrimento con scrollbar nascosta
- Pannello Impostazioni (⚙): incolla l'URL di un feed per aggiungerlo, ✖ per rimuoverlo
- Notizie aggiornate automaticamente ogni 15 minuti
- Modalità mista: tutti i feed uniti e ordinati per orario, oppure raggruppati per fonte
- Tasto Nascondi: il widget si riduce a una piccola icona, clic per mostrarlo di nuovo
- Immagini in cache, impostazioni salvate tra una sessione e l'altra

### File
- Configurazione: `~/.config/ultimora/config.json`
- Cache delle immagini: `~/.cache/ultimora/` (i file più vecchi di 7 giorni vengono rimossi all'avvio)

### Disinstallazione
```bash
sudo apt remove ultimora
```

---

## 2. Installazione manuale (versione Python)

La versione precedente del widget, eseguita direttamente dal sorgente.

### Dipendenze
```bash
sudo apt update
sudo apt install python3-pyqt6 python3-feedparser python3-pil
```

### Avvio
```bash
python3 ultimora.py
```

### Avvio automatico (Systemd)
1. mkdir -p ~/.config/systemd/user
2. nano ~/.config/systemd/user/ultimora.service

```ini
[Unit]
Description=Ultimora Widget
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 %h/scripts/ultimora/ultimora.py
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

3. systemctl --user daemon-reload && systemctl --user enable --now ultimora.service

Modifica il percorso in `ExecStart` se lo script non si trova in `~/scripts/ultimora/`.

### Passare alla versione .deb
Se usi la versione manuale come servizio systemd, rimuovi prima il servizio, altrimenti si avviano due copie del widget:

```bash
systemctl --user disable --now ultimora.service
rm ~/.config/systemd/user/ultimora.service
systemctl --user daemon-reload
```

Poi installa il `.deb` come descritto nella sezione 1. Dopo puoi eliminare la vecchia cartella dello script.

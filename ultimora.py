#!/usr/bin/env python3
import sys
import os
import re
import html
import time
from datetime import datetime, timedelta
import urllib.request
import json
import subprocess
import feedparser
import webbrowser
from PIL import Image, ImageDraw, ImageFont, ImageOps

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QLabel
)

# ==============================================================================
# LOCALIZZAZIONE E TEMATIZZAZIONE DA GNOME
# ==============================================================================
def get_gnome_weather_location(default="Roma"):
    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.Weather", "locations"],
            capture_output=True, text=True, timeout=2
        )
        out = res.stdout.strip()
        match = re.search(r"'([^']+)'", out)
        if match:
            city = match.group(1).strip()
            if city:
                return city
    except Exception:
        pass
    return default

def is_gnome_dark_mode():
    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2
        )
        out = res.stdout.strip().lower()
        if "dark" in out:
            return True
    except Exception:
        pass
    return False

WEATHER_CITY = get_gnome_weather_location("Roma")

def get_theme_colors(is_dark):
    if is_dark:
        return {
            "CARD_BG": (32, 33, 36),         # #202124 (Google Dark)
            "TEXT_COLOR": (241, 243, 244),    # #f1f3f4
            "SUBTEXT_COLOR": (154, 160, 166),
            "FOOTER_COLOR": (138, 180, 248),  # #8ab4f8
            "LINE_COLOR": (60, 64, 67)
        }
    else:
        return {
            "CARD_BG": (243, 243, 243),       # #f3f3f3
            "TEXT_COLOR": (0, 0, 0),
            "SUBTEXT_COLOR": (100, 100, 100),
            "FOOTER_COLOR": (0, 37, 134),     # #002586
            "LINE_COLOR": (210, 210, 210)
        }

RSS_FEEDS = [
    {"name": "TGCOM24", "url": "https://www.tgcom24.mediaset.it/rss/homepage.xml"},
    {"name": "BBC UK", "url": "https://feeds.bbci.co.uk/news/uk/rss.xml"},
]

FONT_PATH = os.path.expanduser("~/scripts/ultimora/Google_Sans/GoogleSans-VariableFont_GRAD,opsz,wght.ttf")

def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def get_font(size):
    if os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()

def get_owm_icon_code(desc, is_dark):
    d = desc.lower()
    if "sun" in d or "clear" in d:
        return "01d" if not is_dark else "01n"
    elif "partly" in d or "few" in d:
        return "02d" if not is_dark else "02n"
    elif "cloud" in d or "overcast" in d:
        return "04d"
    elif "rain" in d or "shower" in d or "drizzle" in d:
        return "10d"
    elif "thunder" in d:
        return "11d"
    elif "snow" in d or "sleet" in d or "flurry" in d:
        return "13d"
    elif "fog" in d or "mist" in d or "haze" in d:
        return "50d"
    return "02d"

# ==============================================================================
# GENERAZIONE CARD METEO DINAMICA
# ==============================================================================
def create_weather_image(city, is_dark):
    colors = get_theme_colors(is_dark)
    SCALE = 2
    W, H = 450 * SCALE, 145 * SCALE

    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([(0, 0), (W - 1, H - 1)], radius=16 * SCALE, fill=colors["CARD_BG"] + (255,))

    current_temp = "N/A"
    condition = "Meteo non disponibile"
    current_icon_url = ""
    hourly_forecast = []

    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            current = data['current_condition'][0]
            current_temp = f"{current['temp_C']}°C"
            condition = current['weatherDesc'][0]['value']
            current_owm = get_owm_icon_code(condition, is_dark)
            current_icon_url = f"https://openweathermap.org/img/wn/{current_owm}@2x.png"

            now_dt = datetime.now()
            all_hourly = []
            for day in data['weather'][:2]:
                for h in day['hourly']:
                    h_val = int(h['time']) // 100
                    all_hourly.append({
                        "hour_val": h_val,
                        "tempC": h['tempC'],
                        "desc": h['weatherDesc'][0]['value']
                    })

            for step in range(1, 6):
                target_time = now_dt + timedelta(hours=step)
                target_hour = target_time.hour
                match = min(all_hourly, key=lambda x: abs(x["hour_val"] - target_hour))
                owm_code = get_owm_icon_code(match["desc"], is_dark)
                icon_url = f"https://openweathermap.org/img/wn/{owm_code}@2x.png"

                hourly_forecast.append({
                    "time": f"{target_hour:02d}:00",
                    "temp": f"{match['tempC']}°",
                    "icon_url": icon_url
                })
    except Exception:
        pass

    font_title = get_font(13 * SCALE)
    font_sub = get_font(11 * SCALE)
    font_temp = get_font(22 * SCALE)
    font_hour = get_font(10 * SCALE)

    draw.text((16 * SCALE, 12 * SCALE), f"Meteo: {city}", font=font_title, fill=colors["TEXT_COLOR"] + (255,))
    draw.text((16 * SCALE, 32 * SCALE), condition, font=font_sub, fill=colors["SUBTEXT_COLOR"] + (255,))

    if current_icon_url:
        big_size = 42 * SCALE
        try:
            tmp_big = f"/tmp/owm_big_{hash(current_icon_url)}.png"
            if not os.path.exists(tmp_big):
                req_big = urllib.request.Request(current_icon_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_big, timeout=2) as resp_big, open(tmp_big, 'wb') as f_big:
                    f_big.write(resp_big.read())
            
            big_im = Image.open(tmp_big).convert("RGBA")
            big_im = big_im.resize((big_size, big_size), Image.Resampling.LANCZOS)
            card.paste(big_im, (290 * SCALE, 8 * SCALE), big_im)
        except Exception:
            pass

    draw.text((345 * SCALE, 14 * SCALE), current_temp, font=font_temp, fill=colors["FOOTER_COLOR"] + (255,))

    if hourly_forecast:
        box_y = 62 * SCALE
        draw.line([(16 * SCALE, box_y), (W - 16 * SCALE, box_y)], fill=colors["LINE_COLOR"] + (255,), width=SCALE)
        
        col_width = (W - 32 * SCALE) / len(hourly_forecast)
        for idx, slot in enumerate(hourly_forecast):
            x_pos = int(16 * SCALE + idx * col_width + (col_width / 2))
            
            draw.text((x_pos - 14 * SCALE, box_y + 6 * SCALE), slot["time"], font=font_hour, fill=colors["SUBTEXT_COLOR"] + (255,))
            
            icon_size = 30 * SCALE
            try:
                tmp_icon = f"/tmp/owm_ico_{hash(slot['icon_url'])}.png"
                if not os.path.exists(tmp_icon):
                    req_ico = urllib.request.Request(slot["icon_url"], headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_ico, timeout=2) as resp_ico, open(tmp_icon, 'wb') as f_ico:
                        f_ico.write(resp_ico.read())
                
                ico_im = Image.open(tmp_icon).convert("RGBA")
                ico_im = ico_im.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                card.paste(ico_im, (x_pos - int(icon_size / 2), box_y + 18 * SCALE), ico_im)
            except Exception:
                pass

            draw.text((x_pos - 10 * SCALE, box_y + 52 * SCALE), slot["temp"], font=font_hour, fill=colors["TEXT_COLOR"] + (255,))

    final_card = card.resize((450, 145), Image.Resampling.LANCZOS)
    im_data = final_card.tobytes("raw", "RGBA")
    qim = QImage(im_data, 450, 145, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qim)

# ==============================================================================
# GENERAZIONE CARD NOTIZIE DINAMICA
# ==============================================================================
def create_card_image(title, pub_time, source_name, img_url, is_dark):
    colors = get_theme_colors(is_dark)
    SCALE = 2
    W, H = 220 * SCALE, 220 * SCALE

    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([(0, 0), (W - 1, H - 1)], radius=16 * SCALE, fill=colors["CARD_BG"] + (255,))

    img_w, img_h = (220 - 16) * SCALE, 115 * SCALE
    if img_url:
        tmp_img = f"/tmp/thumb_{hash(img_url)}.jpg"
        try:
            if not os.path.exists(tmp_img):
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3) as resp, open(tmp_img, 'wb') as f:
                    f.write(resp.read())
            
            im = Image.open(tmp_img).convert("RGB")
            im = ImageOps.fit(im, (img_w, img_h), Image.Resampling.LANCZOS, centering=(0.5, 0.3))
            
            mask = Image.new("L", (img_w, img_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (img_w, img_h)], radius=12 * SCALE, fill=255)
            
            card.paste(im, (8 * SCALE, 8 * SCALE), mask)
        except Exception:
            pass

    font_title = get_font(12 * SCALE)
    font_footer = get_font(10 * SCALE)

    lines = wrap_text(title, font_title, W - (24 * SCALE), draw)
    display_lines = lines[:3]
    if len(lines) > 3:
        display_lines[-1] += "..."

    y_text = (115 + 15) * SCALE
    for line in display_lines:
        draw.text((12 * SCALE, y_text), line, font=font_title, fill=colors["TEXT_COLOR"] + (255,))
        y_text = int(y_text + (15 * SCALE))

    footer_text = f"{pub_time} - {source_name}"
    draw.text((12 * SCALE, H - (20 * SCALE)), footer_text, font=font_footer, fill=colors["FOOTER_COLOR"] + (255,))

    final_card = card.resize((220, 220), Image.Resampling.LANCZOS)
    im_data = final_card.tobytes("raw", "RGBA")
    qim = QImage(im_data, 220, 220, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qim)

class ClickableLabel(QLabel):
    def __init__(self, link_url):
        super().__init__()
        self.link_url = link_url
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.link_url:
            webbrowser.open(self.link_url)

class FeedWorker(QThread):
    cards_ready = pyqtSignal(list)

    def run(self):
        items_data = []
        for feed in RSS_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                # Prende le prime 3 notizie da TGCOM24 e le prime 3 da BBC UK
                for entry in parsed.entries:
                    title = clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    
                    pub_time = "12:00"
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_time = time.strftime("%H:%M", entry.published_parsed)
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        pub_time = time.strftime("%H:%M", entry.updated_parsed)

                    img_url = ""
                    if "enclosures" in entry and entry.enclosures:
                        img_url = entry.enclosures[0].get("href", "")
                    if not img_url and "media_content" in entry:
                        img_url = entry.media_content[0].get("url", "")
                    if not img_url and "media_thumbnail" in entry:
                        img_url = entry.media_thumbnail[0].get("url", "")
                    
                    items_data.append({
                        "title": title,
                        "link": link,
                        "time": pub_time,
                        "source": feed["name"],
                        "img_url": img_url
                    })
            except Exception:
                pass

        self.cards_ready.emit(items_data)

class NewsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_is_dark = is_gnome_dark_mode()
        self.cached_items = []
        self.initUI()
        self.load_feeds()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.check_theme_change)
        self.theme_timer.start(3000)

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        
        # Altezza fissa impostata a 880
        self.setFixedSize(480, 880)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. CARD METEO FISSA
        self.weather_lbl = QLabel()
        main_layout.addWidget(self.weather_lbl)

        # 2. AREA SCROLLABILE CON SCROLLBAR ATTIVA AL BISOGNO
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.grid_layout = QVBoxLayout(self.container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(8)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        # 3. FOOTER FISSO IN BASSO (CHIUDI / RICARICA)
        self.footer_layout = QHBoxLayout()
        self.footer_layout.setContentsMargins(10, 2, 10, 2)

        self.reload_btn = QLabel("🔄 Ricarica")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.mousePressEvent = lambda e: self.load_feeds()

        self.close_btn = QLabel("✖ Chiudi")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.mousePressEvent = lambda e: self.close()

        self.update_footer_style()

        self.footer_layout.addWidget(self.reload_btn)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(self.footer_layout)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 500, 20)
        
        self.weather_lbl.setPixmap(create_weather_image(WEATHER_CITY, self.current_is_dark))

    def update_footer_style(self):
        colors = get_theme_colors(self.current_is_dark)
        style = f"color: rgb({colors['SUBTEXT_COLOR'][0]}, {colors['SUBTEXT_COLOR'][1]}, {colors['SUBTEXT_COLOR'][2]}); font-size: 11px; font-weight: bold;"
        self.reload_btn.setStyleSheet(style)
        self.close_btn.setStyleSheet(style)

    def check_theme_change(self):
        new_is_dark = is_gnome_dark_mode()
        if new_is_dark != self.current_is_dark:
            self.current_is_dark = new_is_dark
            self.update_footer_style()
            self.weather_lbl.setPixmap(create_weather_image(WEATHER_CITY, self.current_is_dark))
            if self.cached_items:
                self.display_cards(self.cached_items)

    def load_feeds(self):
        self.worker = FeedWorker()
        self.worker.cards_ready.connect(self.on_feeds_loaded)
        self.worker.start()

    def on_feeds_loaded(self, items):
        self.cached_items = items
        self.display_cards(items)

    def display_cards(self, items):
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for i in range(0, len(items), 2):
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            pix1 = create_card_image(items[i]["title"], items[i]["time"], items[i]["source"], items[i]["img_url"], self.current_is_dark)
            lbl1 = ClickableLabel(items[i]["link"])
            lbl1.setPixmap(pix1)
            row_layout.addWidget(lbl1)

            if i + 1 < len(items):
                pix2 = create_card_image(items[i+1]["title"], items[i+1]["time"], items[i+1]["source"], items[i+1]["img_url"], self.current_is_dark)
                lbl2 = ClickableLabel(items[i+1]["link"])
                lbl2.setPixmap(pix2)
                row_layout.addWidget(lbl2)

            self.grid_layout.addWidget(row_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NewsWidget()
    window.show()
    sys.exit(app.exec())

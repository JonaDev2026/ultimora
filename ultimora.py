#!/usr/bin/env python3
import sys
import os
import re
import html
import time
import calendar
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
    QScrollArea, QLabel, QLineEdit, QPushButton, QFrame
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
            tmp_big = cache_path("owm_big", current_icon_url, "png")
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
                tmp_icon = cache_path("owm_ico", slot['icon_url'], "png")
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
        tmp_img = cache_path("thumb", img_url, "jpg")
        try:
            
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

import hashlib

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "ultimora")

def cache_path(prefix, url, ext):
    return os.path.join(CACHE_DIR, f"{prefix}_{hashlib.md5(url.encode('utf-8')).hexdigest()}.{ext}")

def init_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        limit = time.time() - 7 * 24 * 3600
        for name in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, name)
            try:
                if os.path.isfile(fp) and os.path.getmtime(fp) < limit:
                    os.remove(fp)
            except Exception:
                pass
    except Exception:
        pass

init_cache()

from concurrent.futures import ThreadPoolExecutor

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def save_config(cfg):
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass

def load_config():
    cfg = {
        "feeds": [{"name": f["name"], "url": f["url"]} for f in RSS_FEEDS],
        "mixed": True,
        "collapsed": False,
        "refresh_minutes": 15,
    }
    if not os.path.exists(CONFIG_PATH):
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("feeds"), list):
            cfg["feeds"] = [
                {"name": str(x.get("name") or x["url"])[:40], "url": x["url"]}
                for x in data["feeds"] if isinstance(x, dict) and x.get("url")
            ]
        for k in ("mixed", "collapsed"):
            if isinstance(data.get(k), bool):
                cfg[k] = data[k]
        rm = data.get("refresh_minutes")
        if isinstance(rm, (int, float)) and not isinstance(rm, bool) and rm >= 1:
            cfg["refresh_minutes"] = rm
    except Exception:
        pass
    return cfg

def prefetch_image(img_url):
    tmp_img = cache_path("thumb", img_url, "jpg")
    if os.path.exists(tmp_img):
        return
    try:
        req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = resp.read()
        with open(tmp_img, 'wb') as f:
            f.write(data)
    except Exception:
        pass

class FeedWorker(QThread):
    cards_ready = pyqtSignal(list)

    def __init__(self, feeds):
        super().__init__()
        self.feeds = feeds

    def fetch_feed(self, feed):
        items = []
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")

                pub_time = "12:00"
                ts = 0
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = time.strftime("%H:%M", entry.published_parsed)
                    ts = calendar.timegm(entry.published_parsed)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_time = time.strftime("%H:%M", entry.updated_parsed)
                    ts = calendar.timegm(entry.updated_parsed)

                img_url = ""
                if "enclosures" in entry and entry.enclosures:
                    img_url = entry.enclosures[0].get("href", "")
                if not img_url and "media_content" in entry:
                    img_url = entry.media_content[0].get("url", "")
                if not img_url and "media_thumbnail" in entry:
                    img_url = entry.media_thumbnail[0].get("url", "")

                items.append({
                    "title": title,
                    "link": link,
                    "time": pub_time,
                    "ts": ts,
                    "source": feed["name"],
                    "img_url": img_url
                })
        except Exception:
            pass
        return items

    def run(self):
        items_data = []
        if self.feeds:
            with ThreadPoolExecutor(max_workers=min(8, len(self.feeds))) as ex:
                for res in ex.map(self.fetch_feed, self.feeds):
                    items_data.extend(res)
            urls = list({i["img_url"] for i in items_data if i["img_url"]})
            if urls:
                with ThreadPoolExecutor(max_workers=8) as ex:
                    list(ex.map(prefetch_image, urls))
        self.cards_ready.emit(items_data)

class AddFeedWorker(QThread):
    result = pyqtSignal(bool, str, str, str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            parsed = feedparser.parse(self.url)
            if not parsed.entries:
                self.result.emit(False, "", self.url, "Feed non valido o non raggiungibile")
                return
            name = ""
            try:
                name = clean_text(parsed.feed.get("title", ""))
            except Exception:
                pass
            if not name:
                name = urllib.parse.urlparse(self.url).netloc
            self.result.emit(True, name[:40], self.url, "")
        except Exception:
            self.result.emit(False, "", self.url, "Errore di connessione")

class NewsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_is_dark = is_gnome_dark_mode()
        self.cached_items = []
        self.cfg = load_config()
        self.mixed = self.cfg["mixed"]
        self.collapsed = False
        self.settings_open = False
        self.initUI()
        if self.cfg["collapsed"]:
            self.collapse_widget()
        self.load_feeds()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.check_theme_change)
        self.theme_timer.start(3000)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_feeds)
        self.refresh_timer.start(int(self.cfg["refresh_minutes"] * 60 * 1000))

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
        self.build_settings_panel()
        main_layout.addWidget(self.settings_panel, 1)

        # 3. FOOTER FISSO IN BASSO (CHIUDI / RICARICA)
        self.footer_layout = QHBoxLayout()
        self.footer_layout.setContentsMargins(10, 2, 10, 2)

        self.reload_btn = QLabel("🔄 Ricarica")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.mousePressEvent = lambda e: self.load_feeds()

        self.close_btn = QLabel("✖ Chiudi")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.mousePressEvent = lambda e: self.close()

        self.shuffle_btn = QLabel("🔀 Per fonte" if self.mixed else "🔀 Mescola")
        self.shuffle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shuffle_btn.mousePressEvent = lambda e: self.toggle_mix()

        self.settings_btn = QLabel("⚙ Impostazioni")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.mousePressEvent = lambda e: self.toggle_settings()

        self.hide_btn = QLabel("⬇ Nascondi")
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.mousePressEvent = lambda e: self.collapse_widget()

        self.icon_lbl = QLabel("📰")
        self.icon_lbl.setFixedSize(56, 56)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_lbl.mousePressEvent = lambda e: self.expand_widget()
        self.icon_lbl.hide()

        self.update_footer_style()

        self.footer_layout.addWidget(self.reload_btn)
        self.footer_layout.addSpacing(14)
        self.footer_layout.addWidget(self.shuffle_btn)
        self.footer_layout.addSpacing(12)
        self.footer_layout.addWidget(self.settings_btn)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.hide_btn)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(self.footer_layout)
        main_layout.addWidget(self.icon_lbl)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 500, 20)
        
        self.weather_lbl.setPixmap(create_weather_image(WEATHER_CITY, self.current_is_dark))

    def collapse_widget(self):
        if self.collapsed:
            return
        self.collapsed = True
        self._exp_pos = self.pos()
        for w in (self.weather_lbl, self.scroll_area, self.settings_panel, self.reload_btn,
                  self.shuffle_btn, self.settings_btn, self.hide_btn, self.close_btn):
            w.hide()
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_lbl.show()
        self.setFixedSize(56, 56)
        self.move(self._exp_pos.x() + 480 - 56, self._exp_pos.y())
        self.cfg["collapsed"] = True
        save_config(self.cfg)

    def expand_widget(self):
        if not self.collapsed:
            return
        self.collapsed = False
        self.icon_lbl.hide()
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().setSpacing(8)
        self.footer_layout.setContentsMargins(10, 2, 10, 2)
        for w in (self.weather_lbl, self.reload_btn, self.shuffle_btn,
                  self.settings_btn, self.hide_btn, self.close_btn):
            w.show()
        self.scroll_area.setVisible(not self.settings_open)
        self.settings_panel.setVisible(self.settings_open)
        self.setFixedSize(480, 880)
        self.move(self._exp_pos)
        self.cfg["collapsed"] = False
        save_config(self.cfg)

    def build_settings_panel(self):
        self.settings_panel = QWidget()
        lay = QVBoxLayout(self.settings_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.set_title = QLabel("Feed RSS / XML")
        lay.addWidget(self.set_title)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Incolla qui l'URL del feed (https://...)")
        self.url_input.returnPressed.connect(self.add_feed)
        self.add_btn = QPushButton("Aggiungi")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_feed)
        row.addWidget(self.url_input)
        row.addWidget(self.add_btn)
        lay.addLayout(row)

        self.set_status = QLabel("")
        lay.addWidget(self.set_status)

        self.feeds_scroll = QScrollArea()
        self.feeds_scroll.setWidgetResizable(True)
        self.feeds_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feeds_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feeds_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        feeds_box = QWidget()
        feeds_box.setStyleSheet("background: transparent;")
        self.feeds_list_layout = QVBoxLayout(feeds_box)
        self.feeds_list_layout.setContentsMargins(0, 0, 0, 0)
        self.feeds_list_layout.setSpacing(6)
        self.feeds_scroll.setWidget(feeds_box)
        lay.addWidget(self.feeds_scroll, 1)

        self.settings_panel.hide()

    def style_settings(self):
        c = get_theme_colors(self.current_is_dark)
        def rgb(k):
            t = c[k]
            return f"rgb({t[0]}, {t[1]}, {t[2]})"
        self.set_title.setStyleSheet(f"color: {rgb('TEXT_COLOR')}; font-size: 13px; font-weight: bold; background: transparent;")
        self.set_status.setStyleSheet(f"color: {rgb('SUBTEXT_COLOR')}; font-size: 11px; background: transparent;")
        self.url_input.setStyleSheet(f"QLineEdit {{ background: {rgb('CARD_BG')}; color: {rgb('TEXT_COLOR')}; border: 1px solid {rgb('LINE_COLOR')}; border-radius: 8px; padding: 6px 8px; font-size: 12px; }}")
        self.add_btn.setStyleSheet(f"QPushButton {{ background: {rgb('CARD_BG')}; color: {rgb('TEXT_COLOR')}; border: 1px solid {rgb('LINE_COLOR')}; border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: bold; }}")
        self.refresh_feed_list()

    def refresh_feed_list(self):
        c = get_theme_colors(self.current_is_dark)
        def rgb(k):
            t = c[k]
            return f"rgb({t[0]}, {t[1]}, {t[2]})"
        while self.feeds_list_layout.count():
            it = self.feeds_list_layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        for f in self.cfg["feeds"]:
            fr = QFrame()
            fr.setObjectName("feedrow")
            fr.setStyleSheet(f"QFrame#feedrow {{ background: {rgb('CARD_BG')}; border-radius: 10px; }}")
            h = QHBoxLayout(fr)
            h.setContentsMargins(12, 8, 12, 8)
            nm = QLabel(f["name"])
            nm.setToolTip(f["url"])
            nm.setStyleSheet(f"color: {rgb('TEXT_COLOR')}; font-size: 12px; background: transparent;")
            x = QLabel("✖")
            x.setCursor(Qt.CursorShape.PointingHandCursor)
            x.setStyleSheet(f"color: {rgb('SUBTEXT_COLOR')}; font-size: 12px; font-weight: bold; background: transparent;")
            x.mousePressEvent = lambda e, u=f["url"]: self.remove_feed(u)
            h.addWidget(nm)
            h.addStretch()
            h.addWidget(x)
            self.feeds_list_layout.addWidget(fr)
        self.feeds_list_layout.addStretch()

    def toggle_settings(self):
        self.settings_open = not self.settings_open
        self.scroll_area.setVisible(not self.settings_open)
        self.settings_panel.setVisible(self.settings_open)
        self.settings_btn.setText("↩ Indietro" if self.settings_open else "⚙ Impostazioni")
        if self.settings_open:
            self.set_status.setText("")
            self.refresh_feed_list()

    def add_feed(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            self.set_status.setText("L'URL deve iniziare con http:// o https://")
            return
        if any(f["url"] == url for f in self.cfg["feeds"]):
            self.set_status.setText("Feed gia' presente")
            return
        w = getattr(self, "add_worker", None)
        if w is not None and w.isRunning():
            return
        self.add_btn.setEnabled(False)
        self.set_status.setText("Verifica in corso...")
        self.add_worker = AddFeedWorker(url)
        self.add_worker.result.connect(self.on_feed_checked)
        self.add_worker.start()

    def on_feed_checked(self, ok, name, url, msg):
        self.add_btn.setEnabled(True)
        if not ok:
            self.set_status.setText(msg)
            return
        self.cfg["feeds"].append({"name": name, "url": url})
        save_config(self.cfg)
        self.url_input.clear()
        self.set_status.setText("Aggiunto: " + name)
        self.refresh_feed_list()
        self.load_feeds()

    def remove_feed(self, url):
        self.cfg["feeds"] = [f for f in self.cfg["feeds"] if f["url"] != url]
        save_config(self.cfg)
        self.set_status.setText("Feed rimosso")
        self.refresh_feed_list()
        self.load_feeds()

    def toggle_mix(self):
        self.mixed = not self.mixed
        self.cfg["mixed"] = self.mixed
        save_config(self.cfg)
        self.shuffle_btn.setText("🔀 Per fonte" if self.mixed else "🔀 Mescola")
        if self.cached_items:
            self.display_cards(self.cached_items)

    def update_footer_style(self):
        colors = get_theme_colors(self.current_is_dark)
        style = f"color: rgb({colors['SUBTEXT_COLOR'][0]}, {colors['SUBTEXT_COLOR'][1]}, {colors['SUBTEXT_COLOR'][2]}); font-size: 11px; font-weight: bold;"
        self.reload_btn.setStyleSheet(style)
        self.close_btn.setStyleSheet(style)
        self.shuffle_btn.setStyleSheet(style)
        self.settings_btn.setStyleSheet(style)
        self.style_settings()
        self.hide_btn.setStyleSheet(style)
        bg = colors['CARD_BG']
        self.icon_lbl.setStyleSheet("background: transparent; font-size: 26px;")

    def check_theme_change(self):
        new_is_dark = is_gnome_dark_mode()
        if new_is_dark != self.current_is_dark:
            self.current_is_dark = new_is_dark
            self.update_footer_style()
            self.weather_lbl.setPixmap(create_weather_image(WEATHER_CITY, self.current_is_dark))
            if self.cached_items:
                self.display_cards(self.cached_items)

    def load_feeds(self):
        w = getattr(self, "worker", None)
        if w is not None and w.isRunning():
            self._reload_again = True
            return
        self._reload_again = False
        self.worker = FeedWorker(list(self.cfg["feeds"]))
        self.worker.cards_ready.connect(self.on_feeds_loaded)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self):
        self.worker.wait()
        if getattr(self, "_reload_again", False):
            self.load_feeds()

    def on_feeds_loaded(self, items):
        self.cached_items = items
        self.display_cards(items)

    def display_cards(self, items):
        if self.mixed:
            items = sorted(items, key=lambda x: x.get("ts", 0), reverse=True)
        self._render_gen = getattr(self, "_render_gen", 0) + 1
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self.render_rows(self._render_gen, items, 0)

    def render_rows(self, gen, items, i):
        if gen != self._render_gen:
            return
        for _ in range(2):
            if i >= len(items):
                return
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
            i += 2
        QTimer.singleShot(0, lambda: self.render_rows(gen, items, i))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NewsWidget()
    window.show()
    sys.exit(app.exec())

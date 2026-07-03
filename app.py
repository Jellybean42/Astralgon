import math
import time

import app
import ntptime
import settings
import wifi
from app_components import clear_background
from events.input import BUTTON_TYPES, Buttons, ButtonDownEvent
from system.eventbus import eventbus

from . import astro
from . import skyview
from .settings_screen import build_settings_layout

PAN_SPEED_DEG_PER_SEC = 60.0
DEFAULT_LAT = 51.99  # Eastnor Castle Deer Park, Herefordshire (EMF Camp site) - placeholder, confirm before shipping
DEFAULT_LON = -2.40
DEFAULT_YEAR = 2026
DEFAULT_MONTH = 7
DEFAULT_DAY = 16
DEFAULT_HOUR = 12
DEFAULT_MINUTE = 0

WIFI_SYNC_TIMEOUT_S = 8


class Astralgon(app.App):
    def __init__(self):
        self.overlays = []
        self.mode = "sky"

        self.button_states = Buttons(self)
        eventbus.on_async(ButtonDownEvent, self._settings_button_handler, self)

        self.pan_alt = 0.0
        self.pan_az = 0.0

        self.lat = settings.get("astralgon_lat", DEFAULT_LAT)
        self.lon = settings.get("astralgon_lon", DEFAULT_LON)

        self.year = DEFAULT_YEAR
        self.month = DEFAULT_MONTH
        self.day = DEFAULT_DAY
        self.hour = DEFAULT_HOUR
        self.minute = DEFAULT_MINUTE

        self.have_valid_time = False
        self.time_source = None
        self.clock_baseline_epoch = 0.0
        self.clock_baseline_ticks = 0
        self.sync_status = "Not yet synced"

        self.settings_layout = None

        self.star_altaz = []  # cached [(name, mag, sin_alt, cos_alt, az_rad), ...]
        self.last_refresh_epoch = None

    async def run(self, render_update):
        await self.try_sync_time()
        if not self.have_valid_time:
            self.mode = "settings"
            self._rebuild_settings_layout()
        await super().run(render_update)

    async def try_sync_time(self):
        try:
            if not wifi.status():
                wifi.connect()
                await wifi.async_wait(duration=WIFI_SYNC_TIMEOUT_S)
            if not wifi.status():
                self.sync_status = "Wi-Fi unavailable - set date & time manually"
                return
            ntptime.settime()
            epoch = time.time()
            self.clock_baseline_epoch = float(epoch)
            self.clock_baseline_ticks = time.ticks_ms()
            self.time_source = "ntp"
            self.have_valid_time = True
            self.sync_status = "Synced via NTP"
        except Exception as e:
            print("Astralgon: NTP sync failed:", e)
            self.sync_status = "Wi-Fi/NTP unavailable - set date & time manually"

    def current_epoch_seconds(self):
        elapsed_ms = time.ticks_diff(time.ticks_ms(), self.clock_baseline_ticks)
        return self.clock_baseline_epoch + elapsed_ms / 1000.0

    def commit_manual_time(self):
        self.day = min(self.day, astro.days_in_month(self.year, self.month))
        epoch = astro.epoch_from_calendar(
            self.year, self.month, self.day, self.hour, self.minute, 0
        )
        self.clock_baseline_epoch = epoch
        self.clock_baseline_ticks = time.ticks_ms()
        self.time_source = "manual"
        self.have_valid_time = True
        self.last_refresh_epoch = None  # force an immediate star refresh
        self.mode = "sky"

    def commit_location(self):
        settings.set("astralgon_lat", self.lat)
        settings.set("astralgon_lon", self.lon)
        settings.save()
        self.last_refresh_epoch = None  # force an immediate star refresh

    def _rebuild_settings_layout(self):
        self.settings_layout = build_settings_layout(self)

    async def _settings_button_handler(self, event):
        if self.mode != "settings":
            return False
        if self.settings_layout is None:
            self._rebuild_settings_layout()
        handled = await self.settings_layout.button_event(event)
        if not handled and BUTTON_TYPES["CANCEL"] in event.button:
            if self.have_valid_time:
                self.mode = "sky"
                self.button_states.clear()
            return True
        if self.mode == "sky":
            self.button_states.clear()
        return handled

    def refresh_star_altaz(self):
        epoch = self.current_epoch_seconds()
        jd = astro.jd_from_epoch(epoch)
        lst = astro.lst_deg(jd, self.lon)

        sin_lst = math.sin(math.radians(lst))
        cos_lst = math.cos(math.radians(lst))
        sin_lat = math.sin(math.radians(self.lat))
        cos_lat = math.cos(math.radians(self.lat))

        # Cache (sin_alt, cos_alt, az_rad) rather than raw alt/az degrees:
        # altitude/azimuth only change on this ~2s refresh cadence, so their
        # trig is worth precomputing here rather than redoing it every frame
        # in projection.project_point() while the view is panned around.
        result = []
        for name, ra_deg, dec_deg, mag, sin_dec, cos_dec, sin_ra, cos_ra in skyview.STARS:
            alt, az = astro.compute_altaz(
                sin_dec, cos_dec, sin_ra, cos_ra, sin_lst, cos_lst, sin_lat, cos_lat
            )
            if alt < 0:
                continue
            alt_rad = math.radians(alt)
            result.append(
                (name, mag, math.sin(alt_rad), math.cos(alt_rad), math.radians(az))
            )
        self.star_altaz = result
        self.last_refresh_epoch = epoch

    def update(self, delta):
        if self.mode == "settings":
            # Must not return False here: base App.run() only calls
            # render_update() on a non-False return, but settings edits are
            # applied by the eventbus button handler, not this method.
            return True

        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()
            return False

        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.mode = "settings"
            self._rebuild_settings_layout()
            return True

        if not self.have_valid_time:
            return False

        step = PAN_SPEED_DEG_PER_SEC * delta / 1000.0
        moved = False
        if self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.pan_az = (self.pan_az + step) % 360.0
            moved = True
        if self.button_states.get(BUTTON_TYPES["LEFT"]):
            self.pan_az = (self.pan_az - step) % 360.0
            moved = True
        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.pan_alt = min(90.0, self.pan_alt + step)
            moved = True
        if self.button_states.get(BUTTON_TYPES["DOWN"]):
            self.pan_alt = max(-90.0, self.pan_alt - step)
            moved = True

        epoch = self.current_epoch_seconds()
        if (
            self.last_refresh_epoch is None
            or epoch - self.last_refresh_epoch > skyview.REFRESH_INTERVAL_S
        ):
            self.refresh_star_altaz()
            moved = True

        return moved

    def draw(self, ctx):
        clear_background(ctx)
        if self.mode == "settings":
            if self.settings_layout is None:
                self._rebuild_settings_layout()
            ctx.rgb(1, 1, 1)
            self.settings_layout.draw(ctx)
        elif not self.have_valid_time:
            ctx.rgb(1, 1, 1)
            ctx.font_size = 16
            ctx.text_align = ctx.CENTER
            ctx.move_to(0, 0).text("Press CONFIRM for settings")
        else:
            skyview.draw_sky(ctx, self.star_altaz, self.pan_alt, self.pan_az)
        self.draw_overlays(ctx)


__app_export__ = Astralgon

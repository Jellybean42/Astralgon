from app_components import layout
from events.input import BUTTON_TYPES

from . import astro


def _stepper_row(label, get_value, set_value, step, lo, hi, wrap, fmt="{}"):
    def value_text():
        return fmt.format(get_value())

    item = layout.DefinitionDisplay(label, value_text())

    async def handler(event, item=item):
        if BUTTON_TYPES["RIGHT"] in event.button:
            delta = step
        elif BUTTON_TYPES["LEFT"] in event.button:
            delta = -step
        else:
            return False
        v = get_value() + delta
        if wrap:
            span = hi - lo + 1
            v = lo + (v - lo) % span
        else:
            v = max(lo, min(hi, v))
        set_value(v)
        item.value = value_text()
        return True

    item.button_handler = handler
    return item


def build_settings_layout(a):
    items = []

    status_item = layout.DefinitionDisplay("Status", a.sync_status)
    items.append(status_item)

    def _retry_sync_label():
        return "Retry Wi-Fi sync"

    async def retry_sync_handler(event, status_item=status_item):
        if BUTTON_TYPES["CONFIRM"] in event.button:
            await a.try_sync_time()
            status_item.value = a.sync_status
            if a.have_valid_time:
                a.mode = "sky"
            return True
        return False

    items.append(layout.ButtonDisplay(_retry_sync_label(), button_handler=retry_sync_handler))

    items.append(
        _stepper_row(
            "Year",
            lambda: a.year,
            lambda v: setattr(a, "year", v),
            1,
            2024,
            2099,
            wrap=False,
        )
    )
    items.append(
        _stepper_row(
            "Month",
            lambda: a.month,
            lambda v: setattr(a, "month", v),
            1,
            1,
            12,
            wrap=True,
        )
    )

    def _set_day(v):
        hi = astro.days_in_month(a.year, a.month)
        a.day = max(1, min(v, hi))

    items.append(
        _stepper_row(
            "Day",
            lambda: a.day,
            _set_day,
            1,
            1,
            31,
            wrap=False,
        )
    )
    items.append(
        _stepper_row(
            "Hour (UTC)",
            lambda: a.hour,
            lambda v: setattr(a, "hour", v),
            1,
            0,
            23,
            wrap=True,
        )
    )
    items.append(
        _stepper_row(
            "Minute",
            lambda: a.minute,
            lambda v: setattr(a, "minute", v),
            1,
            0,
            59,
            wrap=True,
        )
    )
    items.append(
        _stepper_row(
            "Latitude",
            lambda: a.lat,
            lambda v: setattr(a, "lat", v),
            0.5,
            -90.0,
            90.0,
            wrap=False,
            fmt="{:.1f}",
        )
    )
    items.append(
        _stepper_row(
            "Longitude",
            lambda: a.lon,
            lambda v: setattr(a, "lon", v),
            0.5,
            -180.0,
            180.0,
            wrap=False,
            fmt="{:.1f}",
        )
    )

    async def commit_handler(event):
        if BUTTON_TYPES["CONFIRM"] in event.button:
            a.commit_location()
            a.commit_manual_time()
            return True
        return False

    items.append(
        layout.ButtonDisplay("Use this time & location", button_handler=commit_handler)
    )

    return layout.LinearLayout(items)

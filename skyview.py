import math

from app_components import button_labels

from . import projection
from . import starcat

STARS = starcat.STARS
REFRESH_INTERVAL_S = 2.0

MIN_MAG = -1.5
MAX_MAG = 3.5


def _dot_style(mag):
    # Brighter (lower/negative mag) stars get a bigger, more opaque dot.
    t = (mag - MIN_MAG) / (MAX_MAG - MIN_MAG)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    radius = 3.2 - 2.2 * t
    alpha = 1.0 - 0.6 * t
    return radius, alpha


def draw_sky(ctx, star_altaz, pan_alt, pan_az):
    ctx.save()
    ctx.rectangle(-120, -120, 240, 240).clip()

    view = projection.ViewCenter(pan_alt, pan_az)

    closest_name = None
    closest_pos = None
    closest_radius = 0.0
    closest_dist2 = None

    for name, mag, sin_alt, cos_alt, az_rad in star_altaz:
        p = projection.project_point(sin_alt, cos_alt, az_rad, view)
        if p is None:
            continue
        x, y = p
        radius, alpha = _dot_style(mag)
        ctx.rgba(1, 1, 1, alpha).arc(x, y, radius, 0, 2 * math.pi, True).fill()

        dist2 = x * x + y * y
        if closest_dist2 is None or dist2 < closest_dist2:
            closest_dist2 = dist2
            closest_name = name
            closest_pos = (x, y)
            closest_radius = radius

    _draw_horizon_and_compass(ctx, pan_alt, pan_az)
    ctx.restore()

    if closest_name is not None and closest_name != "?":
        x, y = closest_pos
        ctx.save()
        ctx.rgb(1, 1, 1)
        ctx.font_size = 10
        ctx.text_align = ctx.CENTER
        ctx.move_to(x, y + closest_radius + 10).text(closest_name)
        ctx.restore()

    ctx.save()
    ctx.rgb(0.6, 1.0, 0.6)
    ctx.font_size = 12
    ctx.text_align = ctx.CENTER
    ctx.move_to(0, 112).text("Az {:03.0f}  Alt {:+03.0f}".format(pan_az, pan_alt))
    ctx.restore()

    button_labels(
        ctx,
        up_label="Up",
        down_label="Down",
        left_label="Left",
        right_label="Right",
        confirm_label="Settings",
        cancel_label="Exit",
    )


def _draw_horizon_and_compass(ctx, pan_alt, pan_az):
    azimuths = projection.horizon_azimuths(pan_az)
    points = []
    for az in azimuths:
        p = projection.project(0.0, az, pan_alt, pan_az)
        if p is not None:
            points.append(p)

    if len(points) >= 2:
        ctx.rgba(0.4, 0.7, 1.0, 0.6).begin_path()
        ctx.move_to(*points[0])
        for x, y in points[1:]:
            ctx.line_to(x, y)
        ctx.stroke()

    for label, compass_az in projection.COMPASS_POINTS:
        p = projection.project(0.0, compass_az, pan_alt, pan_az)
        if p is None:
            continue
        x, y = p
        ctx.rgba(0.4, 0.7, 1.0, 0.9)
        ctx.font_size = 10
        ctx.text_align = ctx.CENTER
        ctx.move_to(x, y - 6).text(label)

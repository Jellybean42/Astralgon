"""Gnomonic (tangent-plane) projection from Alt/Az onto the 240x240 circular
screen. Pure 2D geometry, no ctx/eventbus dependency.

A gnomonic projection maps great circles (including the horizon) to straight
lines and keeps star patterns near the view center undistorted - the "looking
through a window" feel wanted here, as opposed to a fisheye/whole-sky
projection which deliberately compresses/distorts toward the edges.
"""
import math

HALF_FOV_DEG = 45.0
HALF_SCREEN_PX = 120.0
SCALE = HALF_SCREEN_PX / math.tan(math.radians(HALF_FOV_DEG))
COS_C_CUTOFF = math.cos(math.radians(75.0))
SCREEN_CULL_RADIUS = 135.0


class ViewCenter:
    """Precomputed trig for the current pan direction.

    Build one of these once per frame and reuse it for every star/segment
    endpoint via project_point(), instead of recomputing sin/cos of the view
    center - which doesn't change within a frame - for every single point.
    On real MicroPython hardware, redoing that work per-point (out of ~700
    points/frame with constellation lines) measured as the dominant cost of
    a whole frame, well above the actual ctx drawing calls.
    """

    __slots__ = ("sin_alt", "cos_alt", "az_rad")

    def __init__(self, pan_alt_deg, pan_az_deg):
        pan_alt = math.radians(pan_alt_deg)
        self.sin_alt = math.sin(pan_alt)
        self.cos_alt = math.cos(pan_alt)
        self.az_rad = math.radians(pan_az_deg)


def project_point(sin_alt, cos_alt, az_rad, view):
    """Projects a point given its precomputed (sin_alt, cos_alt, az_rad).

    Callers should precompute these once when a star's alt/az is refreshed
    (every ~2s, see app.py's refresh_star_altaz), not every frame - altitude
    only changes on that slower cadence, only the pan direction changes
    per-frame.
    """
    d_az = az_rad - view.az_rad
    cos_d_az = math.cos(d_az)
    sin_d_az = math.sin(d_az)

    cos_c = view.sin_alt * sin_alt + view.cos_alt * cos_alt * cos_d_az
    if cos_c <= COS_C_CUTOFF:
        return None

    xi = cos_alt * sin_d_az / cos_c
    eta = (view.cos_alt * sin_alt - view.sin_alt * cos_alt * cos_d_az) / cos_c

    x = xi * SCALE
    y = -eta * SCALE

    if x * x + y * y > SCREEN_CULL_RADIUS * SCREEN_CULL_RADIUS:
        return None

    return x, y


def project(alt_deg, az_deg, pan_alt_deg, pan_az_deg):
    """Convenience one-off wrapper for callers with only a handful of points
    (horizon/compass ticks) where precomputing via ViewCenter isn't worth it."""
    alt = math.radians(alt_deg)
    view = ViewCenter(pan_alt_deg, pan_az_deg)
    return project_point(math.sin(alt), math.cos(alt), math.radians(az_deg), view)


def horizon_azimuths(pan_az_deg, span_deg=130.0, step_deg=10.0):
    """Azimuths (alt=0) spanning the current view, for drawing the horizon
    line - reuses project() so it's exactly consistent with stars."""
    start = pan_az_deg - span_deg / 2.0
    n = int(span_deg / step_deg) + 1
    return [(start + i * step_deg) % 360.0 for i in range(n)]


COMPASS_POINTS = (
    ("N", 0.0),
    ("NE", 45.0),
    ("E", 90.0),
    ("SE", 135.0),
    ("S", 180.0),
    ("SW", 225.0),
    ("W", 270.0),
    ("NW", 315.0),
)

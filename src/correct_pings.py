import numpy as np
from typing import List, Any

from .utils import compute_theta_gamma, beam_pattern_from_gamma, tvg_gain

SCALE_FACTOR = 65535.0  # Max value for uint16 to scale corrected intensities


def _get_attr(obj, candidates, default=np.nan):
    """Helper function to get attribute from object with multiple candidate names"""
    for name in candidates:
        if hasattr(obj, name):
            return getattr(obj, name)

    return default


def process_channel(
    xtf_ping: Any,
    altitude: float,
    roll: float,
    install_angle: float,
    tvg_k: float,
    tvg_alpha: float,
    apply_water_mask: bool,
    normalize_gain: bool,
    is_right: bool,
    eps: float = 1e-6
) -> float:
    """Process Channel for an XTF ping"""
    ch = int(is_right)

    chan = xtf_ping.ping_chan_headers[ch]
    smax = float(_get_attr(chan, ["SlantRange"], default=100.0))
    Ns = int(_get_attr(chan, ["NumSamples"], default=len(xtf_ping.data[ch])))
    k = np.arange(1, Ns + 1, dtype=np.float64)

    rng = smax * k / float(Ns)
    if not is_right:
        rng = np.flip(rng)  # left side is typically reversed

    theta, gamma = compute_theta_gamma(rng.reshape(1, -1), np.array([altitude]))
    lambert = 1.0 / np.clip(np.cos(theta), eps, None)
    Phi = beam_pattern_from_gamma(
        gamma,
        roll_deg=np.array([roll]),
        phi0_deg=install_angle,
        is_right=is_right
    )

    gain = lambert / Phi
    gain *= tvg_gain(rng.reshape(1, -1), k=tvg_k, alpha=tvg_alpha)

    if apply_water_mask:
        gain[0, rng <= altitude] = 0.0

    if normalize_gain:
        gain /= np.max(gain) + eps

    I_raw = xtf_ping.data[ch].astype(np.float64) / SCALE_FACTOR
    I_corrected = I_raw * gain[0]
    I_log = np.log1p(I_corrected * SCALE_FACTOR)
    I_log[I_log < 0] = 0

    return I_log


def correct_pings(
    xtf_pings: List[Any],
    yaw_offset: float,
    install_angle: float,
    tvg_k: float,
    tvg_alpha: float,
    contrast_limit: float,
    apply_water_mask: bool,
    normalize_gain: bool
) -> List[Any]:
    """Modify XTF pings with advanced intensity correction."""
    pings = []

    min_val, max_val = np.inf, -np.inf
    for i in range(len(xtf_pings)):
        pings.append(xtf_pings[i])

        for ch in (0, 1):
            pings[-1].SensorHeading += yaw_offset

            altitude = float(_get_attr(
                pings[-1],
                ["SensorPrimaryAltitude", "SensorAltitude", "Altitude"], 
                default=np.nan
            ))

            roll = float(_get_attr(
                pings[-1],
                ["SensorPrimaryRoll", "SensorRoll", "Roll", "MRURoll"],
                default=0.0
            ))

            I_log = process_channel(
                pings[-1],
                altitude,
                roll,
                install_angle,
                tvg_k,
                tvg_alpha,
                apply_water_mask,
                normalize_gain,
                bool(ch)
            )

            min_val = min(min_val, np.min(I_log))
            max_val = max(max_val, np.max(I_log))

            pings[-1].data[ch] = I_log

    contrast_factor = np.power(2, np.log2(SCALE_FACTOR + 1) * contrast_limit) - 1
    for i in range(len(pings)):
        for ch in (0, 1):
            pings[i].data[ch] = (contrast_factor * (pings[i].data[ch] - min_val) / (max_val - min_val)).astype(np.uint16)

    return pings

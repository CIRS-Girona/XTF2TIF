import os, pyxtf
import numpy as np
from pyproj import Proj, CRS
from typing import List, Tuple, Any


def load_xtf(xtf_file_path: str) -> Tuple[Any, Any, List[Any]]:
    """Extract XTF ping data from XTF file"""
    if not os.path.exists(xtf_file_path):
        raise FileNotFoundError("Invalid Path", xtf_file_path)
    elif not xtf_file_path.endswith('.xtf'):
        raise TypeError("Invalid File", xtf_file_path)

    fh, packet = pyxtf.xtf_read(xtf_file_path)
    xtf_pings = packet[pyxtf.XTFHeaderType.sonar]

    return fh, packet, xtf_pings


def beam_pattern_from_gamma(
    gamma: np.ndarray,
    roll_deg: np.ndarray,
    phi0_deg: float,
    is_right: bool,
    kphi: float = 1.0,
) -> np.ndarray:
    """Calculate beam pattern correction factor"""
    roll = np.deg2rad(roll_deg).reshape(-1, 1)    # (H, 1) rad
    phi0 = np.deg2rad(phi0_deg)                   # scalar rad

    phi0_eff = phi0 - roll
    if is_right:
        phi0_eff = phi0 + roll

    x = kphi * np.sin(gamma - phi0_eff)  # (H, W) rad
    return np.power(x / np.sin(x), 4)


def tvg_gain(r: np.ndarray, k: float = 1.0, alpha: float = 0.0) -> np.ndarray:
    """Time-Varying Gain correction"""
    alpha_lin = np.log(10) * alpha / 20.0
    return np.power(r, k) * np.exp(alpha_lin * r)


def compute_theta_gamma(r: np.ndarray, h: np.ndarray, eps: float = 1e-6) -> Tuple[np.ndarray, np.ndarray]:
    """Compute grazing angle (theta) and beam angle (gamma) from range and altitude"""
    h2d = np.clip(h.reshape(-1, 1), 1e-9, None)
    ratio = np.clip(h2d / np.maximum(r, 1e-9), 0.0, 1.0)

    theta = np.clip(np.arccos(ratio), eps, np.pi/2 - eps)
    gamma = np.clip(np.arcsin(ratio), eps, np.pi/2 - eps)

    return theta, gamma


def get_bounds(
    xtf_pings: List[Any],
    epsg_code: int = 25831,
    is_radians: bool = False
) -> Tuple[float, float, float, float]:
    """Calculates geographical bounds from XTF pings"""
    lonlat_to_EN = Proj(CRS.from_epsg(epsg_code), preserve_units=False)
    ping_info = xtf_pings[0].ping_chan_headers[0]

    # Fetch data dimensions
    num_pings = len(xtf_pings)
    num_samples = 2 * ping_info.NumSamples

    # Compute swath resolution
    slant_range = ping_info.SlantRange
    slant_res = 2 * slant_range / num_samples

    # Fetch navigation parameters
    longitude, latitude, altitude, roll, pitch, yaw = zip(*[(
        ping.SensorXcoordinate,
        ping.SensorYcoordinate,
        ping.SensorPrimaryAltitude,
        ping.SensorRoll,
        ping.SensorPitch,
        ping.SensorHeading)
    for ping in xtf_pings])

    east, north = lonlat_to_EN(longitude, latitude)
    altitude = np.asarray(altitude).reshape(num_pings, 1)

    if not is_radians:
        roll, pitch, yaw = np.radians(roll), np.radians(pitch), np.radians(yaw)

    bins = np.arange(num_samples).reshape(1, num_samples)
    bins_from_center = bins - (num_samples - 1) / 2

    n_bins_blind = np.round(altitude / slant_res)  # Bins for Blind Zone per side
    n_bins_ground = (num_samples / 2 - n_bins_blind)  # Bins for Ground Range per side

    # Bins inside the blind zone
    blind_idx = (n_bins_ground <= bins) & (bins < n_bins_ground + 2 * n_bins_blind)

    # Increments along the x-axis (swath width)
    X = np.zeros((num_pings, num_samples))
    inner_term = np.square(slant_res * bins_from_center) - np.square(altitude).reshape(num_pings, 1)
    np.sqrt(np.clip(inner_term, 0, None), where=~blind_idx, out=X)  # Clip data to prevent negative values in sqrt
    X *= np.sign(bins_from_center)

    # Rotation of x-axis (swath) about the z-axis (heading)
    R = np.vstack((np.cos(yaw), -np.sin(yaw))).T
    T = np.vstack((east, north)).T  # Ping coordinates (swath center)

    X = np.expand_dims(X, axis=2)
    T = np.expand_dims(T, axis=1)
    R = np.expand_dims(R, axis=1)

    # Compute the transformation
    swaths = T + R * X

    # Get minimum bound from easting
    flat_index = np.argmin(swaths[:, :, 0])
    row_index, col_index = np.unravel_index(flat_index, swaths[:, :, 0].shape)
    min_en = lonlat_to_EN(swaths[row_index, col_index, 0], swaths[row_index, col_index, 1], inverse=True)

    # Get maximum bound from easting
    flat_index = np.argmax(swaths[:, :, 0])
    row_index, col_index = np.unravel_index(flat_index, swaths[:, :, 0].shape)
    max_en = lonlat_to_EN(swaths[row_index, col_index, 0], swaths[row_index, col_index, 1], inverse=True)

    # Get minimum bound from northing
    flat_index = np.argmin(swaths[:, :, 1])
    row_index, col_index = np.unravel_index(flat_index, swaths[:, :, 1].shape)
    min_north_en = lonlat_to_EN(swaths[row_index, col_index, 0], swaths[row_index, col_index, 1], inverse=True)

    # Get maximum bound from northing
    flat_index = np.argmax(swaths[:, :, 1])
    row_index, col_index = np.unravel_index(flat_index, swaths[:, :, 1].shape)
    max_north_en = lonlat_to_EN(swaths[row_index, col_index, 0], swaths[row_index, col_index, 1], inverse=True)

    # Return bounds as (lon_min, lon_max, lat_min, lat_max)
    lon_min = min(min_en[0], max_en[0])
    lon_max = max(min_en[0], max_en[0])
    lat_min = min(min_north_en[1], max_north_en[1])
    lat_max = max(min_north_en[1], max_north_en[1])

    return lon_min, lon_max, lat_min, lat_max


def inspect_xtf(file_name: str, fh: Any, packet: Any, output_dir: str):
    """Inspect XTF file and save diagnostic information to a text file"""
    label = '.'.join(file_name.split("/")[-1].split(".")[:-1])
    output_path = f"{output_dir}/{label}_stats.txt"

    with open(output_path, 'w') as f:
        print(f"{'='*70}", file=f)
        print(f" XTF DIAGNOSTIC: {file_name}", file=f)
        print(f"{'='*70}", file=f)

        # 1. FILE HEADER SUMMARY
        print(f"\n--- [ FILE HEADER ] ---", file=f)
        print(f"{'Sonar Name:':<25} {fh.SonarName.decode().strip()}", file=f)
        print(f"{'Recording Program:':<25} {fh.RecordingProgramName.decode().strip()} v{fh.RecordingProgramVersion.decode().strip()}", file=f)
        print(f"{'Total Sonar Channels:':<25} {fh.NumberOfSonarChannels}", file=f)

        # 2. CHANNEL CONFIGURATION
        print(f"\n--- [ CHANNEL CONFIGURATION ] ---", file=f)
        for i in range(fh.NumberOfSonarChannels):
            ch = fh.ChanInfo[i]
            name = ch.ChannelName.decode().strip() or f"CH_{i}"
            freq = ch.Frequency
            print(f"CH {i}: {name:<10} | Freq: {freq:>4.0f} kHz | Bytes/Sample: {ch.BytesPerSample}", file=f)

        # 3. PING & NAVIGATION DATA
        if pyxtf.XTFHeaderType.sonar in packet:
            sonar_pings = packet[pyxtf.XTFHeaderType.sonar]
            p1 = sonar_pings[0]

            print(f"\n--- [ FIRST PING METADATA ] ---", file=f)
            print(f"{'Ping Number:':<25} {p1.PingNumber}", file=f)
            print(f"{'Sound Velocity:':<25} {p1.SoundVelocity:.2f} m/s", file=f)
            print(f"{'Coordinates:':<25} Lat: {p1.SensorYcoordinate:.6f}, Lon: {p1.SensorXcoordinate:.6f}", file=f)
            print(f"{'Altitude / Depth:':<25} {p1.SensorPrimaryAltitude:.2f} m / {p1.SensorDepth:.2f} m", file=f)

            # 4. SONAR SETTINGS & BIN SIZE
            print(f"\n--- [ SONAR SETTINGS & RESOLUTION ] ---", file=f)
            for i, ch_header in enumerate(p1.ping_chan_headers):
                # Calculate Bin Size (Resolution)
                # Formula: Slant Range / NumSamples
                samples = ch_header.NumSamples
                range_m = ch_header.SlantRange

                if samples > 0:
                    bin_size = range_m / samples
                    # Convert to cm if very small for readability
                    bin_str = f"{bin_size*100:.2f} cm" if bin_size < 1 else f"{bin_size:.3f} m"
                else:
                    bin_str = "N/A"

                print(f"SubCH {i}: {samples:>5} samples | Range: {range_m:>5.1f} m | Bin Size: {bin_str}", file=f)

            # 5. DATA BUFFER INFO
            print(f"\n--- [ DATA ARRAYS ] ---", file=f)
            for i, data_arr in enumerate(p1.data):
                print(f"Data Stream {i}: {data_arr.dtype} array, shape {data_arr.shape}", file=f)

        print(f"\n{'='*70}\n", file=f)

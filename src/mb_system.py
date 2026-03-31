import os, subprocess
from typing import List, Any

from src.utils import get_bounds


def run_mbsystem_processing(
    xtf_pings: List[Any],
    xtf_path: str,
    output_dir: str,
    resolution: float,
    clip: int,
    epsg_code: int,
    colormap: str
):
    """Run MBSystem commands to generate .tif from XTF file"""
    label = '.'.join(xtf_path.split("/")[-1].split(".")[:-1])

    bounds = get_bounds(xtf_pings, epsg_code=epsg_code)

    # Create datalist file
    datalist_path = os.path.join(output_dir, f"{label}_datalist.txt")
    with open(datalist_path, 'w') as f:
        f.write(f"{label}.xtf 211\n")

    # Prepare bounds string
    lon_min, lon_max, lat_min, lat_max = bounds
    bounds_str = f"-R{lon_min}/{lon_max}/{lat_min}/{lat_max}"

    # Output grid name
    grid_name = os.path.join(output_dir, f"{label}")
    try:
        # Run mbmosaic
        subprocess.run((
            "./mbs.sh",
            "mbmosaic",
            "-A4",                                  # Datatype 4: Sidescan
            f"-I{datalist_path}",                   # Input datalist
            bounds_str,                             # Bounds
            f"-C{clip}",                            # Clip for spline interpolation
            "-N",                                   # Set empty cells to NaN
            f"-E{resolution}/{resolution}/meters",  # Grid resolution
            f"-O{grid_name}"                        # Output prefix
        ), capture_output=True, text=True, check=True)

        grd_file = f"{grid_name}.grd"
        if not os.path.exists(grd_file):
            raise FileNotFoundError(f"Grid file not found: {grd_file}")

        cpt_file = f"{grid_name}.cpt"
        with open(cpt_file, 'w') as f:
            subprocess.run((
                "./mbs.sh",
                "gmt",
                "grd2cpt",
                grd_file,
                f"-C{colormap}"
            ), stdout=f, stderr=subprocess.DEVNULL, check=True)

        if not os.path.exists(cpt_file):
            raise FileNotFoundError(f"CPT file not found: {cpt_file}")

        tif_file = f"{grid_name}.tif"
        subprocess.run((
            "./mbs.sh",
            "gmt",
            "grdimage",
            grd_file,
            f"-C{cpt_file}",
            f"-A{tif_file}",
            "-Q"  # Set NaN values to transparent
        ), stderr=subprocess.DEVNULL, check=True)

        if not os.path.exists(tif_file):
            raise FileNotFoundError(f"TIF file not found: {tif_file}")
    except subprocess.CalledProcessError as e:
        print(f"MBSystem command failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
    except Exception as e:
        print(f"Error running MBSystem: {e}")

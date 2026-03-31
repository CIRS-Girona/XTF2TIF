import os
import yaml
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

from src.utils import load_xtf, inspect_xtf
from src.correct_pings import correct_pings
from src.mb_system import run_mbsystem_processing


def main(xtf_file: str, cfg: dict):
    pipe_cfg = cfg['pipeline']
    corr_cfg = cfg['corrections']
    mb_cfg = cfg['mbsystem']

    input_path = os.path.join(cfg['input_dir'], xtf_file)
    output_xtf_path = os.path.join(cfg['output_dir'], xtf_file)

    try:
        fh, packet, pings = load_xtf(input_path)

        if pipe_cfg['inspect_xtfs']:
            inspect_xtf(xtf_file, fh, packet, cfg['output_dir'])

        if not os.path.exists(output_xtf_path):
            # Apply Intensity Corrections
            if pipe_cfg['apply_corrections']:
                pings = correct_pings(
                    pings,
                    **corr_cfg  # Unpacks all keys from the corrections section
                )

            # Save corrected XTF
            with open(output_xtf_path, 'wb') as f:
                f.write(fh.to_bytes())
                for p in pings:
                    f.write(p.to_bytes())

        # MBSystem Post-Processing
        if pipe_cfg['run_mbsystem']:
            run_mbsystem_processing(
                xtf_pings=pings,
                xtf_path=output_xtf_path,
                output_dir=cfg['output_dir'],
                resolution=mb_cfg['grid_resolution'],
                clip=mb_cfg['clip_percent'],
                colormap=mb_cfg['colormap'],
                epsg_code=mb_cfg['epsg_code']
            )

    except Exception as e:
        print(f"\nError processing {xtf_file}: {e}")


if __name__ == "__main__":
    # Load configuration
    with open("config.yaml", 'r') as f:
        cfg = yaml.safe_load(f)

    os.makedirs(cfg['output_dir'], exist_ok=True)

    args = [(f, cfg) for f in os.listdir(cfg['input_dir']) if f.endswith('.xtf')]
    if not args:
        print(f"No XTF files found in {cfg['input_dir']}")
        exit()

    with ThreadPoolExecutor(max_workers=cfg['num_workers']) as exe:
        list(tqdm(
            exe.map(lambda a: main(*a), args),
            total=len(args)
        ))

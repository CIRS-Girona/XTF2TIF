# XTF2TIF

<div align="center">
  <img src="assets/asset.png" alt="A sample output example">
</div>

**XTF2TIF** is a Python-based processing pipeline designed to transform Side Scan Sonar (SSS) XTF files into high-resolution, georeferenced GeoTIFFs. It bridges the gap between raw sonar data and GIS-ready products by combining custom Python intensity corrections with the robust gridding power of **MB-System**.

## 🚀 Key Features

* **Advanced Intensity Correction:** Includes Time Varied Gain (TVG), Lambert’s Law correction, and Beam Pattern compensation.
* **Automated MB-System Integration:** Automatically handles MB-System commands via Docker to produce georeferenced mosaics.
* **Config-Driven Workflow:** Manage all survey parameters (offsets, installation angles, EPSG codes) from a single YAML file.

---

## 🛠 Prerequisites

### 1. Docker & MB-System
This toolkit relies on the official MB-System Docker image for sonar processing and gridding. **Please follow the [Official MB-System Docker Instructions](https://github.com/dwcaress/MB-System/blob/master/docker/README.md)**.

### 2. Python Environment
Install the required Python dependencies:
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

---

## 📂 Project Structure

```text
XTF2TIFF/
├── data/               # Place raw .xtf files here
├── output/             # Processed XTFs and GeoTIFFs will appear here
├── src/                # Core processing logic
├── config.yaml         # Global configuration (Edit this!)
└── main.py             # Main execution script
```

---

## 📖 Usage

### 1. Configure the Survey
Edit `config.yaml` to match your sonar hardware and survey requirements. 

```yaml
corrections:
  install_angle: 30.0   # Sonar tilt angle

mbsystem:
  grid_resolution: 0.45  # 45cm resolution per pixel in the output GeoTIFF (limited by XTF bin size)
  epsg_code: 25831       # Target coordinate system
```

### 2. Run the Pipeline
Place your `.xtf` files in the `data/` folder and execute the main script:

```bash
python main.py
```

The script will:
1.  **Inspect** the XTF headers and generate a `stats.txt` for each XTF file.
2.  **Correct** the backscatter intensity.
4.  **Grid** the data into a GeoTIFF using the MB-System Docker container.

---

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an issue for feature requests regarding new sonar beam patterns or filtering methods.

<p align="center">
  <img src="static/logo.png" alt="Phase Navigator logo" height="120">
</p>

# Phase Navigator

*Interactive phase diagram generator for up to 4 components (solid phases) using the Materials Project API and **pymatgen**.*

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.10-green?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Materials Project](https://img.shields.io/badge/Materials_Project-API-orange)](https://materialsproject.org)

## ✨ Key Features

- ⚡ **Fast Performance**: Direct query to Materials Project with on-the-fly Plotly rendering
- 🔐 **Secure API Storage**: Encrypted API key storage in browser localStorage with automatic persistence
- 🌡️ **Temperature Control**: Support for 0 K or finite temperature (300–2000 K) calculations
- ⚙️ **Energy Cutoff**: Customizable energy cutoff for unstable phases visualization
- 📱 **Responsive Design**: Mobile-friendly interface with optimized layouts
- 📊 **Interactive Plots**: Fully interactive phase diagrams with zoom, pan, and hover
- 🔄 **Progress Tracking**: Real-time progress indicators during diagram generation
- 💾 **Smart Defaults**: Automatic form filling and parameter memory
- 🚫 **No Page Navigation**: Seamless single-page application with AJAX-based diagram generation
- 🛡️ **Robust Error Handling**: Comprehensive validation and user-friendly error messages

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Build the image
docker build -t phasenavigator .

# Run the container
docker run -d -p 8000:8000 --name phasenavigator phasenavigator

# Access the application
open http://localhost:8000
```

### Manual Installation

#### Prerequisites
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3-pip build-essential gfortran git libblas-dev liblapack-dev

# macOS (using Homebrew)
brew install python@3.10 gcc gfortran openblas lapack

# Windows (using conda)
conda install python=3.10 pip
```

#### Installation Steps
```bash
# Clone the repository
git clone https://github.com/ToshihiroIguchi/PhaseNavigator.git
cd PhaseNavigator

# Install dependencies
pip install -r requirements.txt

# Configure pymatgen
pmg config --install enumlib
pmg config --install bader

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📋 Usage

1. **Get Materials Project API Key**: Sign up and get your free API key at [next-gen.materialsproject.org/api](https://next-gen.materialsproject.org/api)
2. **Enter Chemical Formulas**: Input 2-4 chemical formulas (e.g., `BaO, MgO, SiO2`)
3. **Save API Key**: Enter your API key once - it will be encrypted and stored securely in your browser for future use
4. **Set Parameters**: 
   - Choose temperature (0 K for ground state, or 300-2000 K for finite temperature)
   - Adjust energy cutoff for unstable phases (default: 0.2 eV/atom)
5. **Generate Diagram**: Click "Generate Phase Diagram" and watch the progress
6. **Explore Results**: Interactive phase diagram with temperature and energy cutoff displayed

### Example Input Combinations

- **Battery Materials**: `Li2O, CoO2, MnO2`
- **Ceramics**: `BaO, TiO2, SiO2` 
- **Superconductors**: `Y2O3, BaCO3, CuO`
- **Photovoltaics**: `CdTe, CdS, ZnS`

## 🛠️ Technical Details

### Architecture
- **Backend**: FastAPI with async support
- **Frontend**: Vanilla JavaScript with Plotly.js
- **Data Source**: Materials Project API
- **Computation**: pymatgen for phase diagram calculations
- **Containerization**: Docker with optimized Python 3.10 slim image

### API Endpoints
- `GET /` - Main application interface
- `POST /diagram` - Form submission handler
- `POST /diagram/raw` - JSON API for phase diagram data

### Security Features
- Client-side API key encryption with hex encoding for reliability
- Automatic API key persistence with format validation
- Rate limiting (10 requests per 30 seconds)
- Input validation and sanitization
- No server-side API key storage
- Secure localStorage management with corruption detection

## 📸 Screenshots

<img src="sample.png" alt="Phase Navigator Interface" width="800">

*Interactive phase diagram generation with real-time progress tracking and parameter display*

## 🔧 Configuration

### Environment Variables
- `PORT`: Application port (default: 8000)
- `HOST`: Application host (default: 0.0.0.0)

### Docker Compose (Optional)

```yaml
version: '3.8'
services:
  phasenavigator:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
      - HOST=0.0.0.0
```

## 📝 Requirements

- **Docker** (recommended) or Python 3.10+ with pip
- **Materials Project API Key** (free registration required)
- **Modern web browser** with JavaScript enabled
- **System dependencies** (for manual installation): build-essential, gfortran, git, libblas-dev, liblapack-dev

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚖️ Legal & Disclaimers

### License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Disclaimer
This software is provided "as is" without warranty of any kind. The authors are not responsible for:
- Data accuracy or completeness from the Materials Project API
- Any damages or losses resulting from the use of this software
- The availability or reliability of external APIs and services
- Any research conclusions or decisions made based on generated phase diagrams

### Data Source Attribution
This application uses data from the **Materials Project**, which should be properly cited in any research or publication:
> Jain, A., Ong, S. P., Hautier, G., Chen, W., Richards, W. D., Dacek, S., ... & Persson, K. A. (2013). Commentary: The Materials Project: A materials genome approach to accelerating materials innovation. APL materials, 1(1), 011002.

### Usage Responsibility
Users are responsible for:
- Obtaining and maintaining valid Materials Project API keys
- Complying with Materials Project's terms of service
- Proper attribution of data sources in research and publications
- Validating computational results through appropriate scientific methods
- Ensuring compliance with their institution's data usage policies

## 🙏 Acknowledgments

- [Materials Project](https://materialsproject.org) for providing the comprehensive materials database
- [pymatgen](https://pymatgen.org) for materials analysis tools
- [Plotly.js](https://plotly.com/javascript/) for interactive plotting capabilities
- [FastAPI](https://fastapi.tiangolo.com) for the modern web framework

## 🐛 Troubleshooting

### Common Installation Issues

**Docker not found:**
```bash
# Install Docker on Ubuntu/Debian
sudo apt update && sudo apt install docker.io
sudo systemctl start docker
sudo usermod -aG docker $USER
```

**pip not found:**
```bash
# Ubuntu/Debian
sudo apt install python3-pip

# macOS
python3 -m ensurepip --upgrade
```

**Permission denied for Docker:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in, or run:
newgrp docker
```

**Build dependencies missing:**
```bash
# Ubuntu/Debian
sudo apt install build-essential gfortran git libblas-dev liblapack-dev

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install gcc-gfortran git blas-devel lapack-devel
```

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues](../../issues) page for known problems
2. Create a new issue with detailed information about your problem
3. Include your browser, operating system, and any error messages

---

<p align="center">
  <strong>Phase Navigator</strong> - Making phase diagram generation accessible and interactive
</p>
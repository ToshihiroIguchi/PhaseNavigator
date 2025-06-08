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
- 🔐 **Secure API Storage**: Encrypted API key storage in browser localStorage  
- 🌡️ **Temperature Control**: Support for 0 K or finite temperature (300–2000 K) calculations
- ⚙️ **Energy Cutoff**: Customizable energy cutoff for unstable phases visualization
- 📱 **Responsive Design**: Mobile-friendly interface with optimized layouts
- 📊 **Interactive Plots**: Fully interactive phase diagrams with zoom, pan, and hover
- 🔄 **Progress Tracking**: Real-time progress indicators during diagram generation
- 💾 **Smart Defaults**: Automatic form filling and parameter memory

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

1. **Get Materials Project API Key**: Sign up at [materialsproject.org](https://materialsproject.org) and obtain your API key
2. **Enter Chemical Formulas**: Input 2-4 chemical formulas (e.g., `BaO, MgO, SiO2`)
3. **Set Parameters**: 
   - Choose temperature (0 K for ground state, or 300-2000 K for finite temperature)
   - Adjust energy cutoff for unstable phases (default: 0.2 eV/atom)
4. **Generate Diagram**: Click "Generate Phase Diagram" and watch the progress
5. **Explore Results**: Interactive phase diagram with temperature and energy cutoff displayed

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
- Client-side API key encryption
- Rate limiting (10 requests per 30 seconds)
- Input validation and sanitization
- No server-side API key storage

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

- **Docker** (recommended) or Python 3.10+
- **Materials Project API Key** (free registration required)
- **Modern web browser** with JavaScript enabled

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Materials Project](https://materialsproject.org) for providing the comprehensive materials database
- [pymatgen](https://pymatgen.org) for materials analysis tools
- [Plotly.js](https://plotly.com/javascript/) for interactive plotting capabilities
- [FastAPI](https://fastapi.tiangolo.com) for the modern web framework

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues](../../issues) page for known problems
2. Create a new issue with detailed information about your problem
3. Include your browser, operating system, and any error messages

---

<p align="center">
  <strong>Phase Navigator</strong> - Making phase diagram generation accessible and interactive
</p>
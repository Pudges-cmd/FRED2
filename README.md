# FRED2
Im tired pls i want this research to end

anyways 

# README.md
# 🚨 Disaster Detection System

A portable AI-powered detection system for emergency response using Raspberry Pi Zero 2W, designed to detect humans, cats, and dogs in disaster scenarios and send GPS-enabled SMS alerts.

## 🌟 Features

- **Real-time AI Detection**: Identifies humans, cats, and dogs using YOLOv5/YOLO11
- **GPS Tracking**: Automatic location tagging via SIM7600X 4G module
- **SMS Alerts**: Emergency notifications with detection counts and evacuation info
- **Battery Powered**: 6-8 hours continuous operation
- **Auto-boot**: Starts automatically on system power-up
- **Local Logging**: All detections logged for analysis
- **Firebase Integration**: Optional cloud synchronization

## 📋 Hardware Requirements

- Raspberry Pi Zero 2W
- Raspberry Pi Camera Module V2
- SIM7600X 4G Hat
- Raspberry Pi Battery Hat (5000mAh)
- MicroSD Card (64GB minimum)
- SIM card with SMS capability

## 🚀 Quick Installation

```bash
# Clone repository
git clone https://github.com/yourusername/disaster-detection-system.git
cd disaster-detection-system

# Run automated installation
chmod +x install.sh
sudo ./install.sh
```

## 📖 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API Reference](docs/API.md)

## ⚡ Quick Start

1. **Install System**: Run `sudo ./install.sh`
2. **Configure Settings**: Edit `config/settings.json`
3. **Start Service**: `sudo systemctl start disaster-detection`
4. **Check Status**: `./scripts/status.sh`

## 🔧 Configuration

Copy and edit the configuration file:
```bash
cp config/settings.example.json config/settings.json
nano config/settings.json
```

Add your emergency contacts, configure detection parameters, and set evacuation sites.

## 📱 SMS Alert Format

```
🚨 DISASTER RESPONSE ALERT 🚨
Detected: 3 people, 1 cat, 2 dogs
Location: 13.621800, 123.194500
Google Maps: https://maps.google.com/?q=13.621800,123.194500
Evacuate to: Naga City GSIS Gym
Address: Magsaysay Avenue, Naga City, Camarines Sur
Time: 2025-08-24 14:30:15
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Create an [Issue](https://github.com/yourusername/disaster-detection-system/issues) for bug reports
- Join our [Discussions](https://github.com/yourusername/disaster-detection-system/discussions) for help

---

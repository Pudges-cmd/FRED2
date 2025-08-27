set -e  # Exit on any error

echo "🚀 Installing Disaster Detection System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   exit 1
fi

# Update system
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install system dependencies
print_status "Installing system dependencies..."
apt install -y python3-pip python3-venv python3-dev git cmake \
    libopencv-dev libatlas-base-dev libhdf5-dev libhdf5-serial-dev \
    libharfbuzz0b libwebp6 libtiff5 libjasper-dev libopenjp2-7 \
    libilmbase-dev libopenexr-dev libgstreamer1.0-dev \
    libavcodec-dev libavformat-dev libswscale-dev libqtgui4 \
    libqt4-test libqtcore4

# Enable camera and serial
print_status "Configuring Raspberry Pi settings..."
raspi-config nonint do_camera 0
raspi-config nonint do_serial 0
raspi-config nonint do_i2c 0
raspi-config nonint do_spi 0

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv /opt/disaster_detection_env
source /opt/disaster_detection_env/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install Python packages
print_status "Installing Python packages..."
pip install -r requirements.txt

# Create directories
print_status "Creating system directories..."
mkdir -p /var/log/disaster-detection
mkdir -p /opt/disaster-detection/models
mkdir -p /opt/disaster-detection/logs

# Copy source files
print_status "Installing application files..."
cp -r src/* /opt/disaster-detection/
cp -r config /opt/disaster-detection/
cp -r scripts /opt/disaster-detection/

# Set permissions
chown -R pi:pi /opt/disaster-detection
chown -R pi:pi /var/log/disaster-detection
chmod +x /opt/disaster-detection/scripts/*.sh

# Install systemd service
print_status "Installing system service..."
cp services/disaster-detection.service /etc/systemd/system/
systemctl daemon-reload

# Download YOLO model
print_status "Downloading AI model..."
cd /opt/disaster-detection/models
sudo -u pi python3 -c "
import torch
from ultralytics import YOLO
model = YOLO('yolov5n.pt')
print('Model downloaded successfully')
"

# Configure GPU memory
print_status "Optimizing system performance..."
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo "gpu_mem=128" >> /boot/config.txt
fi

# Create example config if not exists
if [ ! -f /opt/disaster-detection/config/settings.json ]; then
    print_status "Creating default configuration..."
    cp /opt/disaster-detection/config/settings.example.json /opt/disaster-detection/config/settings.json
fi

print_status "Installation completed successfully!"
print_warning "Please configure your settings in /opt/disaster-detection/config/settings.json"
print_warning "Add your emergency contacts and SIM card APN settings"
print_status "To start the service: sudo systemctl enable disaster-detection && sudo systemctl start disaster-detection"
print_status "To check status: sudo systemctl status disaster-detection"

echo ""
echo -e "${GREEN}🎉 Installation Complete!${NC}"
echo "Next steps:"
echo "1. Edit configuration: sudo nano /opt/disaster-detection/config/settings.json"
echo "2. Enable service: sudo systemctl enable disaster-detection"
echo "3. Start service: sudo systemctl start disaster-detection"
echo "4. Check logs: journalctl -u disaster-detection -f"

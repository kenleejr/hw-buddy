#!/bin/bash

# HW Buddy Mobile App Setup and Run Script
# This script automatically configures the backend URL and runs the mobile app

set -e  # Exit on any error

echo "🚀 HW Buddy Mobile App Setup Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_APP_DIR="$SCRIPT_DIR"
MAIN_DART_FILE="$MOBILE_APP_DIR/lib/main.dart"

echo -e "${BLUE}📱 Mobile app directory: $MOBILE_APP_DIR${NC}"

# Function to detect ngrok tunnel
detect_ngrok_tunnel() {
    echo -e "${YELLOW}🔍 Checking for active ngrok tunnel...${NC}" >&2
    
    # Check if ngrok is running and get the public URL
    local ngrok_url=""
    if command -v curl >/dev/null 2>&1; then
        ngrok_url=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o 'https://[^"]*\.ngrok\.io' | head -n1)
    fi
    
    if [[ -n "$ngrok_url" ]]; then
        echo -e "${GREEN}✅ Found active ngrok tunnel: $ngrok_url${NC}" >&2
        echo "$ngrok_url"
    else
        echo "" # Return empty string if no ngrok tunnel found
    fi
}

# Function to get local IP address
get_local_ip() {
    echo -e "${YELLOW}🔍 Finding local IP address...${NC}" >&2
    
    # Try different methods to get IP address
    local ip=""
    
    # Method 1: Try en0 (WiFi on macOS)
    if [[ -z "$ip" ]]; then
        ip=$(ifconfig en0 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
    fi
    
    # Method 2: Try en1 (Ethernet on some systems)
    if [[ -z "$ip" ]]; then
        ip=$(ifconfig en1 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
    fi
    
    # Method 3: Try any interface with 192.168.x.x
    if [[ -z "$ip" ]]; then
        ip=$(ifconfig 2>/dev/null | grep "inet " | grep "192.168" | awk '{print $2}' | head -n1)
    fi
    
    # Method 4: Try any interface with 10.x.x.x
    if [[ -z "$ip" ]]; then
        ip=$(ifconfig 2>/dev/null | grep "inet " | grep "10\." | awk '{print $2}' | head -n1)
    fi
    
    # Method 5: Use route command (Linux/macOS)
    if [[ -z "$ip" ]]; then
        ip=$(route get default 2>/dev/null | grep interface | awk '{print $2}' | xargs ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
    fi
    
    # Method 6: Last resort - use hostname
    if [[ -z "$ip" ]]; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    
    if [[ -z "$ip" ]]; then
        echo -e "${RED}❌ Could not determine local IP address${NC}" >&2
        echo -e "${YELLOW}Please enter your local IP address manually:${NC}" >&2
        read -p "IP Address: " ip
        
        if [[ -z "$ip" ]]; then
            echo -e "${RED}❌ No IP address provided. Exiting.${NC}" >&2
            exit 1
        fi
    fi
    
    echo -e "${GREEN}✅ Found local IP: $ip${NC}" >&2
    # Output only the IP address to stdout for variable assignment
    echo "$ip"
}

# Function to update main.dart with the correct IP
update_main_dart() {
    local ip_address=$1
    local backend_url="http://$ip_address:8000"
    
    echo -e "${YELLOW}📝 Updating main.dart with backend URL: $backend_url${NC}"
    
    if [[ ! -f "$MAIN_DART_FILE" ]]; then
        echo -e "${RED}❌ main.dart not found at: $MAIN_DART_FILE${NC}"
        exit 1
    fi
    
    # Create backup
    cp "$MAIN_DART_FILE" "$MAIN_DART_FILE.backup"
    
    # Update the BACKEND_URL line using a more robust approach
    if grep -q "const String BACKEND_URL" "$MAIN_DART_FILE"; then
        # Use perl instead of sed for better handling of special characters
        perl -i -pe "s|const String BACKEND_URL = .*|const String BACKEND_URL = '$backend_url';|" "$MAIN_DART_FILE"
        echo -e "${GREEN}✅ Updated existing BACKEND_URL in main.dart${NC}"
    else
        echo -e "${RED}❌ Could not find BACKEND_URL in main.dart${NC}"
        echo -e "${YELLOW}Please add this line manually after the imports:${NC}"
        echo "const String BACKEND_URL = '$backend_url';"
        exit 1
    fi
    
    # Verify the change
    echo -e "${BLUE}🔍 Current BACKEND_URL setting:${NC}"
    grep "const String BACKEND_URL" "$MAIN_DART_FILE"
}

# Function to clean and prepare Flutter
prepare_flutter() {
    echo -e "${YELLOW}🧹 Preparing Flutter environment...${NC}"
    
    # Clean previous builds
    echo -e "${BLUE}Cleaning Flutter project...${NC}"
    flutter clean
    
    # Get dependencies
    echo -e "${BLUE}Getting Flutter dependencies...${NC}"
    flutter pub get
    
    # Handle iOS CocoaPods
    if [[ -d "ios" ]]; then
        echo -e "${BLUE}Setting up iOS dependencies...${NC}"
        cd ios
        
        # Clean CocoaPods
        if [[ -d "Pods" ]]; then
            echo -e "${BLUE}Cleaning existing Pods...${NC}"
            rm -rf Pods
        fi
        
        if [[ -f "Podfile.lock" ]]; then
            echo -e "${BLUE}Removing Podfile.lock...${NC}"
            rm Podfile.lock
        fi
        
        # Install CocoaPods
        echo -e "${BLUE}Installing CocoaPods...${NC}"
        pod install --repo-update
        
        cd ..
    fi
    
    # Final clean and pub get
    flutter clean
    flutter pub get
    
    echo -e "${GREEN}✅ Flutter environment prepared${NC}"
}

# Function to test backend connectivity
test_backend_connectivity() {
    local ip_address=$1
    local backend_url="http://$ip_address:8000"
    
    echo -e "${YELLOW}🔍 Testing backend connectivity...${NC}"
    
    # Test health endpoint
    if curl -s --connect-timeout 5 "$backend_url/health" > /dev/null; then
        echo -e "${GREEN}✅ Backend is accessible at $backend_url${NC}"
        return 0
    else
        echo -e "${RED}❌ Backend is not accessible at $backend_url${NC}"
        echo -e "${YELLOW}💡 Make sure your backend is running:${NC}"
        echo "   cd ../backend && ./start_live_server.sh"
        echo ""
        echo -e "${YELLOW}Do you want to continue anyway? (y/N):${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            return 0
        else
            exit 1
        fi
    fi
}

# Function to run the app
run_mobile_app() {
    echo -e "${YELLOW}🚀 Running mobile app...${NC}"
    
    # Check available devices
    echo -e "${BLUE}📱 Available devices:${NC}"
    flutter devices
    
    echo ""
    echo -e "${YELLOW}Choose how to run the app:${NC}"
    echo "1) Run on connected device/simulator (default)"
    echo "2) Build and open in Xcode"
    echo "3) Just build for testing"
    echo "4) Use ngrok tunnel (enter ngrok URL manually)"
    
    read -p "Enter choice (1-4) [1]: " choice
    choice=${choice:-1}
    
    case $choice in
        1)
            echo -e "${BLUE}Running on device/simulator...${NC}"
            flutter run --debug
            ;;
        2)
            echo -e "${BLUE}Building and opening in Xcode...${NC}"
            flutter build ios --debug
            open ios/Runner.xcworkspace
            ;;
        3)
            echo -e "${BLUE}Building for testing...${NC}"
            flutter build ios --debug
            echo -e "${GREEN}✅ Build complete. You can now test in Xcode.${NC}"
            ;;
        4)
            echo -e "${YELLOW}📡 Using ngrok tunnel mode${NC}"
            echo -e "${BLUE}Instructions:${NC}"
            echo "1. Make sure backend is running: cd ../backend && ./start_live_server.sh"
            echo "2. Start ngrok in another terminal: ngrok http 8000"
            echo "3. Copy the HTTPS forwarding URL (e.g., https://abc123.ngrok.io)"
            echo ""
            read -p "Enter your ngrok HTTPS URL: " ngrok_url
            
            if [[ -n "$ngrok_url" ]]; then
                # Update main.dart with ngrok URL
                echo -e "${YELLOW}📝 Updating main.dart with ngrok URL: $ngrok_url${NC}"
                perl -i -pe "s|const String BACKEND_URL = .*|const String BACKEND_URL = '$ngrok_url';|" "$MAIN_DART_FILE"
                echo -e "${GREEN}✅ Updated BACKEND_URL in main.dart${NC}"
                
                # Verify the change
                echo -e "${BLUE}🔍 Current BACKEND_URL setting:${NC}"
                grep "const String BACKEND_URL" "$MAIN_DART_FILE"
                
                echo -e "${BLUE}Running on device/simulator with ngrok...${NC}"
                flutter run --debug
            else
                echo -e "${RED}❌ No ngrok URL provided. Exiting.${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}❌ Invalid choice. Running on device/simulator...${NC}"
            flutter run --debug
            ;;
    esac
}

# Main execution
main() {
    echo -e "${BLUE}Starting HW Buddy Mobile App setup...${NC}"
    
    # Change to mobile app directory
    cd "$MOBILE_APP_DIR"
    
    # Check for ngrok tunnel first
    NGROK_URL=$(detect_ngrok_tunnel)
    
    if [[ -n "$NGROK_URL" ]]; then
        echo -e "${GREEN}🚀 Using ngrok tunnel: $NGROK_URL${NC}"
        
        # Update main.dart with ngrok URL
        perl -i -pe "s|const String BACKEND_URL = .*|const String BACKEND_URL = '$NGROK_URL';|" "$MAIN_DART_FILE"
        echo -e "${GREEN}✅ Updated main.dart with ngrok URL${NC}"
        
        # Verify the change
        echo -e "${BLUE}🔍 Current BACKEND_URL setting:${NC}"
        grep "const String BACKEND_URL" "$MAIN_DART_FILE"
        
        # Test ngrok connectivity
        if curl -s --connect-timeout 5 "$NGROK_URL/health" > /dev/null; then
            echo -e "${GREEN}✅ Backend is accessible via ngrok${NC}"
        else
            echo -e "${YELLOW}⚠️  ngrok tunnel found but backend not responding${NC}"
        fi
        
        # Prepare Flutter environment
        prepare_flutter
        
        # Run the mobile app
        run_mobile_app
    else
        # Fallback to local IP detection
        LOCAL_IP=$(get_local_ip)
        
        # Update main.dart with the IP address
        update_main_dart "$LOCAL_IP"
        
        # Test backend connectivity
        test_backend_connectivity "$LOCAL_IP"
        
        # Prepare Flutter environment
        prepare_flutter
        
        # Run the mobile app
        run_mobile_app
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Mobile app setup complete!${NC}"
    if [[ -n "$NGROK_URL" ]]; then
        echo -e "${BLUE}📱 Your mobile app is configured to connect via ngrok: $NGROK_URL${NC}"
    else
        echo -e "${BLUE}📱 Your mobile app is configured to connect to: http://$LOCAL_IP:8000${NC}"
    fi
    echo ""
    echo -e "${YELLOW}💡 Testing Tips:${NC}"
    echo "   1. Make sure backend is running: cd ../backend && ./start_live_server.sh"
    echo "   2. Start web app: cd ../web-app && npm run dev"
    echo "   3. Create session in web app and scan QR code with mobile app"
    echo "   4. Test direct HTTP upload by taking pictures"
    echo ""
    echo -e "${YELLOW}🔧 Troubleshooting:${NC}"
    echo "   - If connection fails, verify IP address: $LOCAL_IP"
    echo "   - Check firewall settings allow port 8000"
    echo "   - Ensure all devices are on the same network"
}

# Run the main function
main "$@"
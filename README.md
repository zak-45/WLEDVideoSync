Early stage .....
Cast video / image / desktop / window to ddp device e.g. WLED. All tests done on the Win version.

## WLEDVideoSync

WLEDVideoSync is a tool designed to synchronize WLED-controlled LED strips with video content. This project enables users to create immersive lighting experiences that complement their video playback.

**Key Features:**
- Video synchronization with WLED-controlled LED strips
- Multicast feature: aggregate multi WLED devices to a big, BIG one
- Support for various video sources
- Support for desktop / desktop area, window content
- Customizable LED effects

**Portable Installation:**
1. Take the app from releases (Unix/ Mac/ Win)
2. --> On Mac/Linux: chmod +x WLEDVideoSync
3. Execute it to extract the standalone version
4. Go to ./WLEDVideoSync folder and run WLEDVideoSync-{OS} app.
5. --> On Mac/Linux: chmod +x WLEDVideoSync-{OS}.bin

**Manual Installation:**
1. Clone the repository from GitHub
2. Install required dependencies : pip install -r requirements.txt
3. --> on Mac/linux : pip3 install -r requirements.txt
4. Run it with : python -m WLEDVideoSync
5. --> on Mac/linux : python3 -m WLEDVideoSync

**Usage:**
1. Connect your WLED-controlled LED strips
2. Launch the WLEDVideoSync application
3. Select your video source
4. Configure LED mapping and effects
5. Start the synchronization

**Configuration Options:**
- LED strip layout, 2D Matrix
- Color mapping
- Effect intensity
- Synchronization delay

**Troubleshooting:**
- Ensure your WLED device is properly connected and configured
- Check network connectivity between the application and WLED
- Verify video source compatibility
- On linux, wayland do not work, use X11

**Contributing:**
Contributions to the project are welcome. Please follow the standard GitHub fork and pull request workflow.

**License:**
MIT


![image](https://github.com/zak-45/WLEDVideoSync/assets/121941293/9ec42abd-657e-447e-9ef0-075c425bdd47)


![image](https://github.com/zak-45/WLEDVideoSync/assets/121941293/519584f8-af39-442a-9faf-55bf5e0b0a7c)


![image](https://github.com/zak-45/WLEDVideoSync/assets/121941293/b383d1ab-bfd8-43a7-98ac-6fd72206bc16)



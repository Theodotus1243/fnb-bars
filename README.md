# F&B's Bars

F&B's Bars is a frictionless desktop application designed to generate high-quality audio spectrum visualizations with transparency. Perfect for music producers and content creators who need a clean, reactive "bars" overlay for their videos.

![Icon](icon.ico)

## Features

- **Drag & Drop:** Simply drop an `.mp3` or `.wav` file into the app to start rendering.
- **Transparent Output:** Generates VP9 `.webm` files with a native alpha channel—perfect for overlays in OBS, Premiere, or DaVinci Resolve.
- **Customizable Settings:**
  - **Width/Height:** Control the resolution of the output video.
  - **FPS:** Set the frame rate (default 30).
  - **Bars:** Choose how many frequency bars to display (up to 128).
  - **Color:** Full hex/RGB color picker for the bars.
- **Non-Blocking UI:** The app remains responsive during rendering, showing real-time progress and ETA.

## How to Run (Windows)

1. **Download:** Get the latest `FnBs_Bars_Windows.zip` from the GitHub Actions/Releases.
2. **Extract:** Extract the ZIP file to a folder of your choice (e.g., `C:\Apps\FnBsBars`).
3. **Launch:** Open the extracted folder and double-click **`FnBs_Bars.exe`**.

## How to Create a Desktop Shortcut

To make the app easily accessible from your Desktop:

1. Open the folder where you extracted the app.
2. Find the file named **`FnBs_Bars.exe`**.
3. **Right-click** on it and select **Send to** > **Desktop (create shortcut)**.
4. You can now launch the app directly from your desktop!

## Local Development (Linux/Windows)

If you want to run the source code directly:

1. Ensure you have Python 3.10+ and `ffmpeg` installed on your system.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## Requirements

- **FFmpeg:** The standalone Windows version comes bundled with FFmpeg. No extra installation is required.
- **Supported Formats:** `.mp3`, `.wav`.

---
*Created by F&B for the music community.*

# ❄️ Icy TikTok Downloader for ComfyUI

A stylish ComfyUI custom node that downloads TikTok videos without watermarks and outputs video frames as tensors. Features a beautiful blue gradient theme with falling snow animation.

## ✨ Features

- 🎬 Download TikTok videos **without watermarks**
- 🖼️ Outputs video frames as IMAGE tensors for direct use in other nodes
- 🎛️ **Frame rate control** - Set target FPS for frame extraction
- 📊 Returns FPS information for timing synchronization
- 🔄 Multiple download methods (ssstik, snaptik, tikwm, yt-dlp)
- 📁 Saves video file for reuse
- 🏷️ Custom filename support
- ❄️ **Blue gradient theme with falling snow animation**
- 📺 **Video preview in node** (after execution)

## 🎨 Visual Theme

The node features:
- Blue gradient background (from deep blue to purple-blue)
- Glowing cyan borders
- Animated falling snowflakes ❄️
- Hover effects with enhanced glow
- Icy color scheme throughout

## Installation

### Method 1: ComfyUI Manager (Recommended)

1. Open ComfyUI Manager
2. Search for "Icy TikTok Downloader"
3. Click Install

### Method 2: Manual Installation

1. Navigate to your ComfyUI `custom_nodes` folder:
   ```bash
   cd ComfyUI/custom_nodes
   ```

2. Clone this repository:
   ```bash
   git clone https://github.com/your-username/ComfyUI-TikTokDownloader.git
   ```

3. Install dependencies:
   ```bash
   pip install -r ComfyUI-TikTokDownloader/requirements.txt
   ```

4. Restart ComfyUI

## Usage

### ❄️ Icy TikTok Downloader (Full)

This node provides full control over the download process and outputs video frames.

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| tiktok_url | STRING | - | The TikTok video URL to download |
| download_method | ENUM | ssstik | Download method: ssstik, snaptik, tikwm, yt-dlp |
| frame_count | INT | 0 | Number of frames to extract (0 = all frames) |
| target_fps | FLOAT | 0.0 | Target FPS for extraction (0 = original FPS) |
| custom_filename | STRING | - | Optional custom filename (without .mp4) |

**Outputs:**
| Output | Type | Description |
|--------|------|-------------|
| frames | IMAGE | Video frames as tensor [N, H, W, C] (0-1 normalized) |
| frame_count | INT | Number of frames extracted |
| fps | FLOAT | Actual FPS of extracted frames |
| video_path | STRING | Path to the downloaded video file |
| video_info | STRING | JSON string with video metadata |

### ❄️ Icy TikTok Downloader (Simple)

A simplified version with minimal inputs.

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| tiktok_url | STRING | - | The TikTok video URL to download |

**Outputs:**
| Output | Type | Description |
|--------|------|-------------|
| frames | IMAGE | Video frames as tensor |
| frame_count | INT | Number of frames extracted |
| fps | FLOAT | FPS of extracted frames |
| video_path | STRING | Path to the downloaded video file |

## Download Methods

### ssstik (Default)
Uses ssstik.io service - reliable for most videos.

### snaptik
Uses snaptik.app service - alternative method.

### tikwm
Uses tikwm.com API - direct API access.

### yt-dlp
Uses the yt-dlp library - most reliable but may include watermarks.

## Frame Rate Control

The `target_fps` parameter allows you to control the frame extraction rate:

- **0.0** (default): Extract at original video FPS
- **30.0**: Extract at 30 FPS (good for most workflows)
- **24.0**: Cinema standard
- **15.0**: Lower frame count for faster processing

The node will skip frames as needed to achieve the target FPS while maintaining temporal accuracy.

## Example Workflow

```
[TikTok URL] → [❄️ Icy TikTok Downloader] → [frames] → [VAE Encoder] → [Latent]
                                           → [frame_count]
                                           → [fps] → [Timing calculations]
                                           → [video_path] → [Video Save]
```

1. Add the "❄️ Icy TikTok Downloader" node to your workflow
2. Paste a TikTok video URL
3. Set `target_fps` to control frame rate (e.g., 30 for smooth playback)
4. Connect the `frames` output to your next node (e.g., VAE Encode)
5. Run the workflow

## Supported URL Formats

- `https://www.tiktok.com/@username/video/1234567890`
- `https://vm.tiktok.com/ZM6abc123/`
- `https://vt.tiktok.com/ZS6abc123/`

## Frame Output Format

The `frames` output is a tensor with shape `[N, H, W, C]` where:
- N = number of frames
- H = height (pixels)
- W = width (pixels)
- C = channels (3 for RGB)

Values are normalized to 0-1 range (float32).

## Troubleshooting

### Video won't download
- Ensure the URL is correct and the video is publicly accessible
- Try a different download method
- Check if the video has been removed from TikTok

### Watermark still appears
- Try "ssstik" or "snaptik" methods first
- Some videos may have embedded watermarks that cannot be removed

### No frames extracted
- Ensure OpenCV is installed: `pip install opencv-python`
- Check console for error messages

### Snow animation not showing
- Ensure JavaScript is enabled in ComfyUI
- Check browser console for errors
- Refresh the page

### Module not found errors
- Run `pip install -r requirements.txt` in the node directory
- Restart ComfyUI after installing dependencies

## Requirements

- Python 3.8+
- requests
- opencv-python
- numpy
- yt-dlp (optional)
- torch (provided by ComfyUI)

## File Structure

```
ComfyUI-TikTokDownloader/
├── __init__.py              # Module initialization
├── icy_tiktok_downloader.py # Main node implementation
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── js/
    └── icy_tiktok.js       # Frontend theme & snow animation
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for personal use only. Please respect TikTok's Terms of Service and copyright laws when downloading videos.

---

Made with ❄️ for ComfyUI

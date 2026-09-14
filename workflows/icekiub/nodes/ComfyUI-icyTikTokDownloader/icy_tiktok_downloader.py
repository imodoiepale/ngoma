"""
Icy TikTok Video Downloader Node for ComfyUI
Downloads TikTok videos without watermark and outputs video frames
Features: Blue gradient theme with falling snow animation
"""

import os
import requests
import re
import hashlib
import json
import numpy as np
import torch
from urllib.parse import urljoin

# ComfyUI imports
import folder_paths

# Try to import cv2 for video processing
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Try to import optional dependencies
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


class IcyTikTokDownloader:
    """
    ComfyUI node to download TikTok videos without watermark.
    Outputs video frames as tensors for use in other nodes.
    Features a blue gradient theme with falling snow animation.
    """
    
    def __init__(self):
        # Save to output/icytiktok folder
        self.output_dir = os.path.join(folder_paths.get_output_directory(), "icytiktok")
        os.makedirs(self.output_dir, exist_ok=True)
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tiktok_url": ("STRING", {
                    "default": "https://www.tiktok.com/@user/video/1234567890",
                    "multiline": False
                }),
                "download_method": (["ssstik", "snaptik", "tikwm", "yt-dlp"], {
                    "default": "ssstik"
                }),
                "frame_count": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "step": 1
                }),
                "target_fps": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 120.0,
                    "step": 0.5
                }),
            },
            "optional": {
                "custom_filename": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "INT", "FLOAT", "STRING", "STRING", "STRING",)
    RETURN_NAMES = ("frames", "frame_count", "fps", "video_path", "video_info", "audio_path",)
    FUNCTION = "download_video"
    CATEGORY = "video"
    OUTPUT_NODE = True
    
    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from TikTok URL."""
        patterns = [
            r'/video/(\d+)',
            r'/v/(\d+)',
            r'vm\.tiktok\.com/(\w+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def _get_video_via_tikwm(self, url: str) -> dict:
        """Download TikTok video using tikwm.com API."""
        api_url = "https://www.tikwm.com/api/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://www.tikwm.com',
            'Referer': 'https://www.tikwm.com/',
        }
        
        try:
            response = requests.post(
                api_url, 
                data={'url': url, 'count': 12, 'cursor': 0, 'web': 1, 'hd': 1},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0 and data.get('data'):
                video_data = data['data']
                # Get HD video URL if available, otherwise regular
                video_url = video_data.get('hd_play') or video_data.get('play')
                
                # Fix relative URL
                if video_url and video_url.startswith('/'):
                    video_url = 'https://www.tikwm.com' + video_url
                
                return {
                    'success': True,
                    'video_url': video_url,
                    'title': video_data.get('title', ''),
                    'author': video_data.get('author', {}).get('nickname', 'unknown'),
                    'video_id': str(video_data.get('id', '')),
                    'duration': video_data.get('duration', 0),
                }
        except Exception as e:
            print(f"[IcyTikTok] tikwm API error: {e}")
        
        return {'success': False, 'error': 'Failed to fetch video via tikwm API'}
    
    def _get_video_via_ssstik(self, url: str) -> dict:
        """Download TikTok video using ssstik.io method."""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            })
            
            # Try ssstik.io API
            response = session.post(
                'https://ssstik.io/en',
                data={'id': url, 'locale': 'en', 'tt': '0'},
                timeout=30
            )
            
            if response.status_code == 200:
                html = response.text
                # Look for video URL in the response
                match = re.search(r'href="(https://[^"]*\.mp4[^"]*)"', html)
                if match:
                    video_url = match.group(1)
                    return {
                        'success': True,
                        'video_url': video_url,
                        'title': '',
                        'author': 'unknown',
                        'video_id': self._extract_video_id(url),
                        'duration': 0,
                    }
        except Exception as e:
            print(f"[IcyTikTok] ssstik error: {e}")
        
        return {'success': False, 'error': 'Failed to fetch video via ssstik'}
    
    def _get_video_via_snaptik(self, url: str) -> dict:
        """Download TikTok video using snaptik.app method."""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            })
            
            # Get the main page first
            response = session.get('https://snaptik.app/', timeout=30)
            
            # Extract token if present
            token_match = re.search(r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', response.text)
            token = token_match.group(1) if token_match else ''
            
            # Make API request
            api_url = 'https://snaptik.app/abc2.php'
            response = session.post(
                api_url,
                data={'url': url, 'token': token},
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok' and data.get('data'):
                    video_url = data['data']
                    if isinstance(video_url, list):
                        video_url = video_url[0] if video_url else ''
                    elif isinstance(video_url, dict):
                        video_url = video_url.get('url', '')
                    
                    if video_url:
                        return {
                            'success': True,
                            'video_url': video_url,
                            'title': '',
                            'author': 'unknown',
                            'video_id': self._extract_video_id(url),
                            'duration': 0,
                        }
        except Exception as e:
            print(f"[IcyTikTok] snaptik error: {e}")
        
        return {'success': False, 'error': 'Failed to fetch video via snaptik'}
    
    def _get_video_via_yt_dlp(self, url: str) -> dict:
        """Download TikTok video using yt-dlp library."""
        if not YT_DLP_AVAILABLE:
            return {'success': False, 'error': 'yt-dlp not installed'}
        
        try:
            ydl_opts = {
                'format': 'best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_url = None
                
                if 'url' in info:
                    video_url = info['url']
                elif 'manifest_url' in info:
                    video_url = info['manifest_url']
                elif 'formats' in info:
                    for fmt in info['formats']:
                        if fmt.get('url') and fmt.get('vcodec') != 'none':
                            video_url = fmt['url']
                            break
                
                if video_url:
                    return {
                        'success': True,
                        'video_url': video_url,
                        'title': info.get('title', ''),
                        'author': info.get('uploader', 'unknown'),
                        'video_id': info.get('id', ''),
                        'duration': info.get('duration', 0),
                    }
        except Exception as e:
            print(f"[IcyTikTok] yt-dlp error: {e}")
        
        return {'success': False, 'error': 'yt-dlp extraction failed'}
    
    def _download_file(self, url: str, output_path: str) -> bool:
        """Download file from URL to output path."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',
            }
            response = requests.get(url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"[IcyTikTok] Download error: {e}")
            return False
    
    def _extract_audio(self, video_path: str) -> str:
        """
        Extract audio from video file and save as WAV.
        Returns the path to the audio file, or empty string if extraction failed.
        """
        try:
            import subprocess
            
            # Generate audio filename
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            audio_path = os.path.join(self.output_dir, f"{video_basename}.wav")
            
            # Try ffmpeg first
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                     "-ar", "44100", "-ac", "2", audio_path],
                    capture_output=True,
                    timeout=60
                )
                if result.returncode == 0 and os.path.exists(audio_path):
                    print(f"[IcyTikTok] Extracted audio to: {audio_path}")
                    return audio_path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Try moviepy as fallback
            try:
                from moviepy.editor import VideoFileClip
                with VideoFileClip(video_path) as clip:
                    if clip.audio is not None:
                        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
                        print(f"[IcyTikTok] Extracted audio to: {audio_path}")
                        return audio_path
            except ImportError:
                print("[IcyTikTok] moviepy not available for audio extraction")
            except Exception as e:
                print(f"[IcyTikTok] moviepy audio extraction failed: {e}")
            
            print("[IcyTikTok] Audio extraction failed - no audio track or extractor available")
            return ""
            
        except Exception as e:
            print(f"[IcyTikTok] Audio extraction error: {e}")
            return ""
    
    def _load_video_frames(self, video_path: str, max_frames: int = 0, target_fps: float = 0.0) -> tuple:
        """
        Load video frames as tensor.
        Target FPS selects every Nth frame to match the target rate (doesn't slow playback).
        Returns (frames_tensor, frame_count, fps).
        """
        if not CV2_AVAILABLE:
            print("[IcyTikTok] OpenCV not available, cannot extract frames")
            return (torch.zeros(1, 512, 512, 3), 0, 30.0)
        
        if not os.path.exists(video_path):
            print(f"[IcyTikTok] Video file not found: {video_path}")
            return (torch.zeros(1, 512, 512, 3), 0, 30.0)
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[IcyTikTok] Cannot open video: {video_path}")
                return (torch.zeros(1, 512, 512, 3), 0, 30.0)
            
            # Get video properties
            original_fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate frame skip to achieve target FPS (select every Nth frame)
            frame_skip = 1
            effective_fps = original_fps
            if target_fps > 0 and target_fps < original_fps:
                frame_skip = max(1, int(round(original_fps / target_fps)))
                effective_fps = original_fps / frame_skip
            
            # Calculate how many frames we can extract with skip
            max_extractable = total_frames // frame_skip
            if max_frames > 0:
                frames_to_extract = min(max_frames, max_extractable)
            else:
                frames_to_extract = max_extractable
            
            frames = []
            frame_idx = 0
            
            while len(frames) < frames_to_extract:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Only keep frames based on skip rate
                if frame_idx % frame_skip == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)
                
                frame_idx += 1
            
            cap.release()
            
            if not frames:
                print("[IcyTikTok] No frames extracted from video")
                return (torch.zeros(1, 512, 512, 3), 0, effective_fps)
            
            # Convert to tensor [N, H, W, C] normalized to 0-1
            frames_array = np.stack(frames, axis=0)
            frames_tensor = torch.from_numpy(frames_array).float() / 255.0
            
            print(f"[IcyTikTok] Extracted {len(frames)} frames (every {frame_skip}th frame), effective {effective_fps:.2f} FPS, shape: {frames_tensor.shape}")
            return (frames_tensor, len(frames), effective_fps)
            
        except Exception as e:
            print(f"[IcyTikTok] Error extracting frames: {e}")
            return (torch.zeros(1, 512, 512, 3), 0, 30.0)
    
    def download_video(self, tiktok_url: str, download_method: str = "ssstik", 
                       frame_count: int = 0, target_fps: float = 0.0,
                       custom_filename: str = ""):
        """
        Main function to download TikTok video without watermark.
        Returns video frames as tensor.
        """
        print(f"[IcyTikTok] ❄️ Downloading: {tiktok_url}")
        print(f"[IcyTikTok] Method: {download_method}, Target FPS: {target_fps}")
        
        # Clean URL
        tiktok_url = tiktok_url.strip()
        if not tiktok_url:
            empty_tensor = torch.zeros(1, 512, 512, 3)
            return (empty_tensor, 0, 30.0, "", "Error: No URL provided")
        
        # Get video info based on method
        result = None
        if download_method == "tikwm":
            result = self._get_video_via_tikwm(tiktok_url)
        elif download_method == "ssstik":
            result = self._get_video_via_ssstik(tiktok_url)
        elif download_method == "snaptik":
            result = self._get_video_via_snaptik(tiktok_url)
        elif download_method == "yt-dlp":
            result = self._get_video_via_yt_dlp(tiktok_url)
        
        if not result or not result.get('success'):
            error_msg = result.get('error', 'Unknown error') if result else 'No result'
            print(f"[IcyTikTok] Failed to get video: {error_msg}")
            empty_tensor = torch.zeros(1, 512, 512, 3)
            return (empty_tensor, 0, 30.0, "", f"Error: {error_msg}")
        
        video_url = result.get('video_url')
        if not video_url:
            empty_tensor = torch.zeros(1, 512, 512, 3)
            return (empty_tensor, 0, 30.0, "", "Error: No video URL found")
        
        print(f"[IcyTikTok] Video URL: {video_url}")
        
        # Generate filename
        video_id = result.get('video_id', self._extract_video_id(tiktok_url))
        if custom_filename:
            safe_filename = re.sub(r'[^\w\-_\.]', '_', custom_filename)
            if not safe_filename.endswith('.mp4'):
                safe_filename += '.mp4'
            filename = safe_filename
        else:
            filename = f"tiktok_{video_id}.mp4"
        
        output_path = os.path.join(self.output_dir, filename)
        
        # Download the video
        print(f"[IcyTikTok] Downloading to: {output_path}")
        if self._download_file(video_url, output_path):
            # Load video frames
            frames_tensor, num_frames, fps = self._load_video_frames(output_path, frame_count, target_fps)
            
            # Extract audio
            audio_path = self._extract_audio(output_path)
            
            video_info = json.dumps({
                'title': result.get('title', ''),
                'author': result.get('author', ''),
                'video_id': video_id,
                'duration': result.get('duration', 0),
                'file_path': output_path,
                'audio_path': audio_path,
                'frames_extracted': num_frames,
                'fps': fps,
            }, indent=2)
            
            print(f"[IcyTikTok] Successfully downloaded and extracted {num_frames} frames")
            return (frames_tensor, num_frames, fps, output_path, video_info, audio_path)
        else:
            empty_tensor = torch.zeros(1, 512, 512, 3)
            return (empty_tensor, 0, 30.0, "", "Error: Failed to download video file", "")


class IcyTikTokDownloaderSimple:
    """
    Simplified Icy TikTok downloader node with minimal inputs.
    """
    
    def __init__(self):
        # Save to output/icytiktok folder
        self.output_dir = os.path.join(folder_paths.get_output_directory(), "icytiktok")
        os.makedirs(self.output_dir, exist_ok=True)
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tiktok_url": ("STRING", {
                    "default": "https://www.tiktok.com/@user/video/1234567890",
                    "multiline": False
                }),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "INT", "FLOAT", "STRING", "STRING",)
    RETURN_NAMES = ("frames", "frame_count", "fps", "video_path", "audio_path",)
    FUNCTION = "download_video"
    CATEGORY = "video"
    OUTPUT_NODE = True
    
    def download_video(self, tiktok_url: str):
        """Download TikTok video without watermark and return frames."""
        downloader = IcyTikTokDownloader()
        frames, num_frames, fps, video_path, _, audio_path = downloader.download_video(
            tiktok_url, "ssstik", 0, 0.0, ""
        )
        return (frames, num_frames, fps, video_path, audio_path,)


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "IcyTikTokDownloader": IcyTikTokDownloader,
    "IcyTikTokDownloaderSimple": IcyTikTokDownloaderSimple,
}

# Display names for the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    "IcyTikTokDownloader": "❄️ Icy TikTok Downloader",
    "IcyTikTokDownloaderSimple": "❄️ Icy TikTok Downloader (Simple)",
}

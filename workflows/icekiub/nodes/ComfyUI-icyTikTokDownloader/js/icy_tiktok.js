/**
 * Icy TikTok Downloader - ComfyUI Node Extension
 * Simple video preview widget
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * Create video preview widget
 */
function createVideoPreview(node, videoPath) {
    if (!node.domElement || !videoPath) return;
    
    // Remove existing preview
    if (node.icyVideoContainer) {
        node.icyVideoContainer.remove();
    }
    
    // Extract filename
    const filename = videoPath.split(/[/\\]/).pop();
    
    // Create container
    const container = document.createElement("div");
    container.style.cssText = `
        background: rgba(0,0,0,0.1);
        border: 1px solid #555;
        border-radius: 4px;
        padding: 6px;
        margin: 4px 0;
    `;
    
    // Label
    const label = document.createElement("div");
    label.style.cssText = `
        color: #aaa;
        font-size: 10px;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    `;
    label.textContent = `Video: ${filename}`;
    container.appendChild(label);
    
    // Video element
    const video = document.createElement("video");
    video.controls = true;
    video.muted = true;
    video.preload = "metadata";
    video.style.cssText = "width: 100%; max-height: 180px; border-radius: 2px; background: #000;";
    
    // Set video source via ComfyUI API
    const videoUrl = api.apiURL(`/view?filename=${encodeURIComponent(filename)}&subfolder=icytiktok&type=output`);
    video.src = videoUrl;
    
    container.appendChild(video);
    
    // Append to node
    const widgetArea = node.domElement.querySelector(".node-content") || 
                       node.domElement.querySelector(".node-widgets") ||
                       node.domElement;
    widgetArea.appendChild(container);
    
    node.icyVideoContainer = container;
    
    console.log(`[IcyTikTok] Video preview: ${filename}`);
}

// Register the extension
app.registerExtension({
    name: "ComfyUI.IcyTikTokDownloader",
    
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "IcyTikTokDownloader" && nodeData.name !== "IcyTikTokDownloaderSimple") {
            return;
        }
        
        const origOnExecuted = nodeType.prototype.onExecuted;
        
        nodeType.prototype.onExecuted = function(message) {
            const result = origOnExecuted?.apply(this, arguments);
            
            // Extract video path from message
            let videoPath = null;
            
            if (message) {
                if (message.video_path) {
                    videoPath = Array.isArray(message.video_path) 
                        ? message.video_path[0] 
                        : message.video_path;
                }
                else if (message.result && Array.isArray(message.result) && message.result.length >= 4) {
                    videoPath = message.result[3];
                }
            }
            
            if (videoPath) {
                requestAnimationFrame(() => {
                    setTimeout(() => createVideoPreview(this, videoPath), 100);
                });
            }
            
            return result;
        };
    }
});

console.log("[IcyTikTok] Extension loaded");

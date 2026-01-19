// --- Iframe Internal Script ---

// --- Iframe Internal Script ---

// Flags and element references
let revealInitialized = false;
let initialContentLoaded = false; // Flag for first content load
let currentSlideElement = null;
let currentSlideWrapper = null;
let currentDynamicStyles = null;

// Get basePath from window (set by parent frame)
const basePath = window.BASE_PATH || '';

// Define library URLs (copied from src/components/CodePreviewSandbox/templates/externalLibraries.ts)
const libraryUrls = {
  revealJs: `${basePath}/vendor/revealjs/reveal.js`,
  markedJs: `${basePath}/vendor/marked.min.js`,
  chartJs: `${basePath}/vendor/chart.umd.js`,
  fabricJs: `${basePath}/vendor/fabric.min.js`,
  momentJs: `${basePath}/vendor/moment-with-locales.min.js`,
  highlightJs: `${basePath}/vendor/highlight.min.js`,
  lodashJs: `${basePath}/vendor/lodash.min.js`,
  xlsxPopulateJs: `${basePath}/vendor/xlsx-populate.min.js`,
  mermaidJs: `${basePath}/vendor/mermaid.js`,
  domToImageJs: 'https://cdn.bootcdn.net/ajax/libs/dom-to-image/2.6.0/dom-to-image.min.js',
  fileSaverJs: 'https://cdn.bootcdn.net/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js',
};

// Helper function to dynamically load a script
function loadScript(url, async = true, defer = true) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url;
    script.async = async;
    script.defer = defer;
    script.onload = () => {
      resolve();
    };
    script.onerror = (e) => {
      reject(new Error(`Failed to load script: ${url}`));
    };
    document.body.appendChild(script); // Append to body
  });
}

// Helper function to dynamically load a CSS file
function loadCSS(url) {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = url;
    link.onload = () => {
      resolve();
    };
    link.onerror = (e) => {
      reject(new Error(`Failed to load CSS: ${url}`));
    };
    document.head.appendChild(link); // Append to head
  });
}


// Function to initialize RevealJS and get references
function initializeReveal(includeMermaidPlugin = false) { // Add parameter
  if (revealInitialized) return; // Should not happen with new logic, but safe guard

  const revealPlugins = [];
  if (includeMermaidPlugin && window.RevealMermaid) { // Check if plugin should be included AND exists
      revealPlugins.push(RevealMermaid);
  } else if (includeMermaidPlugin && !window.RevealMermaid) {
  }

  Reveal.initialize({
    embedded: true, 
    controls: false,  // 禁用导航控制按钮
    progress: false,  // 禁用进度条
    slideNumber: false,  // 禁用幻灯片编号
    keyboard: false,  // 禁用键盘导航（避免干扰内容交互）
    touch: false,
    mouseWheel: false,  // 禁用鼠标滚轮切换
    hideAddressBar: true,  // 移动设备上隐藏地址栏
    width: "100%",
    height: "100%",
    margin: 0,
    minScale: 1,
    maxScale: 1,
    center: false,
    // Optional Mermaid configuration
    mermaid: {
      // Example config: theme: 'dark'
    },
    // Dynamically add Mermaid plugin
    plugins: revealPlugins,
  });

  // Get references AFTER initialization
  currentSlideElement = document.getElementById('slide-content-section');
  currentSlideWrapper = currentSlideElement?.querySelector('.slide-content-wrapper');
  currentDynamicStyles = document.getElementById('dynamic-styles');

  if (!currentSlideElement || !currentSlideWrapper || !currentDynamicStyles) {
      return; // Stop if elements aren't found
  }

  // --- Function to set wrapper height --- (Remains the same)
  function setWrapperHeight() {
    if (currentSlideWrapper) {
      const slidesContainer = document.querySelector('.slides');
      if (slidesContainer) {
        const slidesHeight = slidesContainer.offsetHeight; // Get rendered height
        currentSlideWrapper.style.height = slidesHeight + 'px';
      }
    }
  }

  // Set initial height after Reveal is ready
  setWrapperHeight();

  // Adjust height and trigger layout on resize events
  const handleResize = () => {
    setWrapperHeight(); // This function updates currentSlideWrapper's height based on .slides
    // Explicitly call layout after a short delay to ensure dimensions are updated
    // and the reveal container itself has valid dimensions.
    setTimeout(() => {
        const revealElement = document.querySelector('.reveal');
        if (Reveal.isReady() && revealElement && revealElement.offsetWidth > 0 && revealElement.offsetHeight > 0) {
            try {
                Reveal.layout();
            } catch (e) {
                // Optionally, send an error message back to the parent
                window.parent.postMessage({ type: 'revealLayoutError', payload: { error: e.message || 'Unknown Reveal.layout error' } }, '*');
            }
        } else {
        }
    }, 100); // Increased delay to 100ms
  };

  Reveal.on('resize', handleResize); // Reveal's internal resize event

  let windowResizeTimeout; // Renamed to avoid conflict if any
  window.addEventListener('resize', () => {
    clearTimeout(windowResizeTimeout);
    // Debounce window resize. The delay here should perhaps be longer
    // or coordinated with Reveal's own resize handling.
    windowResizeTimeout = setTimeout(handleResize, 250); // Increased debounce to 250ms
  });

  // Removed duplicate block

  revealInitialized = true; // Mark as initialized

  // Signal readiness is now sent immediately after script load, not here.
}

// Function to execute slide-specific JS (Remains the same)
function executeSlideScript(jsCode, wrapper) {
  if (!jsCode || !wrapper) return;
  try {
    const scriptFunction = new Function('slideWrapper', jsCode);
    scriptFunction(wrapper);
  } catch (e) {
  }
}

// --- Function to capture an element by ID and handle internal images ---
async function captureElementById(elementId) {
  // --- MODIFIED: Get both target and container elements ---
  const targetElement = document.getElementById(elementId);
  const containerElement = document.querySelector('.slides'); // Capture the container first
  // --- END MODIFIED ---

  if (!targetElement) {
    throw new Error(`Target element with ID "${elementId}" not found inside iframe.`);
  }
  if (!containerElement) {
    throw new Error(`Container element '.slides' not found inside iframe.`);
  }
  if (!window.domtoimage) {
    throw new Error('dom-to-image-more library is not available.');
  }

  // Set scale factor for higher resolution images
  const scaleFactor = 2;

  // --- MODIFIED: Declare originalSources outside try block ---
  let originalSources = new Map(); // Store original src and corresponding Blob URL
  // --- END MODIFIED ---
  // --- Store original styles ---
  const originalStyles = new Map();
  
  // Get all elements within the target element, including the target itself
  const allElementsToStyle = [targetElement, containerElement, ...Array.from(targetElement.querySelectorAll('*'))];
  
  allElementsToStyle.forEach(el => {
      if (el && el.style) {
          originalStyles.set(el, {
              border: el.style.border,
              outline: el.style.outline,
              boxShadow: el.style.boxShadow,
              borderRadius: el.style.borderRadius,
              borderColor: el.style.borderColor,
              borderWidth: el.style.borderWidth,
              borderStyle: el.style.borderStyle
          });
      }
  });

  try {
    // --- Apply temporary styles to remove borders ---
    allElementsToStyle.forEach(el => {
        if (el && el.style) {
            // Set all border-related properties to none with !important, but PRESERVE border-radius
            el.style.setProperty('border', 'none', 'important');
            el.style.setProperty('border-top', 'none', 'important');
            el.style.setProperty('border-right', 'none', 'important');
            el.style.setProperty('border-bottom', 'none', 'important');
            el.style.setProperty('border-left', 'none', 'important');
            el.style.setProperty('border-width', '0', 'important');
            el.style.setProperty('border-style', 'none', 'important');
            el.style.setProperty('border-color', 'transparent', 'important');
            // REMOVED: el.style.setProperty('border-radius', '0', 'important');
            el.style.setProperty('outline', 'none', 'important');
            el.style.setProperty('box-shadow', 'none', 'important');
        }
    });

    // --- OPTIMIZED: Improved image processing with caching strategy ---
    // Find all images within the container
    const images = containerElement.querySelectorAll('img');
    
    // If there are images, only process them using a more efficient approach
    if (images.length > 0) {
      // Add a loading message to inform user
      const loadingMsg = document.createElement('div');
      loadingMsg.style.cssText = 'position:fixed;top:10px;right:10px;background:rgba(0,0,0,0.7);color:white;padding:8px;border-radius:4px;font-size:14px;z-index:9999;';
      loadingMsg.textContent = `Preparing ${images.length} images for capture...`;
      document.body.appendChild(loadingMsg);
      
      // Create a global cache if it doesn't exist to avoid downloading the same image twice
      window._imageBlobCache = window._imageBlobCache || new Map();
      
      // Process images in parallel but with a concurrency limit to avoid overwhelming the browser
      const concurrencyLimit = 3; // Process max 3 images at once
      const imageGroups = [];
      for (let i = 0; i < images.length; i += concurrencyLimit) {
        imageGroups.push(Array.from(images).slice(i, i + concurrencyLimit));
      }
      
      for (const imageGroup of imageGroups) {
        await Promise.all(imageGroup.map(async (img) => {
          const originalSrc = img.src;
          
          // Skip if no src or already a blob URL or data URL
          if (!originalSrc || originalSrc.startsWith('blob:') || originalSrc.startsWith('data:')) {
            return;
          }
          
          // Check if image is already in cache
          if (window._imageBlobCache.has(originalSrc)) {
            const blobUrl = window._imageBlobCache.get(originalSrc);
            originalSources.set(img, { original: originalSrc, blob: blobUrl });
            img.src = blobUrl;
            return;
          }
          
          try {
            // Use a simpler fetch strategy with one retry
            const fetchImage = async (url, retry = false) => {
              const cacheBuster = retry ? `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}` : url;
              const response = await fetch(cacheBuster, { cache: 'force-cache' }); // Try to use browser cache
              if (!response.ok) {
                throw new Error(`Failed to fetch image: ${response.statusText}`);
              }
              return response.blob();
            };
            
            let imageBlob;
            try {
              imageBlob = await fetchImage(originalSrc);
            } catch (e) {
              // One retry with cache busting
              imageBlob = await fetchImage(originalSrc, true);
            }
            
            const blobUrl = URL.createObjectURL(imageBlob);
            window._imageBlobCache.set(originalSrc, blobUrl); // Add to global cache
            originalSources.set(img, { original: originalSrc, blob: blobUrl });
            img.src = blobUrl;
          } catch (fetchError) {
            // Don't let one image failure stop the entire process
          }
        }));
        
        // Update progress message
        loadingMsg.textContent = `Processed ${Math.min(imageGroups.indexOf(imageGroup) * concurrencyLimit + imageGroup.length, images.length)}/${images.length} images...`;
      }
      
      // Remove loading message
      document.body.removeChild(loadingMsg);
    }
    // --- END OPTIMIZED IMAGE PROCESSING ---

    // Wait for fonts
    try {
        await document.fonts.ready;
    } catch (fontError) {
    }

    // Add a small delay to ensure everything is rendered
    await new Promise(resolve => setTimeout(resolve, 100));

    // Get dimensions
    const containerWidth = containerElement.offsetWidth;
    const containerHeight = containerElement.offsetHeight;
    const containerRect = containerElement.getBoundingClientRect();
    const targetRect = targetElement.getBoundingClientRect();
    const cropX = targetRect.left - containerRect.left;
    const cropY = targetRect.top - containerRect.top;
    const cropWidth = targetRect.width;
    const cropHeight = targetRect.height;

    // --- OPTIMIZED: Improved dom-to-image configuration ---
    
    // Use more efficient configuration for dom-to-image
    const domToImageOptions = {
      width: containerWidth * scaleFactor,
      height: containerHeight * scaleFactor,
      quality: 0.95,
      cacheBust: false, // Don't add cache busting query params (we already handled this)
      imagePlaceholder: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', // Transparent 1x1 pixel
      style: {
        transform: `scale(${scaleFactor})`,
        transformOrigin: 'top left',
        width: `${containerWidth}px`,
        height: `${containerHeight}px`
      }
    };
    
    const containerBlob = await domtoimage.toBlob(containerElement, domToImageOptions);

    // --- OPTIMIZED: Better cropping strategy with OffscreenCanvas when available ---
    const croppedBlob = await new Promise((resolve, reject) => {
      const img = new Image();
      
      // Use OffscreenCanvas if available for better performance
      const useOffscreenCanvas = typeof OffscreenCanvas !== 'undefined';
      const canvas = useOffscreenCanvas ? 
        new OffscreenCanvas(cropWidth * scaleFactor, cropHeight * scaleFactor) : 
        document.createElement('canvas');
        
      if (!useOffscreenCanvas) {
        canvas.width = cropWidth * scaleFactor;
        canvas.height = cropHeight * scaleFactor;
      }
      
      const ctx = canvas.getContext('2d', { alpha: true });
      const url = URL.createObjectURL(containerBlob);

      img.onload = () => {
        // Draw the specific portion of the container image
        ctx.drawImage(
          img,
          cropX * scaleFactor,
          cropY * scaleFactor,
          cropWidth * scaleFactor,
          cropHeight * scaleFactor,
          0, 0,
          cropWidth * scaleFactor,
          cropHeight * scaleFactor
        );

        // Convert to blob
        if (useOffscreenCanvas) {
          // OffscreenCanvas has a direct convertToBlob method
          canvas.convertToBlob({ type: 'image/png', quality: 0.95 })
            .then(resolve)
            .catch(reject);
        } else {
          canvas.toBlob(resolve, 'image/png', 0.95);
        }
        
        URL.revokeObjectURL(url);
      };
      
      img.onerror = (err) => {
        URL.revokeObjectURL(url);
        reject(new Error('Failed to load container image for cropping.'));
      };
      
      img.src = url;
    });

    return croppedBlob;

  } catch (error) {
    throw error;
  } finally {
    // --- Restore original styles ---
    originalStyles.forEach((styles, el) => {
      if (el && el.style) {
        el.style.border = styles.border;
        el.style.outline = styles.outline;
        el.style.boxShadow = styles.boxShadow;
        el.style.borderRadius = styles.borderRadius;
        el.style.borderColor = styles.borderColor;
        el.style.borderWidth = styles.borderWidth;
        el.style.borderStyle = styles.borderStyle;
      }
    });

    // Cleanup: Restore original src and revoke Blob URLs
    originalSources.forEach((urls, img) => {
      if (img && urls.original) {
        img.src = urls.original;
      }
      // Note: We don't revoke URLs if they're in the global cache
      if (urls.blob && window._imageBlobCache && !window._imageBlobCache.has(urls.original)) {
        URL.revokeObjectURL(urls.blob);
      }
    });
    
    // Limit cache size to prevent memory issues (keep only the 20 most recent entries)
    if (window._imageBlobCache && window._imageBlobCache.size > 20) {
      const oldestKeys = Array.from(window._imageBlobCache.keys()).slice(0, window._imageBlobCache.size - 20);
      oldestKeys.forEach(key => {
        URL.revokeObjectURL(window._imageBlobCache.get(key));
        window._imageBlobCache.delete(key);
      });
    }
  }
}
// --- Message Listener ---
window.addEventListener('message', (event) => {
  // IMPORTANT: Add origin check in production for security
  // if (event.origin !== 'expected-origin') return;

  const message = event.data;

  // Handle theme updates
  if (message.type === 'updateTheme') {
    const { backgroundColor, textColor } = message.payload;
    if (backgroundColor) {
      document.documentElement.style.setProperty('--iframe-background', backgroundColor);
    }
    if (textColor) {
      document.documentElement.style.setProperty('--iframe-text', textColor);
    }
    return;
  }

  if (message.type === 'updateContent') {
    const { html, css, js } = message.payload;

    // Get dynamic style and wrapper elements (ensure they are available)
    if (!currentDynamicStyles) {
        currentDynamicStyles = document.getElementById('dynamic-styles');
    }
    if (!currentSlideWrapper) {
        const slideElement = document.getElementById('slide-content-section');
        currentSlideWrapper = slideElement?.querySelector('.slide-content-wrapper');
    }

    if (!currentDynamicStyles || !currentSlideWrapper) {
        return;
    }

    // Inject CSS and HTML first
    currentDynamicStyles.textContent = css || '';
    currentSlideWrapper.innerHTML = html;

    // Determine which libraries are needed
    const librariesToLoad = [];
    const coreLibraries = [
      libraryUrls.revealJs,
      libraryUrls.markedJs,
      libraryUrls.highlightJs,
      // Add other core libraries if necessary, e.g., lodash, moment
      libraryUrls.lodashJs,
      libraryUrls.momentJs,
      libraryUrls.fabricJs, // Fabric.js might be needed for some content types
      libraryUrls.xlsxPopulateJs, // XlsxPopulate might be needed
    ];

    librariesToLoad.push(...coreLibraries);

    // Check for optional libraries based on content
    if (html.includes('<pre class="mermaid">') || html.includes('graph TD') || html.includes('sequenceDiagram')) {
      librariesToLoad.push(libraryUrls.mermaidJs);
    }
    // MODIFIED: Load Chart.js if any <canvas> element is present in the HTML.
    // This is a broader condition than before. Consider refining if <canvas> is used extensively for non-chart purposes.
    if (html.includes('<canvas')) {
       librariesToLoad.push(libraryUrls.chartJs);
    }

    // Load libraries if not already loaded
    const loadPromises = librariesToLoad.map(url => {
        // Check if script with this URL already exists
        const existingScript = document.querySelector(`script[src="${url}"]`);
        if (existingScript) {
            return Promise.resolve(); // Already loaded, resolve immediately
        }
        return loadScript(url);
    });

    Promise.all(loadPromises)
      .then(() => {

        const mermaidLoaded = librariesToLoad.includes(libraryUrls.mermaidJs);
        const chartJsRequested = librariesToLoad.includes(libraryUrls.chartJs); // Check if Chart.js was requested

        // Initialize RevealJS, passing whether to include the mermaid plugin
        if (!revealInitialized) {
            initializeReveal(mermaidLoaded); // Pass mermaidLoaded flag
        }

        // Execute slide script AFTER initialization and library checks
        if (revealInitialized) {
            // Check if Chart.js was requested AND if it's actually defined
            if (chartJsRequested && typeof window.Chart === 'undefined') {
                // Optionally send error back to parent
                window.parent.postMessage({ type: 'scriptError', payload: { error: 'Chart.js failed to initialize correctly.' } }, '*');
            } else {
                // Use setTimeout to ensure execution after potential DOM updates/layout changes by RevealJS
                setTimeout(() => executeSlideScript(js, currentSlideWrapper), 0);
            }
        }

        initialContentLoaded = true; // Mark initial load as complete

      })
      .catch(error => {
        // Optionally, send an error message back to the parent
        window.parent.postMessage({ type: 'loadError', payload: { error: 'Failed to load required libraries.' } }, '*');
      });


  } else if (message.type === 'captureElement') {
    // --- Handle Capture Request ---
    const elementId = message.payload?.elementId;
    if (!elementId) {
      window.parent.postMessage({ type: 'captureError', payload: { error: 'Missing elementId in capture request.' } }, '*');
      return;
    }

    // Check if capture libraries are loaded, load if not
    const captureLibraries = [];
    if (!window.domtoimage) {
        captureLibraries.push(libraryUrls.domToImageJs);
    }
    // FileSaver.js is used in the parent, but dom-to-image is needed here.
    // We might need FileSaver.js if we decide to trigger download directly from iframe later,
    // but for now, only dom-to-image is strictly needed in the iframe for capture.
    // If saveAs is used in iframeScript.js, add libraryUrls.fileSaverJs here.
    // Based on current code, saveAs is imported in SandboxFrame.tsx, so it's not needed here.

    const loadCapturePromises = captureLibraries.map(url => {
         const existingScript = document.querySelector(`script[src="${url}"]`);
         if (existingScript) {
             return Promise.resolve();
         }
         return loadScript(url);
    });

    Promise.all(loadCapturePromises)
      .then(() => {
         // Proceed with capture after libraries are loaded
         captureElementById(elementId)
           .then(blob => {
             window.parent.postMessage({ type: 'captureResult', payload: { blob } }, '*');
           })
           .catch(error => {
             window.parent.postMessage({ type: 'captureError', payload: { error: error.message || 'Unknown capture error occurred in iframe.' } }, '*');
           });
      })
      .catch(error => {
         window.parent.postMessage({ type: 'captureError', payload: { error: 'Failed to load capture libraries.' } }, '*');
      });


  } else if (message.type === 'cleanup') {
    // Perform any necessary cleanup inside the iframe
    // Add any specific cleanup needed when the iframe is removed
    // Revoke any Blob URLs created for images during capture
    if (window._imageBlobCache) {
        window._imageBlobCache.forEach(blobUrl => URL.revokeObjectURL(blobUrl));
        window._imageBlobCache.clear();
    }
  }
});

// Set up the message listener

// Immediately signal to the parent that the iframe is ready to receive messages
window.parent.postMessage({ type: 'iframeReady' }, '*');

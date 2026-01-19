/**
 * 图片处理工具
 * 处理图片压缩、格式转换、尺寸调整等
 */

export interface ImageProcessOptions {
  maxWidth?: number;
  maxHeight?: number;
  maxSizeInBytes?: number;
  outputFormat?: 'jpeg' | 'png';
  quality?: number;
}

export interface ImageDimensions {
  width: number;
  height: number;
}

/**
 * 获取图片尺寸
 */
export function getImageDimensions(file: File): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.width, height: img.height });
    };
    
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('无法读取图片尺寸'));
    };
    
    img.src = url;
  });
}

/**
 * 检查图片尺寸是否超限
 */
export function checkImageDimensions(dimensions: ImageDimensions, maxSize: number = 4096): {
  valid: boolean;
  error?: string;
} {
  if (dimensions.width > maxSize || dimensions.height > maxSize) {
    return {
      valid: false,
      error: `图像尺寸超出限制（最大 ${maxSize}x${maxSize} 像素）`
    };
  }
  return { valid: true };
}

/**
 * 计算缩放后的尺寸（保持宽高比）
 */
export function calculateScaledDimensions(
  original: ImageDimensions,
  maxEdge: number
): ImageDimensions {
  const maxDimension = Math.max(original.width, original.height);
  
  if (maxDimension <= maxEdge) {
    return original;
  }
  
  const scale = maxEdge / maxDimension;
  return {
    width: Math.round(original.width * scale),
    height: Math.round(original.height * scale)
  };
}

/**
 * 压缩和调整图片
 */
export async function processImage(
  file: File,
  options: ImageProcessOptions = {}
): Promise<File> {
  const {
    maxWidth = 1440,
    maxHeight = 1440,
    maxSizeInBytes = 3 * 1024 * 1024, // 3MB
    outputFormat = 'jpeg',
    quality = 0.9
  } = options;

  return new Promise((resolve, reject) => {
    const img = new Image();
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      reject(new Error('无法创建 canvas context'));
      return;
    }

    img.onload = async () => {
      // 计算新尺寸
      const maxEdge = Math.min(maxWidth, maxHeight);
      const scaledDimensions = calculateScaledDimensions(
        { width: img.width, height: img.height },
        maxEdge
      );
      
      canvas.width = scaledDimensions.width;
      canvas.height = scaledDimensions.height;
      
      // 绘制调整后的图片
      ctx.drawImage(img, 0, 0, scaledDimensions.width, scaledDimensions.height);
      
      // 转换为指定格式
      let currentQuality = quality;
      let blob: Blob | null = null;
      
      // 逐步降低质量直到满足大小要求
      while (currentQuality > 0.1) {
        blob = await new Promise<Blob | null>((res) => {
          canvas.toBlob(
            (b) => res(b),
            `image/${outputFormat}`,
            currentQuality
          );
        });
        
        if (!blob) break;
        if (blob.size <= maxSizeInBytes) break;
        
        currentQuality -= 0.1;
      }
      
      URL.revokeObjectURL(img.src);
      
      if (!blob) {
        reject(new Error('图片处理失败'));
        return;
      }
      
      // 创建新的 File 对象
      const processedFile = new File(
        [blob],
        file.name.replace(/\.[^/.]+$/, `.${outputFormat}`),
        { type: `image/${outputFormat}` }
      );
      
      resolve(processedFile);
    };
    
    img.onerror = () => {
      URL.revokeObjectURL(img.src);
      reject(new Error('无法加载图片'));
    };
    
    img.src = URL.createObjectURL(file);
  });
}

/**
 * 从 GIF 或 Live Photo 提取第一帧
 */
export async function extractFirstFrame(file: File): Promise<File> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      reject(new Error('无法创建 canvas context'));
      return;
    }

    img.onload = async () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      
      const blob = await new Promise<Blob | null>((res) => {
        canvas.toBlob((b) => res(b), 'image/jpeg', 0.9);
      });
      
      URL.revokeObjectURL(img.src);
      
      if (!blob) {
        reject(new Error('无法提取第一帧'));
        return;
      }
      
      const newFile = new File(
        [blob],
        file.name.replace(/\.[^/.]+$/, '.jpg'),
        { type: 'image/jpeg' }
      );
      
      resolve(newFile);
    };
    
    img.onerror = () => {
      URL.revokeObjectURL(img.src);
      reject(new Error('无法加载图片'));
    };
    
    img.src = URL.createObjectURL(file);
  });
}

/**
 * 检查是否是支持的图片格式
 */
export function isSupportedImageFormat(file: File): boolean {
  const supportedTypes = ['image/jpeg', 'image/jpg', 'image/png'];
  return supportedTypes.includes(file.type.toLowerCase());
}

/**
 * 检查是否是需要特殊处理的格式（GIF、HEIC等）
 */
export function needsSpecialProcessing(file: File): boolean {
  const specialTypes = ['image/gif', 'image/heic', 'image/heif'];
  return specialTypes.includes(file.type.toLowerCase()) || 
         file.name.toLowerCase().endsWith('.heic') ||
         file.name.toLowerCase().endsWith('.heif');
}
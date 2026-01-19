/**
 * 文件转换工具
 * 处理文件到 Base64 的转换等
 */

export interface FileWithBase64 {
  file: File;
  base64: string;
  name: string;
  type: string;
  size: number;
}

/**
 * 将文件转换为 Base64
 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        // 返回纯 base64 字符串（去掉 data:image/jpeg;base64, 前缀）
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      } else {
        reject(new Error('无法读取文件'));
      }
    };
    
    reader.onerror = () => {
      reject(new Error(`读取文件失败: ${file.name}`));
    };
    
    reader.readAsDataURL(file);
  });
}

/**
 * 批量转换文件为 Base64
 */
export async function filesToBase64(files: File[]): Promise<FileWithBase64[]> {
  const promises = files.map(async (file) => {
    try {
      const base64 = await fileToBase64(file);
      return {
        file,
        base64,
        name: file.name,
        type: file.type,
        size: file.size
      };
    } catch (error) {
      console.error(`转换文件 ${file.name} 失败:`, error);
      throw error;
    }
  });
  
  return Promise.all(promises);
}

/**
 * Base64 转 Blob
 */
export function base64ToBlob(base64: string, type: string = 'application/octet-stream'): Blob {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type });
}

/**
 * Base64 转 File
 */
export function base64ToFile(base64: string, fileName: string, type: string = 'application/octet-stream'): File {
  const blob = base64ToBlob(base64, type);
  return new File([blob], fileName, { type });
}

/**
 * 创建文件的预览 URL
 */
export function createFilePreviewUrl(file: File): string {
  return URL.createObjectURL(file);
}

/**
 * 释放预览 URL
 */
export function revokeFilePreviewUrl(url: string): void {
  URL.revokeObjectURL(url);
}

/**
 * 获取文件扩展名
 */
export function getFileExtension(fileName: string): string {
  const parts = fileName.split('.');
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
}

/**
 * 为 FormData 准备文件
 * 将处理后的文件添加到 FormData
 */
export async function prepareFilesForUpload(
  files: File[],
  useBase64: boolean = true
): Promise<{ formData: FormData; fileInfo: Array<{ name: string; size: number; type: string }> }> {
  const formData = new FormData();
  const fileInfo: Array<{ name: string; size: number; type: string }> = [];
  
  if (useBase64) {
    // 使用 Base64 格式上传
    const base64Files = await filesToBase64(files);
    
    for (const fileData of base64Files) {
      formData.append('files', fileData.base64);
      formData.append('fileNames', fileData.name);
      formData.append('fileTypes', fileData.type);
      formData.append('fileSizes', fileData.size.toString());
      
      fileInfo.push({
        name: fileData.name,
        size: fileData.size,
        type: fileData.type
      });
    }
  } else {
    // 直接上传文件对象
    for (const file of files) {
      formData.append('files', file, file.name);
      
      fileInfo.push({
        name: file.name,
        size: file.size,
        type: file.type
      });
    }
  }
  
  return { formData, fileInfo };
}
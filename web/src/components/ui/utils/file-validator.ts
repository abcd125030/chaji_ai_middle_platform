/**
 * 文件验证工具
 * 验证文件类型、大小、数量等
 */

export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

export interface FileValidationOptions {
  maxFileSize?: number;
  maxTotalSize?: number;
  maxFileCount?: number;
  allowedTypes?: string[];
}

// 默认配置
export const DEFAULT_FILE_CONFIG = {
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB per file
  MAX_TOTAL_SIZE: 10 * 1024 * 1024, // 10MB total
  MAX_FILE_COUNT: 5,
  ALLOWED_DOCUMENT_TYPES: [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // docx
    'application/msword', // doc
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // xlsx
    'application/vnd.ms-excel', // xls
    'text/plain',
    'text/csv',
    'text/markdown',
    'application/json'
  ],
  ALLOWED_IMAGE_TYPES: [
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/gif',
    'image/heic',
    'image/heif'
  ]
};

/**
 * 验证单个文件大小
 */
export function validateFileSize(
  file: File,
  maxSize: number = DEFAULT_FILE_CONFIG.MAX_FILE_SIZE
): FileValidationResult {
  if (file.size > maxSize) {
    const sizeMB = (maxSize / (1024 * 1024)).toFixed(0);
    return {
      valid: false,
      error: `文件 "${file.name}" 超过 ${sizeMB}MB 限制`
    };
  }
  return { valid: true };
}

/**
 * 验证文件总大小
 */
export function validateTotalSize(
  files: File[],
  maxTotalSize: number = DEFAULT_FILE_CONFIG.MAX_TOTAL_SIZE
): FileValidationResult {
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  
  if (totalSize > maxTotalSize) {
    const sizeMB = (maxTotalSize / (1024 * 1024)).toFixed(0);
    return {
      valid: false,
      error: `文件总大小超过 ${sizeMB}MB 限制`
    };
  }
  return { valid: true };
}

/**
 * 验证文件数量
 */
export function validateFileCount(
  currentCount: number,
  newCount: number,
  maxCount: number = DEFAULT_FILE_CONFIG.MAX_FILE_COUNT
): FileValidationResult {
  const totalCount = currentCount + newCount;
  
  if (totalCount > maxCount) {
    return {
      valid: false,
      error: `最多只能上传 ${maxCount} 个文件`
    };
  }
  return { valid: true };
}

/**
 * 验证文件类型
 */
export function validateFileType(file: File): FileValidationResult {
  const fileType = file.type.toLowerCase();
  const fileName = file.name.toLowerCase();
  
  // 检查是否是允许的文档类型
  const isAllowedDocument = DEFAULT_FILE_CONFIG.ALLOWED_DOCUMENT_TYPES.includes(fileType);
  
  // 检查是否是允许的图片类型
  const isAllowedImage = DEFAULT_FILE_CONFIG.ALLOWED_IMAGE_TYPES.includes(fileType);
  
  // 某些文件可能没有正确的 MIME type，通过扩展名检查
  const allowedExtensions = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
    '.txt', '.csv', '.md', '.json',
    '.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif'
  ];
  
  const hasAllowedExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
  
  if (!isAllowedDocument && !isAllowedImage && !hasAllowedExtension) {
    return {
      valid: false,
      error: `不支持的文件类型: ${file.name}`
    };
  }
  
  return { valid: true };
}

/**
 * 批量验证文件
 */
export function validateFiles(
  newFiles: File[],
  existingFiles: File[] = [],
  options: FileValidationOptions = {}
): {
  valid: boolean;
  errors: string[];
  validFiles: File[];
} {
  const errors: string[] = [];
  const validFiles: File[] = [];
  
  const {
    maxFileSize = DEFAULT_FILE_CONFIG.MAX_FILE_SIZE,
    maxTotalSize = DEFAULT_FILE_CONFIG.MAX_TOTAL_SIZE,
    maxFileCount = DEFAULT_FILE_CONFIG.MAX_FILE_COUNT
  } = options;
  
  // 验证文件数量
  const countResult = validateFileCount(existingFiles.length, newFiles.length, maxFileCount);
  if (!countResult.valid && countResult.error) {
    errors.push(countResult.error);
    return { valid: false, errors, validFiles: [] };
  }
  
  // 验证每个文件
  for (const file of newFiles) {
    // 验证文件类型
    const typeResult = validateFileType(file);
    if (!typeResult.valid) {
      if (typeResult.error) errors.push(typeResult.error);
      continue;
    }
    
    // 验证单个文件大小
    const sizeResult = validateFileSize(file, maxFileSize);
    if (!sizeResult.valid) {
      if (sizeResult.error) errors.push(sizeResult.error);
      continue;
    }
    
    validFiles.push(file);
  }
  
  // 验证总大小
  const allFiles = [...existingFiles, ...validFiles];
  const totalSizeResult = validateTotalSize(allFiles, maxTotalSize);
  if (!totalSizeResult.valid && totalSizeResult.error) {
    errors.push(totalSizeResult.error);
    return { valid: false, errors, validFiles: [] };
  }
  
  return {
    valid: errors.length === 0,
    errors,
    validFiles
  };
}

/**
 * 获取文件的友好大小显示
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const units = ['B', 'KB', 'MB', 'GB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`;
}

/**
 * 判断是否是图片文件
 */
export function isImageFile(file: File): boolean {
  return DEFAULT_FILE_CONFIG.ALLOWED_IMAGE_TYPES.includes(file.type.toLowerCase()) ||
         /\.(jpg|jpeg|png|gif|heic|heif)$/i.test(file.name);
}
/**
 * 服务端日志记录器
 * 仅在 Node.js 环境（服务端）使用
 */

import fs from 'fs';
import path from 'path';
import { format } from 'util';

// 日志级别
export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR'
}

class ServerLogger {
  private logDir: string;
  private logFile: string;
  private errorLogFile: string;

  constructor() {
    // 日志目录
    this.logDir = path.join(process.cwd(), 'logs');
    
    // 确保日志目录存在
    if (!fs.existsSync(this.logDir)) {
      fs.mkdirSync(this.logDir, { recursive: true });
    }

    // 日志文件路径
    const dateStr = new Date().toISOString().split('T')[0];
    this.logFile = path.join(this.logDir, `app-${dateStr}.log`);
    this.errorLogFile = path.join(this.logDir, `error-${dateStr}.log`);
  }

  private formatMessage(level: LogLevel, message: string, ...args: unknown[]): string {
    const timestamp = new Date().toISOString();
    const formattedMessage = format(message, ...args);
    return `[${timestamp}] [${level}] ${formattedMessage}\n`;
  }

  private writeToFile(filePath: string, content: string) {
    try {
      fs.appendFileSync(filePath, content, 'utf8');
    } catch (error) {
      console.error('Failed to write log:', error);
    }
  }

  private log(level: LogLevel, message: string, ...args: unknown[]) {
    const formattedMessage = this.formatMessage(level, message, ...args);
    
    // 写入主日志文件
    this.writeToFile(this.logFile, formattedMessage);
    
    // ERROR 级别也写入错误日志文件
    if (level === LogLevel.ERROR) {
      this.writeToFile(this.errorLogFile, formattedMessage);
    }
    
    // 同时输出到控制台
    const consoleMethod = level === LogLevel.ERROR ? 'error' : 
                         level === LogLevel.WARN ? 'warn' : 'log';
    console[consoleMethod](formattedMessage.trim());
  }

  debug(message: string, ...args: unknown[]) {
    this.log(LogLevel.DEBUG, message, ...args);
  }

  info(message: string, ...args: unknown[]) {
    this.log(LogLevel.INFO, message, ...args);
  }

  warn(message: string, ...args: unknown[]) {
    this.log(LogLevel.WARN, message, ...args);
  }

  error(message: string, error?: unknown, ...args: unknown[]) {
    if (error instanceof Error) {
      const errorDetails = {
        message: error.message,
        stack: error.stack,
        name: error.name
      };
      this.log(LogLevel.ERROR, `${message} - Error: ${JSON.stringify(errorDetails)}`, ...args);
    } else if (error) {
      try {
        this.log(LogLevel.ERROR, `${message} - Details: ${JSON.stringify(error)}`, ...args);
      } catch {
        this.log(LogLevel.ERROR, `${message} - Details: [Unable to stringify error]`, ...args);
      }
    } else {
      this.log(LogLevel.ERROR, message, ...args);
    }
  }

  // 记录 HTTP 请求
  logRequest(method: string, url: string, headers?: Record<string, string>, body?: unknown) {
    const requestInfo = {
      method,
      url,
      headers: headers ? this.sanitizeHeaders(headers) : undefined,
      body: body ? this.truncateBody(body) : undefined,
      timestamp: new Date().toISOString()
    };
    this.info('HTTP Request: %j', requestInfo);
  }

  // 记录 HTTP 响应
  logResponse(status: number, url: string, responseData?: unknown, duration?: number) {
    const responseInfo = {
      status,
      url,
      data: responseData ? this.truncateBody(responseData) : undefined,
      duration: duration ? `${duration}ms` : undefined,
      timestamp: new Date().toISOString()
    };
    const level = status >= 400 ? LogLevel.ERROR : LogLevel.INFO;
    this.log(level, 'HTTP Response: %j', responseInfo);
  }

  // 清理敏感 headers
  private sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
    const sanitized = { ...headers };
    // 隐藏敏感信息
    if (sanitized.authorization) {
      sanitized.authorization = 'Bearer ***';
    }
    if (sanitized.cookie) {
      sanitized.cookie = '***';
    }
    return sanitized;
  }

  // 截断过长的 body
  private truncateBody(body: unknown, maxLength: number = 1000): string | unknown {
    const bodyStr = typeof body === 'string' ? body : JSON.stringify(body);
    if (bodyStr.length > maxLength) {
      return bodyStr.substring(0, maxLength) + '... [truncated]';
    }
    return body;
  }
}

// 单例模式
let loggerInstance: ServerLogger | null = null;

export function getLogger(): ServerLogger {
  // 仅在服务端创建 logger
  if (typeof window === 'undefined') {
    if (!loggerInstance) {
      loggerInstance = new ServerLogger();
    }
    return loggerInstance;
  }
  
  // 客户端返回一个 mock logger
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    logRequest: () => {},
    logResponse: () => {}
  } as unknown as ServerLogger;
}

export const logger = getLogger();
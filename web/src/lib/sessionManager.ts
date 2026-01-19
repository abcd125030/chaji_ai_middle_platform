import { v4 as uuidv4 } from 'uuid';
import { logger } from './server-logger';

export interface FileInfo {
  name: string;
  size: number;
  type: string;
}

export interface WebSearchResult {
  title: string;
  url: string;
}

export interface CitationSegment {
  label: string;
  value: string;
  short_url: string;
}

export interface Citation {
  segments: CitationSegment[];
  end_index: number;
  start_index: number;
}

export interface WebSearchToolResult {
  text: string;
  citations: Citation[];
}

export interface WebSearchToolOutputData {
  result: WebSearchToolResult;
  status: string;
}

export interface TaskStep {
  type: 'plan' | 'tool_output' | 'reflection' | 'final_answer' | 'error' | 'todo_created' | 'todo_updated' | 'todo_update';
  tool_name?: string; // tool_output类型时，tool_name可能在顶层
  data: {
    thought?: string;
    tool_name?: string;
    data?: unknown;
    conclusion?: string;
    todo_count?: number;
    todos?: Array<{ id: number; task: string; priority: string; [key: string]: unknown }>;
    operation?: string;
    task_ids?: number[];
    [key: string]: unknown;
  };
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  files?: FileInfo[];
  taskId?: string;
  taskSteps?: TaskStep[];
  finalWebSearchResults?: WebSearchResult[];
  error_type?: string;  // 任务异常类型
  task_status?: string; // 任务状态
  todoData?: {
    total_count: number;
    completed_count: number;
    todo_list: Array<{
      id: number;
      task: string;
      completed: boolean;
      completion_details?: {
        completed_by_tool?: string;
        output?: string;
      };
    }>;
  };
  is_complete?: boolean;
  timestamp: Date;
}

export interface SessionData {
  sessionId: string;
  userId: string;
  messages: Message[];
  lastActivity: Date;
  title?: string; // 会话标题，保持与数据库一致
  sseConnection?: unknown; // Replace 'unknown' with a more specific type if you have one for SSE response
}

class SessionManager {
  private sessions = new Map<string, SessionData>();

  constructor() {
    setInterval(() => this.cleanupExpiredSessions(), 60 * 1000); // Check every minute
  }

  async createSession(userId: string): Promise<string> {
    const sessionId = uuidv4();
    const newSession: SessionData = {
      sessionId,
      userId,
      messages: [],
      lastActivity: new Date(),
    };
    this.sessions.set(sessionId, newSession);
    
    // Get user info from localStorage if available
    let displayName: string | undefined;
    try {
      if (typeof window !== 'undefined' && localStorage) {
        const auth = localStorage.getItem('auth');
        if (auth) {
          const authData = JSON.parse(auth);
          displayName = authData.user?.name ||
                       authData.user?.username ||
                       authData.name ||
                       authData.username;
          logger.debug('Got displayName from localStorage:', displayName);
        }
      }
    } catch (error) {
      logger.error('Error reading user info from localStorage:', error);
    }

    // Note: Database operations removed - web app no longer uses database directly
    // User profile and session persistence should be handled by backend API

    return sessionId;
  }

  async getSession(sessionId: string): Promise<SessionData | null> {
    if (this.sessions.has(sessionId)) {
      const session = this.sessions.get(sessionId)!;
      session.lastActivity = new Date();
      return session;
    }
    
    // Session not found in memory cache
    // Note: Database lookup removed - sessions are now ephemeral
    return null;
    
  }

  updateSession(sessionId: string, data: Partial<SessionData>): void {
    if (this.sessions.has(sessionId)) {
      const session = this.sessions.get(sessionId)!;
      Object.assign(session, data, { lastActivity: new Date() });
    }
  }

  addMessageToSession(sessionId: string, message: Message): void {
    if (this.sessions.has(sessionId)) {
      const session = this.sessions.get(sessionId)!;
      session.messages.push(message);
      session.lastActivity = new Date();
    }
  }

  updateMessageInSession(sessionId: string, updatedMessage: {
    id: bigint;
    content: string;
    taskId?: string;
    taskSteps?: TaskStep[];
    is_complete: boolean;
    timestamp: Date;
  }): void {
    if (this.sessions.has(sessionId)) {
      const session = this.sessions.get(sessionId)!;
      // 找到对应的消息并更新
      const messageIndex = session.messages.findIndex(msg => 
        msg.role === 'assistant' && msg.taskId === updatedMessage.taskId
      );
      
      if (messageIndex !== -1) {
        const existingMessage = session.messages[messageIndex];
        session.messages[messageIndex] = {
          ...existingMessage,
          content: updatedMessage.content,
          taskId: updatedMessage.taskId,
          taskSteps: updatedMessage.taskSteps || existingMessage.taskSteps,
          timestamp: updatedMessage.timestamp,
        };
        session.lastActivity = new Date();
      }
    }
  }

  private cleanupExpiredSessions(): void {
    const now = new Date();
    for (const [sessionId, session] of this.sessions.entries()) {
      if (now.getTime() - session.lastActivity.getTime() > 10 * 60 * 1000) { // 10 minutes
        this.sessions.delete(sessionId);
        logger.info(`Inactive session ${sessionId} has been cleared from memory.`);
      }
    }
  }
}

export const sessionManager = new SessionManager();

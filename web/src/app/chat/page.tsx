// 声明这是一个客户端组件
'use client';

// 导入React相关hooks
import { useEffect, useState, useRef } from "react";
import { Toaster, toast } from 'react-hot-toast';
import { initDB, getFiles, deleteFile, FileRecord } from '@/lib/db';
import ChatMessages from '@/components/ui/ChatMessages';
import ChatInput from '@/components/ui/ChatInput';
import ChatTopBar from '@/components/ui/ChatTopBar';
import ConversationTips from '@/components/ui/ConversationTips';
import RouteGuard from '@/components/ui/RouteGuard';
import { Message, TaskStep } from "@/lib/sessionManager";
import { authFetch } from '@/lib/auth-fetch';
import { useSubscription } from '@/hooks/useSubscription';

interface TodoTask {
  id: number;
  task: string;
  completed: boolean;
  completion_details?: {
    completed_by_tool?: string;
    output?: string;
  };
}

/**
 * 点阵背景组件 - 创建固定点阵，每个点可以变成星芒状态
 */
const DotMatrix = () => {
  const [sparklingDots, setSparklingDots] = useState<Set<string>>(new Set());
  const [dots, setDots] = useState<Array<{ x: number; y: number; id: string }>>([]);

  useEffect(() => {
    // 初始化点阵
    const generateDots = () => {
      const dotArray = [];
      const spacing = 40; // 40px 间距
      const cols = Math.ceil(window.innerWidth / spacing);
      const rows = Math.ceil(window.innerHeight / spacing);
      
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          dotArray.push({
            x: col * spacing + spacing / 2,
            y: row * spacing + spacing / 2,
            id: `${col}-${row}`
          });
        }
      }
      setDots(dotArray);
    };

    generateDots();
    window.addEventListener('resize', generateDots);
    
    return () => window.removeEventListener('resize', generateDots);
  }, []);

  useEffect(() => {
    // 随机激活点变成星芒
    const interval = setInterval(() => {
      if (dots.length > 0 && Math.random() > 0.7) { // 30%概率
        const randomDot = dots[Math.floor(Math.random() * dots.length)];
        
        // 添加星芒状态
        setSparklingDots(prev => {
          const newSet = new Set(prev);
          newSet.add(randomDot.id);
          return newSet;
        });
        
        // 动画结束后移除星芒状态
        setTimeout(() => {
          setSparklingDots(prev => {
            const newSet = new Set(prev);
            newSet.delete(randomDot.id);
            return newSet;
          });
        }, 850);
      }
    }, 300);

    return () => clearInterval(interval);
  }, [dots]);

  return (
    <>
      {dots.map(dot => (
        <div
          key={dot.id}
          className={`dot ${sparklingDots.has(dot.id) ? 'sparkle' : ''}`}
          style={{
            left: `${dot.x}px`,
            top: `${dot.y}px`,
          }}
        />
      ))}
    </>
  );
};

/**
 * 首页组件 - 聊天应用的主容器
 * 管理核心状态并协调子组件
 */
export default function ChatPage() {
  // 订阅功能
  const { openSubscription, SubscriptionComponent } = useSubscription();
  
  // 基础状态管理
  const [sendShortcut, setSendShortcut] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<FileRecord[]>([]);
  const [totalUploadSize, setTotalUploadSize] = useState(0);
  
  // 对话状态
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  
  // 任务检查状态
  const [isCheckingTasks, setIsCheckingTasks] = useState(false);

  // 拖拽相关状态
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);

  // 组件挂载时执行的副作用
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkAndLoad = async () => {
        try {
              // 初始化页面
              const initializeDB = async () => {
                await initDB();
                const files = await getFiles();
                setUploadedFiles(files);
                const initialSize = files.reduce((sum, file) => sum + file.size, 0);
                setTotalUploadSize(initialSize);
              };
              initializeDB();
              
              setSendShortcut(navigator.platform.indexOf('Mac') > -1 ? 'Command + Enter' : 'Control + Enter');
        
              const loadSession = async () => {
                const storedSessionId = localStorage.getItem('sessionId');
                if (storedSessionId) {
                  setIsLoading(true);
                  try {
                    const response = await authFetch(`/api/chat/sessions/${storedSessionId}/messages`);
                    if (response.ok) {
                      const data = await response.json();
                      setSessionId(storedSessionId);
                      
                      // 转换snake_case到camelCase，处理task_steps和final_web_search_results
                      const transformedMessages = (data.messages || []).map((msg: Record<string, unknown>) => ({
                        ...msg,
                        taskSteps: msg.task_steps || msg.taskSteps,
                        finalWebSearchResults: msg.final_web_search_results || msg.finalWebSearchResults,
                        // 删除原始的snake_case字段
                        task_steps: undefined,
                        final_web_search_results: undefined,
                      }));
                      
                      setMessages(transformedMessages);
                      
                      // 检查并恢复未完成的任务
                      const hasIncompleteTasks = transformedMessages.some((msg: Record<string, unknown>) => 
                        msg.role === 'assistant' && msg.task_id && msg.is_complete === false
                      );
                      
                      if (hasIncompleteTasks) {
                        console.log('[TASK_RECOVERY] Found incomplete tasks, attempting recovery...');
                        try {
                          const recoveryResponse = await authFetch('/api/chat/check-incomplete-tasks', {
                            method: 'POST',
                            headers: {
                              'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({})
                          });
                          
                          if (recoveryResponse.ok) {
                            const recoveryData = await recoveryResponse.json();
                            console.log('[TASK_RECOVERY] Task recovery result:', recoveryData);
                            
                            // 如果有任务被更新，重新加载消息
                            let finalMessages = transformedMessages;
                            if (recoveryData.updated > 0) {
                              const reloadResponse = await authFetch(`/api/chat/sessions/${storedSessionId}/messages`);
                              if (reloadResponse.ok) {
                                const reloadData = await reloadResponse.json();
                                const reloadedMessages = (reloadData.messages || []).map((msg: Record<string, unknown>) => ({
                                  ...msg,
                                  taskSteps: msg.task_steps || msg.taskSteps,
                                  finalWebSearchResults: msg.final_web_search_results || msg.finalWebSearchResults,
                                  task_steps: undefined,
                                  final_web_search_results: undefined,
                                }));
                                setMessages(reloadedMessages);
                                finalMessages = reloadedMessages;
                                toast.success(`Restored ${recoveryData.updated} task execution results`);
                              }
                            }
                            
                            // 无论是否有任务被更新，都检查是否有任务仍在运行需要重连
                            const runningTask = finalMessages.find((msg: Record<string, unknown>) => 
                              msg.role === 'assistant' && msg.task_id && msg.is_complete === false
                            );
                            
                            if (runningTask?.task_id) {
                              console.log('[TASK_RECOVERY] Detected running task, attempting to reconnect:', runningTask.task_id);
                              await reconnectToRunningTask(runningTask.task_id as string, storedSessionId);
                            }
                          }
                        } catch (error) {
                          console.error('[TASK_RECOVERY] Failed to recover tasks:', error);
                        }
                      }
                    } else if (response.status === 404) {
                      toast.error('The conversation you are accessing does not exist.');
                      localStorage.removeItem('sessionId');
                      setSessionId(null);
                    } else if (response.status === 403) {
                      toast.error('You cannot access data that does not belong to you.');
                      localStorage.removeItem('sessionId');
                      setSessionId(null);
                    } else {
                      const errorData = await response.json();
                      toast.error(errorData.error || 'Failed to load session.');
                      localStorage.removeItem('sessionId');
                      setSessionId(null);
                    }
                  } catch {
                    toast.error('Error occurred while loading session.');
                    localStorage.removeItem('sessionId');
                    setSessionId(null);
                  } finally {
                    setIsLoading(false);
                  }
                }
              };
        
              loadSession();

              // 检查未完成的任务
              const checkIncompleteTasksOnLoad = async () => {
                // 检查上次检查时间，避免过于频繁的检查
                const lastCheckKey = 'lastTaskCheck';
                const lastCheck = localStorage.getItem(lastCheckKey);
                const now = Date.now();
                const checkInterval = 30000; // 30秒检查间隔
                
                if (lastCheck && (now - parseInt(lastCheck)) < checkInterval) {
                  console.log('Skipping task check - too soon since last check');
                  return;
                }
                
                localStorage.setItem(lastCheckKey, now.toString());
                setIsCheckingTasks(true);
                
                try {
                  const response = await authFetch('/api/chat/check-incomplete-tasks', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json'
                    }
                  });
                  
                  if (response.ok) {
                    const result = await response.json();
                    if (result.updated > 0) {
                      console.log(`Updated ${result.updated} incomplete tasks`);
                      // 如果有任务被更新，重新加载消息
                      const storedSessionId = localStorage.getItem('sessionId');
                      if (storedSessionId) {
                        const messagesResponse = await authFetch(`/api/chat/sessions/${storedSessionId}/messages`);
                        if (messagesResponse.ok) {
                          const messagesData = await messagesResponse.json();
                          
                          // 转换snake_case到camelCase，处理task_steps和final_web_search_results
                          const transformedMessages = (messagesData.messages || []).map((msg: Record<string, unknown>) => ({
                            ...msg,
                            taskSteps: msg.task_steps || msg.taskSteps,
                            finalWebSearchResults: msg.final_web_search_results || msg.finalWebSearchResults,
                            // 删除原始的snake_case字段
                            task_steps: undefined,
                            final_web_search_results: undefined,
                          }));
                          
                          setMessages(transformedMessages);
                        }
                      }
                    }
                  }
                } catch (error) {
                  console.error('Failed to check incomplete tasks:', error);
                  // 静默处理错误，不影响用户使用
                } finally {
                  setIsCheckingTasks(false);
                }
              };
              
              checkIncompleteTasksOnLoad();

        } catch (error) {
          console.error('Failed to initialize page', error);
        }
      };

      checkAndLoad();
    }

    const eventSource = eventSourceRef.current;
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  /**
   * 重新连接到运行中的任务
   * @param taskId 任务ID
   * @param sessionId 会话ID
   */
  const reconnectToRunningTask = async (taskId: string, sessionId: string) => {
    try {
      // 1. 首先检查任务是否仍在运行
      const statusResponse = await authFetch(`/api/chat/tasks/${taskId}/status`);
      if (!statusResponse.ok) {
        console.log('[SSE_RECONNECT] Unable to get task status');
        return;
      }
      
      const statusData = await statusResponse.json();
      console.log('[SSE_RECONNECT] Task status:', statusData);
      
      if (!statusData.exists || statusData.is_completed) {
        console.log('[SSE_RECONNECT] Task completed or does not exist, no need to reconnect');
        return;
      }
      
      // 2. 设置加载状态并显示重连提示
      setIsLoading(true);
      toast.success('Reconnecting to running task...');
      
      // 3. 创建统一的JSON请求体来触发SSE连接
      const reconnectBody = {
        message: '[RECONNECT]', // Special marker indicating this is a reconnection request
        mode: '',  // 重连时不需要mode
        files: [],  // 重连时不需要文件
        task_id: taskId  // Pass the task ID to reconnect
      };
      
      // 4. 建立SSE连接，复用现有的messages API
      const response = await authFetch(`/api/chat/sessions/${sessionId}/messages`, {
        method: 'POST',
        body: JSON.stringify(reconnectBody),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
      });

      if (!response.ok) {
        throw new Error(`Reconnection failed: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("Response body is null");
      }

      // 5. 处理SSE流，复用现有的事件处理逻辑
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      console.log('[SSE_RECONNECT] Starting to receive SSE stream');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        let eventEndIndex;
        while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
          const eventString = buffer.substring(0, eventEndIndex);
          buffer = buffer.substring(eventEndIndex + 2);

          if (eventString.startsWith('data: ')) {
            const jsonString = eventString.substring(6);
            try {
              const event = JSON.parse(jsonString);
              console.log(`[SSE_RECONNECT] Received event: ${event.type}`, event);
              
              // 复用现有的事件处理逻辑
              if (event.type === 'END') {
                // 任务完成，SSE流结束
                setIsLoading(false);
                
                // 从最后一条消息的 taskSteps 中提取 final_answer 作为 content
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    const taskSteps = lastMessage.taskSteps || [];
                    // 查找 final_answer 或 error 步骤
                    const finalAnswerStep = taskSteps.find((step: TaskStep) => step.type === 'final_answer' || step.type === 'error');
                    if (finalAnswerStep) {
                      // 兼容新旧字段：优先使用 output，回退到 final_answer 或 message
                      const finalAnswer = finalAnswerStep.data?.output || finalAnswerStep.data?.final_answer || finalAnswerStep.data?.message;
                      if (finalAnswer) {
                        lastMessage.content = typeof finalAnswer === 'string' ? finalAnswer : String(finalAnswer);
                      }
                    }
                    // 标记任务为完成
                    lastMessage.is_complete = true;
                  }
                  return newMessages;
                });
                
                console.log('[SSE_RECONNECT] Task completed');
                toast.success('Task completed!');
                // 终止 SSE 流
                reader.cancel();
                break;
              } else if (event.type === 'error' || event.type === 'task_error') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    newMessages[newMessages.length - 1] = event.message || {
                      ...lastMessage,
                      content: 'Task execution failed, please try again later'
                    };
                  }
                  return newMessages;
                });
                toast.error(event.message?.content || 'Task execution failed');
                setIsLoading(false);
                break;
              } else if (event.type === 'task_abnormal') {
                // 处理任务异常事件
                const { error_type, message: errorMessage, task_status } = event.data || {};

                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    // 更新消息内容为错误提示
                    lastMessage.content = errorMessage || 'Task execution abnormal';
                    // 添加异常标记
                    lastMessage.error_type = error_type;
                    lastMessage.task_status = task_status;
                  }
                  return newMessages;
                });

                // 根据错误类型显示不同的提示
                if (error_type === 'task_failed_without_answer') {
                  toast.error('Task failed, please try again');
                } else if (error_type === 'task_cancelled') {
                  toast('Task has been cancelled', { icon: '⚠️' });
                } else if (error_type === 'completed_without_answer') {
                  toast('Task completed but output format is non-standard', { icon: '⚠️' });
                } else if (error_type === 'no_action_history') {
                  toast.error('Task record exception, unable to retrieve execution process');
                }

                console.warn('[SSE_RECONNECT] Task abnormal:', { error_type, message: errorMessage, task_status });
                // 不要break，继续接收END事件
              } else if (event.type === 'timeout') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    newMessages[newMessages.length - 1] = {
                      ...lastMessage,
                      content: 'Page timeout, task may still be running in background. Please refresh to get progress.'
                    };
                  }
                  return newMessages;
                });
                toast.error('Page timeout, please refresh to get progress');
                setIsLoading(false);
                break;
              } else if (event.type !== 'task_started') {
                // 处理中间事件 (plan, tool_output, reflection 等)
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessageIndex = newMessages.length - 1;
                  
                  if (lastMessageIndex > -1) {
                    const originalLastMessage = newMessages[lastMessageIndex];
                    if (originalLastMessage && originalLastMessage.role === 'assistant') {
                      const existingSteps = originalLastMessage.taskSteps || [];
                      const isDuplicate = existingSteps.some(step => 
                        step.type === event.type && 
                        JSON.stringify(step.data) === JSON.stringify(event.data)
                      );
                      
                      if (!isDuplicate) {
                        const updatedLastMessage = {
                          ...originalLastMessage,
                          taskSteps: [...existingSteps, event],
                        };

                        if (event.type === 'plan') {
                          updatedLastMessage.content = `Thinking plan: \n${event.data.output || event.data.thought || ''}`  // 兼容新旧字段
                        } else if (event.type === 'tool_output') {
                          const toolName = event.data?.tool_name || event.tool_name || 'Unknown tool';
                          updatedLastMessage.content = `Calling tool: \n[${toolName}]`;
                        } else if (event.type === 'todo') {
                          // 处理TODO事件，显示详细的任务清单
                          const todoData = event.data;
                          const totalCount = todoData?.total_count || 0;
                          const completedCount = todoData?.completed_count || 0;
                          const todoList = todoData?.todo_list || [];
                          
                          let todoContent = `📋 Task list (${completedCount}/${totalCount} completed)\n\n`;
                          
                          const pendingTasks = todoList.filter((t: TodoTask) => !t.completed);
                          if (pendingTasks.length > 0) {
                            todoContent += '**Pending tasks:**\n';
                            pendingTasks.forEach((task: TodoTask) => {
                              todoContent += `⏳ ${task.id}. ${task.task}\n`;
                            });
                          }
                          
                          const completedTasks = todoList.filter((t: TodoTask) => t.completed);
                          if (completedTasks.length > 0) {
                            todoContent += '\n**Completed tasks:**\n';
                            completedTasks.forEach((task: TodoTask) => {
                              todoContent += `✅ ${task.id}. ${task.task}`;
                              if (task.completion_details?.completed_by_tool) {
                                todoContent += ` (via ${task.completion_details.completed_by_tool})`;
                              }
                              todoContent += '\n';
                            });
                          }
                          
                          updatedLastMessage.content = todoContent;
                          updatedLastMessage.todoData = todoData;
                        } else if (event.type === 'final_answer' || event.type === 'error') {
                          // 保存 final_answer 或 error 内容，兼容新旧字段
                          const finalContent = event.data?.output || event.data?.final_answer || event.data?.message;
                          if (finalContent) {
                            updatedLastMessage.content = finalContent;
                          } else {
                            updatedLastMessage.content = 'Task completed!';
                          }
                        }
                        
                        newMessages[lastMessageIndex] = updatedLastMessage;
                      }
                    }
                  }
                  return newMessages;
                });
              }
            } catch (e) {
              console.error('[SSE_RECONNECT] Failed to parse event:', e);
            }
          }
        }
      }
      
    } catch (error) {
      console.error('[SSE_RECONNECT] Reconnection failed:', error);
      setIsLoading(false);
      toast.error('Reconnection failed, please refresh the page manually');
    }
  };

  /**
   * 处理拖拽进入事件
   * @param e React拖拽事件
   */
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current++;
    if (dragCounter.current > 0) {
      setIsDragging(true);
    }
  };

  /**
   * 处理拖拽离开事件
   * @param e React拖拽事件
   */
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  };

  /**
   * 处理文件拖放事件
   * @param e React拖拽事件
   */
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    dragCounter.current = 0;

    // 获取拖拽的文件列表
    const files = Array.from(e.dataTransfer.files);
    
    // 允许的文件类型和扩展名
    const allowedTypes = [
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/pdf',
      'text/markdown',
      'text/plain',
      'application/json',
      'image/jpeg',
      'image/png',
      'image/webp',
    ];

    const allowedExtensions = ['.docx', '.xlsx', '.ppt', '.pdf', '.md', '.txt', '.json', '.jpg', '.jpeg', '.png', '.webp'];

    // 过滤出有效的文件
    const validFiles = files.filter(file => {
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
      return allowedTypes.includes(file.type) || allowedExtensions.includes(fileExtension ?? '');
    });

    if (files.length === 0) {
      return;
    }

    // Check file count limit (maximum 6 files)
    if (uploadedFiles.length + validFiles.length > 6) {
      toast.error('You can upload up to 6 files maximum');
      return;
    }

    // Check file size limit (total size not exceeding 200MB)
    const newTotalSize = validFiles.reduce((sum, file) => sum + file.size, totalUploadSize);
    if (newTotalSize > 200 * 1024 * 1024) {
      toast.error('Total file size cannot exceed 200MB');
      return;
    }

    if (validFiles.length > 0) {
      setTotalUploadSize(newTotalSize);
      const { addFile } = await import('@/lib/db');
      const uploadPromises = validFiles.map(file => addFile(file));
      const toastId = toast.loading(`Uploading ${validFiles.length} files...`);

      try {
        // Upload files and update state
        const newFiles = await Promise.all(uploadPromises);
        setUploadedFiles(prevFiles => [...prevFiles, ...newFiles]);
        toast.success(`${validFiles.length} files uploaded successfully`, { id: toastId });
      } catch {
        toast.error('Upload failed', { id: toastId });
      }
    } else {
      toast.error('Unsupported file type. Only docx, xlsx, ppt, pdf, md, txt, json, jpg, png, webp are supported.', {
        duration: 4000,
      });
    }
  };

  /**
   * 处理文件删除
   * @param id 要删除的文件ID
   */
  const handleFileDelete = async (id: string) => {
    const fileToDelete = uploadedFiles.find(file => file.id === id);
    if (fileToDelete) {
      await deleteFile(id);
      setUploadedFiles(prevFiles => prevFiles.filter(file => file.id !== id));
      setTotalUploadSize(prevSize => prevSize - fileToDelete.size);
      toast.success('File deleted');
    }
  };

  /**
   * 处理消息提交
   * @param message 用户输入的消息
   * @param activeMode 当前激活的模式
   */
  const handleSubmit = async (message: string, activeMode: string | null) => {
    if (!message.trim() || isLoading) return;

    setIsLoading(true);
    const userMessage: Message = {
      role: 'user',
      content: message,
      timestamp: new Date(),
      files: uploadedFiles.map(f => ({ name: f.name, size: f.size, type: f.type })),
    };
    setMessages(prev => [...prev, userMessage]);

    // 构建 JSON 请求体 - 统一结构
    const requestBody: Record<string, unknown> = {
      message: message,
      mode: activeMode || '',  // 改为 mode，未选择时为空字符串
      files: uploadedFiles.length > 0 
        ? uploadedFiles.map(file => ({
            name: file.name,
            type: file.type,
            size: file.size,
            data: file.data // 已经是 base64 格式
          }))
        : []  // 没有文件时为空数组
    };

    // Clear uploaded files after adding them to the form
    const deletePromises = uploadedFiles.map(file => deleteFile(file.id));
    await Promise.all(deletePromises);
    setUploadedFiles([]);
    setTotalUploadSize(0);

    // Add a placeholder for the assistant's response
    const assistantPlaceholder: Message = {
      role: 'assistant',
      content: '',  // 空内容，让 loading 动画可以显示
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, assistantPlaceholder]);

    try {
      console.log('Sending message with authFetch...');
      
      let currentSessionId = sessionId;
      
      // 如果没有sessionId，创建会话
      if (!currentSessionId) {
        try {
          const sessionResponse = await authFetch(`/api/chat/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
          });
          if (!sessionResponse.ok) {
            throw new Error('Failed to create a new chat session.');
          }
          const sessionData = await sessionResponse.json();
          currentSessionId = sessionData.sessionId;
          setSessionId(currentSessionId);
          localStorage.setItem('sessionId', currentSessionId!);
        } catch (error) {
          if (error instanceof Response && (error.status === 401 || error.status === 403)) {
            setMessages(prev => prev.slice(0, -2));
            setIsLoading(false);
            return;
          }
          
          const errorMessage = error instanceof Error ? error.message : 'Failed to create session';
          toast.error(errorMessage);
          setIsLoading(false);
          setMessages(prev => prev.slice(0, -2));
          return;
        }
      }

      const response = await authFetch(`/api/chat/sessions/${currentSessionId}/messages`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream', // 请求 SSE 流式响应
        },
      });

      if (!response.ok) {
        // If it's an authentication error, throw the Response object directly
        if (response.status === 401 || response.status === 403) {
          throw response;
        }
        // Handle payment required error
        if (response.status === 402) {
          const errorData = await response.json();
          toast.error(errorData.error || 'Subscription required. Please upgrade to continue.');
          openSubscription();
          setMessages(prev => prev.slice(0, -2)); // Remove user message and assistant placeholder
          setIsLoading(false);
          return;
        }
        throw new Error(`Server error: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("Response body is null");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Process buffer line by line for events
        let eventEndIndex;
        while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
          const eventString = buffer.substring(0, eventEndIndex);
          buffer = buffer.substring(eventEndIndex + 2);

          if (eventString.startsWith('data: ')) {
            const jsonString = eventString.substring(6);
            try {
              const event = JSON.parse(jsonString);
              console.log(`[SSE] Received event: ${event.type}`, event);
              
              if (event.type === 'END') {
                // 任务完成，SSE流结束
                setIsLoading(false);
                
                // 检查任务状态
                if (event.status === 'FAILED' || event.status === 'failed') {
                  toast.error('Task execution failed, please try again later');
                  console.error('Task failed:', event);
                } else if (event.status === 'COMPLETED' || event.status === 'completed') {
                  console.log('[SSE] Task completed successfully');
                }
                
                // 从最后一条消息的 taskSteps 中提取 final_answer 作为 content
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    const taskSteps = lastMessage.taskSteps || [];
                    // 查找 final_answer 或 error 步骤
                    const finalAnswerStep = taskSteps.find((step: TaskStep) => step.type === 'final_answer' || step.type === 'error');
                    if (finalAnswerStep) {
                      // 兼容新旧字段：优先使用 output，回退到 final_answer 或 message
                      const finalAnswer = finalAnswerStep.data?.output || finalAnswerStep.data?.final_answer || finalAnswerStep.data?.message;
                      if (finalAnswer) {
                        lastMessage.content = typeof finalAnswer === 'string' ? finalAnswer : String(finalAnswer);
                      }
                    }
                    // 标记任务为完成
                    lastMessage.is_complete = true;
                  }
                  return newMessages;
                });
                
                // 终止 SSE 流 - 通过设置 done 标志
                reader.cancel();
                break;
              } else if (event.type === 'error' || event.type === 'task_error') {
                // 错误事件
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    newMessages[newMessages.length - 1] = event.message || {
                      ...lastMessage,
                      content: 'Task execution failed, please try again later'
                    };
                  }
                  return newMessages;
                });
                toast.error(event.message?.content || 'Task execution failed');
                setIsLoading(false);
              } else if (event.type === 'task_abnormal') {
                // 处理任务异常事件
                const { error_type, message: errorMessage, task_status } = event.data || {};

                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    // 更新消息内容为错误提示
                    lastMessage.content = errorMessage || '任务执行异常';
                    // 添加异常标记
                    lastMessage.error_type = error_type;
                    lastMessage.task_status = task_status;
                  }
                  return newMessages;
                });

                // 根据错误类型显示不同的提示
                if (error_type === 'task_failed_without_answer') {
                  toast.error('任务执行失败，请重试');
                } else if (error_type === 'task_cancelled') {
                  toast('任务已被取消', { icon: '⚠️' });
                } else if (error_type === 'completed_without_answer') {
                  toast('任务完成但输出格式非标准', { icon: '⚠️' });
                } else if (error_type === 'no_action_history') {
                  toast.error('任务记录异常，无法获取执行过程');
                }

                console.warn('[SSE] Task abnormal:', { error_type, message: errorMessage, task_status });
                // 不要设置isLoading为false，等待END事件
              } else if (event.type === 'task_timeout' || event.type === 'timeout') {
                // 超时事件
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    newMessages[newMessages.length - 1] = {
                      ...lastMessage,
                      content: 'Page timeout, task may still be running in background. Please refresh to get progress.'
                    };
                  }
                  return newMessages;
                });
                toast.error('Page timeout, please refresh to get progress');
                setIsLoading(false);
              } else if (event.type === 'monitor_started') {
                // 监控开始事件，显示提示
                console.log('[SSE] Monitor started:', event.data?.message);
              } else if (event.type !== 'task_started') {
                // 处理 plan, tool_output, reflection 等中间事件
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessageIndex = newMessages.length - 1;
                  
                  if (lastMessageIndex > -1) {
                    const originalLastMessage = newMessages[lastMessageIndex];
                    if (originalLastMessage && originalLastMessage.role === 'assistant') {
                      // 检查是否已存在相同的事件（简单去重）
                      const existingSteps = originalLastMessage.taskSteps || [];
                      const isDuplicate = existingSteps.some(step => 
                        step.type === event.type && 
                        JSON.stringify(step.data) === JSON.stringify(event.data)
                      );
                      
                      if (isDuplicate) {
                        console.log(`[Chat] Skipping duplicate event: ${event.type}`);
                        return newMessages; // 跳过重复事件
                      }
                      
                      // 通过创建新的消息和taskSteps数组来确保不可变性
                      const updatedLastMessage = {
                        ...originalLastMessage,
                        taskSteps: [...existingSteps, event],
                      };

                      // 更新内容以在流式传输期间提供视觉反馈
                      if (event.type === 'plan') {
                        updatedLastMessage.content = `思考计划: \n${event.data.output || event.data.thought || ''}`;  // 兼容新旧字段
                      } else if (event.type === 'tool_output') {
                        // 尝试从多个位置获取工具名称
                        const toolName = event.data?.tool_name || 
                                       event.data?.metadata?.tool_name || 
                                       event.tool_name || 
                                       'Unknown tool';
                        updatedLastMessage.content = `调用工具: \n[${toolName}]`;
                      } else if (event.type === 'todo') {
                        // 处理TODO事件，显示详细的任务清单
                        const todoData = event.data;
                        const totalCount = todoData?.total_count || 0;
                        const completedCount = todoData?.completed_count || 0;
                        const todoList = todoData?.todo_list || [];
                        
                        // 构建TODO清单显示内容
                        let todoContent = `📋 任务清单 (${completedCount}/${totalCount} 已完成)\n\n`;
                        
                        // 显示未完成的任务
                        const pendingTasks = todoList.filter((t: TodoTask) => !t.completed);
                        if (pendingTasks.length > 0) {
                          todoContent += '**待处理任务:**\n';
                          pendingTasks.forEach((task: TodoTask) => {
                            todoContent += `⏳ ${task.id}. ${task.task}\n`;
                          });
                        }
                        
                        // 显示已完成的任务
                        const completedTasks = todoList.filter((t: TodoTask) => t.completed);
                        if (completedTasks.length > 0) {
                          todoContent += '\n**已完成任务:**\n';
                          completedTasks.forEach((task: TodoTask) => {
                            todoContent += `✅ ${task.id}. ${task.task}`;
                            if (task.completion_details?.completed_by_tool) {
                              todoContent += ` (通过 ${task.completion_details.completed_by_tool})`;
                            }
                            todoContent += '\n';
                          });
                        }
                        
                        updatedLastMessage.content = todoContent;
                        
                        // 同时将TODO数据存储在taskSteps中，以便TaskStepsDisplay组件使用
                        updatedLastMessage.todoData = todoData;
                      } else if (event.type === 'reflection') {
                        updatedLastMessage.content = `Reflection check: \n[${event.data.output || event.data.conclusion || ''}]`;  // 兼容新旧字段
                      } else if (event.type === 'final_answer' || event.type === 'error') {
                        // 保存 final_answer 或 error 内容，兼容新旧字段
                        const finalContent = event.data?.output || event.data?.final_answer || event.data?.message;
                        if (finalContent) {
                          updatedLastMessage.content = finalContent;
                        } else {
                          updatedLastMessage.content = 'Task completed!';
                        }
                      }
                      
                      newMessages[lastMessageIndex] = updatedLastMessage;
                    }
                  }
                  return newMessages;
                });
              }
              // 'task_started' 事件在客户端被忽略
            } catch (_e) {
              console.error("Error parsing SSE event", _e);
            }
          }
        }
      }

    } catch (error) {
      // Check if it's an authentication error (Response object)
      if (error instanceof Response && (error.status === 401 || error.status === 403)) {
        // Authentication error already handled by interceptor, clean up local state
        setMessages(prev => prev.slice(0, -2)); // Remove user message and assistant placeholder
        return;
      }
      
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      toast.error(`Failed to send message: ${errorMessage}`);
      setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.content = `Error: ${errorMessage}`;
          }
          return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * 处理消息的重新提交（例如，编辑后重新发送）
   * @param contextMessages 包含到当前消息为止的上下文
   */
  const handleResubmit = async (contextMessages: Message[]) => {
    if (!sessionId) {
      toast.error("Cannot resubmit message without a session.");
      return;
    }

    const lastMessage = contextMessages[contextMessages.length - 1];
    if (!lastMessage || lastMessage.role !== 'user') {
      toast.error("Cannot resubmit non-user message.");
      return;
    }

    setIsLoading(true);

    try {
      // 1. Delete all messages after this message from the database
      const currentMessageIndex = messages.findIndex(msg => msg.timestamp === lastMessage.timestamp);
      
      const deleteResponse = await authFetch(`/api/chat/sessions/${sessionId}/messages`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          afterIndex: currentMessageIndex === 0 ? -1 : currentMessageIndex - 1,
          isFirstMessage: currentMessageIndex === 0
        }), // Delete this message and all messages after it
      });

      // Show success feedback
      if (currentMessageIndex === 0) {
        toast.success('Restarting conversation...');
      } else {
        toast.success('Resending message...');
      }

      if (!deleteResponse.ok) {
        const errorData = await deleteResponse.json();
        throw new Error(errorData.error || 'Failed to delete old messages');
      }
      
      // 2. Update local state to reflect deletion
      setMessages(prev => prev.slice(0, currentMessageIndex));

      // 3. 使用最后一条消息的内容和空的 activeMode 调用 handleSubmit
      //    注意：这里我们假设重新提交总是使用默认模式
      await handleSubmit(lastMessage.content, null);

    } catch (error) {
      // 检查是否是认证错误
      if (error instanceof Response && (error.status === 401 || error.status === 403)) {
        // Authentication error already handled by interceptor
        setIsLoading(false);
        return;
      }
      
      const errorMessage = error instanceof Error ? error.message : 'Resubmission failed';
      toast.error(`Resubmission failed: ${errorMessage}`);
      setIsLoading(false);
    }
  };

  // 组件渲染

  return (
    <RouteGuard>
    <div className="flex flex-col min-h-screen font-[family-name:var(--font-geist-sans)]">
      {/* 点状星空背景 */}
      <div className="geometric-background">
        {/* 点阵系统 - 每个点都可以变成星芒 */}
        {typeof window !== 'undefined' && (
          <DotMatrix />
        )}
      </div>
      
      {/* Toast通知容器 */}
      <Toaster position="top-center" />
      
      {/* 订阅模态框 */}
      <SubscriptionComponent />
      
      {/* 顶部导航栏 */}
      <ChatTopBar />
      
      {/* 主要内容区域 */}
      <div className="flex-1 flex flex-col">

        {/* 聊天消息区域 - 可滚动 */}
        <div className="flex flex-1 flex-col overflow-y-auto px-4 pt-4 pb-4 chat-messages-container">
          {/* 任务检查状态提示 */}
          {isCheckingTasks && (
            <div className="text-sm text-gray-500 mb-2 text-center">
              Checking for incomplete tasks...
            </div>
          )}
          
          {(!messages || messages.length === 0) && !isLoading && !sessionId ? (
            <ConversationTips />
          ) : (
            <ChatMessages
              messages={messages}
              isLoading={isLoading}
              onEditPrompt={(messageContent: string) => toast.success(`Edit prompt: ${messageContent}`)}
              onResubmit={handleResubmit}
            />
          )}
        </div>

        {/* 输入区域 - 固定在底部 */}
        <div className="flex-shrink-0 p-4">
          <ChatInput
            uploadedFiles={uploadedFiles}
            setUploadedFiles={setUploadedFiles}
            totalUploadSize={totalUploadSize}
            setTotalUploadSize={setTotalUploadSize}
            isLoading={isLoading}
            sendShortcut={sendShortcut}
            onSubmit={handleSubmit}
            onFileDelete={handleFileDelete}
            onDrop={handleDrop}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            isDragging={isDragging}
          />
        </div>
      </div>
    </div>
    </RouteGuard>
  );
}
'use client';

import React, { useState, useRef, useEffect } from 'react';
import { PencilSquareIcon, CheckIcon, SparklesIcon, ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TaskStepsDisplay from './TaskStepsDisplay';
import Image from 'next/image';
import { siteConfig } from '@/lib/site-config';

import {
  Message,
  TaskStep,
} from '@/lib/sessionManager';

interface ChatMessagesProps {
  messages: Message[];
  isLoading: boolean;
  onEditPrompt: (messageContent: string) => void;
  onResubmit: (contextMessages: Message[]) => void;
}

/**
 * Chat messages component - Responsible for rendering chat message list
 * Includes user messages, AI replies, task execution steps and final results
 */
const ChatMessages: React.FC<ChatMessagesProps> = ({ messages, isLoading, onEditPrompt, onResubmit }) => {
  const [expandedSteps, setExpandedSteps] = useState<Map<number, boolean>>(new Map());
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const contentEditableRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [userScrolled, setUserScrolled] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Map<number, boolean>>(new Map());
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (editingIndex !== null && contentEditableRef.current) {
      contentEditableRef.current.focus();
    }
  }, [editingIndex]);

  // Check if mobile on mount
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Auto scroll to bottom logic
  useEffect(() => {
    if (shouldAutoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, shouldAutoScroll]);

  // Detect if user scrolled manually
  useEffect(() => {
    const handleScroll = () => {
      const container = document.querySelector('.chat-messages-container');
      if (container) {
        const { scrollTop, scrollHeight, clientHeight } = container;
        const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 5;
        
        // If user scrolled to bottom, re-enable auto-scroll
        if (isAtBottom) {
          if (userScrolled) {
            setShouldAutoScroll(true);
            setUserScrolled(false);
          }
        } else {
          // User is not at bottom, means they scrolled manually
          if (shouldAutoScroll) {
            setShouldAutoScroll(false);
            setUserScrolled(true);
          }
        }
      }
    };

    const container = document.querySelector('.chat-messages-container');
    if (container) {
      container.addEventListener('scroll', handleScroll);
      return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [shouldAutoScroll, userScrolled]);

  // Auto expand/collapse execution steps
  useEffect(() => {
    if (messages.length === 0) return;

    const lastMessageIndex = messages.length - 1;
    const lastMessage = messages[lastMessageIndex];

    // Only operate on assistant messages with taskSteps
    if (lastMessage.role === 'assistant' && lastMessage.taskSteps) {
      setExpandedSteps(prev => {
        const newMap = new Map(prev);
        // If loading, expand; otherwise collapse
        newMap.set(lastMessageIndex, isLoading);
        return newMap;
      });
    }
  }, [isLoading, messages]);

  const toggleStepsExpanded = (messageIndex: number) => {
    setExpandedSteps(prev => {
      const newMap = new Map(prev);
      newMap.set(messageIndex, !newMap.get(messageIndex));
      return newMap;
    });
  };

  const getWebSearchSegments = (taskSteps: TaskStep[] | undefined) => {
    if (!taskSteps) return [];

    const allSegmentsRaw =
      taskSteps
        .filter(
          step =>
            step.type === 'tool_output' &&
            ('tool_name' in step && (step.tool_name === 'WebSearchTool' || step.tool_name === 'web_search')),
        )
        .flatMap(step => {
          const toolData = step.data as Record<string, unknown>;
          let citations: Array<{ segments?: Array<{ label: string; value: string }> }> = [];
          
          // Try multiple data paths to be compatible with different return formats
          const rawData = toolData?.raw_data as Record<string, unknown>;
          const primaryResult = toolData?.primary_result as Record<string, unknown>;
          const dataResult = (toolData?.data as Record<string, unknown>)?.result as Record<string, unknown>;
          const result = toolData?.result as Record<string, unknown>;
          
          if (rawData?.citations && Array.isArray(rawData.citations)) {
            // New format: tool_output.raw_data.citations (primary_result is now plain text)
            citations = rawData.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if (primaryResult?.citations && Array.isArray(primaryResult.citations)) {
            // Compatible with old format: tool_output.primary_result.citations
            citations = primaryResult.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if (dataResult?.citations && Array.isArray(dataResult.citations)) {
            citations = dataResult.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if (result?.citations && Array.isArray(result.citations)) {
            citations = result.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          }
          
          return citations.flatMap(c => c.segments || []);
        })
        .filter(Boolean) || [];

    return Array.from(
      new Map(allSegmentsRaw.map(item => [item.value, item])).values(),
    );
  };

  if (messages.length === 0 && !isLoading) {
    return null;
  }

  // Check if there are executing tasks or existing assistant messages
  const hasAssistantMessage = messages.some(msg => msg.role === 'assistant');

  return (
    <div className="w-full max-w-3xl mx-auto">
      {messages.map((message, index) => (
        <div key={index} className="mb-6">
          {message.role === 'user' ? (
            <div className="flex justify-end items-start space-x-3">
              <div className="min-w-[150px] sm:min-w-[200px] max-w-[85%] sm:max-w-[75%] lg:max-w-[70%] bg-[var(--accent)] text-[var(--foreground)] rounded-2xl rounded-tr-md px-4 py-3 pr-8 relative group">
                <div
                  className="text-sm whitespace-pre-wrap outline-none cursor-text"
                  contentEditable={editingIndex === index}
                  suppressContentEditableWarning
                  onDoubleClick={() => {
                    console.log('Double click to edit');
                    setEditingIndex(index);
                  }}
                  ref={contentEditableRef}
                  style={{
                    userSelect: 'text',
                    WebkitUserSelect: 'text'
                  }}
                >
                  {message.content}
                </div>
                {editingIndex === index ? (
                  <div className="absolute -bottom-8 -right-2 flex space-x-1">
                    <button
                      className="p-1 rounded-full bg-[var(--accent)] text-[var(--foreground)] hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--accent)]"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (contentEditableRef.current) {
                          onEditPrompt(contentEditableRef.current.textContent || '');
                          setEditingIndex(null);
                        }
                      }}
                      title="Confirm Edit"
                    >
                      <CheckIcon className="h-4 w-4" />
                    </button>
                    <button
                      className="p-1 rounded-full bg-[var(--accent)] text-[var(--foreground)] hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--accent)]"
                      onClick={async (e) => {
                        e.stopPropagation();
                        // If editing, complete edit first
                        if (editingIndex !== null && contentEditableRef.current) {
                          onEditPrompt(contentEditableRef.current.textContent || '');
                          setEditingIndex(null);
                        }

                        // Collect current message and all messages above it
                        const currentMessageIndex = messages.findIndex(msg =>
                          msg.content === message.content &&
                          msg.timestamp === message.timestamp
                        );
                        const contextMessages = messages.slice(0, currentMessageIndex + 1);
                        
                        // Call parent component callback to handle resubmit flow
                        onResubmit(contextMessages);
                      }}
                      title="Magic Optimization"
                    >
                      <SparklesIcon className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    className="absolute -bottom-8 -right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-1 rounded-full text-[var(--foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--accent)]"
                    onClick={() => setEditingIndex(index)}
                    title="Edit Prompt"
                  >
                    <PencilSquareIcon className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="flex-shrink-0">
                <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-[var(--accent)] border border-[var(--border)] flex items-center justify-center text-[var(--foreground)] text-xs sm:text-sm font-medium">
                  U
                </div>
              </div>
            </div>
          ) : (
            <div className="w-full">
              <div className="flex items-center space-x-3 mb-2">
                <div className="flex-shrink-0">
                  <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-[var(--card-bg)] border-2 border-[var(--accent)] flex items-center justify-center text-[var(--foreground)] text-xs sm:text-sm font-bold">
                    C
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-[var(--foreground)]">
                  {siteConfig.assistantName}
                </h3>
              </div>
              <div className="min-w-[200px] sm:min-w-[300px] max-w-[95%] sm:max-w-[90%] lg:max-w-[85%] bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl rounded-bl-md px-4 py-3 ml-11">
                {/* Show execution steps first */}
                {message.taskSteps && (
                  <TaskStepsDisplay
                    steps={message.taskSteps as unknown as TaskStep[]}
                    isExpanded={expandedSteps.get(index) || false}
                    onToggleExpanded={() => toggleStepsExpanded(index)}
                    isLoading={isLoading && index === messages.length - 1}
                  />
                )}
                
                {/* Show loading icon based on LOADING_SVG env variable */}
                {isLoading &&
                index === messages.length - 1 &&
                message.role === 'assistant' ? (
                  <div className="flex justify-center mt-4">
                    <Image 
                      src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/${process.env.NEXT_PUBLIC_LOADING_SVG || 'frago'}.svg`}
                      alt="Loading"
                      width={80}
                      height={80}
                      className="brightness-0 invert"
                      priority
                    />
                  </div>
                ) : null}

                {/* Final Markdown content (only show when loading is complete) */}
                {/* Only show final content when (a) not loading or (b) loading but this is an old message */}
                {(!isLoading || index < messages.length - 1) &&
                  message.content && (
                    <div className="markdown-content">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          table: ({ children }) => (
                            <div className="table-container">
                              <table>{children}</table>
                            </div>
                          ),
                          a: ({ href, children }) => (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  )}
                {/* Show citation links */}
                {/* Show citation links, but not before final answer is generated */}
                {(() => {
                  const segments = getWebSearchSegments(message.taskSteps);
                  if (
                    segments.length > 0 &&
                    !(isLoading && index === messages.length - 1)
                  ) {
                    const isExpanded = expandedSources.has(index) ? expandedSources.get(index) : !isMobile;
                    return (
                      <div className="mt-4 pt-3">
                        <button
                          onClick={() => {
                            const newMap = new Map(expandedSources);
                            newMap.set(index, !isExpanded);
                            setExpandedSources(newMap);
                          }}
                          className="flex items-center gap-2 mb-3 text-sm font-semibold text-[var(--foreground)] opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
                        >
                          {isExpanded ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronRightIcon className="w-4 h-4" />}
                          <span>All Search Sources ({segments.length})</span>
                        </button>
                        {isExpanded && (
                          <div className="flex flex-wrap gap-2">
                            {segments.map((segment, i) => (
                              <a
                                key={i}
                                href={segment.value}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center px-3 py-1.5 bg-[var(--accent)] text-[var(--foreground)] text-sm rounded-full transition-all duration-200 hover:bg-[var(--foreground)] hover:text-[var(--background)] hover:shadow-md"
                              >
                                <svg 
                                  className="w-3 h-3 mr-1.5 opacity-60" 
                                  fill="none" 
                                  stroke="currentColor" 
                                  viewBox="0 0 24 24"
                                >
                                  <path 
                                    strokeLinecap="round" 
                                    strokeLinejoin="round" 
                                    strokeWidth={2} 
                                    d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" 
                                  />
                                </svg>
                                <span className="font-medium">{segment.label}</span>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
            </div>
          )}
        </div>
      ))}
      {/* Only show loading state when there's no assistant message and isLoading is true */}
      {isLoading && !hasAssistantMessage && (
        <div className="mb-6">
          <div className="w-full">
            <div className="flex items-center space-x-3 mb-2">
              <div className="flex-shrink-0">
                <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-[var(--card-bg)] border-2 border-[var(--accent)] flex items-center justify-center text-[var(--foreground)] text-xs sm:text-sm font-bold">
                  C
                </div>
              </div>
              <h3 className="text-lg font-semibold text-[var(--foreground)]">
                {siteConfig.assistantName}
              </h3>
            </div>
            <div className="min-w-[200px] sm:min-w-[300px] max-w-[95%] sm:max-w-[90%] lg:max-w-[85%] bg-[var(--code-bg)] rounded-2xl rounded-bl-md px-4 py-3 ml-11">
              <div className="flex items-center space-x-2 text-[var(--foreground)] opacity-70">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--foreground)]"></div>
                <span className="text-sm">Task is executing...</span>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Bottom marker element for auto-scroll */}
      <div ref={messagesEndRef} style={{ height: '1px' }} />
    </div>
  );
};

export default ChatMessages;
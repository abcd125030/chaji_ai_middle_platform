'use client';

import React, { useRef, useEffect } from 'react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TaskStep,
} from '@/lib/sessionManager';

interface TaskStepsDisplayProps {
  steps: TaskStep[];
  isExpanded: boolean;
  onToggleExpanded: () => void;
  isLoading: boolean;
}

const TaskStepsDisplay: React.FC<TaskStepsDisplayProps> = ({
  steps,
  isExpanded,
  onToggleExpanded,
  isLoading,
}) => {
  const stepsContainerRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom
  useEffect(() => {
    if (isExpanded && stepsContainerRef.current) {
      const container = stepsContainerRef.current;
      container.scrollTop = container.scrollHeight;
    }
  }, [steps.length, isExpanded, isLoading]);
  const renderStepContent = (step: TaskStep, stepIndex: number) => {
    switch (step.type) {
      case 'plan':
        return (
          <div>
            <p className="font-semibold">Thinking</p>
            <p className="text-[var(--foreground)] opacity-70 mt-1">{step.data.thought}</p>
            {step.data.tool_name && (
              <p className="text-[var(--foreground)] opacity-70 mt-1">
                Tool: <span className="font-mono bg-[var(--accent)] px-1 rounded">{step.data.tool_name}</span>
              </p>
            )}
          </div>
        );
      case 'tool_output': {
        // For tool_output type, tool_name is at the top level
        const toolName = ('tool_name' in step ? step.tool_name : step.data?.tool_name) || 'Unknown Tool';
        if (toolName === 'WebSearchTool' || toolName === 'web_search') {
          // Compatible with different tool name formats
          const toolData = step.data as Record<string, unknown>;
          let citations: Array<{ segments?: Array<{ label: string; value: string }> }> = [];
          
          // Debug log
          console.log('[WebSearch Data Debug]', {
            toolName,
            toolData,
            hasPrimaryResult: !!(toolData as Record<string, unknown>)?.primary_result,
            hasDataResult: !!((toolData as Record<string, unknown>)?.data as Record<string, unknown>)?.result,
            hasResult: !!(toolData as Record<string, unknown>)?.result,
            primaryResultCitations: ((toolData as Record<string, unknown>)?.primary_result as Record<string, unknown>)?.citations,
          });
          
          // Try multiple data paths to be compatible with different return formats
          const rawData = (toolData as Record<string, unknown>)?.raw_data as Record<string, unknown>;
          const primaryResult = (toolData as Record<string, unknown>)?.primary_result as Record<string, unknown>;
          const dataResult = ((toolData as Record<string, unknown>)?.data as Record<string, unknown>)?.result as Record<string, unknown>;
          
          if (rawData?.citations && Array.isArray(rawData.citations)) {
            // New format: tool_output.raw_data.citations (primary_result is now plain text)
            citations = rawData.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if (primaryResult?.citations && Array.isArray(primaryResult.citations)) {
            // Compatible with old format: tool_output.primary_result.citations
            citations = primaryResult.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if (dataResult?.citations && Array.isArray(dataResult.citations)) {
            // Old format: tool_output.data.result.citations
            citations = dataResult.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          } else if ((toolData as Record<string, unknown>)?.result && Array.isArray(((toolData as Record<string, unknown>).result as Record<string, unknown>)?.citations)) {
            // Another format: tool_output.result.citations
            const result = (toolData as Record<string, unknown>).result as Record<string, unknown>;
            citations = result.citations as Array<{ segments?: Array<{ label: string; value: string }> }>;
          }
          
          if (citations && citations.length > 0) {
            const allSegmentsRaw = citations.flatMap(c => c.segments || []);
            const allSegments = Array.from(
              new Map(allSegmentsRaw.map(item => [item.value, item])).values(),
            );

            return (
              <div>
                <p className="font-semibold">
                  Using{' '}
                  <span className="font-mono bg-[var(--accent)] px-1 rounded">
                    {toolName}
                  </span>
                  {allSegments.length > 0 && ` searched ${allSegments.length} links, reading now`}
                </p>
                {/* <pre className="text-xs bg-gray-800 p-2 rounded mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all">
                  {toolData.primary_result?.text || toolData.result?.text || ''}
                </pre> */}
              </div>
            );
          } else {
            // Show tool usage info even without citations
            return (
              <div>
                <p className="font-semibold">
                  Using{' '}
                  <span className="font-mono bg-[var(--accent)] px-1 rounded">
                    {toolName}
                  </span>
                  {!isLoading || stepIndex < steps.length - 1 ? ' search completed' : ' searching...'}
                </p>
              </div>
            );
          }
        }
        return (
          <div>
            <p className="font-semibold">
              Using{' '}
              <span className="font-mono bg-[var(--accent)] px-1 rounded">
                {String(toolName)}
              </span>
            </p>
            {/* <pre className="text-xs bg-gray-800 p-2 rounded mt-1 max-h-40 overflow-auto">
              {JSON.stringify(step.data.data, null, 2)}
            </pre> */}
          </div>
        );
      }
      case 'todo_created':
        return (
          <div>
            <p className="font-semibold">Create Task List</p>
            {step.data.todo_count && (
              <p className="text-[var(--foreground)] opacity-70 mt-1">
                Created {step.data.todo_count} tasks
              </p>
            )}
            {step.data.todos && Array.isArray(step.data.todos) && (
              <ul className="text-[var(--foreground)] opacity-70 mt-1 ml-4 list-disc">
                {(step.data.todos as Array<{ id: number; task: string; priority: string }>).slice(0, 3).map((todo, idx) => (
                  <li key={idx} className="text-sm">
                    #{todo.id}: {todo.task} (Priority: {todo.priority})
                  </li>
                ))}
                {(step.data.todos as Array<unknown>).length > 3 && (
                  <li className="text-sm">{(step.data.todos as Array<unknown>).length - 3} more tasks...</li>
                )}
              </ul>
            )}
          </div>
        );
      case 'todo_update':
        // New TODO update event format
        return (
          <div>
            <p className="font-semibold">📋 Task List Progress</p>
            {step.data.total_count !== undefined && step.data.completed_count !== undefined && (
              <p className="text-[var(--foreground)] opacity-70 mt-1">
                Progress: {String(step.data.completed_count)}/{String(step.data.total_count)} tasks completed
              </p>
            )}
            {step.data.todo_list && Array.isArray(step.data.todo_list) ? (
              <div className="mt-2 space-y-1">
                {(step.data.todo_list as Array<{id: number; task: string; completed: boolean; suggested_tools?: string[]}>)
                  .slice(0, 5)
                  .map((todo, idx) => (
                    <div key={idx} className="text-sm flex items-start space-x-2">
                      <span className="mt-0.5">
                        {todo.completed ? '✅' : '⏳'}
                      </span>
                      <span className={todo.completed ? 'line-through opacity-60' : ''}>
                        #{todo.id}: {todo.task}
                        {todo.suggested_tools && todo.suggested_tools.length > 0 && (
                          <span className="text-xs opacity-60 ml-1">
                            ({todo.suggested_tools.join(', ')})
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                {(step.data.todo_list as Array<unknown>).length > 5 && (
                  <div className="text-sm opacity-60">
                    {(step.data.todo_list as Array<unknown>).length - 5} more tasks...
                  </div>
                )}
              </div>
            ) : null}
          </div>
        );
      case 'todo_updated':
        // Keep old todo_updated handling for compatibility
        return (
          <div>
            <p className="font-semibold">Update Task Status</p>
            {step.data.operation && (
              <p className="text-[var(--foreground)] opacity-70 mt-1">
                Operation: {step.data.operation === 'mark_completed' ? 'Mark Completed' : 
                       step.data.operation === 'modify' ? 'Modify Task' : 
                       step.data.operation === 'reorder' ? 'Reorder' : 
                       step.data.operation}
              </p>
            )}
            {step.data.task_ids && Array.isArray(step.data.task_ids) && (
              <p className="text-[var(--foreground)] opacity-70 mt-1">
                Task IDs: {(step.data.task_ids as number[]).join(', ')}
              </p>
            )}
          </div>
        );
      case 'final_answer':
      case 'error':
        // Skip rendering final_answer and error steps (content is shown in the message)
        return null;
      default:
        return <p>Unknown step: {step.type}</p>;
    }
  };

  // Don't render anything if there are no steps to display (excluding final_answer)
  const visibleSteps = steps.filter(s => s.type !== 'final_answer');
  if (visibleSteps.length === 0) {
    return null;
  }

  return (
    <div className="mb-4">
      <button
        onClick={onToggleExpanded}
        className="flex items-center space-x-2 text-sm font-medium mb-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-opacity w-full text-left"
      >
        {isExpanded ? (
          <ChevronDownIcon className="h-4 w-4" />
        ) : (
          <ChevronRightIcon className="h-4 w-4" />
        )}
        <span>
          {isLoading ? `Executing (${visibleSteps.length})` : `Execution Steps (${visibleSteps.length})`}
        </span>
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            ref={stepsContainerRef}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="space-y-2 text-sm max-h-96 overflow-y-auto pr-2"
          >
            {visibleSteps.map((step, index) => {
              const isCurrentStep = isLoading && index === visibleSteps.length - 1;
              const isCompletedStep = !isCurrentStep;

              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className="p-3 bg-[var(--background)] rounded-lg"
                >
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 pt-1 w-4 h-4 flex items-center justify-center">
                      {isCurrentStep && (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--foreground)]"></div>
                      )}
                      {isCompletedStep && (
                        <div className="w-4 h-4 rounded-full bg-[var(--foreground)] flex items-center justify-center">
                          <CheckIcon className="h-3 w-3 text-[var(--background)]" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      {renderStepContent(step, index)}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default TaskStepsDisplay;
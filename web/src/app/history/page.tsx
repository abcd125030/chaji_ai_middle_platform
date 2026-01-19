'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch } from '@/lib/auth-fetch';
import ChatTopBar from '@/components/ui/ChatTopBar';
import RouteGuard from '@/components/ui/RouteGuard';
import { Toaster, toast } from 'react-hot-toast';

interface Session {
  id: string;
  ai_conversation_id: string;
  title: string | null;
  last_message_preview: string | null;
  last_interacted_at: string;
  is_pinned: boolean;
  is_archived: boolean;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  file_count: number;
  has_active_tasks: boolean;
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await authFetch('/api/chat/sessions');
        if (response.ok) {
          const data = await response.json();
          setSessions(data);
        } else {
          toast.error('Failed to load conversation history.');
        }
      } catch {
        toast.error('Error occurred while loading conversation history.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchSessions();
  }, []);

  const handleSessionClick = (sessionId: string) => {
    localStorage.setItem('sessionId', sessionId);
    //Print message indicating sessionId has been set
    console.log(`Session ID set to: ${sessionId}`);
    // Clean up potentially existing old sessionData
    localStorage.removeItem('sessionData');
    router.push('/chat');
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <RouteGuard>
    <div className="flex flex-col min-h-screen bg-[var(--background)] text-[var(--foreground)] font-[family-name:var(--font-geist-sans)]">
      <Toaster position="top-center" />
      <ChatTopBar />
      <main className="flex-1 p-4 sm:p-6 md:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl sm:text-3xl font-bold mb-6">History</h1>
          {isLoading ? (
            <div className="text-center opacity-70">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="text-center opacity-70">No history found.</div>
          ) : (
            <div className="flex flex-col gap-4">
              {sessions.map(session => {
                const previewText = session.last_message_preview || 'No preview available';
                
                return (
                  <div
                    key={session.id}
                    onClick={() => handleSessionClick(session.id)}
                    className={`bg-[var(--background-light)] border rounded-lg p-4 cursor-pointer hover:border-[var(--foreground)] transition-colors duration-200 flex flex-row justify-between items-start gap-4 ${
                      session.has_active_tasks ? 'border-[var(--accent)]' : 'border-[var(--accent)]'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-2 mb-1 flex-wrap">
                        <h2 className="font-bold text-lg truncate flex-1 min-w-0">
                          {session.title || `Session ${formatTime(session.created_at)}`}
                        </h2>
                        <div className="flex gap-1 flex-shrink-0">
                          {session.is_pinned && (
                            <span className="text-xs border border-[var(--accent)] text-[var(--accent)] px-2 py-0.5 rounded-full whitespace-nowrap">
                              Pinned
                            </span>
                          )}
                          {session.has_active_tasks && (
                            <span className="text-xs bg-[var(--foreground)] text-[var(--background)] px-2 py-0.5 rounded-full whitespace-nowrap">
                              Active Tasks
                            </span>
                          )}
                        </div>
                      </div>
                      <p className="text-sm opacity-70 break-words line-clamp-2 mb-1">
                        {previewText}
                      </p>
                      <div className="flex flex-wrap gap-3 text-xs opacity-50">
                        <span className="whitespace-nowrap">{session.message_count} messages</span>
                        {session.file_count > 0 && <span className="whitespace-nowrap">{session.file_count} files</span>}
                        {session.tags && session.tags.length > 0 && (
                          <span className="truncate max-w-[200px]">Tags: {session.tags.join(', ')}</span>
                        )}
                      </div>
                    </div>
                    <div className="text-xs opacity-50 text-right flex-shrink-0 whitespace-nowrap">
                      {formatTime(session.last_interacted_at)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
    </RouteGuard>
  );
}
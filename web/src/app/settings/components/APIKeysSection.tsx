'use client';

import React, { useState, useEffect } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  KeyIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { authFetch } from '@/lib/auth-fetch';

interface APIKey {
  id: string;
  name: string;
  key_display: string;
  status: 'active' | 'revoked';
  created_at: string;
  last_used_at: string | null;
}

interface CreateKeyResponse {
  status: string;
  data: {
    id: string;
    name: string;
    key: string;
    key_prefix: string;
    key_suffix: string;
    created_at: string;
  };
  message: string;
}

const APIKeysSection: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showCreatedKey, setShowCreatedKey] = useState(false);
  const [editingKeyId, setEditingKeyId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  // Fetch API keys on mount
  useEffect(() => {
    fetchAPIKeys();
  }, []);

  const fetchAPIKeys = async () => {
    try {
      setIsLoading(true);
      const response = await authFetch('/api/user/api-keys');
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          setApiKeys(data.data);
        }
      } else {
        toast.error('Failed to load API keys');
      }
    } catch (error) {
      console.error('Error fetching API keys:', error);
      toast.error('Failed to load API keys');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast.error('Please enter a name for the API key');
      return;
    }

    setIsCreating(true);
    try {
      const response = await authFetch('/api/user/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });

      if (response.ok) {
        const data: CreateKeyResponse = await response.json();
        if (data.status === 'success') {
          setCreatedKey(data.data.key);
          setShowCreatedKey(true);
          toast.success('API key created successfully');
          fetchAPIKeys();
        }
      } else {
        toast.error('Failed to create API key');
      }
    } catch (error) {
      console.error('Error creating API key:', error);
      toast.error('Failed to create API key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    try {
      const response = await authFetch(`/api/user/api-keys/${keyId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast.success('API key deleted');
        setApiKeys(apiKeys.filter(key => key.id !== keyId));
        setShowDeleteConfirm(null);
      } else {
        toast.error('Failed to delete API key');
      }
    } catch (error) {
      console.error('Error deleting API key:', error);
      toast.error('Failed to delete API key');
    }
  };

  const handleUpdateName = async (keyId: string) => {
    if (!editingName.trim()) {
      toast.error('Name cannot be empty');
      return;
    }

    try {
      const response = await authFetch(`/api/user/api-keys/${keyId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editingName.trim() }),
      });

      if (response.ok) {
        toast.success('API key name updated');
        setApiKeys(apiKeys.map(key =>
          key.id === keyId ? { ...key, name: editingName.trim() } : key
        ));
        setEditingKeyId(null);
        setEditingName('');
      } else {
        toast.error('Failed to update API key name');
      }
    } catch (error) {
      console.error('Error updating API key:', error);
      toast.error('Failed to update API key name');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch {
      toast.error('Failed to copy');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setNewKeyName('');
    setCreatedKey(null);
    setShowCreatedKey(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[var(--foreground)]">API Keys</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Manage your API keys for accessing the OpenAI-compatible endpoint
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          <span>Create Key</span>
        </button>
      </div>

      {/* Usage Info */}
      <div className="bg-[var(--accent)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-semibold text-[var(--foreground)] mb-2">How to use</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Use your API key in the Authorization header:
        </p>
        <code className="block mt-2 p-3 bg-[var(--card-bg)] rounded text-sm font-mono text-[var(--foreground)]">
          Authorization: Bearer sk-your-api-key
        </code>
        <p className="text-sm text-[var(--muted-foreground)] mt-2">
          Endpoint: <code className="text-purple-500">/api/llm/v1/chat/completions/</code>
        </p>
      </div>

      {/* API Keys List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-8 text-[var(--muted-foreground)]">
            Loading...
          </div>
        ) : apiKeys.length === 0 ? (
          <div className="text-center py-12 bg-[var(--card-bg)] rounded-lg border border-[var(--border)]">
            <KeyIcon className="w-12 h-12 mx-auto text-[var(--muted-foreground)] mb-4" />
            <p className="text-[var(--muted-foreground)]">No API keys yet</p>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">
              Create your first API key to get started
            </p>
          </div>
        ) : (
          apiKeys.map(key => (
            <div
              key={key.id}
              className="bg-[var(--card-bg)] border border-[var(--border)] rounded-lg p-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  {/* Name */}
                  {editingKeyId === key.id ? (
                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        className="px-2 py-1 bg-[var(--background)] border border-[var(--border)] rounded text-[var(--foreground)] text-sm"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleUpdateName(key.id);
                          if (e.key === 'Escape') {
                            setEditingKeyId(null);
                            setEditingName('');
                          }
                        }}
                      />
                      <button
                        onClick={() => handleUpdateName(key.id)}
                        className="p-1 text-green-500 hover:bg-green-500/10 rounded"
                      >
                        <CheckIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          setEditingKeyId(null);
                          setEditingName('');
                        }}
                        className="p-1 text-red-500 hover:bg-red-500/10 rounded"
                      >
                        <XMarkIcon className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-medium text-[var(--foreground)]">{key.name}</h3>
                      <button
                        onClick={() => {
                          setEditingKeyId(key.id);
                          setEditingName(key.name);
                        }}
                        className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] rounded"
                      >
                        <PencilIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Key Display */}
                  <div className="flex items-center gap-2 mb-2">
                    <code className="text-sm font-mono text-[var(--muted-foreground)] bg-[var(--background)] px-2 py-1 rounded">
                      {key.key_display}
                    </code>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      key.status === 'active'
                        ? 'bg-green-500/20 text-green-500'
                        : 'bg-red-500/20 text-red-500'
                    }`}>
                      {key.status}
                    </span>
                  </div>

                  {/* Dates */}
                  <div className="flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
                    <span>Created: {formatDate(key.created_at)}</span>
                    {key.last_used_at && (
                      <span>Last used: {formatDate(key.last_used_at)}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => setShowDeleteConfirm(key.id)}
                    className="p-2 text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                    title="Delete key"
                  >
                    <TrashIcon className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Delete Confirmation */}
              {showDeleteConfirm === key.id && (
                <div className="mt-4 pt-4 border-t border-[var(--border)]">
                  <p className="text-sm text-[var(--foreground)] mb-3">
                    Are you sure you want to delete this API key? This action cannot be undone.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDeleteKey(key.id)}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg transition-colors"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(null)}
                      className="px-3 py-1.5 bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-[var(--foreground)] text-sm rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create Key Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={closeCreateModal}
          />

          {/* Modal */}
          <div className="relative bg-[var(--card-bg)] border border-[var(--border)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-[var(--foreground)]">
                {createdKey ? 'API Key Created' : 'Create New API Key'}
              </h3>
              <button
                onClick={closeCreateModal}
                className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] rounded"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            {createdKey ? (
              /* Show Created Key */
              <div className="space-y-4">
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium mb-2">
                    Important: Copy your API key now
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    This is the only time you will see the full API key. Store it securely.
                  </p>
                </div>

                <div className="relative">
                  <div className="flex items-center gap-2 p-3 bg-[var(--background)] border border-[var(--border)] rounded-lg">
                    <code className="flex-1 text-sm font-mono text-[var(--foreground)] break-all">
                      {showCreatedKey ? createdKey : '••••••••••••••••••••••••••••••••'}
                    </code>
                    <button
                      onClick={() => setShowCreatedKey(!showCreatedKey)}
                      className="p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] rounded"
                    >
                      {showCreatedKey ? (
                        <EyeSlashIcon className="w-5 h-5" />
                      ) : (
                        <EyeIcon className="w-5 h-5" />
                      )}
                    </button>
                    <button
                      onClick={() => copyToClipboard(createdKey)}
                      className="p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] rounded"
                    >
                      <ClipboardDocumentIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                <button
                  onClick={closeCreateModal}
                  className="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                >
                  Done
                </button>
              </div>
            ) : (
              /* Create Key Form */
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-2">
                    Key Name
                  </label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g., Production API Key"
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateKey();
                    }}
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={closeCreateModal}
                    className="flex-1 py-2 bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-[var(--foreground)] rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateKey}
                    disabled={isCreating || !newKeyName.trim()}
                    className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                  >
                    {isCreating ? 'Creating...' : 'Create'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default APIKeysSection;

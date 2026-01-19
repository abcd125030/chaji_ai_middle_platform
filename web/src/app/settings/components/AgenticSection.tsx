'use client';

import React, { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface Character {
  id: string;
  name: string;
  language: string;
  style: string;
}

const AgenticSection: React.FC = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newCharacterName, setNewCharacterName] = useState('');
  const [newCharacterLanguage, setNewCharacterLanguage] = useState('');
  const [newCharacterStyle, setNewCharacterStyle] = useState('');

  const handleCreateCharacter = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCharacterName.trim() || !newCharacterLanguage.trim()) {
      toast.error('Name and Language are required');
      return;
    }
    const newCharacter = {
      id: Date.now().toString(),
      name: newCharacterName,
      language: newCharacterLanguage,
      style: newCharacterStyle
    };
    setCharacters([...characters, newCharacter]);
    setNewCharacterName('');
    setNewCharacterLanguage('');
    setNewCharacterStyle('');
    setShowCreateForm(false);
    toast.success('Character created successfully');
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold text-[var(--foreground)] mb-6">
        Agentic Characters
      </h2>
      
      {/* Character List */}
      {!showCreateForm ? (
        <div>
          <div className="mb-6">
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-6 py-2.5 bg-[var(--foreground)] text-[var(--background)] rounded-full font-medium text-sm transition-all hover:scale-105 hover:shadow-[0_8px_16px_rgba(0,0,0,0.15)]"
            >
              + Create New Character
            </button>
          </div>
          
          {characters.length === 0 ? (
            <div className="bg-[var(--accent)] rounded-lg p-12 text-center">
              {/* Animated walking person silhouette */}
              <div className="mx-auto mb-4 w-20 h-20">
                <svg viewBox="0 0 64 64" className="w-full h-full">
                  <g className="animate-pulse">
                    {/* Person silhouette */}
                    <path
                      d="M32 8c3.3 0 6 2.7 6 6s-2.7 6-6 6-6-2.7-6-6 2.7-6 6-6zm4 14h-8c-2.2 0-4 1.8-4 4v12c0 1.1.9 2 2 2s2-.9 2-2v-10h1v24c0 1.1.9 2 2 2s2-.9 2-2V40h2v12c0 1.1.9 2 2 2s2-.9 2-2V28h1v10c0 1.1.9 2 2 2s2-.9 2-2V26c0-2.2-1.8-4-4-4z"
                      fill="var(--foreground)"
                      opacity="0.4"
                    >
                      <animateTransform
                        attributeName="transform"
                        type="translate"
                        values="0,0; -1,0; 0,0; 1,0; 0,0"
                        dur="8s"
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="opacity"
                        values="0.4; 0.45; 0.4; 0.45; 0.4"
                        dur="8s"
                        repeatCount="indefinite"
                      />
                    </path>
                    {/* Shadow */}
                    <ellipse
                      cx="32"
                      cy="56"
                      rx="8"
                      ry="2"
                      fill="var(--foreground)"
                      opacity="0.1"
                    >
                      <animate
                        attributeName="rx"
                        values="8; 7; 8; 9; 8"
                        dur="8s"
                        repeatCount="indefinite"
                      />
                    </ellipse>
                  </g>
                </svg>
              </div>
              <h3 className="text-lg font-medium text-[var(--foreground)] mb-2">No Characters Yet</h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                Create your first AI character to get started
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              {characters.map((character) => (
                <div key={character.id} className="bg-[var(--accent)] rounded-lg p-6 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-lg font-semibold text-[var(--foreground)]">{character.name}</h3>
                    <button
                      onClick={() => setCharacters(characters.filter(c => c.id !== character.id))}
                      className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>
                  <p className="text-sm text-purple-600 font-medium mb-2">{character.language}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">{character.style}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Character Creation Form */
        <div className="bg-[var(--accent)] rounded-lg p-8">
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-6">Create New Character</h3>
          <form className="space-y-6" onSubmit={handleCreateCharacter}>
            {/* Character Name */}
            <div className="flex items-start">
              <label htmlFor="characterName" className="w-32 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
                Name <span className="text-red-500">*</span>
              </label>
              <div className="flex-1">
                <input
                  type="text"
                  id="characterName"
                  value={newCharacterName}
                  onChange={(e) => setNewCharacterName(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                  placeholder="e.g. Code Mentor, Writing Assistant"
                  required
                />
              </div>
            </div>

            {/* Response Language */}
            <div className="flex items-start">
              <label htmlFor="characterLanguage" className="w-32 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
                Language <span className="text-red-500">*</span>
              </label>
              <div className="flex-1">
                <select
                  id="characterLanguage"
                  value={newCharacterLanguage}
                  onChange={(e) => setNewCharacterLanguage(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                  required
                >
                  <option value="">Select Response Language</option>
                  <option value="English">English</option>
                  <option value="Chinese">中文 (Chinese)</option>
                  <option value="Japanese">日本語 (Japanese)</option>
                  <option value="Korean">한국어 (Korean)</option>
                  <option value="Spanish">Español (Spanish)</option>
                  <option value="French">Français (French)</option>
                  <option value="German">Deutsch (German)</option>
                  <option value="Russian">Русский (Russian)</option>
                  <option value="Portuguese">Português (Portuguese)</option>
                  <option value="Italian">Italiano (Italian)</option>
                  <option value="Mixed">Mixed (Adaptive)</option>
                </select>
              </div>
            </div>

            {/* Language Style */}
            <div className="flex items-start">
              <label htmlFor="characterStyle" className="w-32 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
                Style
              </label>
              <div className="flex-1">
                <select
                  id="characterStyle"
                  value={newCharacterStyle}
                  onChange={(e) => setNewCharacterStyle(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                >
                  <option value="">Select Language Style</option>
                  <option value="Professional">Professional</option>
                  <option value="Casual">Casual</option>
                  <option value="Friendly">Friendly</option>
                  <option value="Formal">Formal</option>
                  <option value="Academic">Academic</option>
                  <option value="Creative">Creative</option>
                  <option value="Technical">Technical</option>
                  <option value="Concise">Concise</option>
                  <option value="Detailed">Detailed</option>
                  <option value="Humorous">Humorous</option>
                </select>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-center space-x-4 pt-4">
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewCharacterName('');
                  setNewCharacterLanguage('');
                  setNewCharacterStyle('');
                }}
                className="px-6 py-2.5 bg-gray-200 text-gray-700 rounded-full font-medium text-sm transition-all hover:bg-gray-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-6 py-2.5 bg-[var(--foreground)] text-[var(--background)] rounded-full font-medium text-sm transition-all hover:scale-105 hover:shadow-[0_8px_16px_rgba(0,0,0,0.15)]"
              >
                Create Character
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default AgenticSection;
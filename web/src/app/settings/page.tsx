'use client';

import React, { useState, useEffect } from 'react';
import ProfileSection from './components/ProfileSection';
import AgenticSection from './components/AgenticSection';
import CollectionsSection from './components/CollectionsSection';
import KnowledgeSection from './components/KnowledgeSection';
import FlowsSection from './components/FlowsSection';
import APIKeysSection from './components/APIKeysSection';
import {
  UserCircleIcon,
  CpuChipIcon,
  FolderOpenIcon,
  BookOpenIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  HomeIcon,
  KeyIcon,
} from '@heroicons/react/24/outline';
import Link from 'next/link';

const SettingsPage = () => {
  const [selectedMenu, setSelectedMenu] = useState<'profile' | 'agentic' | 'collections' | 'knowledge' | 'flows' | 'apikeys'>('profile');
  const [isMobile, setIsMobile] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);

  const menuItems = [
    { id: 'profile', label: 'Profile', icon: UserCircleIcon, description: '个人信息与偏好' },
    { id: 'agentic', label: 'Agentic', icon: CpuChipIcon, description: 'AI助手配置' },
    { id: 'collections', label: 'Collections', icon: FolderOpenIcon, description: '收藏管理' },
    { id: 'knowledge', label: 'Knowledge', icon: BookOpenIcon, description: '知识库设置' },
    { id: 'flows', label: 'Flows', icon: ArrowPathIcon, description: '工作流配置' },
    { id: 'apikeys', label: 'API Keys', icon: KeyIcon, description: 'API密钥管理' },
  ];

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleMenuSelect = (menuId: typeof selectedMenu) => {
    setSelectedMenu(menuId);
    if (isMobile) {
      setShowMobileMenu(false);
    }
  };

  // Mobile App-like layout
  if (isMobile) {
    return (
      <div className="fixed inset-0 flex flex-col bg-[var(--background)] overscroll-none">
        {/* Mobile Header - Fixed at top */}
        <header className="flex-shrink-0 bg-[var(--background)] border-b border-[var(--border)] z-40">
          <div className="px-4 py-3 flex items-center justify-between">
            <Link
              href="/"
              className="text-[var(--foreground)] p-2 -ml-2 hover:bg-[var(--accent)] rounded-lg transition-colors"
            >
              <HomeIcon className="w-5 h-5" />
            </Link>
            <h1 className="text-lg font-semibold text-[var(--foreground)] flex-1 text-center">
              {menuItems.find(item => item.id === selectedMenu)?.label}
            </h1>
            <button
              onClick={() => setShowMobileMenu(true)}
              className="text-[var(--foreground)] p-2 -mr-2"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </header>

        {/* Mobile Menu Overlay */}
        {showMobileMenu && (
          <>
            {/* Backdrop */}
            <div 
              className="fixed inset-0 bg-black/50 z-40 transition-opacity"
              onClick={() => setShowMobileMenu(false)}
            />
            
            {/* Slide-in Menu */}
            <div className="fixed inset-y-0 left-0 z-50 w-[85%] max-w-sm bg-[var(--background)] shadow-xl transform transition-transform">
              <div className="flex flex-col h-full">
                {/* Menu Header */}
                <div className="px-4 py-6 border-b border-[var(--border)]">
                  <h2 className="text-2xl font-bold text-[var(--foreground)]">设置</h2>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">管理您的应用偏好</p>
                </div>
                
                {/* Menu Items */}
                <nav className="flex-1 overflow-y-auto overscroll-contain py-4">
                  {menuItems.map((item) => {
                    const Icon = item.icon;
                    const isSelected = selectedMenu === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleMenuSelect(item.id as typeof selectedMenu)}
                        className={`
                          w-full flex items-center px-4 py-3 transition-colors
                          ${isSelected 
                            ? 'bg-[var(--accent)] border-l-4 border-purple-500' 
                            : 'hover:bg-[var(--accent)]'
                          }
                        `}
                      >
                        <Icon className={`w-6 h-6 ${isSelected ? 'text-purple-500' : 'text-[var(--foreground)]'}`} />
                        <div className="ml-3 flex-1 text-left">
                          <div className="font-medium text-[var(--foreground)]">{item.label}</div>
                          <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{item.description}</div>
                        </div>
                        <ChevronRightIcon className="w-4 h-4 text-[var(--muted-foreground)]" />
                      </button>
                    );
                  })}
                </nav>
                
                {/* Menu Footer */}
                <div className="p-4 border-t border-[var(--border)] space-y-2">
                  <Link
                    href="/"
                    className="flex items-center justify-center gap-2 w-full py-3 bg-[var(--accent)] hover:bg-[var(--accent)]/80 rounded-lg transition-colors"
                    onClick={() => setShowMobileMenu(false)}
                  >
                    <HomeIcon className="w-5 h-5 text-[var(--foreground)]" />
                    <span className="text-[var(--foreground)] font-medium">返回首页</span>
                  </Link>
                  <button
                    onClick={() => setShowMobileMenu(false)}
                    className="w-full py-2 text-[var(--muted-foreground)] text-sm"
                  >
                    关闭菜单
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Mobile Content - Scrollable area */}
        <main className="flex-1 overflow-y-auto overscroll-contain">
          <div className="p-4 pb-safe">
            {selectedMenu === 'profile' && <ProfileSection isMobile={true} />}
            {selectedMenu === 'agentic' && <AgenticSection />}
            {selectedMenu === 'collections' && <CollectionsSection />}
            {selectedMenu === 'knowledge' && <KnowledgeSection />}
            {selectedMenu === 'flows' && <FlowsSection isMobile={true} />}
            {selectedMenu === 'apikeys' && <APIKeysSection />}
          </div>
        </main>

        {/* Bottom Tab Bar - Fixed at bottom */}
        <nav className="flex-shrink-0 bg-[var(--card-bg)] border-t border-[var(--border)] shadow-[0_-4px_12px_rgba(0,0,0,0.3)]">
          <div className="flex justify-around items-center h-14 px-2 safe-area-inset-bottom">
            {menuItems.slice(0, 4).map((item) => {
              const Icon = item.icon;
              const isSelected = selectedMenu === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleMenuSelect(item.id as typeof selectedMenu)}
                  className="flex flex-col items-center justify-center flex-1 py-1 min-w-0"
                >
                  <Icon className={`w-5 h-5 ${isSelected ? 'text-purple-500' : 'text-[var(--muted-foreground)]'}`} />
                  <span className={`text-[10px] mt-0.5 ${isSelected ? 'text-purple-500 font-medium' : 'text-[var(--muted-foreground)]'}`}>
                    {item.label}
                  </span>
                </button>
              );
            })}
            <button
              onClick={() => setShowMobileMenu(true)}
              className="flex flex-col items-center justify-center flex-1 py-1 min-w-0"
            >
              <svg className="w-5 h-5 text-[var(--muted-foreground)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
              </svg>
              <span className="text-[10px] mt-0.5 text-[var(--muted-foreground)]">更多</span>
            </button>
          </div>
        </nav>
      </div>
    );
  }

  // Desktop layout (unchanged)
  return (
    <div className="flex">
      {/* Desktop Sidebar Menu */}
      <aside className="w-64 h-[calc(100vh-60px)] bg-[var(--background)] border-r border-[var(--border)] sticky top-[60px]">
        <div className="p-6">
          {/* Header with Back Button */}
          <div className="flex items-center justify-between mb-6">
            <Link
              href="/"
              className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              <ArrowLeftIcon className="w-4 h-4" />
              <span>Back</span>
            </Link>
            <h1 className="text-lg font-semibold text-[var(--foreground)]">Settings</h1>
          </div>
          <nav className="space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isSelected = selectedMenu === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedMenu(item.id as typeof selectedMenu)}
                  className={`
                    group relative w-full flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all
                    ${isSelected 
                      ? 'bg-[var(--accent)] text-[var(--foreground)]' 
                      : 'text-[var(--foreground)] opacity-70 hover:opacity-100 hover:bg-[var(--accent)]'
                    }
                  `}
                >
                  {isSelected && (
                    <span className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-purple-400 to-pink-400 rounded-r-full" />
                  )}
                  <Icon className="w-5 h-5 mr-2 ml-1" />
                  <span className="relative">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Desktop Content Area */}
      <main className="flex-1 w-full">
        <div className="w-full sm:w-full md:max-w-[90%] lg:max-w-[80%] xl:max-w-[70%] 2xl:max-w-[60%] mx-auto p-8">
          {selectedMenu === 'profile' && <ProfileSection />}
          {selectedMenu === 'agentic' && <AgenticSection />}
          {selectedMenu === 'collections' && <CollectionsSection />}
          {selectedMenu === 'knowledge' && <KnowledgeSection />}
          {selectedMenu === 'flows' && <FlowsSection />}
          {selectedMenu === 'apikeys' && <APIKeysSection />}
        </div>
      </main>
    </div>
  );
};

export default SettingsPage;
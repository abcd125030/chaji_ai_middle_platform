'use client';

import React, { useState, useEffect, useRef } from 'react';
import { UserCircleIcon, Bars3Icon, ChevronDownIcon, ArrowLeftStartOnRectangleIcon, Cog6ToothIcon, PlusIcon, ClockIcon, SparklesIcon, HomeIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';
import Image from 'next/image';
import { isAuthenticated, verifyToken } from '@/lib/auth-fetch';
import { useRouter, usePathname } from 'next/navigation';
import Logo from '@/components/ui/Logo';
import { useSubscription } from '@/hooks/useSubscription';

interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
}

/**
 * Specialized TopBar for Chat and History pages
 * Features a simplified menu with only Create and History options
 * Desktop: Shows menu items directly, no folding
 * Mobile: Everything folds into hamburger menu (business items first, then user items)
 */
const ChatTopBar: React.FC = () => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const { openSubscription, SubscriptionComponent } = useSubscription();

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth');
      localStorage.removeItem('sessionId');
      router.push('/auth/login');
    }
  };

  const handleNewChat = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('sessionId');
      // Remove sessionData to ensure a clean new chat
      localStorage.removeItem('sessionData');
      
      // 如果已经在 /chat 页面，直接刷新；否则导航到 /chat
      if (pathname === '/chat') {
        window.location.reload();
      } else {
        router.push('/chat');
      }
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Check authentication first
      if (!isAuthenticated()) {
        router.push('/auth/login');
        return;
      }

      // Verify token validity
      const checkTokenValidity = async () => {
        const isValid = await verifyToken();
        if (!isValid) {
          router.push('/auth/login');
          return;
        }
      };
      
      checkTokenValidity();

      const auth = localStorage.getItem('auth');
      if (auth) {
        try {
          const authData = JSON.parse(auth);

          // Handle different data structures
          if (authData.user) { // Check for nested user object first
            setUserInfo({
              id: authData.user.id,
              name: authData.user.name || authData.user.username || 'User',
              avatar: authData.user.avatar || authData.user.avatar_url
            });
          } else if (authData.id) { // Fallback to flat structure
            setUserInfo({
              id: authData.id,
              name: authData.name || authData.username || 'User',
              avatar: authData.avatar || authData.avatar_url
            });
          }
        } catch (error) {
          console.error('Failed to parse user info:', error);
        }
      }
    }
  }, [router]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (mobileMenuRef.current && !mobileMenuRef.current.contains(event.target as Node)) {
        setIsMobileMenuOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const allNavigationItems = [
    { 
      name: 'Create', 
      icon: PlusIcon, 
      action: handleNewChat,
      isActive: pathname === '/chat',
      key: 'create'
    },
    { 
      name: 'History', 
      icon: ClockIcon, 
      href: '/history',
      isActive: pathname === '/history',
      key: 'history'
    }
  ];

  const showItems = process.env.NEXT_PUBLIC_CHAT_MENU_SHOW?.split(',').map(s => s.trim()) || [];
  const navigationItems = allNavigationItems.filter(item => showItems.includes(item.key));
  const showUpgrade = showItems.includes('payments');

  return (
    <div className="w-full bg-[var(--background)] border-b border-[var(--border)] px-5 py-2">
      <div className="flex items-center justify-between">
        {/* Left Logo/Home Area */}
        <div className="flex items-center">
          {/* Desktop: Show Logo */}
          <div className="hidden md:block">
            <Logo />
          </div>
          {/* Mobile: Show Home Icon */}
          <Link 
            href="/" 
            className="md:hidden p-2 -ml-2 text-[var(--foreground)] hover:bg-[var(--accent)] rounded-lg transition-colors"
          >
            <HomeIcon className="h-5 w-5" />
          </Link>
        </div>

        {/* Right Navigation Area */}
        <div className="flex items-center space-x-6">
          {userInfo ? (
            <>
              {/* Desktop Navigation - Always visible on large screens, no folding */}
              <nav className="hidden md:flex items-center space-x-2">
                {navigationItems.map((item) => (
                  item.href ? (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={`group relative flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm transition-all overflow-hidden ${
                        item.isActive
                          ? 'bg-[var(--accent)] text-[var(--foreground)]'
                          : 'text-[var(--foreground)] opacity-70 hover:opacity-100 hover:bg-[var(--accent)]'
                      }`}
                    >
                      {/* Flash light effect on hover - 135 degree angle */}
                      <span className="absolute inset-0 -skew-x-12 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-[1200ms] ease-out" />
                      <item.icon className="h-4 w-4 relative" />
                      <span className="relative">{item.name}</span>
                    </Link>
                  ) : (
                    <button
                      key={item.name}
                      onClick={item.action}
                      className={`group relative flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm transition-all overflow-hidden ${
                        item.isActive
                          ? 'bg-[var(--accent)] text-[var(--foreground)]'
                          : 'text-[var(--foreground)] opacity-70 hover:opacity-100 hover:bg-[var(--accent)]'
                      }`}
                    >
                      {/* Flash light effect on hover - 135 degree angle */}
                      <span className="absolute inset-0 -skew-x-12 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-[1200ms] ease-out" />
                      <item.icon className="h-4 w-4 relative" />
                      <span className="relative">{item.name}</span>
                    </button>
                  )
                ))}
              </nav>

              {/* Desktop Upgrade button - right before user avatar */}
              {showUpgrade && (
                <button
                  onClick={() => openSubscription()}
                  className="hidden md:flex group relative items-center space-x-2 px-3 py-1.5 rounded-lg text-sm transition-all overflow-hidden bg-[var(--decor-hover)]/10 border border-[var(--decor-hover)]/20 text-[var(--decor-hover)] hover:bg-[var(--decor-hover)]/20"
                >
                  <SparklesIcon className="h-4 w-4" />
                  <span>Upgrade</span>
                </button>
              )}

              {/* Desktop User Avatar with Dropdown - Only visible on large screens */}
              <div className="hidden md:block relative" ref={userMenuRef}>
                <button
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  className="flex items-center space-x-1 group"
                >
                  <div className="flex-shrink-0">
                    {userInfo.avatar ? (
                      <Image
                        src={userInfo.avatar}
                        alt={userInfo.name}
                        width={24}
                        height={24}
                        className="h-6 w-6 rounded-full object-cover border border-[var(--border)]"
                        onError={(e) => {
                          console.warn('Avatar load failed:', userInfo.avatar);
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    ) : (
                      <UserCircleIcon className="h-6 w-6 text-[var(--foreground)] opacity-70" />
                    )}
                  </div>
                  <ChevronDownIcon className="h-3 w-3 text-[var(--foreground)] opacity-50 group-hover:opacity-100 transition-opacity" />
                </button>

                {/* User Dropdown Menu - Desktop only */}
                {isUserMenuOpen && (
                  <div className="absolute right-0 mt-2 w-40 bg-[var(--background)] rounded-lg shadow-lg border border-[var(--border)] overflow-hidden z-50">
                    <Link
                      href="/settings"
                      className="group relative flex items-center space-x-2 px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
                      onClick={() => setIsUserMenuOpen(false)}
                    >
                      <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                      <Cog6ToothIcon className="h-4 w-4 relative" />
                      <span className="relative">Settings</span>
                    </Link>
                    <button
                      onClick={() => {
                        setIsUserMenuOpen(false);
                        handleLogout();
                      }}
                      className="group relative flex items-center space-x-2 w-full px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden text-left"
                    >
                      <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                      <ArrowLeftStartOnRectangleIcon className="h-4 w-4 relative" />
                      <span className="relative">Logout</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Mobile Hamburger Menu - Only visible on small screens, no "Menu" text */}
              <div className="md:hidden relative" ref={mobileMenuRef}>
                <button
                  onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                  className="p-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-opacity"
                  aria-label="Toggle menu"
                >
                  <Bars3Icon className="h-5 w-5" />
                </button>

                {/* Mobile Dropdown Menu */}
                {isMobileMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-[var(--background)] rounded-lg shadow-lg border border-[var(--border)] overflow-hidden z-50">
                    {/* Business Navigation Items First */}
                    <div className="border-b border-[var(--border)]">
                      {/* Upgrade button - mobile */}
                      {showUpgrade && (
                        <button
                          onClick={() => {
                            openSubscription();
                            setIsMobileMenuOpen(false);
                          }}
                          className="group relative flex items-center space-x-3 w-full px-4 py-3 text-sm transition-all overflow-hidden text-left bg-[var(--decor-hover)]/10 text-[var(--decor-hover)]"
                        >
                          <span className="absolute inset-y-0 left-0 w-0.5 bg-[var(--decor-hover)] transform transition-transform duration-200" />
                          <SparklesIcon className="h-4 w-4 relative" />
                          <span className="relative font-medium">Upgrade to Pro</span>
                        </button>
                      )}
                      
                      {navigationItems.map((item) => (
                        item.href ? (
                          <Link
                            key={item.name}
                            href={item.href}
                            className={`group relative flex items-center space-x-3 px-4 py-3 text-sm transition-all overflow-hidden ${
                              item.isActive
                                ? 'bg-[var(--accent)] text-[var(--foreground)]'
                                : 'text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)]'
                            }`}
                            onClick={() => setIsMobileMenuOpen(false)}
                          >
                            <span className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-purple-400 to-pink-400 transform -translate-x-full group-hover:translate-x-0 transition-transform duration-200" />
                            <item.icon className="h-4 w-4 relative" />
                            <span className="relative">{item.name}</span>
                          </Link>
                        ) : (
                          <button
                            key={item.name}
                            onClick={() => {
                              item.action?.();
                              setIsMobileMenuOpen(false);
                            }}
                            className={`group relative flex items-center space-x-3 w-full px-4 py-3 text-sm transition-all overflow-hidden text-left ${
                              item.isActive
                                ? 'bg-[var(--accent)] text-[var(--foreground)]'
                                : 'text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)]'
                            }`}
                          >
                            <span className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-purple-400 to-pink-400 transform -translate-x-full group-hover:translate-x-0 transition-transform duration-200" />
                            <item.icon className="h-4 w-4 relative" />
                            <span className="relative">{item.name}</span>
                          </button>
                        )
                      ))}
                    </div>

                    {/* User Menu Items After Business Items */}
                    <div className="py-1">
                      <div className="px-4 py-2 flex items-center space-x-2 text-[var(--foreground)] opacity-60">
                        {userInfo.avatar ? (
                          <Image
                            src={userInfo.avatar}
                            alt={userInfo.name}
                            width={20}
                            height={20}
                            className="h-5 w-5 rounded-full object-cover border border-[var(--border)]"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        ) : (
                          <UserCircleIcon className="h-5 w-5" />
                        )}
                        <span className="text-sm font-medium">{userInfo.name}</span>
                      </div>
                      <Link
                        href="/settings"
                        className="group relative flex items-center space-x-3 px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
                        onClick={() => setIsMobileMenuOpen(false)}
                      >
                        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                        <Cog6ToothIcon className="h-4 w-4 relative" />
                        <span className="relative">Settings</span>
                      </Link>
                      <button
                        onClick={() => {
                          setIsMobileMenuOpen(false);
                          handleLogout();
                        }}
                        className="group relative flex items-center space-x-3 w-full px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden text-left"
                      >
                        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                        <ArrowLeftStartOnRectangleIcon className="h-4 w-4 relative" />
                        <span className="relative">Logout</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Not logged in state */
            <Link href="/auth/login" className="flex items-center space-x-2 opacity-50 cursor-pointer hover:opacity-80">
              <UserCircleIcon className="h-6 w-6 text-[var(--foreground)]" />
              <span className="text-sm text-[var(--foreground)] hidden sm:inline">
                Login
              </span>
            </Link>
          )}
        </div>
      </div>
      
      {/* Subscription Modal */}
      <SubscriptionComponent />
    </div>
  );
};

export default ChatTopBar;
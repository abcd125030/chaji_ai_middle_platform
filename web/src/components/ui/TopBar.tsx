'use client';

import React, { useState, useEffect, useRef } from 'react';
import { UserCircleIcon, Bars3Icon, ChevronDownIcon, ArrowLeftStartOnRectangleIcon, Cog6ToothIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';
import Image from 'next/image';
import { isAuthenticated, verifyToken } from '@/lib/auth-fetch';
import { useRouter } from 'next/navigation';
import Logo from '@/components/ui/Logo';

interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
}


/**
 * Top navigation bar component - displays app logo and user info
 * Left side: CHAGEE AI Studio logo and beta tag
 * Right side: Navigation menu and user avatar
 */
const TopBar: React.FC = () => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth');
      localStorage.removeItem('sessionId');
      router.push('/auth/login');
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Only check if user is authenticated, don't force redirect
      if (!isAuthenticated()) {
        return; // User not logged in, but allow them to view the page
      }

      // If authenticated, verify token validity but don't force redirect
      const checkTokenValidity = async () => {
        const isValid = await verifyToken();
        if (!isValid) {
          // Token invalid, clear auth data but don't redirect
          localStorage.removeItem('auth');
          localStorage.removeItem('sessionId');
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
  }, []);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
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

  return (
    <div className="w-full bg-[var(--background)] border-b border-[var(--border)] px-5 py-2">
      <div className="flex items-center justify-between">
        {/* Left Logo Area */}
        <div className="flex items-center">
          <Logo />
        </div>

        {/* Right User Info Area */}
        <div className="flex items-center space-x-6">
          {/* Desktop Navigation - Always visible on large screens, regardless of login status */}
          <nav className="hidden md:flex items-center space-x-2">
            {(() => {
              const menuItems = [
                { name: 'Agentic', href: '/chat', key: 'agentic' },
                { name: 'Presentation', href: '/presentation', key: 'presentation' },
                { name: 'Tools', href: '/tools', key: 'tools' },
                { name: 'Docs', href: '/docs', key: 'docs' },
                { name: 'Dashboard', href: '/dashboard', key: 'dashboard' },
              ];
              const showItems = process.env.NEXT_PUBLIC_TOPBAR_MENU_SHOW?.split(',').map(s => s.trim()) || [];
              return menuItems.filter(item => showItems.includes(item.key));
            })().map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="group relative px-3 py-1.5 rounded-lg text-sm text-[var(--foreground)] opacity-70 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
              >
                {/* Flash light effect on hover - 135 degree angle */}
                <span className="absolute inset-0 -skew-x-12 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-[1200ms] ease-out" />
                <span className="relative">{item.name}</span>
              </Link>
            ))}
          </nav>

          {userInfo ? (
            <>
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

                {/* User Dropdown Menu */}
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

              {/* Mobile Hamburger Menu - Only visible on small screens */}
              <div className="md:hidden relative" ref={menuRef}>
                <button
                  onClick={() => setIsMenuOpen(!isMenuOpen)}
                  className="p-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-opacity"
                  aria-label="Toggle menu"
                >
                  <Bars3Icon className="h-5 w-5" />
                </button>

                {/* Mobile Dropdown Menu */}
                {isMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-[var(--background)] rounded-lg shadow-lg border border-[var(--border)] overflow-hidden z-50">
                    {/* Business Navigation Items First */}
                    <div className="border-b border-[var(--border)]">
                      {(() => {
                        const menuItems = [
                          { name: 'Agentic', href: '/chat', key: 'agentic' },
                          { name: 'Presentation', href: '/presentation', key: 'presentation' },
                          { name: 'Tools', href: '/tools', key: 'tools' },
                          { name: 'Docs', href: '/docs', key: 'docs' },
                          { name: 'Dashboard', href: '/dashboard', key: 'dashboard' },
                        ];
                        const showItems = process.env.NEXT_PUBLIC_TOPBAR_MENU_SHOW?.split(',').map(s => s.trim()) || [];
                        return menuItems.filter(item => showItems.includes(item.key));
                      })().map((item) => (
                        <Link
                          key={item.name}
                          href={item.href}
                          className="group relative block px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
                          onClick={() => setIsMenuOpen(false)}
                        >
                          {/* Slide-in effect */}
                          <span className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-purple-400 to-pink-400 transform -translate-x-full group-hover:translate-x-0 transition-transform duration-200" />
                          
                          {/* Highlight sweep effect */}
                          <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                          
                          <span className="relative">{item.name}</span>
                        </Link>
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
                        onClick={() => setIsMenuOpen(false)}
                      >
                        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                        <Cog6ToothIcon className="h-4 w-4 relative" />
                        <span className="relative">Settings</span>
                      </Link>
                      <button
                        onClick={() => {
                          setIsMenuOpen(false);
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
            <>
              {/* Desktop Login button */}
              <Link href="/auth/login" className="hidden md:flex items-center space-x-2 opacity-50 cursor-pointer hover:opacity-80">
                <UserCircleIcon className="h-6 w-6 text-[var(--foreground)]" />
                <span className="text-sm text-[var(--foreground)]">
                  Login
                </span>
              </Link>
              
              {/* Mobile Hamburger Menu for non-logged in users */}
              <div className="md:hidden relative" ref={menuRef}>
                <button
                  onClick={() => setIsMenuOpen(!isMenuOpen)}
                  className="p-2 text-[var(--foreground)] opacity-70 hover:opacity-100 transition-opacity"
                  aria-label="Toggle menu"
                >
                  <Bars3Icon className="h-5 w-5" />
                </button>

                {/* Mobile Dropdown Menu */}
                {isMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-[var(--background)] rounded-lg shadow-lg border border-[var(--border)] overflow-hidden z-50">
                    {/* Business Navigation Items */}
                    <div className="border-b border-[var(--border)]">
                      {(() => {
                        const menuItems = [
                          { name: 'Agentic', href: '/chat', key: 'agentic' },
                          { name: 'Presentation', href: '/presentation', key: 'presentation' },
                          { name: 'Tools', href: '/tools', key: 'tools' },
                          { name: 'Docs', href: '/docs', key: 'docs' },
                          { name: 'Dashboard', href: '/dashboard', key: 'dashboard' },
                        ];
                        const showItems = process.env.NEXT_PUBLIC_TOPBAR_MENU_SHOW?.split(',').map(s => s.trim()) || [];
                        return menuItems.filter(item => showItems.includes(item.key));
                      })().map((item) => (
                        <Link
                          key={item.name}
                          href={item.href}
                          className="group relative block px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
                          onClick={() => setIsMenuOpen(false)}
                        >
                          {/* Slide-in effect */}
                          <span className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-purple-400 to-pink-400 transform -translate-x-full group-hover:translate-x-0 transition-transform duration-200" />
                          
                          {/* Highlight sweep effect */}
                          <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                          
                          <span className="relative">{item.name}</span>
                        </Link>
                      ))}
                    </div>

                    {/* Login option */}
                    <div className="py-1">
                      <Link
                        href="/auth/login"
                        className="group relative flex items-center space-x-3 px-4 py-3 text-sm text-[var(--foreground)] opacity-80 hover:opacity-100 hover:bg-[var(--accent)] transition-all overflow-hidden"
                        onClick={() => setIsMenuOpen(false)}
                      >
                        <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500" />
                        <UserCircleIcon className="h-4 w-4 relative" />
                        <span className="relative">Login</span>
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TopBar;
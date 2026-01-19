'use client';

import { useEffect } from 'react';
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { siteConfig } from '@/lib/site-config';
import { Logo } from '@/components/logo';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState<'feishu' | 'google' | 'email' | null>(null);
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showVerification, setShowVerification] = useState(false);
  const [verificationCode, setVerificationCode] = useState('');
  const [verificationEmail, setVerificationEmail] = useState('');
  
  // Get enabled auth methods from environment variables
  const enabledAuthMethods = (process.env.NEXT_PUBLIC_ENABLED_AUTH_METHODS || 'feishu,google')
    .split(',')
    .map(method => method.trim().toLowerCase());
  
  const isFeishuEnabled = enabledAuthMethods.includes('feishu');
  const isGoogleEnabled = enabledAuthMethods.includes('google');
  const isEmailEnabled = enabledAuthMethods.includes('email');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const auth = localStorage.getItem('auth');
      if (auth) {
        try {
          // Validate if auth is valid JSON
          const authData = JSON.parse(auth);
          // Fix: Check correct field 'access' instead of 'token'
          if (authData && authData.access) {
            const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
            // Directly redirect to chat page to avoid loop
            window.location.href = `${basePath}/chat`;
            return;
          }
        } catch {
          // If parsing fails, clear invalid auth
          localStorage.removeItem('auth');
        }
      }
      
      // Handle callback URL
      const params = new URLSearchParams(window.location.search);
      const callbackUrl = params.get('callbackUrl');
      if (callbackUrl) {
        sessionStorage.setItem('callbackUrl', callbackUrl);
      }
    }
  }, []);

  const handleFeishuLogin = async () => {
    setIsLoading('feishu');
    setError('');
    
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      window.location.href = `${basePath}/api/auth/feishu/login?redirect_uri=${encodeURIComponent(process.env.NEXT_PUBLIC_FEISHU_REDIRECT_URI || '')}`;
    } catch {
      setError('Feishu login service is temporarily unavailable');
      setIsLoading(null);
    }
  };

  const handleEmailLogin = async () => {
    if (!email || !password) {
      setError('Please enter email and password');
      return;
    }
    
    setIsLoading('email');
    setError('');
    
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const response = await fetch(`${basePath}/api/auth/email/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        if (data.data.require_verification) {
          // Verification required
          setVerificationEmail(email);
          setShowVerification(true);
        } else {
          // Login successful
          localStorage.setItem('auth', JSON.stringify({
            access: data.data.access,
            refresh: data.data.refresh,
            user: data.data.user,
          }));
          
          // Redirect to originally requested page or chat page
          const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
          const callbackUrl = sessionStorage.getItem('callbackUrl') || `${basePath}/chat`;
          sessionStorage.removeItem('callbackUrl');
          window.location.href = callbackUrl;
        }
      } else {
        setError(data.message || 'Login failed');
      }
    } catch (err) {
      console.error('Email login error:', err);
      setError('Login service is temporarily unavailable');
    } finally {
      setIsLoading(null);
    }
  };
  
  const handleVerifyCode = async () => {
    if (!verificationCode) {
      setError('Please enter verification code');
      return;
    }
    
    setIsLoading('email');
    setError('');
    
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const response = await fetch(`${basePath}/api/auth/email/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          email: verificationEmail, 
          code: verificationCode 
        }),
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        // Verification successful, login
        const authData = {
          access: data.data.access,
          refresh: data.data.refresh,
          user: data.data.user,
        };
        
        // Save authentication info
        localStorage.setItem('auth', JSON.stringify(authData));
        console.log('Auth saved:', authData);
        
        // 跳转到原始请求的页面或聊天页面
        const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
        const callbackUrl = sessionStorage.getItem('callbackUrl') || `${basePath}/chat`;
        sessionStorage.removeItem('callbackUrl');
        console.log('Redirecting to:', callbackUrl);
        window.location.href = callbackUrl;
      } else {
        setError(data.message || 'Invalid verification code');
      }
    } catch (err) {
      console.error('Verification error:', err);
      setError('Verification service is temporarily unavailable');
    } finally {
      setIsLoading(null);
    }
  };
  
  const handleResendCode = async () => {
    setIsLoading('email');
    setError('');
    
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const response = await fetch(`${basePath}/api/auth/email/resend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: verificationEmail }),
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        setError('New verification code has been sent to your email');
      } else {
        setError(data.message || 'Failed to send');
      }
    } catch (err) {
      console.error('Resend code error:', err);
      setError('Service is temporarily unavailable');
    } finally {
      setIsLoading(null);
    }
  };

  const handleGoogleLogin = async () => {
    setIsLoading('google');
    setError('');
    
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const redirectUri = `${window.location.origin}${basePath}/auth/google/callback`;
      
      // Call API to get Google OAuth URL
      const response = await fetch(`${basePath}/api/auth/google/login?redirect_uri=${encodeURIComponent(redirectUri)}`);
      
      if (!response.ok) {
        throw new Error('Failed to get Google login URL');
      }
      
      const data = await response.json();
      
      if (data.auth_url) {
        // Redirect to Google OAuth page
        window.location.href = data.auth_url;
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (err) {
      console.error('Google login error:', err);
      setError('Google login service is temporarily unavailable');
      setIsLoading(null);
    }
  };

  // If showing verification code page
  if (showVerification) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-black">
        <div className="w-full max-w-md">
          {/* Back to Home Link */}
          <Link 
            href="/" 
            className="inline-flex items-center gap-2 text-sm text-white/60 hover:text-white mb-6 transition-colors group"
          >
            <ArrowLeftIcon className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span>Back to Home</span>
          </Link>
          
          <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl p-8 space-y-6">
            {/* Header */}
            <div className="text-center space-y-2">
              <div className="flex justify-center mb-4">
                <Logo size="lg" />
              </div>
              <h1 className="text-2xl font-bold gradient-title">
                Verify Your Email
              </h1>
              <p className="text-sm text-[var(--foreground)] opacity-50">
                Verification code has been sent to {verificationEmail}
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="rounded-lg bg-[var(--card-bg)] border border-[var(--border)] p-4">
                <p className="text-sm text-[var(--foreground)] opacity-70 text-center">{error}</p>
              </div>
            )}

            {/* Verification Form */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-2">
                  Verification Code
                </label>
                <input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="Enter 6-digit code"
                  maxLength={6}
                  className="w-full px-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg 
                    text-[var(--foreground)] text-center text-lg tracking-widest placeholder:text-[var(--foreground)]/20
                    focus:outline-none focus:border-[var(--foreground)] transition-colors"
                  disabled={isLoading === 'email'}
                  onKeyDown={(e) => e.key === 'Enter' && handleVerifyCode()}
                />
              </div>
            </div>

            {/* Verify Button */}
            <button
              onClick={handleVerifyCode}
              disabled={isLoading === 'email'}
              className="w-full px-4 py-3 bg-[var(--accent)] border border-[var(--border)] rounded-lg 
                font-medium text-[var(--foreground)] hover:border-[var(--foreground)]
                transition-all duration-200 ease
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading === 'email' ? (
                <div className="w-5 h-5 mx-auto border-2 border-[var(--foreground)] opacity-50 border-t-transparent rounded-full animate-spin" />
              ) : (
                'Verify'
              )}
            </button>

            {/* Resend Code */}
            <div className="text-center space-y-2">
              <button
                onClick={handleResendCode}
                disabled={isLoading === 'email'}
                className="text-sm text-[var(--foreground)] opacity-50 hover:opacity-100 underline"
              >
                Resend verification code
              </button>
              
              <br />
              
              <button
                onClick={() => {
                  setShowVerification(false);
                  setError('');
                  setEmail('');
                  setPassword('');
                  setVerificationCode('');
                }}
                className="text-sm text-[var(--foreground)] opacity-50 hover:opacity-100 underline"
              >
                Back to login
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default login page
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-black">
      <div className="w-full max-w-md">
        {/* Back to Home Link */}
        <Link 
          href="/" 
          className="inline-flex items-center gap-2 text-sm text-white/60 hover:text-white mb-6 transition-colors group"
        >
          <ArrowLeftIcon className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          <span>Back to Home</span>
        </Link>
        
        <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl p-8 space-y-8">
          {/* Header */}
          <div className="text-center space-y-2">
            <div className="flex justify-center mb-4">
              <Logo size="lg" />
            </div>
            <h1 className="text-2xl font-bold gradient-title">
              Welcome to {siteConfig.name}
            </h1>
            <p className="text-sm text-[var(--foreground)] opacity-50">
              Please choose your login method
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="rounded-lg bg-[var(--card-bg)] border border-[var(--border)] p-4">
              <p className="text-sm text-[var(--foreground)] opacity-70 text-center">{error}</p>
            </div>
          )}

          {/* Email Login Form - Show input fields if email login is enabled */}
          {isEmailEnabled && (
            <>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="example@email.com"
                    className="w-full px-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg 
                      text-[var(--foreground)] placeholder:text-[var(--foreground)]/20
                      focus:outline-none focus:border-[var(--foreground)] transition-colors"
                    disabled={isLoading !== null}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="w-full px-4 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg 
                      text-[var(--foreground)] placeholder:text-[var(--foreground)]/20
                      focus:outline-none focus:border-[var(--foreground)] transition-colors"
                    disabled={isLoading !== null}
                    onKeyDown={(e) => e.key === 'Enter' && handleEmailLogin()}
                  />
                </div>
              </div>

              {/* Email Login Button */}
              <button
                onClick={handleEmailLogin}
                disabled={isLoading !== null}
                className="w-full px-4 py-3 bg-[var(--accent)] border border-[var(--border)] rounded-lg 
                  font-medium text-[var(--foreground)] hover:border-[var(--foreground)]
                  transition-all duration-200 ease
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading === 'email' ? (
                  <div className="w-5 h-5 mx-auto border-2 border-[var(--foreground)] opacity-50 border-t-transparent rounded-full animate-spin" />
                ) : (
                  'Login / Register'
                )}
              </button>
            </>
          )}

          {/* Divider - Only show when there are other login methods */}
          {isEmailEnabled && (isFeishuEnabled || isGoogleEnabled) && (
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--border)]"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-[var(--card-bg)] text-[var(--foreground)] opacity-50">
                  OR
                </span>
              </div>
            </div>
          )}

          {/* Other Login Methods */}
          <div className="space-y-3">
            {/* Feishu Login */}
            {isFeishuEnabled && (
              <button
                onClick={handleFeishuLogin}
                disabled={isLoading !== null}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 
                  bg-[var(--card-bg)] 
                  border border-[var(--border)] 
                  rounded-lg font-medium text-[var(--foreground)]
                  hover:bg-[var(--accent)] 
                  hover:border-[var(--foreground)]
                  transition-all duration-200 ease
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading === 'feishu' ? (
                  <div className="w-5 h-5 border-2 border-[var(--foreground)] opacity-50 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Image 
                      src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/lark.png`}
                      alt="Feishu"
                      width={24}
                      height={24}
                      className="rounded"
                    />
                    <span>Login with Lark</span>
                    <span className="text-xs bg-[var(--accent)] text-[var(--foreground)] opacity-70 px-2 py-0.5 rounded-full ml-auto">
                      Enterprise
                    </span>
                  </>
                )}
              </button>
            )}

            {/* Google Login */}
            {isGoogleEnabled && (
              <button
                onClick={handleGoogleLogin}
                disabled={isLoading !== null}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 
                  bg-[var(--background)] 
                  border border-[var(--border)] 
                  rounded-lg font-medium text-[var(--foreground)]
                  hover:bg-[var(--accent)] 
                  hover:border-[var(--foreground)]
                  transition-all duration-200 ease
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading === 'google' ? (
                  <div className="w-5 h-5 border-2 border-[var(--foreground)] opacity-50 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path
                        fill="currentColor"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="currentColor" opacity="0.8"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="currentColor" opacity="0.6"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      />
                      <path
                        fill="currentColor" opacity="0.9"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      />
                    </svg>
                    <span>Login with Google</span>
                  </>
                )}
              </button>
            )}
          </div>

          {/* Footer */}
          <div className="pt-6 border-t border-[var(--border)]">
            <p className="text-center text-xs text-[var(--foreground)] opacity-50">
              By logging in, you agree to our{' '}
              <a
                href="/terms"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--foreground)] opacity-70 hover:opacity-100 underline"
              >
                Terms of Service
              </a>
              {' '}and{' '}
              <a
                href="/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--foreground)] opacity-70 hover:opacity-100 underline"
              >
                Privacy Policy
              </a>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <p className="text-center text-xs text-[var(--foreground)] opacity-50 mt-8">
          Having issues? Please contact{' '}
          <a href="mailto:support@example.com" className="text-[var(--foreground)] opacity-70 hover:opacity-100 underline">
            Technical Support
          </a>
        </p>
      </div>
    </div>
  );
}
'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Image from 'next/image';

function GoogleCallbackContent() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');

      if (errorParam) {
        setError(`Google login failed: ${errorParam}`);
        setTimeout(() => {
          window.location.href = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/auth/login`;
        }, 3000);
        return;
      }

      if (!code || !state) {
        setError('Login parameters missing');
        setTimeout(() => {
          window.location.href = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/auth/login`;
        }, 3000);
        return;
      }

      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/auth/google/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ code, state }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Login failed');
        }

        const data = await response.json();

        // Save authentication data
        if (data.tokens && data.user) {
          const authData = {
            access: data.tokens.access,
            refresh: data.tokens.refresh,
            user: data.user,
          };
          localStorage.setItem('auth', JSON.stringify(authData));

          // Get callback URL or redirect to home
          const callbackUrl = sessionStorage.getItem('callbackUrl');
          sessionStorage.removeItem('callbackUrl');
          
          window.location.href = callbackUrl || (process.env.NEXT_PUBLIC_BASE_PATH || '/');
        } else {
          throw new Error('Invalid login response format');
        }
      } catch (err) {
        console.error('Google callback error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Google login processing failed';
        setError(errorMessage);
        setTimeout(() => {
          window.location.href = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/auth/login`;
        }, 3000);
      }
    };

    handleCallback();
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-black">
      <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl p-8 max-w-md w-full">
        <div className="text-center space-y-4">
          {error ? (
            <>
              <div className="w-16 h-16 bg-[var(--accent)] rounded-full flex items-center justify-center mx-auto">
                <svg className="w-8 h-8 text-[var(--foreground)] opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-[var(--foreground)]">Login Failed</h2>
              <p className="text-[var(--foreground)] opacity-50">{error}</p>
              <p className="text-sm text-[var(--foreground)] opacity-30">Redirecting to login page...</p>
            </>
          ) : (
            <>
              <div className="flex justify-center items-center">
                <Image 
                  src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/${process.env.NEXT_PUBLIC_LOADING_SVG || 'frago'}.svg`}
                  alt="Loading"
                  width={80}
                  height={80}
                  className="brightness-0 invert"
                  priority
                />
              </div>
              <h2 className="text-xl font-semibold text-[var(--foreground)]">Processing Login</h2>
              <p className="text-[var(--foreground)] opacity-50">Verifying your Google account...</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center p-4 bg-black">
        <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-2xl p-8 max-w-md w-full">
          <div className="text-center space-y-4">
            <div className="flex justify-center items-center">
              <Image 
                src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/${process.env.NEXT_PUBLIC_LOADING_SVG || 'frago'}.svg`}
                alt="Loading"
                width={80}
                height={80}
                className="brightness-0 invert"
                priority
              />
            </div>
            <h2 className="text-xl font-semibold text-[var(--foreground)]">Loading</h2>
            <p className="text-[var(--foreground)] opacity-50">Initializing...</p>
          </div>
        </div>
      </div>
    }>
      <GoogleCallbackContent />
    </Suspense>
  );
}
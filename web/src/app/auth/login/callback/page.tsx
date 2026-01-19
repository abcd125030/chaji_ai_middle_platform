'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { useEffect, useState, useRef, Suspense } from 'react';
import Image from 'next/image';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState('');
  const hasCalledRef = useRef(false);

  useEffect(() => {
    // Prevent duplicate calls (React Strict Mode, router changes, etc.)
    if (hasCalledRef.current) {
      return;
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !state) {
      setError('缺少必要的授权参数');
      return;
    }

    hasCalledRef.current = true;

    const authenticate = async () => {
      try {
        // 使用本地 API 代理而不是直接调用后端
        const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
        const response = await fetch(
          `${basePath}/api/auth/feishu/callback`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code, state }),
            credentials: 'include'
          }
        );

        if (!response.ok) {
          throw new Error('认证失败');
        }

        const data = await response.json();
        
        // 存储用户信息和token到本地
        localStorage.setItem('auth', JSON.stringify({
          ...data.tokens,
          user: data.user
        }));

        // 直接进行页面跳转，不需要任何同步操作
        const callbackUrl = sessionStorage.getItem('callbackUrl');
        console.log(`callbackUrl: ${callbackUrl}`);
        sessionStorage.removeItem('callbackUrl');
        
        // 处理callbackUrl，避免basePath重复
        let finalUrl = callbackUrl || '/';
        
        // 如果callbackUrl以basePath开头，说明是绝对路径，需要去掉basePath前缀
        // 因为router.push会自动添加basePath
        if (basePath && finalUrl.startsWith(basePath)) {
          finalUrl = finalUrl.slice(basePath.length) || '/';
        }
        
        console.log(`finalUrl for router.push: ${finalUrl}`);
        router.push(finalUrl);
      } catch (err) {
        setError((err as Error).message || '登录过程中发生错误');
      }
    };

    authenticate();
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-black">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="flex justify-center items-center p-8">
            <Image 
              src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/${process.env.NEXT_PUBLIC_LOADING_SVG || 'frago'}.svg`}
              alt="Loading"
              width={166}
              height={166}
              className="brightness-0 invert"
            />
          </div>
          {error && (
            <div className="mt-4 p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-md">
              <p className="text-[var(--foreground)] opacity-70">{error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center p-4 bg-black">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <h1 className="text-3xl font-bold gradient-title">加载中...</h1>
          </div>
        </div>
      </div>
    }>
      <CallbackContent />
    </Suspense>
  );
}
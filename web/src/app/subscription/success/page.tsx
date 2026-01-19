'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

function PaymentSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get('order_id');
  
  useEffect(() => {
    // 5秒后自动跳转到主页
    const timer = setTimeout(() => {
      router.push('/_studio');
    }, 5000);
    
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50">
      <div className="text-center">
        <CheckCircleIcon className="w-24 h-24 text-green-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          支付成功！
        </h1>
        <p className="text-gray-600 mb-2">
          感谢您的订阅，您现在可以享受所有高级功能了
        </p>
        {orderId && (
          <p className="text-sm text-gray-500 mb-6">
            订单号：{orderId}
          </p>
        )}
        <div className="space-y-4">
          <button
            onClick={() => router.push('/_studio')}
            className="px-6 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
          >
            返回主页
          </button>
          <p className="text-sm text-gray-500">
            5秒后自动跳转...
          </p>
        </div>
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto"></div>
        </div>
      </div>
    }>
      <PaymentSuccessContent />
    </Suspense>
  );
}
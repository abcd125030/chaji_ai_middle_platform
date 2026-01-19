'use client';

import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { XCircleIcon } from '@heroicons/react/24/solid';

function PaymentFailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get('order_id');
  const reason = searchParams.get('reason');
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50">
      <div className="text-center">
        <XCircleIcon className="w-24 h-24 text-red-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          支付失败
        </h1>
        <p className="text-gray-600 mb-2">
          {reason || '支付过程中出现了问题，请重试'}
        </p>
        {orderId && (
          <p className="text-sm text-gray-500 mb-6">
            订单号：{orderId}
          </p>
        )}
        <div className="space-x-4">
          <button
            onClick={() => router.push('/_studio/subscription')}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            重新支付
          </button>
          <button
            onClick={() => router.push('/_studio')}
            className="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
          >
            返回主页
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PaymentFailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-500 mx-auto"></div>
        </div>
      </div>
    }>
      <PaymentFailContent />
    </Suspense>
  );
}
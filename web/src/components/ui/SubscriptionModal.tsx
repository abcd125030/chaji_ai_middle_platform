'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { toast } from 'react-hot-toast';
import { authFetch } from '@/lib/auth-fetch';
import { 
  XMarkIcon,
  CheckCircleIcon, 
  XCircleIcon,
  ClockIcon,
  ArrowLeftIcon,
  QrCodeIcon,
  CpuChipIcon,
  PuzzlePieceIcon,
  ChatBubbleLeftRightIcon
} from '@heroicons/react/24/outline';

interface PaymentOrder {
  order_id: string;
  payment_url: string;
  qrcode_url: string;
  amount: string;
  expire_time: string;
}

interface PricingPlan {
  id: string;
  name: string;
  price: string;
  originalPrice?: string;
  discount?: string;
  duration: string;
  features: string[];
  popular?: boolean;
}

interface SubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

// Helper function to get pricing from env
const getPricing = (plan: string): { price: string; originalPrice: string; discount: string } => {
  // Default values for each plan
  const defaults: Record<string, { original: string; discount: number }> = {
    basic: { original: '93', discount: 85 },
    pro: { original: '190', discount: 80 },
    max: { original: '969', discount: 75 }
  };
  
  const planDefaults = defaults[plan.toLowerCase()];
  if (!planDefaults) {
    return { price: '0', originalPrice: '', discount: '' };
  }
  
  // Try to read from env, fallback to defaults
  const envOriginalKey = `NEXT_PUBLIC_PRICE_${plan.toUpperCase()}_ORIGINAL`;
  const envDiscountKey = `NEXT_PUBLIC_PRICE_${plan.toUpperCase()}_DISCOUNT`;
  
  const originalPrice = process.env[envOriginalKey] || planDefaults.original;
  const discount = Number(process.env[envDiscountKey] || planDefaults.discount);
  const price = Math.round(Number(originalPrice) * discount / 100).toString();
  
  // Format discount display - show percentage off
  const percentOff = 100 - discount;
  const discountText = discount === 100 ? '' : `${percentOff}% OFF`;
  
  console.log(`Pricing for ${plan}:`, {
    envOriginalKey,
    envDiscountKey,
    originalPrice,
    discount,
    price,
    discountText
  });
  
  return {
    price,
    originalPrice: discount < 100 ? originalPrice : '',
    discount: discountText
  };
};

const pricingPlans: PricingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    price: '0',
    duration: 'month',
    features: [
      '[Agentic] 1 Agentic Tasks per Day',
      '[Extension] 10 Webpage Collecting',
      '[Chat] Ultimate Access'
    ]
  },
  {
    id: 'basic',
    name: 'Basic',
    ...getPricing('basic'),
    duration: 'month',
    features: [
      '300 daily refresh credits',
      '1,900 monthly credits',
      '+1,900 bonus credits monthly',
      'Unlimited chat mode access',
      'Advanced models in Agent mode',
      '2 concurrent tasks',
      '2 scheduled tasks',
      'Image generation',
      'Video generation',
      'Presentation generation',
      'Exclusive data sources'
    ]
  },
  {
    id: 'pro',
    name: 'Pro',
    ...getPricing('pro'),
    duration: 'month',
    features: [
      '300 daily refresh credits',
      '3,900 monthly credits',
      '+3,900 bonus credits monthly',
      'Unlimited chat mode access',
      'Advanced models in Agent mode',
      '3 concurrent tasks',
      '3 scheduled tasks',
      'Image generation',
      'Video generation',
      'Presentation generation',
      'Exclusive data sources'
    ],
    popular: true
  },
  {
    id: 'max',
    name: 'Max',
    ...getPricing('max'),
    duration: 'month',
    features: [
      '300 daily refresh credits',
      '19,900 monthly credits',
      '+19,900 bonus credits monthly',
      'Unlimited chat mode access',
      'Advanced models in Agent mode',
      '10 concurrent tasks',
      '10 scheduled tasks',
      'Image generation',
      'Video generation',
      'Presentation generation',
      'Manus workflow editor',
      'Exclusive data sources',
      'Early access to Beta features'
    ]
  }
];

export default function SubscriptionModal({ isOpen, onClose, onSuccess }: SubscriptionModalProps) {
  const [currentOrder, setCurrentOrder] = useState<PaymentOrder | null>(null);
  const [orderStatus, setOrderStatus] = useState<string>('');
  const [remainingTime, setRemainingTime] = useState<string>('');
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [loadingPlanId, setLoadingPlanId] = useState<string | null>(null);

  // Calculate remaining time
  useEffect(() => {
    if (!currentOrder) return;

    const updateRemainingTime = () => {
      const expireTime = new Date(currentOrder.expire_time).getTime();
      const now = new Date().getTime();
      const diff = expireTime - now;

      if (diff <= 0) {
        setRemainingTime('Expired');
        setCurrentOrder(null);
        return;
      }

      const minutes = Math.floor(diff / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      setRemainingTime(`${minutes}m ${seconds}s`);
    };

    updateRemainingTime();
    const interval = setInterval(updateRemainingTime, 1000);
    return () => clearInterval(interval);
  }, [currentOrder]);

  // Poll payment status
  useEffect(() => {
    if (!currentOrder) return;

    let isActive = true;
    let timeoutId: NodeJS.Timeout;
    let queryCount = 0;

    const checkPaymentStatus = async () => {
      if (!isActive) return;
      
      queryCount++;
      
      try {
        const controller = new AbortController();
        const timeoutSignal = setTimeout(() => controller.abort(), 5000);
        
        const response = await authFetch('/api/payment/query-status', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            order_id: currentOrder.order_id
          }),
          signal: controller.signal
        });
        
        clearTimeout(timeoutSignal);

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.status === 'success' && data.data.order_status === 'success') {
          setOrderStatus('success');
          toast.success('Payment successful! Thank you for subscribing');
          setTimeout(() => {
            setCurrentOrder(null);
            setOrderStatus('');
            onSuccess?.();
            onClose();
          }, 2000);
          return;
        } else if (data.data?.order_status === 'cancelled') {
          setOrderStatus('cancelled');
          setCurrentOrder(null);
          return;
        } else if (data.data?.order_status === 'failed') {
          setOrderStatus('failed');
          setCurrentOrder(null);
          return;
        }
        
        if (isActive) {
          const nextDelay = queryCount <= 3 ? 5000 : 10000;
          timeoutId = setTimeout(checkPaymentStatus, nextDelay);
        }
      } catch (error) {
        console.error('Failed to check payment status:', error);
        if (isActive && queryCount < 20) {
          timeoutId = setTimeout(checkPaymentStatus, 15000);
        }
      }
    };

    timeoutId = setTimeout(checkPaymentStatus, 3000);

    return () => {
      isActive = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [currentOrder, onSuccess, onClose]);

  // Create payment order
  const createPaymentOrder = async (plan: PricingPlan) => {
    setLoadingPlanId(plan.id);
    setOrderStatus('');
    
    const amount = plan.price;
    
    try {
      const response = await authFetch('/api/payment/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          amount: amount,
          title: plan.name,
          description: `${plan.name} - ${plan.duration}`,
          product_id: plan.id,
          payment_method: 'wechat'  // 硬编码为微信支付
        })
      });

      const data = await response.json();
      
      if (data.status === 'success') {
        setCurrentOrder(data.data);
        toast.success('Order created successfully, please scan to pay');
      } else {
        toast.error(data.error || 'Failed to create order');
      }
    } catch (error) {
      console.error('Failed to create order:', error);
      toast.error('Failed to create order, please try again');
    } finally {
      setLoadingPlanId(null);
    }
  };

  // Cancel order
  const handleCancelClick = () => {
    setShowCancelConfirm(true);
  };
  
  const cancelOrder = async () => {
    if (!currentOrder) return;
    
    setShowCancelConfirm(false);
    
    try {
      const response = await authFetch('/api/payment/cancel-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          order_id: currentOrder.order_id
        })
      });

      const data = await response.json();
      
      if (data.status === 'success') {
        toast.success('Order cancelled');
        setCurrentOrder(null);
        setOrderStatus('');
      } else {
        toast.error(data.error || 'Failed to cancel order');
      }
    } catch (error) {
      console.error('Failed to cancel order:', error);
      toast.error('Failed to cancel order');
    }
  };

  const handleClose = () => {
    if (currentOrder) {
      setShowCancelConfirm(true);
    } else {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] overflow-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/80 backdrop-blur-sm"
        onClick={handleClose}
      />
      
      {/* Modal content container */}
      <div className="flex min-h-full items-center justify-center p-4">
        {/* Modal content */}
        <div className="relative z-10 bg-black border border-[#2A2A2A] rounded-2xl w-full max-w-7xl max-h-[90vh] overflow-y-auto my-auto">
          {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-2 hover:bg-white/10 rounded-lg transition-colors z-10"
        >
          <XMarkIcon className="w-6 h-6 text-[#888888] hover:text-white" />
        </button>

        {/* Content */}
        <div className="p-8">
          {!currentOrder ? (
            <>
              {/* Header */}
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-white">
                  Power Up Your Agentic Copilot
                </h2>
              </div>

              {/* Pricing plans grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {pricingPlans.map((plan) => (
                  <div
                    key={plan.id}
                    className="relative group overflow-visible"
                  >
                    {/* Discount badge */}
                    {plan.discount && (
                      <div className="absolute -top-3 left-4 z-20">
                        <span className="px-2 py-1 bg-[var(--decor-hover)] text-black text-[10px] font-bold rounded">
                          {plan.discount}
                        </span>
                      </div>
                    )}
                    
                    {/* Beta badge for paid plans */}
                    {(plan.id === 'basic' || plan.id === 'pro' || plan.id === 'max') && (
                      <div className="absolute -top-3 right-4 z-20 overflow-hidden rounded">
                        <span className="relative block px-2 py-1 bg-[#2A2A2A] text-[#888888] text-[10px] beta-badge-flash">
                          Beta
                        </span>
                      </div>
                    )}
                    
                    {/* Card */}
                    <div className={`relative h-full bg-gradient-to-b from-[#1A1A1A] to-[#0A0A0A] border rounded-xl p-4 transition-all flex flex-col ${
                      plan.price === '0' 
                        ? 'border-[#2A2A2A]' 
                        : 'border-[#2A2A2A] hover:border-[#3A3A3A]'
                    }`}>
                      
                      {/* Plan name */}
                      <div className="text-left mb-4">
                        <h3 className="text-lg font-bold text-white mb-1">
                          {plan.name}
                        </h3>
                        
                        {/* Price */}
                        {plan.price === '0' ? (
                          <>
                            <div className="flex items-baseline gap-1">
                              <span className="text-2xl font-bold text-[#888888]">
                                Free
                              </span>
                            </div>
                            <div className="h-[20px]">
                              {/* Empty space to match the height of price plans' "Save" line */}
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="flex items-baseline gap-1">
                              <span className="text-sm text-[#888888]">¥</span>
                              <span className="text-2xl font-bold text-[#EDEDED]">
                                {plan.price}
                              </span>
                              <span className="text-sm text-[#888888]">/ month</span>
                            </div>
                            <div className="h-[20px]">
                              {plan.originalPrice && (
                                <div className="flex items-center gap-2">
                                  <span className="text-[#666666] line-through text-xs">
                                    ¥{plan.originalPrice}
                                  </span>
                                  <span className="text-[var(--decor-hover)] text-xs font-medium">
                                    Save ¥{Number(plan.originalPrice) - Number(plan.price)}
                                  </span>
                                </div>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                      
                      {/* Features - flex-grow to push button to bottom */}
                      <ul className="space-y-2 mb-4 flex-grow">
                        {plan.features.map((feature, index) => {
                          // Parse icon type from feature text
                          const iconMatch = feature.match(/^\[([^\]]+)\]\s*(.+)/);
                          const iconType = iconMatch ? iconMatch[1].toLowerCase() : null;
                          const featureText = iconMatch ? iconMatch[2] : feature;
                          
                          // Select icon based on type
                          let Icon = CheckCircleIcon;
                          let iconStyle = { color: 'var(--icon-check)' };
                          
                          if (iconType === 'agentic') {
                            Icon = CpuChipIcon;
                            iconStyle = { color: 'var(--icon-agentic)' };
                          } else if (iconType === 'extension') {
                            Icon = PuzzlePieceIcon;
                            iconStyle = { color: 'var(--icon-extension)' };
                          } else if (iconType === 'chat') {
                            Icon = ChatBubbleLeftRightIcon;
                            iconStyle = { color: 'var(--icon-chat)' };
                          }
                          
                          return (
                            <li key={index} className="flex items-start gap-2">
                              <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" style={iconStyle} />
                              <span className="text-xs leading-relaxed text-[#ADADAD]">
                                {featureText}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                      
                      {/* Action button */}
                      {plan.price === '0' ? (
                        <button 
                          disabled
                          className="w-full py-2.5 rounded-lg bg-[#1A1A1A] text-[#666666] text-sm font-medium cursor-not-allowed"
                        >
                          Current Plan
                        </button>
                      ) : (
                        <button 
                          onClick={() => createPaymentOrder(plan)}
                          disabled={loadingPlanId === plan.id}
                          className={`w-full py-2.5 rounded-lg text-sm font-medium transition-all ${
                            loadingPlanId === plan.id
                              ? 'bg-[#2A2A2A] text-[#888888] cursor-not-allowed'
                              : 'bg-white text-black hover:bg-[#EDEDED]'
                          }`}
                        >
                          {loadingPlanId === plan.id ? (
                            <span className="flex items-center justify-center gap-2">
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#888888]"></div>
                              Processing...
                            </span>
                          ) : (
                            `Upgrade to ${plan.name}`
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            // Payment QR code view
            <div className="max-w-2xl mx-auto">
              <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl overflow-hidden">
                {/* Payment header */}
                <div className="p-8 text-white bg-gradient-to-r from-purple-600/20 to-blue-500/20 border-b border-purple-500/20">
                  <div className="flex items-center justify-between mb-4">
                    <button
                      onClick={() => setCurrentOrder(null)}
                      className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    >
                      <ArrowLeftIcon className="w-5 h-5" />
                    </button>
                    <span className="font-medium">Payment</span>
                    <div className="w-9"></div>
                  </div>
                  
                  <div className="text-center">
                    <p className="text-[#ADADAD] text-base mb-3">Payment Amount</p>
                    <p className="text-5xl font-bold">¥{currentOrder.amount}</p>
                  </div>
                </div>

                {/* QR code area */}
                <div className="p-12">
                  {orderStatus === 'success' ? (
                    <div className="text-center py-20">
                      <CheckCircleIcon className="w-32 h-32 text-green-400 mx-auto mb-6" />
                      <p className="text-3xl font-semibold text-white">Payment Successful</p>
                      <p className="text-lg text-[#888888] mt-3">Thank you for your subscription</p>
                    </div>
                  ) : orderStatus === 'failed' ? (
                    <div className="text-center py-20">
                      <XCircleIcon className="w-32 h-32 text-red-400 mx-auto mb-6" />
                      <p className="text-3xl font-semibold text-white">Payment Failed</p>
                      <p className="text-lg text-[#888888] mt-3">Please try again</p>
                    </div>
                  ) : (
                    <>
                      <div className="bg-black border border-[#1A1A1A] rounded-xl p-6 mb-8">
                        {currentOrder.qrcode_url ? (
                          <div className="relative">
                            <Image
                              src={currentOrder.qrcode_url}
                              alt="Payment QR Code"
                              width={320}
                              height={320}
                              className="w-full max-w-[320px] mx-auto rounded-lg"
                            />
                          </div>
                        ) : (
                          <div className="w-[320px] h-[320px] mx-auto bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                            <QrCodeIcon className="w-20 h-20 text-[#888888]" />
                          </div>
                        )}
                      </div>

                      <div className="text-center space-y-4">
                        <p className="text-xl text-white font-medium">
                          Please scan to pay
                        </p>
                        
                        <div className="flex items-center justify-center gap-2 text-sm">
                          <ClockIcon className="w-4 h-4 text-[#888888]" />
                          <span className="text-[#888888]">
                            Time remaining: 
                            <span className={`font-medium ml-1 ${
                              remainingTime.includes('Expired') ? 'text-red-400' : 'text-white'
                            }`}>
                              {remainingTime}
                            </span>
                          </span>
                        </div>

                        <div className="flex items-center justify-center gap-1">
                          <div className="w-1 h-1 bg-green-400 rounded-full animate-pulse"></div>
                          <span className="text-sm text-[#888888]">Checking payment status</span>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {/* Bottom actions */}
                {orderStatus !== 'success' && (
                  <div className="px-8 pb-8 space-y-4">
                    {currentOrder.payment_url && (
                      <a
                        href={currentOrder.payment_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block w-full py-4 bg-[#1A1A1A] hover:bg-[#2A2A2A] text-[#EDEDED] text-lg rounded-lg transition-colors text-center font-medium"
                      >
                        Open Payment Page
                      </a>
                    )}
                    
                    <button
                      onClick={handleCancelClick}
                      className="w-full py-4 text-[#888888] hover:text-white text-lg transition-colors"
                    >
                      Cancel Payment
                    </button>
                  </div>
                )}
              </div>

              {/* Order info */}
              <div className="mt-6 text-center text-base text-[#888888]">
                Order ID: {currentOrder.order_id}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Cancel Confirmation Modal */}
      {showCancelConfirm && (
        <div className="absolute inset-0 z-60 flex items-center justify-center">
          <div 
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowCancelConfirm(false)}
          />
          
          <div className="relative bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl p-6 max-w-sm mx-4">
            <div className="text-center">
              <div className="mx-auto w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              
              <h3 className="text-xl font-semibold text-white mb-2">
                Cancel Payment?
              </h3>
              <p className="text-[#888888] mb-6">
                Are you sure you want to cancel this payment?
              </p>
              
              <div className="flex gap-3">
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="flex-1 py-2 px-4 bg-[#1A1A1A] text-white rounded-lg hover:bg-[#2A2A2A] transition-colors"
                >
                  Continue
                </button>
                <button
                  onClick={() => {
                    cancelOrder();
                    onClose();
                  }}
                  className="flex-1 py-2 px-4 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition-colors font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
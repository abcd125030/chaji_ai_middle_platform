'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { Toaster, toast } from 'react-hot-toast';
import { authFetch } from '@/lib/auth-fetch';
import TopBar from '@/components/ui/TopBar';
import { 
  CreditCardIcon, 
  CheckCircleIcon, 
  XCircleIcon,
  ClockIcon,
  ArrowLeftIcon,
  QrCodeIcon,
  SparklesIcon
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
  duration: string;
  features: string[];
  popular?: boolean;
}

const pricingPlans: PricingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    price: '0',
    duration: 'month',
    features: [
      '3 messages per day',
      'Qwen-Max model',
      'Basic response speed',
      'Community support',
      'No file uploads',
      'Queue waiting required'
    ]
  },
  {
    id: 'basic',
    name: 'Basic',
    price: '8',
    originalPrice: '16',
    duration: 'month',
    features: [
      '300 messages per day',
      'GPT-3.5 + Qwen models',
      '2x faster response',
      'Basic file uploads',
      'Email support',
      '1,500 tokens per request'
    ]
  },
  {
    id: 'plus',
    name: 'Plus',
    price: '17',
    originalPrice: '33',
    duration: 'month',
    features: [
      '1000 messages per day',
      'GPT-4 + Claude models',
      '5x faster response',
      'Advanced file analysis',
      'Image generation',
      'API access (5k calls)',
      '3,800 tokens per request',
      'Priority support'
    ],
    popular: true
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '83',
    originalPrice: '166',
    duration: 'month',
    features: [
      'Unlimited messages',
      'All premium models',
      '10x faster response',
      'Custom fine-tuning',
      'Unlimited API calls',
      'Team collaboration',
      '19,900 tokens per request',
      'Dedicated support',
      'Custom integrations'
    ]
  }
];

export default function SubscriptionPage() {
  const [loading, setLoading] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<PaymentOrder | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PricingPlan | null>(pricingPlans[2]); // Default to Plus (popular)
  const [customAmount, setCustomAmount] = useState('');
  const [orderStatus, setOrderStatus] = useState<string>('');
  const [remainingTime, setRemainingTime] = useState<string>('');
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  
  // Check if custom amount feature is enabled
  const showCustomAmount = process.env.NEXT_PUBLIC_ENABLE_CUSTOM_AMOUNT === 'true';

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
  }, [currentOrder]);

  // Create payment order
  const createPaymentOrder = async () => {
    setLoading(true);
    setOrderStatus('');
    
    const amount = customAmount || selectedPlan?.price || '0';
    
    try {
      const response = await authFetch('/api/payment/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          amount: amount,
          title: customAmount ? 'Custom Recharge' : (selectedPlan?.name || 'Subscription'),
          description: customAmount ? `Recharge ¥${amount}` : (selectedPlan ? `${selectedPlan.name} - ${selectedPlan.duration}` : 'Subscription'),
          product_id: customAmount ? 'custom_recharge' : (selectedPlan?.id || 'subscription')
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
      setLoading(false);
    }
  };

  // Cancel order with confirmation
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

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <Toaster position="top-center" />
      
      {/* TopBar */}
      <TopBar />
      
      {/* Animated background */}
      <div className="fixed inset-0 bg-black -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 via-transparent to-blue-900/10" />
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-600/5 rounded-full filter blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/5 rounded-full filter blur-3xl animate-pulse delay-1000" />
        </div>
      </div>

      {/* Main content - centered vertically and horizontally */}
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="relative z-10 max-w-7xl w-full py-12">
          {/* Page header */}
          <div className="text-center mb-16">
            <div className="mb-4">
              <span className="inline-flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-full text-sm text-[#ADADAD]">
                <SparklesIcon className="w-4 h-4" />
                LIMITED TIME OFFER - 50% OFF
              </span>
            </div>
            <h1 className="text-5xl font-bold text-white mb-4">
              Choose Your Plan
            </h1>
            <p className="text-[#888888] text-xl max-w-2xl mx-auto">
              Get started with our powerful AI assistant. Upgrade anytime to unlock more features.
            </p>
          </div>

        {!currentOrder ? (
          <>
            {/* Pricing plans - 4 column grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
              {pricingPlans.map((plan) => (
                <div
                  key={plan.id}
                  onClick={() => {
                    if (plan.price !== '0') {
                      setSelectedPlan(plan);
                      setCustomAmount('');
                    }
                  }}
                  className={`relative group ${
                    plan.price === '0' ? 'cursor-default' : 'cursor-pointer'
                  }`}
                >
                  {/* Popular badge */}
                  {plan.popular && (
                    <div className="absolute -top-4 left-0 right-0 flex justify-center z-20">
                      <div className="bg-gradient-to-r from-purple-500 to-blue-500 text-white px-6 py-1.5 rounded-full text-sm font-semibold shadow-lg">
                        MOST POPULAR
                      </div>
                    </div>
                  )}
                  
                  {/* Card */}
                  <div className={`relative h-full bg-gradient-to-b from-[#1A1A1A] to-[#0A0A0A] border rounded-2xl p-6 transition-all ${
                    plan.popular 
                      ? 'border-transparent bg-gradient-to-b from-purple-900/20 to-blue-900/20 shadow-xl shadow-purple-500/10' 
                      : selectedPlan?.id === plan.id
                      ? 'border-[#EDEDED] shadow-lg shadow-white/5'
                      : 'border-[#2A2A2A] hover:border-[#3A3A3A]'
                  } ${
                    plan.price !== '0' ? 'hover:transform hover:-translate-y-1' : ''
                  }`}>
                    
                    {/* Plan name */}
                    <div className="text-center mb-6">
                      <h3 className={`text-lg font-bold mb-4 ${
                        plan.popular ? 'text-transparent bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text' : 'text-white'
                      }`}>
                        {plan.name.toUpperCase()}
                      </h3>
                      
                      {/* Price */}
                      {plan.price === '0' ? (
                        <div className="py-2">
                          <span className="text-3xl font-bold text-[#888888]">Free</span>
                        </div>
                      ) : (
                        <div>
                          {plan.originalPrice && (
                            <div className="text-[#666666] line-through text-sm mb-1">
                              ¥{plan.originalPrice}/mo
                            </div>
                          )}
                          <div className="flex items-baseline justify-center gap-1">
                            <span className="text-sm text-[#888888]">¥</span>
                            <span className={`text-4xl font-bold ${
                              plan.popular ? 'text-white' : 'text-[#EDEDED]'
                            }`}>{plan.price}</span>
                            <span className="text-sm text-[#888888]">/mo</span>
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Divider */}
                    <div className={`h-px mb-6 ${
                      plan.popular 
                        ? 'bg-gradient-to-r from-transparent via-purple-500/50 to-transparent' 
                        : 'bg-[#2A2A2A]'
                    }`} />
                    
                    {/* Features */}
                    <ul className="space-y-3 mb-6">
                      {plan.features.map((feature, index) => {
                        const isNegative = feature.includes('No ') || feature.includes('Queue');
                        return (
                          <li key={index} className="flex items-start gap-2">
                            {isNegative ? (
                              <XCircleIcon className="w-4 h-4 text-[#666666] flex-shrink-0 mt-0.5" />
                            ) : (
                              <CheckCircleIcon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                                plan.popular ? 'text-purple-400' : 'text-green-400'
                              }`} />
                            )}
                            <span className={`text-xs leading-relaxed ${
                              isNegative ? 'text-[#666666]' : 'text-[#ADADAD]'
                            }`}>
                              {feature}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                    
                    {/* Select button */}
                    {plan.price !== '0' && (
                      <button className={`w-full py-2.5 rounded-lg font-semibold text-sm transition-all ${
                        selectedPlan?.id === plan.id
                          ? 'bg-[#EDEDED] text-[#0A0A0A]'
                          : plan.popular
                          ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white hover:shadow-lg hover:shadow-purple-500/25'
                          : 'bg-[#2A2A2A] text-[#888888] hover:bg-[#3A3A3A] hover:text-white'
                      }`}>
                        {selectedPlan?.id === plan.id ? 'Selected' : 'Select Plan'}
                      </button>
                    )}
                    
                    {plan.price === '0' && (
                      <div className="text-center py-2.5">
                        <span className="text-xs text-[#666666]">Current Plan</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Custom amount input - only show if enabled */}
            {showCustomAmount && (
              <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6 mb-6">
                <h3 className="text-lg font-semibold text-white mb-4">Custom Amount</h3>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={customAmount}
                    onChange={(e) => {
                      setCustomAmount(e.target.value);
                      if (e.target.value) {
                        setSelectedPlan(null);
                      }
                    }}
                    className="flex-1 px-4 py-2 bg-black border border-[#1A1A1A] rounded-lg text-white placeholder-[#888888] focus:outline-none focus:border-[#EDEDED] transition-colors"
                    placeholder="Enter custom amount"
                    step="0.01"
                    min="0.01"
                  />
                  <button
                    onClick={() => {
                      setCustomAmount('');
                      setSelectedPlan(pricingPlans[2]); // Reset to Plus plan
                    }}
                    className="px-4 py-2 text-[#888888] hover:text-white transition-colors"
                  >
                    Clear
                  </button>
                </div>
              </div>
            )}


            {/* Payment button */}
            <button
              onClick={createPaymentOrder}
              disabled={loading || (!selectedPlan && (!showCustomAmount || !customAmount))}
              className={`w-full py-4 rounded-xl font-medium text-lg transition-all flex items-center justify-center gap-2 ${
                loading || (!selectedPlan && (!showCustomAmount || !customAmount))
                  ? 'bg-[#1A1A1A] text-[#888888] cursor-not-allowed'
                  : 'bg-[#EDEDED] text-[#0A0A0A] hover:opacity-90 border-2 border-[#0A0A0A]'
              }`}
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[#0A0A0A]"></div>
                  Creating order...
                </>
              ) : (
                <>
                  <CreditCardIcon className="w-6 h-6" />
                  Pay Now ¥{customAmount || selectedPlan?.price || '0'}
                </>
              )}
            </button>
          </>
        ) : (
          // QR code payment interface
          <div className="max-w-md mx-auto">
            <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl overflow-hidden">
              {/* Payment header */}
              <div className="p-6 text-white bg-gradient-to-r from-purple-600/20 to-blue-500/20 border-b border-purple-500/20">
                <div className="flex items-center justify-between mb-4">
                  <button
                    onClick={handleCancelClick}
                    className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                  >
                    <ArrowLeftIcon className="w-5 h-5" />
                  </button>
                  <span className="font-medium">Payment</span>
                  <div className="w-9"></div>
                </div>
                
                <div className="text-center">
                  <p className="text-[#ADADAD] text-sm mb-2">Payment Amount</p>
                  <p className="text-4xl font-bold">¥{currentOrder.amount}</p>
                </div>
              </div>

              {/* QR code area */}
              <div className="p-8">
                {orderStatus === 'success' ? (
                  <div className="text-center py-12">
                    <CheckCircleIcon className="w-20 h-20 text-green-400 mx-auto mb-4" />
                    <p className="text-xl font-semibold text-white">Payment Successful</p>
                    <p className="text-[#888888] mt-2">Thank you for your subscription</p>
                  </div>
                ) : orderStatus === 'failed' ? (
                  <div className="text-center py-12">
                    <XCircleIcon className="w-20 h-20 text-red-400 mx-auto mb-4" />
                    <p className="text-xl font-semibold text-white">Payment Failed</p>
                    <p className="text-[#888888] mt-2">Please try again</p>
                  </div>
                ) : (
                  <>
                    <div className="bg-black border border-[#1A1A1A] rounded-xl p-4 mb-6">
                      {currentOrder.qrcode_url ? (
                        <div className="relative">
                          <Image
                            src={currentOrder.qrcode_url}
                            alt="Payment QR Code"
                            width={240}
                            height={240}
                            className="w-full max-w-[240px] mx-auto rounded-lg"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent rounded-lg pointer-events-none" />
                        </div>
                      ) : (
                        <div className="w-[240px] h-[240px] mx-auto bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                          <QrCodeIcon className="w-16 h-16 text-[#888888]" />
                        </div>
                      )}
                    </div>

                    <div className="text-center space-y-3">
                      <p className="text-white font-medium">
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
                <div className="px-6 pb-6 space-y-3">
                  {currentOrder.payment_url && (
                    <a
                      href={currentOrder.payment_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full py-3 bg-[#1A1A1A] hover:bg-[#2A2A2A] text-[#EDEDED] rounded-lg transition-colors text-center font-medium border border-[#2A2A2A]"
                    >
                      Open Payment Page
                    </a>
                  )}
                  
                  <button
                    onClick={handleCancelClick}
                    className="w-full py-3 text-[#888888] hover:text-white transition-colors"
                  >
                    Cancel Payment
                  </button>
                </div>
              )}
            </div>

            {/* Order info */}
            <div className="mt-4 text-center text-sm text-[#888888]">
              Order ID: {currentOrder.order_id}
            </div>
          </div>
        )}
        </div>
      </div>
      
      {/* Cancel Confirmation Modal */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setShowCancelConfirm(false)}
          />
          
          {/* Modal */}
          <div className="relative bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl p-6 max-w-sm mx-4">
            <div className="text-center">
              {/* Warning Icon */}
              <div className="mx-auto w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              
              <h3 className="text-xl font-semibold text-white mb-2">
                Cancel Payment?
              </h3>
              <p className="text-[#888888] mb-6">
                Are you sure you want to cancel this payment? You will need to create a new order to continue.
              </p>
              
              {/* Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="flex-1 py-2 px-4 bg-[#1A1A1A] text-white rounded-lg hover:bg-[#2A2A2A] transition-colors"
                >
                  Continue Payment
                </button>
                <button
                  onClick={cancelOrder}
                  className="flex-1 py-2 px-4 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition-colors font-medium"
                >
                  Yes, Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
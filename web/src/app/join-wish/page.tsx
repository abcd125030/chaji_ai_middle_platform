'use client';

import { useState } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import TopBar from '@/components/ui/TopBar';
import { 
  SparklesIcon,
  CheckCircleIcon,
  UserIcon,
  EnvelopeIcon,
  BuildingOfficeIcon,
  ChatBubbleBottomCenterTextIcon,
  ArrowRightIcon
} from '@heroicons/react/24/outline';

interface FormData {
  name: string;
  email: string;
  company: string;
  role: string;
  interest: string;
  message: string;
}

export default function JoinWishPage() {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    email: '',
    company: '',
    role: '',
    interest: '',
    message: ''
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const interestOptions = [
    'AI Assistant Integration',
    'Enterprise Solutions',
    'API Access',
    'Custom Development',
    'Partnership',
    'Other'
  ];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.name || !formData.email || !formData.interest) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    // Basic email validation
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(formData.email)) {
      toast.error('Please enter a valid email address');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // 调用后端API
      const response = await fetch('/api/auth/join-wish/submit/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth') ? JSON.parse(localStorage.getItem('auth') || '{}').access : ''}`
        },
        body: JSON.stringify(formData)
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        setIsSuccess(true);
        toast.success(data.message || 'Thank you for your interest! We will contact you soon.');
      } else if (data.status === 'info') {
        // 账号已激活
        toast(data.message, {
          icon: 'ℹ️',
          duration: 4000,
        });
        setIsSubmitting(false);
        return;
      } else {
        throw new Error(data.message || 'Failed to submit');
      }
    } catch (error) {
      console.error('Submit error:', error);
      toast.error('Failed to submit. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNewSubmission = () => {
    setIsSuccess(false);
    setFormData({
      name: '',
      email: '',
      company: '',
      role: '',
      interest: '',
      message: ''
    });
  };

  return (
    <div className="min-h-screen bg-black flex flex-col">
      <Toaster position="top-center" />
      
      {/* TopBar */}
      <TopBar />
      
      {/* Animated background */}
      <div className="fixed inset-0 bg-black -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 via-transparent to-blue-900/10" />
        <div className="geometric-background opacity-20" />
      </div>
      
      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-2xl w-full">
          {!isSuccess ? (
            // Form Section
            <div className="bg-gray-900/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-800">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-r from-purple-500 to-blue-500 mb-4">
                  <SparklesIcon className="w-8 h-8 text-white" />
                </div>
                <h1 className="text-3xl font-bold text-white mb-2">Join the Wishlist</h1>
                <p className="text-gray-400">Be the first to experience our AI platform</p>
              </div>
              
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Name Field */}
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
                      <UserIcon className="inline w-4 h-4 mr-1" />
                      Name *
                    </label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      value={formData.name}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      placeholder="Your name"
                      required
                    />
                  </div>
                  
                  {/* Email Field */}
                  <div>
                    <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                      <EnvelopeIcon className="inline w-4 h-4 mr-1" />
                      Email *
                    </label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      placeholder="your@email.com"
                      required
                    />
                  </div>
                  
                  {/* Company Field */}
                  <div>
                    <label htmlFor="company" className="block text-sm font-medium text-gray-300 mb-2">
                      <BuildingOfficeIcon className="inline w-4 h-4 mr-1" />
                      Company
                    </label>
                    <input
                      type="text"
                      id="company"
                      name="company"
                      value={formData.company}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      placeholder="Your company (optional)"
                    />
                  </div>
                  
                  {/* Role Field */}
                  <div>
                    <label htmlFor="role" className="block text-sm font-medium text-gray-300 mb-2">
                      Role
                    </label>
                    <input
                      type="text"
                      id="role"
                      name="role"
                      value={formData.role}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      placeholder="Your role (optional)"
                    />
                  </div>
                </div>
                
                {/* Interest Field */}
                <div>
                  <label htmlFor="interest" className="block text-sm font-medium text-gray-300 mb-2">
                    <SparklesIcon className="inline w-4 h-4 mr-1" />
                    What are you interested in? *
                  </label>
                  <select
                    id="interest"
                    name="interest"
                    value={formData.interest}
                    onChange={handleInputChange}
                    className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    required
                  >
                    <option value="">Select an option</option>
                    {interestOptions.map(option => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
                
                {/* Message Field */}
                <div>
                  <label htmlFor="message" className="block text-sm font-medium text-gray-300 mb-2">
                    <ChatBubbleBottomCenterTextIcon className="inline w-4 h-4 mr-1" />
                    Message
                  </label>
                  <textarea
                    id="message"
                    name="message"
                    value={formData.message}
                    onChange={handleInputChange}
                    rows={4}
                    className="w-full px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                    placeholder="Tell us more about your needs (optional)"
                  />
                </div>
                
                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3 px-6 bg-gradient-to-r from-purple-500 to-blue-500 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center"
                >
                  {isSubmitting ? (
                    <>
                      <svg className="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Submitting...
                    </>
                  ) : (
                    <>
                      Join Waitlist
                      <ArrowRightIcon className="w-5 h-5 ml-2" />
                    </>
                  )}
                </button>
              </form>
            </div>
          ) : (
            // Success Section
            <div className="bg-gray-900/50 backdrop-blur-xl rounded-2xl p-12 border border-gray-800 text-center">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-500/20 mb-6">
                <CheckCircleIcon className="w-12 h-12 text-green-500" />
              </div>
              
              <h2 className="text-3xl font-bold text-white mb-4">Welcome Aboard!</h2>
              <p className="text-gray-300 mb-8 max-w-md mx-auto">
                Thank you for joining our wishlist. We&apos;re excited to have you as an early adopter.
                We&apos;ll contact you at <span className="text-purple-400 font-medium">{formData.email}</span> as soon as we&apos;re ready.
              </p>
              
              <div className="space-y-4">
                <div className="bg-gray-800/50 rounded-lg p-4 text-left max-w-md mx-auto">
                  <h3 className="text-white font-semibold mb-2">What happens next?</h3>
                  <ul className="text-gray-400 text-sm space-y-1">
                    <li>• You&apos;ll receive a confirmation email shortly</li>
                    <li>• We&apos;ll notify you when early access is available</li>
                    <li>• You&apos;ll get exclusive updates and insights</li>
                    <li>• Early access to new features and capabilities</li>
                  </ul>
                </div>
                
                <button
                  onClick={handleNewSubmission}
                  className="mt-6 px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white font-medium rounded-lg transition-colors duration-200"
                >
                  Submit Another Request
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
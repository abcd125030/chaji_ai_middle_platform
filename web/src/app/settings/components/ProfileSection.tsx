'use client';

import React, { useState, KeyboardEvent, useEffect } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { authFetch } from '@/lib/auth-fetch';

interface ProfileSectionProps {
  isMobile?: boolean;
}

const ProfileSection: React.FC<ProfileSectionProps> = ({ isMobile = false }) => {
  const [agenticName, setAgenticName] = useState('');
  const [userPreference, setUserPreference] = useState('');
  const [domainTags, setDomainTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [occupation, setOccupation] = useState('');
  const [industry, setIndustry] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [activationCode, setActivationCode] = useState('');
  const [isActivating, setIsActivating] = useState(false);
  const [activatedFeatures, setActivatedFeatures] = useState<Array<{ name: string; expiry?: string }>>([]);

  // Industry options from backend UserProfile model
  const industryOptions = [
    { value: '', label: 'Select Industry' },
    { value: 'technology', label: 'Technology' },
    { value: 'finance', label: 'Finance' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'education', label: 'Education' },
    { value: 'retail', label: 'Retail' },
    { value: 'manufacturing', label: 'Manufacturing' },
    { value: 'real_estate', label: 'Real Estate' },
    { value: 'hospitality', label: 'Hospitality' },
    { value: 'transportation', label: 'Transportation' },
    { value: 'energy', label: 'Energy' },
    { value: 'media', label: 'Media & Entertainment' },
    { value: 'telecommunications', label: 'Telecommunications' },
    { value: 'agriculture', label: 'Agriculture' },
    { value: 'construction', label: 'Construction' },
    { value: 'government', label: 'Government' },
    { value: 'non_profit', label: 'Non-Profit' },
    { value: 'consulting', label: 'Consulting' },
    { value: 'legal', label: 'Legal' },
    { value: 'insurance', label: 'Insurance' },
    { value: 'pharmaceutical', label: 'Pharmaceutical' },
    { value: 'automotive', label: 'Automotive' },
    { value: 'aerospace', label: 'Aerospace & Defense' },
    { value: 'logistics', label: 'Logistics & Supply Chain' },
    { value: 'e_commerce', label: 'E-Commerce' },
    { value: 'other', label: 'Other' },
  ];

  // Tag colors for visual variety
  const tagColors = [
    'bg-blue-100 text-blue-700 border-blue-200',
    'bg-green-100 text-green-700 border-green-200',
    'bg-purple-100 text-purple-700 border-purple-200',
    'bg-yellow-100 text-yellow-700 border-yellow-200',
    'bg-pink-100 text-pink-700 border-pink-200',
    'bg-indigo-100 text-indigo-700 border-indigo-200',
  ];

  const handleTagKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && tagInput.trim()) {
      e.preventDefault();
      if (domainTags.length < 6) {
        if (!domainTags.includes(tagInput.trim())) {
          setDomainTags([...domainTags, tagInput.trim()]);
          setTagInput('');
        } else {
          toast.error('This tag already exists');
        }
      } else {
        toast.error('Maximum 6 tags allowed');
      }
    }
  };

  const removeTag = (indexToRemove: number) => {
    setDomainTags(domainTags.filter((_, index) => index !== indexToRemove));
  };

  const handleSave = async () => {
    if (!agenticName.trim()) {
      toast.error('Name is required');
      return;
    }

    setIsSaving(true);
    try {
      // TODO: Implement actual save logic to backend
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call
      toast.success('Settings saved successfully');
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleActivateCode = async () => {
    if (!activationCode.trim()) {
      toast.error('请输入激活码');
      return;
    }

    setIsActivating(true);
    try {
      const response = await authFetch('/api/activation/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: activationCode.trim() }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        toast.success(data.message || '激活成功');
        setActivatedFeatures(data.data?.features || []);
        setActivationCode('');
        // 可选：刷新用户权限或功能状态
        fetchActivatedFeatures();
      } else {
        toast.error(data.message || '激活码无效');
      }
    } catch {
      toast.error('激活失败，请稍后重试');
    } finally {
      setIsActivating(false);
    }
  };

  // 获取已激活的功能列表
  const fetchActivatedFeatures = async () => {
    try {
      const response = await authFetch('/api/activation/features', {
        method: 'GET',
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          setActivatedFeatures(data.data?.features || []);
        }
      }
    } catch (error) {
      console.error('Failed to fetch activated features:', error);
    }
  };

  const getCharCount = (text: string) => {
    return { total: text.length, words: text.split(/\s+/).filter(Boolean).length };
  };

  const charCount = getCharCount(userPreference);

  // 组件加载时获取已激活的功能
  useEffect(() => {
    fetchActivatedFeatures();
  }, []);

  // Mobile-optimized layout
  if (isMobile) {
    return (
      <div>
        <div className="space-y-6">
          {/* Mobile Form Cards */}
          <div className="bg-[var(--accent)] rounded-2xl p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--foreground)] mb-3 uppercase tracking-wider">基本信息</h3>
            
            {/* Name Field */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
                姓名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={agenticName}
                onChange={(e) => setAgenticName(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="请输入您的姓名"
                required
              />
            </div>

            {/* Occupation Field */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
                职业
              </label>
              <input
                type="text"
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="如：软件工程师、产品经理"
              />
            </div>

            {/* Industry Field */}
            <div>
              <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
                行业
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {industryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Preferences Card */}
          <div className="bg-[var(--accent)] rounded-2xl p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--foreground)] mb-3 uppercase tracking-wider">偏好设置</h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
                个人偏好
              </label>
              <textarea
                value={userPreference}
                onChange={(e) => {
                  const count = getCharCount(e.target.value);
                  if (count.words <= 300) {
                    setUserPreference(e.target.value);
                  }
                }}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                placeholder="描述您的偏好和兴趣"
                rows={3}
              />
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                {charCount.words}/300 字
              </p>
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium text-[var(--foreground)] mb-1">
                标签
              </label>
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagKeyDown}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="输入后按回车添加标签"
                disabled={domainTags.length >= 6}
              />
              <div className="flex flex-wrap gap-2 mt-2">
                {domainTags.map((tag, index) => (
                  <span
                    key={index}
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${tagColors[index % tagColors.length]}`}
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(index)}
                      className="ml-2"
                    >
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Activation Code Card */}
          <div className="bg-[var(--accent)] rounded-2xl p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--foreground)] mb-3 uppercase tracking-wider">激活码</h3>
            
            <div className="flex gap-2">
              <input
                type="text"
                value={activationCode}
                onChange={(e) => setActivationCode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleActivateCode();
                  }
                }}
                className="flex-1 px-3 py-2 bg-[var(--background)] rounded-lg text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="输入激活码"
                disabled={isActivating}
              />
              <button
                onClick={handleActivateCode}
                disabled={isActivating || !activationCode.trim()}
                className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg font-medium disabled:opacity-50"
              >
                {isActivating ? '验证中' : '激活'}
              </button>
            </div>
            
            {activatedFeatures.length > 0 && (
              <div className="mt-3 p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-2">
                  已激活功能：
                </p>
                <div className="flex flex-wrap gap-2">
                  {activatedFeatures.map((feature, index) => (
                    <span key={index} className="px-2 py-1 bg-green-100 dark:bg-green-800/30 text-green-700 dark:text-green-300 rounded text-xs">
                      {feature.name}
                      {feature.expiry && (
                        <span className="ml-1 opacity-75">
                          ({new Date(feature.expiry).toLocaleDateString('zh-CN')})
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Save Button */}
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full py-3 bg-[var(--foreground)] text-[var(--background)] rounded-full font-semibold text-base transition-all hover:scale-[1.02] disabled:opacity-50"
          >
            {isSaving ? '保存中...' : '保存设置'}
          </button>
        </div>
      </div>
    );
  }

  // Desktop layout (original)
  return (
    <div>
      <h2 className="text-2xl font-semibold text-[var(--foreground)] mb-3">
        Profile Settings
      </h2>
      <p className="text-sm text-[var(--muted-foreground)] mb-6 leading-relaxed">
        Your profile information helps your AI assistant understand who you are and personalize its responses. 
        When agentic running, your assistant will use this context to provide more relevant and tailored assistance based on your background, preferences, and expertise.
      </p>
      <div className="bg-[var(--accent)] rounded-lg p-8">
        <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
          {/* Your Name Field */}
          <div className="flex items-start">
            <label htmlFor="agenticName" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
              Your Name <span className="text-red-500">*</span>
            </label>
            <div className="flex-1">
              <input
                type="text"
                id="agenticName"
                value={agenticName}
                onChange={(e) => setAgenticName(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                placeholder="Enter your name"
                required
              />
            </div>
          </div>

          {/* Occupation Field */}
          <div className="flex items-start">
            <label htmlFor="occupation" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
              Your Occupation
            </label>
            <div className="flex-1">
              <input
                type="text"
                id="occupation"
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                placeholder="e.g. Software Engineer, Product Manager, Designer"
              />
            </div>
          </div>

          {/* Industry Field */}
          <div className="flex items-start">
            <label htmlFor="industry" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
              Your Industry
            </label>
            <div className="flex-1">
              <select
                id="industry"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
              >
                {industryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* User Preference Field */}
          <div className="flex items-start">
            <label htmlFor="userPreference" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
              Your Preferences
            </label>
            <div className="flex-1">
              <textarea
                id="userPreference"
                value={userPreference}
                onChange={(e) => {
                  const count = getCharCount(e.target.value);
                  if (count.words <= 300) {
                    setUserPreference(e.target.value);
                  }
                }}
                className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all resize-none"
                placeholder="Describe your preferences and interests (optional)"
                rows={4}
              />
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                {charCount.words} words (Max: 300 words)
              </p>
            </div>
          </div>

          {/* Personal Tags Field */}
          <div className="flex items-start">
            <label htmlFor="domainTags" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
              Your Tags
            </label>
            <div className="flex-1">
              <div className="mb-2">
                <input
                  type="text"
                  id="domainTags"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                  placeholder="Type and press Enter to add tags (max 6)"
                  disabled={domainTags.length >= 6}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {domainTags.map((tag, index) => (
                  <span
                    key={index}
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${tagColors[index % tagColors.length]}`}
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(index)}
                      className="ml-2 hover:opacity-75"
                    >
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
              {domainTags.length > 0 && (
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                  {domainTags.length}/6 tags
                </p>
              )}
            </div>
          </div>

          {/* Activation Code Section */}
          <div className="border-t border-[var(--border)] pt-6 mt-8">
            <div className="flex items-start">
              <label htmlFor="activationCode" className="w-40 text-right pr-4 pt-2 text-sm font-medium text-[var(--foreground)]">
                激活码
              </label>
              <div className="flex-1">
                <div className="flex gap-3">
                  <input
                    type="text"
                    id="activationCode"
                    value={activationCode}
                    onChange={(e) => setActivationCode(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleActivateCode();
                      }
                    }}
                    className="flex-1 px-3 py-2 bg-[var(--background)] rounded-md text-[var(--foreground)] focus:outline-none transition-all"
                    placeholder="输入激活码以解锁功能"
                    disabled={isActivating}
                  />
                  <button
                    type="button"
                    onClick={handleActivateCode}
                    disabled={isActivating || !activationCode.trim()}
                    className="px-6 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-md font-medium transition-all hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isActivating ? '验证中...' : '激活'}
                  </button>
                </div>
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                  输入激活码以解锁专属功能和权限
                </p>
                
                {/* Activated Features Display */}
                {activatedFeatures.length > 0 && (
                  <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-md">
                    <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-2">
                      已激活功能：
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {activatedFeatures.map((feature, index) => (
                        <div key={index} className="flex items-center gap-1">
                          <span className="px-2 py-1 bg-green-100 dark:bg-green-800/30 text-green-700 dark:text-green-300 rounded text-xs">
                            {feature.name}
                          </span>
                          {feature.expiry && (
                            <span className="text-xs text-green-600 dark:text-green-400">
                              (到期: {new Date(feature.expiry).toLocaleDateString('zh-CN')})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-center pt-4">
            <button
              type="submit"
              disabled={isSaving}
              className="px-8 py-3 bg-[var(--foreground)] text-[var(--background)] rounded-full font-semibold text-base transition-all hover:scale-105 hover:shadow-[0_10px_20px_rgba(0,0,0,0.15)] focus:outline-none focus:ring-2 focus:ring-[var(--foreground)] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProfileSection;
'use client';

import { useEffect, useState, useRef } from 'react';
import { getRandomTips, ConversationTip } from '@/data/conversation-tips';

export default function ConversationTips() {
  const [tips, setTips] = useState<ConversationTip[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Initialize with 5 unique tips
    const initialTips = getRandomTips(5);
    setTips(initialTips);
    setIsVisible(true);
    
    // Set timer to switch every 5 seconds
    intervalRef.current = setInterval(() => {
      switchToNextTip();
    }, 6000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const switchToNextTip = () => {
    // Fade out first
    setFadeOut(true);
    
    setTimeout(() => {
      setCurrentIndex(prev => {
        // Cycle to next, if at end then get new set of 5 tips
        if (prev >= 4) {
          const newTips = getRandomTips(5);
          setTips(newTips);
          return 0;
        }
        return prev + 1;
      });
      setFadeOut(false);
      setIsVisible(true);
    }, 300);
  };

  if (tips.length === 0) return null;
  const currentTip = tips[currentIndex];

  return (
    <div className="flex flex-1 items-center justify-center px-8">
      <div className="max-w-xl">
        {/* Tip content container - elegant styling */}
        <div 
          className={`
            relative p-8 rounded-2xl bg-gradient-to-b from-[#050505] to-[#0a0a0a]
            backdrop-blur-sm shadow-2xl
            transition-all duration-300 ease-in-out
            ${isVisible && !fadeOut ? 'opacity-100 transform translate-y-0' : 'opacity-0 transform translate-y-2'}
          `}
          style={{
            boxShadow: '0 0 40px rgba(74, 106, 122, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.02)'
          }}
        >
          {/* Decorative quotation marks */}
          <div className="absolute left-6 top-6 text-2xl text-[var(--decor-primary)] opacity-15 select-none">
            &ldquo;
          </div>
          <div className="absolute right-6 bottom-6 text-2xl text-[var(--decor-primary)] opacity-15 select-none">
            &rdquo;
          </div>
          
          {/* Tip content - smaller font size */}
          <p className="text-xs md:text-sm text-[#ADADAD] leading-relaxed mb-6 px-4 text-center">
            {currentTip.content}
          </p>
          
          {/* Source label - right aligned */}
          <div className="flex items-center justify-end pr-2">
            <span className="text-sm text-[#888888] mr-2">——</span>
            <span className="text-base font-semibold text-[#EDEDED] tracking-wide">
              {currentTip.speaker}
            </span>
          </div>
        </div>
        
        {/* Progress indicator - 5 bars take turns being active */}
        <div className="mt-6 flex justify-center gap-2">
          {[...Array(5)].map((_, index) => (
            <div
              key={index}
              className={`
                h-1 rounded-full transition-all duration-300 overflow-hidden
                ${index === currentIndex ? 'w-8 bg-[var(--border)]' : 'w-8 bg-[var(--border)]'}
              `}
            >
              {index === currentIndex && (
                <div 
                  className="h-full bg-[var(--decor-hover)] rounded-full"
                  style={{
                    animation: 'progressFill 5s linear'
                  }}
                />
              )}
            </div>
          ))}
        </div>
      </div>
      
      <style jsx>{`
        @keyframes progressFill {
          from {
            width: 0%;
          }
          to {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
}
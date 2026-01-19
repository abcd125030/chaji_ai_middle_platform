'use client';

import { useState, useCallback } from 'react';
import SubscriptionModal from '@/components/ui/SubscriptionModal';

export function useSubscription() {
  const [isOpen, setIsOpen] = useState(false);
  const [onSuccessCallback, setOnSuccessCallback] = useState<(() => void) | null>(null);

  const openSubscription = useCallback((successCallback?: () => void) => {
    setIsOpen(true);
    if (successCallback) {
      setOnSuccessCallback(() => successCallback);
    }
  }, []);

  const closeSubscription = useCallback(() => {
    setIsOpen(false);
    setOnSuccessCallback(null);
  }, []);

  const handleSuccess = useCallback(() => {
    onSuccessCallback?.();
    closeSubscription();
    // Optionally refresh user data or permissions here
    window.location.reload();
  }, [onSuccessCallback, closeSubscription]);

  const SubscriptionComponent = () => (
    <SubscriptionModal
      isOpen={isOpen}
      onClose={closeSubscription}
      onSuccess={handleSuccess}
    />
  );

  return {
    openSubscription,
    closeSubscription,
    SubscriptionComponent,
    isOpen
  };
}
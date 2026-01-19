/**
 * Fullscreen control component - Tailwind version
 *
 * This component provides fullscreen toggle functionality for the code preview sandbox,
 * allowing users to enter or exit fullscreen mode.
 * The component renders as a button with a fullscreen icon that toggles fullscreen state when clicked.
 */
import React from 'react';
import { ArrowsPointingOutIcon, ArrowsPointingInIcon } from '@heroicons/react/24/outline';

/**
 * Properties interface for the fullscreen control component
 */
export interface FullscreenControlProps {
  isFullscreen: boolean; // Whether currently in fullscreen state
  onFullscreenChange: (isFullscreen: boolean) => void; // Callback function when fullscreen state changes
}

/**
 * Fullscreen control component
 *
 * @param props - Component properties
 * @param props.isFullscreen - Whether currently in fullscreen state
 * @param props.onFullscreenChange - Callback function when fullscreen state changes
 * @returns Returns the fullscreen control button component
 */
export default function FullscreenControl({
  isFullscreen,
  onFullscreenChange,
}: FullscreenControlProps) {
  /**
   * Handle fullscreen state toggle
   * Based on current fullscreen state, call appropriate browser APIs to enter or exit fullscreen mode
   */
  const handleFullscreenToggle = () => {
    // Get preview container element
    const container = document.getElementById('preview-container');
    if (!container) return;

    if (!isFullscreen) {
      // If currently not fullscreen, request to enter fullscreen mode
      if (container.requestFullscreen) {
        container.requestFullscreen();
      }
    } else {
      // If currently fullscreen, request to exit fullscreen mode
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    // Call callback function to notify parent component that fullscreen state has changed
    onFullscreenChange(!isFullscreen);
  };

  // Render fullscreen control button
  return (
    <button
      onClick={handleFullscreenToggle}
      title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
      className={`
        w-8 h-8 p-1.5
        flex items-center justify-center
        rounded
        pointer-events-auto
        transition-all duration-200 ease-in-out
        bg-transparent hover:bg-black/10 dark:hover:bg-white/10
        ${isFullscreen 
          ? 'text-blue-600 dark:text-blue-400' 
          : 'text-gray-600 dark:text-gray-400'}
        hover:text-black dark:hover:text-white
      `}
    >
      {isFullscreen ? (
        <ArrowsPointingInIcon className="w-4 h-4" />
      ) : (
        <ArrowsPointingOutIcon className="w-4 h-4" />
      )}
    </button>
  );
}
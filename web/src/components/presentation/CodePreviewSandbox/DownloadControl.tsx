/**
 * Download control button component - Tailwind version
 *
 * This component provides a download icon button used to trigger download operations.
 * Designed to integrate with the CodePreviewSandbox environment, following the same theme and visual design.
 */
import React from 'react';
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline';

/**
 * Properties interface for the download control button
 */
export interface DownloadControlProps {
  onClick: () => void; // Callback function triggered when button is clicked
  title?: string; // Button tooltip text (displayed on hover)
}

/**
 * Download control button component
 *
 * @param props - Component properties
 * @param props.onClick - Callback function triggered when button is clicked, typically used to handle download logic
 * @param props.title - Button tooltip text, defaults to "Download Image"
 * @returns React component
 */
export default function DownloadControl({
  onClick,
  title = 'Download Image', // Default tooltip text
}: DownloadControlProps) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="
        w-8 h-8 p-1.5
        flex items-center justify-center
        rounded
        pointer-events-auto
        transition-all duration-200 ease-in-out
        bg-transparent hover:bg-black/10 dark:hover:bg-white/10
        text-gray-600 dark:text-gray-400
        hover:text-black dark:hover:text-white
      "
    >
      <ArrowDownTrayIcon className="w-4 h-4" />
    </button>
  );
}
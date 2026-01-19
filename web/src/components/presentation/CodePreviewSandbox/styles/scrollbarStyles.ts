export const scrollbarStyles = `
  /* WebKit Scrollbar Styles (e.g., Chrome, Safari, Edge) */
  ::-webkit-scrollbar {
    width: 3px; /* Controlled by --scrollbar-width variable, to be set to 3px */
    height: 3px; /* For horizontal scrollbars */
    background-color: transparent; /* Explicitly set track background here if not in ::-webkit-scrollbar-track */
  }
  
  ::-webkit-scrollbar-track {
    background-color: transparent; /* Track color */
  }

  ::-webkit-scrollbar-thumb {
    background-color: rgba(205, 0, 0, 0.65); /* Thumb color from theme's highlight */
    border-radius: 3px; /* Make it fully rounded based on width */
    transition: background-color 0.2s ease;
  }
  
  ::-webkit-scrollbar-thumb:hover {
    background-color: rgba(205, 0, 0, 0.85); /* Hover color from theme */
  }

  ::-webkit-scrollbar-button {
    display: none; /* Hide scrollbar arrows */
  }
`;

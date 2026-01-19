// public/sandbox/editModeScript.js
(function() {

  // --- CSS Injection ---
  function injectCSS(cssContent) {
    const styleElement = document.createElement('style');
    styleElement.type = 'text/css';
    styleElement.textContent = cssContent;
    document.head.appendChild(styleElement);
  }

  // CSS content obtained from editModeStyle.css
  const css = `
/* public/sandbox/editModeStyle.css */

/* --- Base Menu Styling (Inspired by MUI Paper/Popover) --- */
.edit-mode-style-menu {
    position: absolute;
    z-index: 10000;
    background-color: #ffffff; /* White background */
    color: rgba(0, 0, 0, 0.87); /* Default text color */
    border-radius: 8px; /* Rounded corners */
    box-shadow: 0px 5px 5px -3px rgba(0,0,0,0.2),
                0px 8px 10px 1px rgba(0,0,0,0.14),
                0px 3px 14px 2px rgba(0,0,0,0.12); /* MUI elevation 8 */
    padding: 8px; /* Padding around buttons */
    display: none; /* Initially hidden */
    font-family: "Roboto", "Helvetica", "Arial", sans-serif; /* MUI default font */
    font-size: 0.875rem; /* 14px */
    white-space: nowrap; /* Prevent buttons wrapping */
    transition: opacity 0.2s ease-in-out, transform 0.2s ease-in-out; /* Smooth transition */
    opacity: 0; /* Start transparent for fade-in */
    transform: scale(0.95); /* Start slightly smaller for pop effect */
}

.edit-mode-style-menu.visible {
    display: block;
    opacity: 1;
    transform: scale(1);
}


/* --- Button Styling (Inspired by MUI Button) --- */
.edit-mode-style-menu button {
    min-width: 64px;
    padding: 5px 15px; /* Vertical and horizontal padding */
    margin: 4px; /* Spacing between buttons */
    font-family: "Roboto", "Helvetica", "Arial", sans-serif;
    font-size: 0.875rem; /* 14px */
    font-weight: 500; /* Medium weight */
    line-height: 1.75;
    letter-spacing: 0.02857em;
    text-transform: uppercase; /* Uppercase text */
    color: #1976d2; /* Primary color (blue) */
    background-color: transparent; /* Transparent background */
    border: 1px solid rgba(25, 118, 210, 0.5); /* Primary border, semi-transparent */
    border-radius: 4px; /* Rounded corners */
    cursor: pointer;
    transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
    outline: none; /* Remove default outline */
}

.edit-mode-style-menu button:hover {
    background-color: rgba(25, 118, 210, 0.04); /* Light blue background on hover */
    border-color: #1976d2; /* Solid primary border on hover */
}

.edit-mode-style-menu button:active {
    background-color: rgba(25, 118, 210, 0.12); /* Darker blue background when active */
    box-shadow: 0px 2px 4px -1px rgba(0,0,0,0.2),
                0px 4px 5px 0px rgba(0,0,0,0.14),
                0px 1px 10px 0px rgba(0,0,0,0.12); /* Add subtle shadow when active */
}

/* --- Custom Replace Dialog Styling --- */
.edit-mode-replace-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5); /* Semi-transparent backdrop */
    z-index: 10001; /* Above menu */
    display: flex;
    justify-content: center;
    align-items: center;
    opacity: 0;
    transition: opacity 0.2s ease-in-out;
}

.edit-mode-replace-dialog-overlay.visible {
    opacity: 1;
}

.edit-mode-replace-dialog {
    background-color: #ffffff;
    padding: 16px; /* Further reduced padding */
    border-radius: 8px; /* Further adjusted radius */
    box-shadow: 0px 6px 15px rgba(0,0,0,0.12); /* Adjusted shadow */
    min-width: 300px; /* Adjusted min-width */
    max-width: 500px;
    font-family: "Roboto", "Helvetica", "Arial", sans-serif;
    transform: scale(0.95);
    transition: transform 0.2s ease-in-out;
}

.edit-mode-replace-dialog-overlay.visible .edit-mode-replace-dialog {
     transform: scale(1);
}


.edit-mode-replace-dialog h3 {
    margin-top: 0;
    margin-bottom: 12px; /* Reduced margin */
    font-size: 1.15rem; /* Slightly smaller */
    font-weight: 500;
    line-height: 1.5;
    letter-spacing: 0.0075em;
    color: rgba(0, 0, 0, 0.87);
}

.edit-mode-replace-dialog .original-text {
    font-size: 0.875rem;
    color: rgba(0, 0, 0, 0.6);
    margin-bottom: 10px; /* Reduced margin */
    padding: 6px 8px; /* Reduced padding */
    background-color: rgba(0, 0, 0, 0.05);
    border-radius: 4px;
    max-height: 100px;
    overflow-y: auto;
    word-break: break-word;
}

.edit-mode-replace-dialog label {
    display: block;
    font-size: 0.75rem;
    color: rgba(0, 0, 0, 0.6);
    margin-bottom: 2px; /* Reduced margin */
}

.edit-mode-replace-dialog textarea {
    width: 100%;
    padding: 8px 10px; /* Further reduced padding */
    border: 1px solid #d0d0d0;
    border-radius: 4px; /* Adjusted radius */
    font-size: 1rem;
    font-family: inherit;
    color: rgba(0, 0, 0, 0.87); /* Ensure text is dark for visibility */
    min-height: 80px;
    box-sizing: border-box;
    margin-bottom: 10px; /* Further reduced margin */
    resize: vertical;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.edit-mode-replace-dialog textarea:focus {
    outline: none;
    border-color: #1976d2;
    box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2); /* Softer focus ring */
}

.edit-mode-replace-dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px; /* Further reduced gap */
}

/* Modernized Dialog Action Button Styles */
.edit-mode-replace-dialog-actions button {
    min-width: 80px;
    padding: 8px 18px; /* Adjusted padding */
    margin: 0; /* Remove margin if gap is used */
    font-family: "Roboto", "Helvetica", "Arial", sans-serif;
    font-size: 0.875rem; /* 14px */
    font-weight: 500;
    line-height: 1.75;
    letter-spacing: 0.02em;
    text-transform: none; /* Use normal case */
    border-radius: 6px; /* Consistent radius */
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
    outline: none;
    border: 1px solid transparent; /* Base border */
}

/* Specific style for Cancel button (Outlined) */
.edit-mode-replace-dialog-actions button.cancel {
    color: #555; /* Dark grey text */
    background-color: transparent;
    border-color: #ccc; /* Light grey border */
}

.edit-mode-replace-dialog-actions button.cancel:hover {
    background-color: rgba(0, 0, 0, 0.04); /* Subtle grey background on hover */
    border-color: #aaa; /* Slightly darker border */
    color: #333;
}

.edit-mode-replace-dialog-actions button.cancel:active {
     background-color: rgba(0, 0, 0, 0.08);
}


/* Specific style for Confirm button (Solid) */
.edit-mode-replace-dialog-actions button.confirm {
    color: #ffffff;
    background-color: #1976d2; /* Primary blue */
    border-color: #1976d2;
    box-shadow: 0 2px 4px rgba(25, 118, 210, 0.2); /* Subtle shadow */
}

.edit-mode-replace-dialog-actions button.confirm:hover {
    background-color: #1565c0; /* Darker blue */
    border-color: #1565c0;
    box-shadow: 0 3px 6px rgba(21, 101, 192, 0.3); /* Enhanced shadow */
}

.edit-mode-replace-dialog-actions button.confirm:active {
    background-color: #115293; /* Even darker blue */
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}
`;
  injectCSS(css);

  // --- Configuration ---
  const TARGET_SELECTOR = '.slide-content-wrapper'; // Target area for text selection
  const MENU_ID = 'text-style-menu';
  // 注意：这些指令定义必须与后端保持一致
  const commandInstructions = {
    'replace': '将选中文本替换为新内容', // Base instruction for replace
  };

  // --- State ---
  let styleMenuElement = null;
  let currentSelectedText = '';
  let currentSelectionRange = null;

  // --- Menu Creation ---
  function createStyleMenu() {
    if (document.getElementById(MENU_ID)) {
      return document.getElementById(MENU_ID);
    }

    const menu = document.createElement('div');
    menu.id = MENU_ID;
    menu.className = 'edit-mode-style-menu'; // Apply base class

    Object.keys(commandInstructions).forEach(command => {
      const button = document.createElement('button');
      button.dataset.command = command;
      // Styles are now handled by CSS

      // More specific labels
      switch(command) {
          case 'replace': button.textContent = '修改文字'; break;
          default: button.textContent = command.charAt(0).toUpperCase() + command.slice(1);
      }

      menu.appendChild(button);
    });

    document.body.appendChild(menu);
    return menu;
  }

  // --- Menu Positioning and Visibility ---
  function positionAndShowMenu(menu, range) {
    if (!menu || !range) return;
    const rect = range.getBoundingClientRect();

    // Calculate initial position (above the end of selection)
    let top = window.scrollY + rect.top - menu.offsetHeight - 5;
    let left = window.scrollX + rect.left + (rect.width / 2) - (menu.offsetWidth / 2);

    // Adjust if menu goes off-screen top
    if (top < window.scrollY) {
        top = window.scrollY + rect.bottom + 5; // Move below selection
    }
    // Adjust if menu goes off-screen left
    if (left < window.scrollX) {
        left = window.scrollX + 5;
    }
    // Adjust if menu goes off-screen right
    if (left + menu.offsetWidth > window.scrollX + window.innerWidth) {
        left = window.scrollX + window.innerWidth - menu.offsetWidth - 5;
    }
     // Adjust if menu goes off-screen bottom (less likely if positioned above/below)
    if (top + menu.offsetHeight > window.scrollY + window.innerHeight) {
         // If it also didn't fit above, it might be a large selection or small screen.
         // We could try centering it vertically, but for now, just cap it.
         top = window.scrollY + window.innerHeight - menu.offsetHeight - 5;
    }

    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
    // Use class for visibility and transition
    menu.classList.add('visible');
  }

  function hideMenu(menu) {
    if (menu && menu.classList.contains('visible')) {
      menu.classList.remove('visible');
      // Optional: listen for transition end to set display: none if needed,
      // but opacity: 0 and pointer-events: none might suffice depending on CSS.
    }
    currentSelectedText = ''; // Clear selection when hiding
    currentSelectionRange = null;
  }

  // --- Selection Check ---
  function isSelectionInTargetArea(selection) {
    if (!selection || selection.rangeCount === 0) {
      return false;
    }
    const range = selection.getRangeAt(0);
    // Use range.startContainer or commonAncestorContainer depending on desired behavior
    const container = range.commonAncestorContainer;
    const targetElement = document.querySelector(TARGET_SELECTOR);

    if (!targetElement) {
        // Decide behavior: allow anywhere or restrict? Restricting seems safer.
        return false;
    }

    // Check if the selection's container is the target or inside the target
    const nodeToCheck = container.nodeType === Node.TEXT_NODE ? container.parentElement : container;
    return targetElement.contains(nodeToCheck);
  }

  // --- Event Listeners ---
  document.addEventListener('mouseup', (event) => {
    // Use setTimeout to allow potential click events on the menu to register first,
    // and to ensure selection state is finalized.
    setTimeout(() => {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        // Only show menu if selection is not empty and within the target area
        if (selectedText && isSelectionInTargetArea(selection)) {
            currentSelectedText = selectedText;
            currentSelectionRange = selection.getRangeAt(0).cloneRange(); // Store range
            if (!styleMenuElement) {
                styleMenuElement = createStyleMenu(); // Ensure menu exists
            }
            // Check if the mouseup event target is inside the menu itself
            if (styleMenuElement && !styleMenuElement.contains(event.target)) {
                 positionAndShowMenu(styleMenuElement, currentSelectionRange);
            } else if (!styleMenuElement) {
            }
        } else {
            // If mouseup is outside the menu and selection is lost or invalid, hide menu
            if (styleMenuElement && !styleMenuElement.contains(event.target)) {
                 hideMenu(styleMenuElement);
            }
        }
    }, 0);
  });

  document.addEventListener('mousedown', (event) => {
    // Hide menu if clicking outside of it, unless the click starts a new selection inside the target
    if (styleMenuElement && styleMenuElement.style.display !== 'none' && !styleMenuElement.contains(event.target)) {
        const selection = window.getSelection();
        // Check if the click target is within the allowed editing area
        const targetElement = document.querySelector(TARGET_SELECTOR);
        const isClickInTarget = targetElement && targetElement.contains(event.target);

        // Hide immediately if click is outside target area.
        // If inside, the mouseup listener will handle showing/hiding based on selection result.
        if (!isClickInTarget) {
             hideMenu(styleMenuElement);
        }
    }
  });

  // --- Custom Replace Dialog ---
  function showReplaceDialog(originalText, callback) {
    // Remove existing dialog if any
    const existingDialog = document.getElementById('edit-mode-replace-dialog-overlay');
    if (existingDialog) {
        existingDialog.remove();
    }

    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'edit-mode-replace-dialog-overlay';
    overlay.className = 'edit-mode-replace-dialog-overlay'; // Initially hidden by CSS (opacity 0)

    // Create dialog box
    const dialog = document.createElement('div');
    dialog.className = 'edit-mode-replace-dialog';

    // Title
    const title = document.createElement('h3');
    title.textContent = '替换文本';
    dialog.appendChild(title);

    // Original text display
    const originalTextDiv = document.createElement('div');
    originalTextDiv.className = 'original-text';
    originalTextDiv.textContent = `原文: ${originalText}`;
    dialog.appendChild(originalTextDiv);

    // Input Label
    const label = document.createElement('label');
    label.htmlFor = 'edit-mode-replace-input';
    label.textContent = '替换为:';
    dialog.appendChild(label);

    // Input Textarea
    const textarea = document.createElement('textarea');
    textarea.id = 'edit-mode-replace-input';
    textarea.value = originalText; // Pre-fill with original text
    dialog.appendChild(textarea);

    // Action Buttons Container
    const actions = document.createElement('div');
    actions.className = 'edit-mode-replace-dialog-actions';

    // Cancel Button
    const cancelButton = document.createElement('button');
    cancelButton.textContent = '取消';
    cancelButton.className = 'cancel'; // Apply cancel style
    cancelButton.onclick = () => {
        overlay.classList.remove('visible');
        // Remove after transition
        setTimeout(() => overlay.remove(), 200); // Match CSS transition duration
        callback(null); // Indicate cancellation
    };
    actions.appendChild(cancelButton);

    // Confirm Button
    const confirmButton = document.createElement('button');
    confirmButton.textContent = '确认';
    confirmButton.className = 'confirm'; // Apply confirm style
    confirmButton.onclick = () => {
        const newText = textarea.value;
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
        callback(newText); // Pass the new text
    };
    actions.appendChild(confirmButton);

    dialog.appendChild(actions);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Trigger visibility transition
    requestAnimationFrame(() => {
        overlay.classList.add('visible');
        textarea.focus(); // Focus the input field
        textarea.select(); // Select the pre-filled text
    });

     // Allow closing with Escape key
    const escapeKeyListener = (event) => {
        if (event.key === 'Escape') {
            cancelButton.click();
            document.removeEventListener('keydown', escapeKeyListener); // Clean up listener
        }
    };
    document.addEventListener('keydown', escapeKeyListener);

    // Ensure listener is removed if dialog is closed by button click
    const originalCancelClick = cancelButton.onclick;
    cancelButton.onclick = () => {
        originalCancelClick();
        document.removeEventListener('keydown', escapeKeyListener);
    };
    const originalConfirmClick = confirmButton.onclick;
    confirmButton.onclick = () => {
        originalConfirmClick();
        document.removeEventListener('keydown', escapeKeyListener);
    };
  }


  // --- Menu Interaction ---
  function handleMenuClick(event) {
    const button = event.target.closest('button[data-command]');
    if (button && styleMenuElement && styleMenuElement.contains(button)) {
      const command = button.dataset.command;
      const selectedTextToSend = currentSelectedText;

      if (!selectedTextToSend) {
        hideMenu(styleMenuElement);
        return;
      }

      // Hide the main menu immediately when an action starts
      hideMenu(styleMenuElement);

      if (command === 'replace') {
        showReplaceDialog(selectedTextToSend, (newText) => {
          // This callback is executed when the dialog is closed (Confirm or Cancel)
          if (newText !== null) { // User confirmed (null means cancelled)
            const payload = {
              selectedText: selectedTextToSend,
              action: command,
              newText: newText, // Use the text from the dialog
            };
            window.parent.postMessage({
              type: 'requestTextModification',
              payload
            }, '*'); // IMPORTANT: Replace '*' with the specific origin
          } else {
          }
        });
      } else {
        // Handle other commands directly if needed
        // Example for other commands (if any were added)
        /*
        const payload = {
          selectedText: selectedTextToSend,
          action: command,
        };
        window.parent.postMessage({
          type: 'requestTextModification',
          payload
        }, '*');
        */
      }
      // Note: Menu is already hidden at the start of the interaction
    }
  }

  // --- Initialization ---
  // Create the menu element on script load
  styleMenuElement = createStyleMenu();
  if (styleMenuElement) {
      // Use event delegation on the menu for clicks
      styleMenuElement.addEventListener('click', handleMenuClick);
  } else {
  }

})();
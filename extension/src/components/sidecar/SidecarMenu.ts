/**
 * SidecarMenu Component
 * 
 * Hamburger menu with settings and secondary features.
 * Includes notifications toggle, privacy mode, theme and density selection.
 * Uses centralized theme system for consistency with Mini.
 */

import { PrivacyMode } from '../../services/personalization';
import * as ToastManager from '../../services/toastManager';
import { 
  THEME_LIST, 
  DENSITY_LIST,
  ThemeId,
  DensityId,
  saveTheme,
  saveDensity,
  applyStyles,
  loadTheme,
  loadDensity
} from '../../styles/themes';

export interface SidecarMenuProps {
  onCollapse: () => void;
  onHistoryClick: () => void;
  onSettingsClick: () => void;
  onHelpClick: () => void;
  onPrivacyChange: (enabled: boolean) => void;
  onNotificationsChange: (enabled: boolean) => void;
  onThemeChange?: (theme: string) => void;
  onDensityChange?: (density: string) => void;
  onViewChange?: (view: 'focus' | 'all') => void;
  currentView?: 'focus' | 'all';
  currentTheme?: ThemeId;
  currentDensity?: DensityId;
}

// View options for factor filtering
const VIEW_OPTIONS = [
  { id: 'focus' as const, label: 'My Focus', icon: '◎', desc: 'Only relevant factors' },
  { id: 'all' as const, label: 'All', icon: '☰', desc: 'Show all 5 factors' },
];

/**
 * Create the SidecarMenu element
 */
export function SidecarMenu(props: SidecarMenuProps): HTMLElement {
  const { 
    onHistoryClick, 
    onSettingsClick, 
    onHelpClick, 
    onPrivacyChange, 
    onNotificationsChange, 
    onThemeChange,
    onDensityChange,
    onViewChange, 
    currentView = 'focus',
    currentTheme = 'light',
    currentDensity = 'normal'
  } = props;
  
  const container = document.createElement('div');
  container.className = 'sidecar-menu';
  
  // Hamburger button (three dots vertical)
  const menuBtn = document.createElement('button');
  menuBtn.className = 'sidecar-menu-btn';
  menuBtn.innerHTML = `<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>`;
  menuBtn.title = 'Menu';
  
  // Dropdown menu
  const dropdown = document.createElement('div');
  dropdown.className = 'sidecar-menu-dropdown';
  dropdown.style.display = 'none';
  
  // Toggle dropdown
  menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  });
  
  // Close on outside click
  document.addEventListener('click', () => {
    dropdown.style.display = 'none';
  });
  
  // Menu items
  const items: Array<{
    label: string;
    icon: string;
    onClick?: () => void;
    toggle?: {
      key: string;
      getState: () => Promise<boolean>;
      onChange: (enabled: boolean) => void;
    };
    submenu?: boolean;
  }> = [
    {
      label: 'Notifications',
      icon: 'bell',
      toggle: {
        key: 'notifications',
        getState: async () => ToastManager.isEnabled(),
        onChange: async (enabled) => {
          await ToastManager.setEnabled(enabled);
          onNotificationsChange(enabled);
        },
      },
    },
    {
      label: 'Privacy mode',
      icon: 'lock',
      toggle: {
        key: 'privacy',
        getState: () => PrivacyMode.isEnabled(),
        onChange: async (enabled) => {
          await PrivacyMode.setEnabled(enabled);
          onPrivacyChange(enabled);
        },
      },
    },
    { label: 'divider', icon: '' },
    {
      label: 'Theme',
      icon: 'palette',
      submenu: true,
    },
    {
      label: 'Text Size',
      icon: 'textsize',
      submenu: true,
    },
    {
      label: 'View',
      icon: 'view',
      submenu: true,
    },
    { label: 'divider', icon: '' },
    {
      label: 'History',
      icon: 'history',
      onClick: () => {
        dropdown.style.display = 'none';
        onHistoryClick();
      },
    },
    {
      label: 'Settings',
      icon: 'settings',
      onClick: () => {
        dropdown.style.display = 'none';
        onSettingsClick();
      },
    },
    {
      label: 'Help',
      icon: 'help',
      onClick: () => {
        dropdown.style.display = 'none';
        onHelpClick();
      },
    },
  ];
  
  for (const item of items) {
    if (item.label === 'divider') {
      const divider = document.createElement('div');
      divider.className = 'sidecar-menu-divider';
      dropdown.appendChild(divider);
      continue;
    }
    
    const menuItem = document.createElement('div');
    menuItem.className = 'sidecar-menu-item';
    
    // Icon (SVG)
    const icon = document.createElement('span');
    icon.className = 'sidecar-menu-icon';
    icon.innerHTML = getMenuIcon(item.icon);
    menuItem.appendChild(icon);
    
    // Label
    const label = document.createElement('span');
    label.className = 'sidecar-menu-label';
    label.textContent = item.label;
    menuItem.appendChild(label);
    
    // Toggle switch (for notifications/privacy)
    if (item.toggle) {
      const toggle = createToggle(item.toggle.key, item.toggle.getState, item.toggle.onChange);
      menuItem.appendChild(toggle);
    } else if (item.submenu && item.label === 'Theme') {
      // Theme submenu arrow
      const arrow = document.createElement('span');
      arrow.className = 'sidecar-menu-arrow';
      arrow.textContent = '›';
      menuItem.appendChild(arrow);
      
      // Theme submenu
      const submenu = createThemeSubmenu(onThemeChange);
      menuItem.appendChild(submenu);
      
      menuItem.addEventListener('mouseenter', () => {
        submenu.style.display = 'block';
      });
      menuItem.addEventListener('mouseleave', () => {
        submenu.style.display = 'none';
      });
    } else if (item.submenu && item.label === 'Text Size') {
      // Text Size submenu arrow
      const arrow = document.createElement('span');
      arrow.className = 'sidecar-menu-arrow';
      arrow.textContent = '›';
      menuItem.appendChild(arrow);
      
      // Text Size (density) submenu
      const submenu = createDensitySubmenu(currentDensity, onDensityChange, () => {
        dropdown.style.display = 'none';
      });
      menuItem.appendChild(submenu);
      
      menuItem.addEventListener('mouseenter', () => {
        submenu.style.display = 'block';
      });
      menuItem.addEventListener('mouseleave', () => {
        submenu.style.display = 'none';
      });
    } else if (item.submenu && item.label === 'View') {
      // View submenu arrow
      const arrow = document.createElement('span');
      arrow.className = 'sidecar-menu-arrow';
      arrow.textContent = '›';
      menuItem.appendChild(arrow);
      
      // View submenu
      const submenu = createViewSubmenu(currentView, onViewChange, () => {
        dropdown.style.display = 'none';
      });
      menuItem.appendChild(submenu);
      
      menuItem.addEventListener('mouseenter', () => {
        submenu.style.display = 'block';
      });
      menuItem.addEventListener('mouseleave', () => {
        submenu.style.display = 'none';
      });
    } else if (item.onClick) {
      menuItem.addEventListener('click', item.onClick);
      menuItem.style.cursor = 'pointer';
    }
    
    dropdown.appendChild(menuItem);
  }
  
  container.appendChild(menuBtn);
  container.appendChild(dropdown);
  
  return container;
}

/**
 * Get SVG icon for menu item
 */
function getMenuIcon(name: string): string {
  const icons: Record<string, string> = {
    bell: '<svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/></svg>',
    lock: '<svg viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>',
    palette: '<svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c2.76 0 5-2.24 5-5 0-4.42-4.03-8-9-8zm-5.5 9c-.83 0-1.5-.67-1.5-1.5S5.67 9 6.5 9 8 9.67 8 10.5 7.33 12 6.5 12zm3-4C8.67 8 8 7.33 8 6.5S8.67 5 9.5 5s1.5.67 1.5 1.5S10.33 8 9.5 8zm5 0c-.83 0-1.5-.67-1.5-1.5S13.67 5 14.5 5s1.5.67 1.5 1.5S15.33 8 14.5 8zm3 4c-.83 0-1.5-.67-1.5-1.5S16.67 9 17.5 9s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>',
    textsize: '<svg viewBox="0 0 24 24"><path d="M9 4v3h5v12h3V7h5V4H9zm-6 8h3v7h3v-7h3V9H3v3z"/></svg>',
    view: '<svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>',
    history: '<svg viewBox="0 0 24 24"><path d="M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/></svg>',
    settings: '<svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>',
    help: '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/></svg>',
  };
  return icons[name] || '';
}

/**
 * Create view submenu for factor filtering preference
 */
function createViewSubmenu(
  currentView: 'focus' | 'all',
  onViewChange?: (view: 'focus' | 'all') => void,
  closeDropdown?: () => void
): HTMLElement {
  const submenu = document.createElement('div');
  submenu.className = 'sidecar-menu-submenu';
  submenu.style.display = 'none';
  
  for (const option of VIEW_OPTIONS) {
    const item = document.createElement('div');
    item.className = `sidecar-menu-submenu-item ${currentView === option.id ? 'active' : ''}`;
    item.innerHTML = `
      <span class="sidecar-menu-view-icon">${option.icon}</span>
      <span class="sidecar-menu-view-label">${option.label}</span>
      ${currentView === option.id ? '<span class="sidecar-menu-check">✓</span>' : ''}
    `;
    item.title = option.desc;
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      onViewChange?.(option.id);
      closeDropdown?.();
    });
    submenu.appendChild(item);
  }
  
  return submenu;
}

/**
 * Create theme submenu using centralized theme system
 */
function createThemeSubmenu(onThemeChange?: (theme: string) => void): HTMLElement {
  const submenu = document.createElement('div');
  submenu.className = 'sidecar-menu-submenu';
  submenu.style.display = 'none';
  
  for (const theme of THEME_LIST) {
    const option = document.createElement('div');
    option.className = 'sidecar-menu-submenu-item';
    option.innerHTML = `
      <span class="sidecar-menu-theme-icon">${theme.icon}</span>
      <span class="sidecar-menu-theme-label">${theme.label}</span>
    `;
    option.addEventListener('click', async (e) => {
      e.stopPropagation();
      // Apply theme to sidecar using centralized system
      const sidebar = document.getElementById('mobius-os-sidebar');
      if (sidebar) {
        const currentDensity = await loadDensity();
        applyStyles(sidebar, theme.id as ThemeId, currentDensity);
      }
      await saveTheme(theme.id as ThemeId);
      onThemeChange?.(theme.id);
      submenu.style.display = 'none';
    });
    submenu.appendChild(option);
  }
  
  return submenu;
}

/**
 * Create density (text size) submenu
 */
function createDensitySubmenu(
  currentDensity: DensityId,
  onDensityChange?: (density: string) => void,
  closeDropdown?: () => void
): HTMLElement {
  const submenu = document.createElement('div');
  submenu.className = 'sidecar-menu-submenu';
  submenu.style.display = 'none';
  
  for (const density of DENSITY_LIST) {
    const option = document.createElement('div');
    option.className = `sidecar-menu-submenu-item ${currentDensity === density.id ? 'active' : ''}`;
    option.innerHTML = `
      <span class="sidecar-menu-density-label">${density.label}</span>
      <span class="sidecar-menu-density-desc">${density.description}</span>
      ${currentDensity === density.id ? '<span class="sidecar-menu-check">✓</span>' : ''}
    `;
    option.addEventListener('click', async (e) => {
      e.stopPropagation();
      // Apply density using centralized system
      const sidebar = document.getElementById('mobius-os-sidebar');
      if (sidebar) {
        const currentTheme = await loadTheme();
        applyStyles(sidebar, currentTheme, density.id as DensityId);
      }
      // Also apply to mini widget
      const mini = document.getElementById('mobius-mini-widget');
      if (mini) {
        const currentTheme = await loadTheme();
        applyStyles(mini, currentTheme, density.id as DensityId);
      }
      await saveDensity(density.id as DensityId);
      onDensityChange?.(density.id);
      closeDropdown?.();
    });
    submenu.appendChild(option);
  }
  
  return submenu;
}

/**
 * Create a toggle switch
 */
function createToggle(
  key: string,
  getState: () => Promise<boolean>,
  onChange: (enabled: boolean) => void
): HTMLElement {
  const toggle = document.createElement('label');
  toggle.className = 'sidecar-menu-toggle';
  
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.className = 'sidecar-menu-toggle-input';
  input.dataset.key = key;
  
  const slider = document.createElement('span');
  slider.className = 'sidecar-menu-toggle-slider';
  
  // Set initial state
  void getState().then((enabled) => {
    input.checked = enabled;
  });
  
  // Handle change
  input.addEventListener('change', () => {
    onChange(input.checked);
  });
  
  // Prevent menu item click from toggling
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
  });
  
  toggle.appendChild(input);
  toggle.appendChild(slider);
  
  return toggle;
}

/**
 * Create the collapse button (separate from menu for header)
 */
export function CollapseButton(onClick: () => void): HTMLElement {
  const btn = document.createElement('button');
  btn.className = 'sidecar-collapse-btn';
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>';
  btn.title = 'Collapse to mini';
  btn.addEventListener('click', onClick);
  return btn;
}

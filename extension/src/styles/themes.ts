/**
 * Centralized Theme & Density System
 * 
 * Provides consistent styling across Mini and Sidecar surfaces.
 * - Themes: Color schemes (light, dark, modern, etc.)
 * - Density: Font size and spacing scales (compact, normal, comfortable)
 */

// =============================================================================
// TYPES
// =============================================================================

export type ThemeId = 'light' | 'dark' | 'midnight' | 'ocean' | 'forest' | 'sunset';
export type DensityId = 'compact' | 'normal' | 'comfortable';

export interface Theme {
  id: ThemeId;
  label: string;
  icon: string;
  colors: {
    // Backgrounds
    bgPrimary: string;
    bgSecondary: string;
    bgTertiary: string;
    bgHover: string;
    bgActive: string;
    
    // Text
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    textInverse: string;
    
    // Accents
    accent: string;
    accentHover: string;
    accentText: string;
    
    // Status colors
    success: string;
    warning: string;
    error: string;
    info: string;
    
    // Borders & Shadows
    border: string;
    borderLight: string;
    shadow: string;
    shadowStrong: string;
    
    // Special
    overlay: string;
    glass: string;
  };
}

export interface Density {
  id: DensityId;
  label: string;
  description: string;
  scale: {
    // Font sizes
    fontXs: string;
    fontSm: string;
    fontBase: string;
    fontMd: string;
    fontLg: string;
    fontXl: string;
    
    // Spacing
    spaceXs: string;
    spaceSm: string;
    spaceBase: string;
    spaceMd: string;
    spaceLg: string;
    
    // Component sizes
    iconSm: string;
    iconBase: string;
    iconLg: string;
    avatarSm: string;
    avatarBase: string;
    buttonHeight: string;
    inputHeight: string;
    
    // Border radius
    radiusSm: string;
    radiusBase: string;
    radiusLg: string;
  };
}

// =============================================================================
// THEME DEFINITIONS
// =============================================================================

export const THEMES: Record<ThemeId, Theme> = {
  light: {
    id: 'light',
    label: 'Light',
    icon: '☀️',
    colors: {
      bgPrimary: '#ffffff',
      bgSecondary: '#f8fafc',
      bgTertiary: '#f1f5f9',
      bgHover: '#e2e8f0',
      bgActive: '#cbd5e1',
      textPrimary: '#0f172a',
      textSecondary: '#475569',
      textMuted: '#94a3b8',
      textInverse: '#ffffff',
      accent: '#2563eb',
      accentHover: '#1d4ed8',
      accentText: '#ffffff',
      success: '#16a34a',
      warning: '#ca8a04',
      error: '#dc2626',
      info: '#0891b2',
      border: '#e2e8f0',
      borderLight: '#f1f5f9',
      shadow: 'rgba(0, 0, 0, 0.05)',
      shadowStrong: 'rgba(0, 0, 0, 0.1)',
      overlay: 'rgba(15, 23, 42, 0.5)',
      glass: 'rgba(255, 255, 255, 0.8)',
    },
  },
  
  dark: {
    id: 'dark',
    label: 'Dark',
    icon: '🌙',
    colors: {
      bgPrimary: '#1e293b',
      bgSecondary: '#0f172a',
      bgTertiary: '#020617',
      bgHover: '#334155',
      bgActive: '#475569',
      textPrimary: '#f8fafc',
      textSecondary: '#cbd5e1',
      textMuted: '#64748b',
      textInverse: '#0f172a',
      accent: '#3b82f6',
      accentHover: '#60a5fa',
      accentText: '#ffffff',
      success: '#22c55e',
      warning: '#eab308',
      error: '#ef4444',
      info: '#06b6d4',
      border: '#334155',
      borderLight: '#1e293b',
      shadow: 'rgba(0, 0, 0, 0.3)',
      shadowStrong: 'rgba(0, 0, 0, 0.5)',
      overlay: 'rgba(0, 0, 0, 0.7)',
      glass: 'rgba(30, 41, 59, 0.9)',
    },
  },
  
  midnight: {
    id: 'midnight',
    label: 'Midnight',
    icon: '🌌',
    colors: {
      bgPrimary: '#0a0a1a',
      bgSecondary: '#12122a',
      bgTertiary: '#1a1a3a',
      bgHover: '#252550',
      bgActive: '#303060',
      textPrimary: '#e0e0ff',
      textSecondary: '#a0a0d0',
      textMuted: '#6060a0',
      textInverse: '#0a0a1a',
      accent: '#8b5cf6',
      accentHover: '#a78bfa',
      accentText: '#ffffff',
      success: '#34d399',
      warning: '#fbbf24',
      error: '#f87171',
      info: '#38bdf8',
      border: '#252550',
      borderLight: '#1a1a3a',
      shadow: 'rgba(0, 0, 0, 0.4)',
      shadowStrong: 'rgba(0, 0, 0, 0.6)',
      overlay: 'rgba(10, 10, 26, 0.8)',
      glass: 'rgba(18, 18, 42, 0.95)',
    },
  },
  
  ocean: {
    id: 'ocean',
    label: 'Ocean',
    icon: '🌊',
    colors: {
      bgPrimary: '#f0f9ff',
      bgSecondary: '#e0f2fe',
      bgTertiary: '#bae6fd',
      bgHover: '#7dd3fc',
      bgActive: '#38bdf8',
      textPrimary: '#0c4a6e',
      textSecondary: '#0369a1',
      textMuted: '#0284c7',
      textInverse: '#f0f9ff',
      accent: '#0284c7',
      accentHover: '#0369a1',
      accentText: '#ffffff',
      success: '#059669',
      warning: '#d97706',
      error: '#dc2626',
      info: '#0891b2',
      border: '#7dd3fc',
      borderLight: '#bae6fd',
      shadow: 'rgba(3, 105, 161, 0.1)',
      shadowStrong: 'rgba(3, 105, 161, 0.2)',
      overlay: 'rgba(12, 74, 110, 0.5)',
      glass: 'rgba(240, 249, 255, 0.9)',
    },
  },
  
  forest: {
    id: 'forest',
    label: 'Forest',
    icon: '🌲',
    colors: {
      bgPrimary: '#f0fdf4',
      bgSecondary: '#dcfce7',
      bgTertiary: '#bbf7d0',
      bgHover: '#86efac',
      bgActive: '#4ade80',
      textPrimary: '#14532d',
      textSecondary: '#166534',
      textMuted: '#15803d',
      textInverse: '#f0fdf4',
      accent: '#16a34a',
      accentHover: '#15803d',
      accentText: '#ffffff',
      success: '#059669',
      warning: '#ca8a04',
      error: '#dc2626',
      info: '#0891b2',
      border: '#86efac',
      borderLight: '#bbf7d0',
      shadow: 'rgba(22, 101, 52, 0.1)',
      shadowStrong: 'rgba(22, 101, 52, 0.2)',
      overlay: 'rgba(20, 83, 45, 0.5)',
      glass: 'rgba(240, 253, 244, 0.9)',
    },
  },
  
  sunset: {
    id: 'sunset',
    label: 'Sunset',
    icon: '🌅',
    colors: {
      bgPrimary: '#fffbeb',
      bgSecondary: '#fef3c7',
      bgTertiary: '#fde68a',
      bgHover: '#fcd34d',
      bgActive: '#fbbf24',
      textPrimary: '#78350f',
      textSecondary: '#92400e',
      textMuted: '#b45309',
      textInverse: '#fffbeb',
      accent: '#f59e0b',
      accentHover: '#d97706',
      accentText: '#ffffff',
      success: '#16a34a',
      warning: '#ca8a04',
      error: '#dc2626',
      info: '#0891b2',
      border: '#fcd34d',
      borderLight: '#fde68a',
      shadow: 'rgba(180, 83, 9, 0.1)',
      shadowStrong: 'rgba(180, 83, 9, 0.2)',
      overlay: 'rgba(120, 53, 15, 0.5)',
      glass: 'rgba(255, 251, 235, 0.9)',
    },
  },
};

// =============================================================================
// DENSITY DEFINITIONS
// =============================================================================

export const DENSITIES: Record<DensityId, Density> = {
  compact: {
    id: 'compact',
    label: 'Compact',
    description: 'Smaller text, more content visible',
    scale: {
      fontXs: '9px',
      fontSm: '10px',
      fontBase: '11px',
      fontMd: '12px',
      fontLg: '13px',
      fontXl: '14px',
      spaceXs: '2px',
      spaceSm: '4px',
      spaceBase: '6px',
      spaceMd: '8px',
      spaceLg: '12px',
      iconSm: '12px',
      iconBase: '14px',
      iconLg: '16px',
      avatarSm: '20px',
      avatarBase: '28px',
      buttonHeight: '24px',
      inputHeight: '26px',
      radiusSm: '3px',
      radiusBase: '5px',
      radiusLg: '8px',
    },
  },
  
  normal: {
    id: 'normal',
    label: 'Normal',
    description: 'Balanced text size, matches EMR',
    scale: {
      fontXs: '11px',
      fontSm: '12px',
      fontBase: '13px',
      fontMd: '14px',
      fontLg: '15px',
      fontXl: '16px',
      spaceXs: '3px',
      spaceSm: '6px',
      spaceBase: '8px',
      spaceMd: '12px',
      spaceLg: '16px',
      iconSm: '14px',
      iconBase: '16px',
      iconLg: '20px',
      avatarSm: '24px',
      avatarBase: '32px',
      buttonHeight: '28px',
      inputHeight: '32px',
      radiusSm: '4px',
      radiusBase: '6px',
      radiusLg: '10px',
    },
  },
  
  comfortable: {
    id: 'comfortable',
    label: 'Comfortable',
    description: 'Larger text, easier to read',
    scale: {
      fontXs: '12px',
      fontSm: '13px',
      fontBase: '14px',
      fontMd: '15px',
      fontLg: '17px',
      fontXl: '19px',
      spaceXs: '4px',
      spaceSm: '8px',
      spaceBase: '10px',
      spaceMd: '14px',
      spaceLg: '20px',
      iconSm: '16px',
      iconBase: '18px',
      iconLg: '24px',
      avatarSm: '28px',
      avatarBase: '36px',
      buttonHeight: '32px',
      inputHeight: '36px',
      radiusSm: '5px',
      radiusBase: '8px',
      radiusLg: '12px',
    },
  },
};

// =============================================================================
// CSS GENERATION
// =============================================================================

/**
 * Generate CSS custom properties for a theme
 */
export function generateThemeCSS(theme: Theme): string {
  const { colors } = theme;
  return `
    --mobius-bg-primary: ${colors.bgPrimary};
    --mobius-bg-secondary: ${colors.bgSecondary};
    --mobius-bg-tertiary: ${colors.bgTertiary};
    --mobius-bg-hover: ${colors.bgHover};
    --mobius-bg-active: ${colors.bgActive};
    --mobius-text-primary: ${colors.textPrimary};
    --mobius-text-secondary: ${colors.textSecondary};
    --mobius-text-muted: ${colors.textMuted};
    --mobius-text-inverse: ${colors.textInverse};
    --mobius-accent: ${colors.accent};
    --mobius-accent-hover: ${colors.accentHover};
    --mobius-accent-text: ${colors.accentText};
    --mobius-success: ${colors.success};
    --mobius-warning: ${colors.warning};
    --mobius-error: ${colors.error};
    --mobius-info: ${colors.info};
    --mobius-border: ${colors.border};
    --mobius-border-light: ${colors.borderLight};
    --mobius-shadow: ${colors.shadow};
    --mobius-shadow-strong: ${colors.shadowStrong};
    --mobius-overlay: ${colors.overlay};
    --mobius-glass: ${colors.glass};
  `.trim();
}

/**
 * Generate CSS custom properties for a density
 */
export function generateDensityCSS(density: Density): string {
  const { scale } = density;
  return `
    --mobius-font-xs: ${scale.fontXs};
    --mobius-font-sm: ${scale.fontSm};
    --mobius-font-base: ${scale.fontBase};
    --mobius-font-md: ${scale.fontMd};
    --mobius-font-lg: ${scale.fontLg};
    --mobius-font-xl: ${scale.fontXl};
    --mobius-space-xs: ${scale.spaceXs};
    --mobius-space-sm: ${scale.spaceSm};
    --mobius-space-base: ${scale.spaceBase};
    --mobius-space-md: ${scale.spaceMd};
    --mobius-space-lg: ${scale.spaceLg};
    --mobius-icon-sm: ${scale.iconSm};
    --mobius-icon-base: ${scale.iconBase};
    --mobius-icon-lg: ${scale.iconLg};
    --mobius-avatar-sm: ${scale.avatarSm};
    --mobius-avatar-base: ${scale.avatarBase};
    --mobius-button-height: ${scale.buttonHeight};
    --mobius-input-height: ${scale.inputHeight};
    --mobius-radius-sm: ${scale.radiusSm};
    --mobius-radius-base: ${scale.radiusBase};
    --mobius-radius-lg: ${scale.radiusLg};
  `.trim();
}

/**
 * Generate full CSS style block with theme and density
 */
export function generateStyleBlock(themeId: ThemeId, densityId: DensityId): string {
  const theme = THEMES[themeId] || THEMES.light;
  const density = DENSITIES[densityId] || DENSITIES.normal;
  
  return `
    ${generateThemeCSS(theme)}
    ${generateDensityCSS(density)}
  `;
}

// =============================================================================
// STORAGE
// =============================================================================

const STORAGE_KEYS = {
  theme: 'mobius.theme',
  density: 'mobius.density',
} as const;

/**
 * Save theme preference
 */
export async function saveTheme(themeId: ThemeId): Promise<void> {
  try {
    await chrome.storage.local.set({ [STORAGE_KEYS.theme]: themeId });
  } catch (e) {
    console.warn('[Mobius] Failed to save theme:', e);
  }
}

/**
 * Load theme preference
 */
export async function loadTheme(): Promise<ThemeId> {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEYS.theme);
    const saved = result[STORAGE_KEYS.theme] as ThemeId;
    return THEMES[saved] ? saved : 'light';
  } catch {
    return 'light';
  }
}

/**
 * Save density preference
 */
export async function saveDensity(densityId: DensityId): Promise<void> {
  try {
    await chrome.storage.local.set({ [STORAGE_KEYS.density]: densityId });
  } catch (e) {
    console.warn('[Mobius] Failed to save density:', e);
  }
}

/**
 * Load density preference
 */
export async function loadDensity(): Promise<DensityId> {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEYS.density);
    const saved = result[STORAGE_KEYS.density] as DensityId;
    return DENSITIES[saved] ? saved : 'normal';
  } catch {
    return 'normal';
  }
}

// =============================================================================
// APPLICATION
// =============================================================================

/**
 * Apply theme and density to a root element
 */
export function applyStyles(
  root: HTMLElement,
  themeId: ThemeId,
  densityId: DensityId
): void {
  const css = generateStyleBlock(themeId, densityId);
  root.setAttribute('style', `${root.getAttribute('style') || ''}; ${css}`);
  
  // Also add class for CSS-based overrides
  root.classList.remove(
    'theme-light', 'theme-dark', 'theme-midnight', 'theme-ocean', 'theme-forest', 'theme-sunset',
    'density-compact', 'density-normal', 'density-comfortable'
  );
  root.classList.add(`theme-${themeId}`, `density-${densityId}`);
}

/**
 * Initialize styles from saved preferences
 */
export async function initializeStyles(root: HTMLElement): Promise<{ theme: ThemeId; density: DensityId }> {
  const theme = await loadTheme();
  const density = await loadDensity();
  applyStyles(root, theme, density);
  return { theme, density };
}

// =============================================================================
// THEME LIST FOR UI
// =============================================================================

export const THEME_LIST = Object.values(THEMES).map(t => ({
  id: t.id,
  label: t.label,
  icon: t.icon,
}));

export const DENSITY_LIST = Object.values(DENSITIES).map(d => ({
  id: d.id,
  label: d.label,
  description: d.description,
}));

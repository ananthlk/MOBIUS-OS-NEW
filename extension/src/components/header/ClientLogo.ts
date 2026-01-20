/**
 * ClientLogo Component
 * Displays client/customer logo and name
 */

export interface ClientLogoProps {
  logoUrl?: string;
  clientName: string;
  compact?: boolean; // For Mini widget (smaller size)
}

/**
 * Aspire Health FL logo as inline SVG (teal/cyan healthcare brand)
 * Used for CMHC (Community Mental Health Center) in Florida
 */
const ASPIRE_HEALTH_LOGO_SVG = `
<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="32" height="32" rx="6" fill="#0891b2"/>
  <path d="M16 6L22 18H10L16 6Z" fill="white" opacity="0.9"/>
  <circle cx="16" cy="22" r="4" fill="white" opacity="0.9"/>
  <path d="M8 24C8 20 11 17 16 17C21 17 24 20 24 24" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
</svg>
`;

/**
 * Known client logos mapping (client name -> SVG or URL)
 */
const CLIENT_LOGOS: Record<string, string> = {
  'CMHC': ASPIRE_HEALTH_LOGO_SVG,
  'Aspire Health': ASPIRE_HEALTH_LOGO_SVG,
  'Aspire Health FL': ASPIRE_HEALTH_LOGO_SVG,
};

/**
 * Client display names (internal name -> display name)
 */
const CLIENT_DISPLAY_NAMES: Record<string, string> = {
  'CMHC': 'Aspire Health FL',
};

export function ClientLogo({ logoUrl, clientName, compact = false }: ClientLogoProps): HTMLElement {
  const container = document.createElement('div');
  container.className = compact ? 'client-logo client-logo-compact' : 'client-logo';
  
  // Determine display name (may differ from internal clientName)
  const displayName = CLIENT_DISPLAY_NAMES[clientName] || clientName;
  
  // Check for known client logo
  const knownLogo = CLIENT_LOGOS[clientName];
  
  if (logoUrl) {
    // External logo URL provided
    const img = document.createElement('img');
    img.src = logoUrl;
    img.alt = displayName;
    container.appendChild(img);
  } else if (knownLogo && knownLogo.trim().startsWith('<svg')) {
    // Inline SVG logo - create properly sized wrapper
    const logoWrapper = document.createElement('div');
    logoWrapper.className = 'client-logo-svg';
    // Set explicit inline styles to ensure visibility
    const size = compact ? '18px' : '24px';
    logoWrapper.style.cssText = `width: ${size}; height: ${size}; flex-shrink: 0; display: flex; align-items: center; justify-content: center;`;
    logoWrapper.innerHTML = knownLogo.trim();
    // Ensure SVG fills the wrapper
    const svg = logoWrapper.querySelector('svg');
    if (svg) {
      svg.style.cssText = 'width: 100%; height: 100%; display: block;';
    }
    container.appendChild(logoWrapper);
  } else if (knownLogo) {
    // URL to logo
    const img = document.createElement('img');
    img.src = knownLogo;
    img.alt = displayName;
    container.appendChild(img);
  } else {
    // Fallback: placeholder with initials
    const placeholder = document.createElement('div');
    placeholder.className = 'client-logo-placeholder';
    const initials = displayName
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w[0]?.toUpperCase())
      .join('')
      .slice(0, 3);
    placeholder.textContent = initials || displayName.slice(0, 1).toUpperCase();
    container.appendChild(placeholder);
  }
  
  // Add client name text (hide on compact mode to save space)
  if (!compact) {
    const name = document.createElement('span');
    name.className = 'client-name';
    name.textContent = displayName;
    container.appendChild(name);
  }
  
  return container;
}

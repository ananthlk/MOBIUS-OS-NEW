/**
 * ClientLogo Component
 * Displays client/customer logo and name
 */

export interface ClientLogoProps {
  logoUrl?: string;
  clientName: string;
}

export function ClientLogo({ logoUrl, clientName }: ClientLogoProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'client-logo';
  
  if (logoUrl) {
    const img = document.createElement('img');
    img.src = logoUrl;
    img.alt = clientName;
    container.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'client-logo-placeholder';
    const initials = clientName
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w[0]?.toUpperCase())
      .join('')
      .slice(0, 3);
    placeholder.textContent = initials || clientName.slice(0, 1).toUpperCase();
    container.appendChild(placeholder);
  }
  
  const name = document.createElement('span');
  name.className = 'client-name';
  name.textContent = clientName;
  container.appendChild(name);
  
  return container;
}

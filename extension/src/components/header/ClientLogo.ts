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
    placeholder.textContent = clientName.substring(0, 4).toUpperCase();
    container.appendChild(placeholder);
  }
  
  const name = document.createElement('span');
  name.className = 'client-name';
  name.textContent = clientName;
  container.appendChild(name);
  
  return container;
}

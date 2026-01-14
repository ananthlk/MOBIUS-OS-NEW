/**
 * UserDetails Component
 * Displays current user information
 */

export interface UserDetailsProps {
  userName: string;
  userRole: string;
}

export function UserDetails({ userName, userRole }: UserDetailsProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'user-info';
  
  const text = document.createElement('span');
  text.innerHTML = `<strong>User:</strong> ${userName} | <strong>Role:</strong> ${userRole}`;
  
  container.appendChild(text);
  return container;
}

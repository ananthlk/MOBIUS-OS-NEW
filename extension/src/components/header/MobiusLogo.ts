/**
 * MobiusLogo Component
 * Animated infinity symbol logo with status indication
 */

import { Status } from '../../types';

export interface MobiusLogoProps {
  status: Status;
  size?: number;
}

export function MobiusLogo({ status, size = 32 }: MobiusLogoProps): HTMLElement {
  const container = document.createElement('div');
  container.className = `mobius-logo status-${status}`;
  
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 100 100');
  svg.setAttribute('width', size.toString());
  svg.setAttribute('height', size.toString());
  
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  
  // Normal gradient (grey to white)
  const normalGrad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
  normalGrad.setAttribute('id', 'infinityGradNormal');
  normalGrad.setAttribute('x1', '0%');
  normalGrad.setAttribute('y1', '50%');
  normalGrad.setAttribute('x2', '100%');
  normalGrad.setAttribute('y2', '50%');
  
  const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  stop1.setAttribute('offset', '0%');
  stop1.setAttribute('style', 'stop-color:#666;stop-opacity:1');
  normalGrad.appendChild(stop1);
  
  const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  stop2.setAttribute('offset', '50%');
  stop2.setAttribute('style', 'stop-color:#ffffff;stop-opacity:1');
  normalGrad.appendChild(stop2);
  
  const stop3 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  stop3.setAttribute('offset', '100%');
  stop3.setAttribute('style', 'stop-color:#666;stop-opacity:1');
  normalGrad.appendChild(stop3);
  
  defs.appendChild(normalGrad);
  
  // Processing gradient (animated)
  const processingGrad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
  processingGrad.setAttribute('id', 'infinityGradProcessing');
  processingGrad.setAttribute('x1', '0%');
  processingGrad.setAttribute('y1', '50%');
  processingGrad.setAttribute('x2', '100%');
  processingGrad.setAttribute('y2', '50%');
  
  const procStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  procStop1.setAttribute('offset', '0%');
  procStop1.setAttribute('style', 'stop-color:#666;stop-opacity:1');
  const animate1 = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
  animate1.setAttribute('attributeName', 'stop-color');
  animate1.setAttribute('values', '#666;#ffffff;#666');
  animate1.setAttribute('dur', '2s');
  animate1.setAttribute('repeatCount', 'indefinite');
  procStop1.appendChild(animate1);
  processingGrad.appendChild(procStop1);
  
  const procStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  procStop2.setAttribute('offset', '50%');
  procStop2.setAttribute('style', 'stop-color:#ffffff;stop-opacity:1');
  const animate2 = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
  animate2.setAttribute('attributeName', 'stop-color');
  animate2.setAttribute('values', '#ffffff;#666;#ffffff');
  animate2.setAttribute('dur', '2s');
  animate2.setAttribute('repeatCount', 'indefinite');
  procStop2.appendChild(animate2);
  processingGrad.appendChild(procStop2);
  
  const procStop3 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
  procStop3.setAttribute('offset', '100%');
  procStop3.setAttribute('style', 'stop-color:#666;stop-opacity:1');
  const animate3 = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
  animate3.setAttribute('attributeName', 'stop-color');
  animate3.setAttribute('values', '#666;#ffffff;#666');
  animate3.setAttribute('dur', '2s');
  animate3.setAttribute('repeatCount', 'indefinite');
  procStop3.appendChild(animate3);
  processingGrad.appendChild(procStop3);
  
  defs.appendChild(processingGrad);
  svg.appendChild(defs);
  
  // Infinity symbol paths
  const pathData = 'M 25 50 C 25 30, 35 20, 50 30 C 50 30, 50 30, 50 50 C 50 70, 70 80, 80 50 C 80 30, 70 20, 50 30 C 50 30, 50 30, 50 50 C 50 70, 30 80, 25 50';
  
  // Normal path
  const normalGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  normalGroup.setAttribute('class', 'path-normal');
  const normalPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  normalPath.setAttribute('d', pathData);
  normalPath.setAttribute('stroke', 'url(#infinityGradNormal)');
  normalPath.setAttribute('stroke-width', '4.5');
  normalPath.setAttribute('fill', 'none');
  normalPath.setAttribute('stroke-linecap', 'round');
  normalGroup.appendChild(normalPath);
  svg.appendChild(normalGroup);
  
  // Processing path
  const processingGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  processingGroup.setAttribute('class', 'path-processing');
  const processingPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  processingPath.setAttribute('d', pathData);
  processingPath.setAttribute('stroke', 'url(#infinityGradProcessing)');
  processingPath.setAttribute('stroke-width', '4.5');
  processingPath.setAttribute('fill', 'none');
  processingPath.setAttribute('stroke-linecap', 'round');
  processingGroup.appendChild(processingPath);
  svg.appendChild(processingGroup);
  
  container.appendChild(svg);
  return container;
}

/**
 * MessageTools Component
 * Three-dot menu for per-message actions (copy/email/print/export)
 */

export type MessageToolAction = 'copy' | 'email' | 'print' | 'export';

export interface MessageToolsProps {
  text: string;
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function MessageTools({ text }: MessageToolsProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'message-tools';

  const btn = document.createElement('button');
  btn.className = 'message-tools-btn';
  btn.type = 'button';
  btn.title = 'Message tools';
  btn.textContent = '⋯';

  const dropdown = document.createElement('div');
  dropdown.className = 'message-tools-dropdown';

  const makeItem = (label: string, onClick: () => void) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'message-tools-item';
    item.textContent = label;
    item.addEventListener('click', () => {
      onClick();
      dropdown.classList.remove('show');
    });
    return item;
  };

  dropdown.appendChild(
    makeItem('Copy', async () => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
    })
  );

  dropdown.appendChild(
    makeItem('Email', () => {
      const subject = encodeURIComponent('Mobius OS message');
      const body = encodeURIComponent(text);
      window.location.href = `mailto:?subject=${subject}&body=${body}`;
    })
  );

  dropdown.appendChild(
    makeItem('Print', () => {
      const win = window.open('', '_blank', 'noopener,noreferrer,width=600,height=800');
      if (!win) return;
      win.document.write(`<pre style="white-space:pre-wrap;font-family:ui-sans-serif,system-ui">${text}</pre>`);
      win.document.close();
      win.focus();
      win.print();
      win.close();
    })
  );

  dropdown.appendChild(
    makeItem('Export', () => {
      const safe = new Date().toISOString().replace(/[:.]/g, '-');
      downloadText(`mobius-message-${safe}.txt`, text);
    })
  );

  const toggle = (e: Event) => {
    e.stopPropagation();
    dropdown.classList.toggle('show');
  };
  btn.addEventListener('click', toggle);

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!container.contains(e.target as Node)) dropdown.classList.remove('show');
  });

  container.appendChild(btn);
  container.appendChild(dropdown);
  return container;
}


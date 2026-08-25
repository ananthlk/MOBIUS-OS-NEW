/**
 * Local PHI screen — runs ENTIRELY in the page. Nothing leaves the browser.
 *
 * Purpose: screen captured page content BEFORE the user consents to sharing
 * it with Mobius chat, so potential PHI is surfaced for acknowledgement
 * while the content has had zero network egress.
 *
 * This is deliberately NOT the authoritative PHI gate. Platform policy says
 * "call the phi-classifier, never build your own" — that holds for
 * enforcement: mobius-chat's server-side gate (which calls the shared
 * classifier) still scans everything that is actually sent, post-consent.
 * This module is a pre-egress screening layer only, tuned like the
 * classifier: recall over precision, masked evidence, never raw spans.
 *
 * Known gap (why the server gate still matters): unlabeled person names
 * cannot be reliably detected with local patterns. The server classifier
 * catches those after consent; its verdict triggers a second explicit
 * acknowledgement before any override.
 */

export interface PhiFinding {
  category: string;
  label: string;
  redacted_span: string;
  count: number;
}

export interface PhiScreenResult {
  phi_flag: boolean;
  identifier_labels: string[];
  findings: PhiFinding[];
}

/** Mask a matched span the way the classifier does: lead char + bullets. */
function mask(span: string): string {
  return span
    .split(/(\s+)/)
    .map((part) =>
      /\s/.test(part) ? part : part.length <= 1 ? part : part[0] + '•'.repeat(Math.min(part.length - 1, 8))
    )
    .join('');
}

interface Rule {
  category: string;
  label: string;
  regex: RegExp;
}

// High-recall identifier patterns (HIPAA §164.514(b)(2) identifier classes
// that pattern-match reliably). Names are handled only in labeled form.
const RULES: Rule[] = [
  { category: 'ssn', label: 'SSN', regex: /\b\d{3}-\d{2}-\d{4}\b/g },
  { category: 'mrn', label: 'MRN', regex: /\bMRN[-:#\s]*[A-Za-z0-9][A-Za-z0-9-]{3,}\b/gi },
  {
    category: 'date_of_birth',
    label: 'Date of Birth',
    regex: /\b(?:DOB|date\s+of\s+birth|birth\s*date)\b[:\s]*(?:\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})?/gi,
  },
  {
    category: 'date',
    label: 'Date',
    regex: /\b\d{1,2}[\/\-]\d{1,2}[\/\-](?:\d{4}|\d{2})\b/g,
  },
  {
    category: 'phone',
    label: 'Phone',
    regex: /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b/g,
  },
  {
    category: 'email',
    label: 'Email',
    regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
  },
  {
    category: 'member_id',
    label: 'Member/Policy ID',
    regex: /\b(?:member|policy|subscriber|medicaid|medicare|insurance)\s*(?:id|no|num|number|#)\b[:\s]*[A-Za-z0-9][A-Za-z0-9-]{4,}/gi,
  },
  {
    category: 'address',
    label: 'Street Address',
    regex: /\b\d{1,5}\s+[A-Za-z][A-Za-z\s]{1,30}\b(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way|terrace|ter|place|pl)\.?\b/gi,
  },
  {
    category: 'name_labeled',
    label: 'Name (labeled)',
    regex: /\b(?:patient|pt|member|beneficiary)\s*(?:name)?\s*[:\-]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b/g,
  },
];

/**
 * Screen text for likely PHI. Pure function, no I/O of any kind.
 */
export function screenTextForPhi(text: string): PhiScreenResult {
  const findings: PhiFinding[] = [];
  const labels = new Set<string>();

  for (const rule of RULES) {
    const matches = text.match(rule.regex);
    if (matches && matches.length > 0) {
      labels.add(rule.label);
      findings.push({
        category: rule.category,
        label: rule.label,
        redacted_span: mask(matches[0].trim()),
        count: matches.length,
      });
    }
  }

  return {
    phi_flag: findings.length > 0,
    identifier_labels: Array.from(labels),
    findings,
  };
}

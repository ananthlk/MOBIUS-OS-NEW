/**
 * RecordIDInput Component
 * Input for patient/claim/visit IDs
 */

export type RecordType = 'Patient ID' | 'Claim ID' | 'Visit ID' | 'Authorization ID' | 'Other';

export interface RecordIDInputProps {
  recordType?: RecordType;
  value?: string;
  onChange: (recordType: RecordType, value: string) => void;
}

export function RecordIDInput({ recordType = 'Patient ID', value = '', onChange }: RecordIDInputProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'record-id-input';
  
  const label = document.createElement('label');
  label.textContent = 'Record ID:';
  
  const select = document.createElement('select');
  select.id = 'recordType';
  const types: RecordType[] = ['Patient ID', 'Claim ID', 'Visit ID', 'Authorization ID', 'Other'];
  types.forEach(type => {
    const option = document.createElement('option');
    option.value = type;
    option.textContent = type;
    if (type === recordType) option.selected = true;
    select.appendChild(option);
  });
  
  const input = document.createElement('input');
  input.type = 'text';
  input.id = 'recordIdInput';
  input.placeholder = 'Enter ID (e.g., MRN553)';
  input.value = value;
  
  select.addEventListener('change', () => {
    onChange(select.value as RecordType, input.value);
  });
  
  input.addEventListener('input', () => {
    onChange(select.value as RecordType, input.value);
  });
  
  container.appendChild(label);
  container.appendChild(select);
  container.appendChild(input);
  
  return container;
}
